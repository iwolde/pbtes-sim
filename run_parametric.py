"""
Parametric Sweep Entry Point (Robust, Resumable & Spyder-Ready)
===============================================================
Runs parametric sweeps over design and physical variables by calling the single-simulation
logic from run_simulation.py in a loop.

Features:
  - Manifest Checkpointing: Keeps state in results/parametric_manifest.csv. If stopped,
    re-running will automatically resume from the last pending simulation.
  - Crash Recovery: Interrupted (running→pending) jobs are cleaned up on restart.
    Partial CSVs and orphaned design caches are deleted.
  - Fault Tolerance: Failed jobs are logged; the sweep continues.
  - Progress Dashboard: Spyder/IPython-friendly live status table with per-job metrics,
    elapsed time, and ETA.
  - Cache Isolation: Each job gets a unique --run-id, isolating .tespy_cache/ per job.

Usage:
    python run_parametric.py --sweep topology       # Parallel vs Series, direct vs indirect
    python run_parametric.py --sweep aperture       # aperture area sweep
    python run_parametric.py --sweep tes_volume     # tank D x H grid (30 points)
    python run_parametric.py --sweep physical_sens  # particle diameter, void fraction, insulation
    python run_parametric.py --sweep htf            # primary NaK vs Air baseline
    python run_parametric.py --sweep full           # all of the sweeps combined

Optional overrides and controls:
    --days              Number of simulation days per sweep point (default: 365)
    --tag               Result file tag prefix (default: 'sweep')
    --retry-failed      Force-retry failed simulations instead of skipping them
    --reset-manifest    Archive the existing manifest and start a fresh sweep grid
    --job-range         Only process jobs in slice "start:end" (e.g., "0:15")
    --no-progress       Suppress the progress dashboard
    --dashboard-interval  Seconds between dashboard refreshes (default: at every job completion)
"""

import os
import sys
import argparse
import json
import traceback
import time
import shutil
import stat
import glob as globmod
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_simulation import run_single_simulation

BASELINE_PARAMS = {
    'topology': 'Parallel',
    'tank_config': 'indirect',
    'htf': 'INCOMP::NaK',
    'aperture': 1000.0,
    'tank_diameter': 7.0,
    'tank_height': 5.0,
    'particle_diameter': 0.050,
    'void_fraction': 0.40,
    'insulation_thickness': 1.0,
}

APERTURE_SWEEP = [500.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0]

TES_DIAMETER_SWEEP = [4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
TES_HEIGHT_SWEEP   = [3.0, 4.0, 5.0, 6.0, 8.0]

TOPOLOGY_COMBOS = [
    ('Parallel', 'indirect'),
    ('Parallel', 'direct'),
    ('Series',   'indirect'),
    ('Series',   'direct'),
]

PARTICLE_SWEEP = [0.03, 0.05, 0.07, 0.10]
VOID_SWEEP = [0.35, 0.40, 0.45]
INSULATION_SWEEP = [0.5, 0.75, 1.0, 1.25]

HTF_SWEEP = ['INCOMP::NaK', 'Air']

MANIFEST_PATH = os.path.join('results', 'parametric_manifest.csv')


def make_run_id(topology, tank_config, htf, aperture, tank_diameter, tank_height,
                particle_diameter, void_fraction, insulation_thickness, days, tag):
    """Generate a unique, deterministic cache isolation key from job parameters."""
    htf_clean = htf.replace('INCOMP::', '')
    return (f"{tag}_{topology}_{tank_config}_{htf_clean}_"
            f"D{tank_diameter:.1f}_H{tank_height:.1f}_A{aperture:.0f}_"
            f"dp{particle_diameter:.3f}_vf{void_fraction:.2f}_"
            f"ins{insulation_thickness:.2f}_{days}d")


def get_job_id(job):
    """Generate a unique job ID string (used for logging; run_id is the cache key)."""
    htf_clean = job['htf'].replace('INCOMP::', '')
    return (
        f"{job['tag']}_{job['topology']}_{job['tank_config']}_{htf_clean}_"
        f"D{job['tank_diameter']:.1f}_H{job['tank_height']:.1f}_A{job['aperture']:.0f}_"
        f"dp{job['particle_diameter']:.3f}_vf{job['void_fraction']:.2f}_ins{job['insulation_thickness']:.2f}_"
        f"{job['days']}d"
    )


def generate_sweep_grid(sweep_type, days, tag, job_range=None):
    """Generate a list of unique job dictionaries for the requested sweep type."""
    jobs = []

    def create_job(**overrides):
        job = BASELINE_PARAMS.copy()
        job.update(overrides)
        job['days'] = days
        job['tag'] = tag
        job['job_id'] = get_job_id(job)
        job['run_id'] = make_run_id(
            topology=job['topology'],
            tank_config=job['tank_config'],
            htf=job['htf'],
            aperture=job['aperture'],
            tank_diameter=job['tank_diameter'],
            tank_height=job['tank_height'],
            particle_diameter=job['particle_diameter'],
            void_fraction=job['void_fraction'],
            insulation_thickness=job['insulation_thickness'],
            days=job['days'],
            tag=job['tag']
        )
        return job

    if sweep_type in ['aperture', 'full']:
        for ap in APERTURE_SWEEP:
            jobs.append(create_job(aperture=ap))

    if sweep_type in ['tes_volume', 'full']:
        for D in TES_DIAMETER_SWEEP:
            for H in TES_HEIGHT_SWEEP:
                jobs.append(create_job(tank_diameter=D, tank_height=H))

    if sweep_type in ['topology', 'full']:
        for top, tc in TOPOLOGY_COMBOS:
            jobs.append(create_job(topology=top, tank_config=tc))

    if sweep_type in ['physical_sens', 'full']:
        for dp in PARTICLE_SWEEP:
            jobs.append(create_job(particle_diameter=dp))
        for vf in VOID_SWEEP:
            jobs.append(create_job(void_fraction=vf))
        for ins in INSULATION_SWEEP:
            jobs.append(create_job(insulation_thickness=ins))

    if sweep_type in ['htf', 'full']:
        for h in HTF_SWEEP:
            jobs.append(create_job(htf=h))

    seen = set()
    unique_jobs = []
    for j in jobs:
        key = (
            j['topology'], j['tank_config'], j['htf'], j['aperture'],
            j['tank_diameter'], j['tank_height'], j['particle_diameter'],
            j['void_fraction'], j['insulation_thickness'], j['days'], j['tag']
        )
        if key not in seen:
            seen.add(key)
            unique_jobs.append(j)

    if job_range is not None:
        start, end = job_range
        unique_jobs = unique_jobs[start:end]

    return unique_jobs


def load_or_create_manifest(sweep_type, days, tag, reset=False):
    """Load existing manifest, run crash-recovery, append new grid combinations, or create a fresh one."""
    os.makedirs('results', exist_ok=True)
    grid_jobs = generate_sweep_grid(sweep_type, days, tag)
    df_grid = pd.DataFrame(grid_jobs)

    tracking_cols = {
        'status': 'pending',
        'elapsed_seconds': np.nan,
        'output_file': '',
        'error_message': '',
        'solar_fraction_pct': np.nan,
        'total_solar_kJ': np.nan,
        'total_aux_kJ': np.nan,
        'total_tes_discharge_kJ': np.nan,
        'convergence_errors': np.nan,
        'timestamp': ''
    }
    for col, default in tracking_cols.items():
        df_grid[col] = default

    if os.path.exists(MANIFEST_PATH) and not reset:
        print(f"Loading existing manifest from: {MANIFEST_PATH}")
        try:
            df_existing = pd.read_csv(MANIFEST_PATH)

            running_mask = df_existing['status'] == 'running'
            if running_mask.any():
                print(f"  -> Crash recovery: resetting {running_mask.sum()} interrupted 'running' job(s) back to 'pending'.")
                for idx in df_existing[running_mask].index:
                    row = df_existing.loc[idx]
                    _cleanup_interrupted_job(row)
                df_existing.loc[running_mask, 'status'] = 'pending'
                df_existing.loc[running_mask, 'error_message'] = 'Interrupted execution'

            merged_list = []
            existing_jobs = {row['job_id']: row.to_dict() for _, row in df_existing.iterrows()}

            for _, grid_row in df_grid.iterrows():
                jid = grid_row['job_id']
                if jid in existing_jobs:
                    merged_list.append(existing_jobs[jid])
                else:
                    merged_list.append(grid_row.to_dict())

            df_manifest = pd.DataFrame(merged_list)
            df_manifest.to_csv(MANIFEST_PATH, index=False)
            return df_manifest
        except Exception as e:
            print(f"[Warning] Failed to parse existing manifest: {e}. Recreating...")

    if reset and os.path.exists(MANIFEST_PATH):
        archive_path = f"{os.path.splitext(MANIFEST_PATH)[0]}_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.rename(MANIFEST_PATH, archive_path)
        print(f"Archived existing manifest to: {archive_path}")

    print(f"Creating a new manifest with {len(df_grid)} jobs.")
    df_grid.to_csv(MANIFEST_PATH, index=False)
    return df_grid


def _cleanup_interrupted_job(row):
    """Delete partial output CSV and orphaned design cache for an interrupted job."""
    output_file = row.get('output_file', '')
    if isinstance(output_file, str) and output_file and os.path.exists(output_file):
        try:
            os.remove(output_file)
            print(f"    Deleted partial output: {output_file}")
        except Exception as e:
            print(f"    Warning: could not delete partial output {output_file}: {e}")

    run_id = row.get('run_id', '')
    if isinstance(run_id, str) and run_id:
        cache_dir = os.path.join('.tespy_cache', run_id)
        if os.path.isdir(cache_dir):
            try:
                def _force_remove(func, path, exc_info):
                    try:
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    except Exception:
                        pass
                shutil.rmtree(cache_dir, onerror=_force_remove)
                print(f"    Deleted orphaned cache: {cache_dir}")
            except Exception as e:
                print(f"    Warning: could not delete cache {cache_dir}: {e}")


def save_manifest_state(df_manifest):
    """Write the manifest dataframe atomically to disk."""
    temp_path = MANIFEST_PATH + ".tmp"
    df_manifest.to_csv(temp_path, index=False)
    if os.path.exists(temp_path):
        if os.path.exists(MANIFEST_PATH):
            os.remove(MANIFEST_PATH)
        os.rename(temp_path, MANIFEST_PATH)


def print_dashboard(df_manifest, batch_start, current_idx, total_queued, is_spyder=True):
    """Print a live status dashboard. Uses IPython clear_output in Spyder; plain ASCII otherwise."""
    now = time.time()
    elapsed = now - batch_start
    n_ok = int((df_manifest['status'] == 'ok').sum())
    n_failed = int((df_manifest['status'] == 'failed').sum())
    n_running = int((df_manifest['status'] == 'running').sum())
    n_pending = int((df_manifest['status'] == 'pending').sum())
    total = len(df_manifest)

    pct_done = (n_ok + n_failed) / total * 100 if total > 0 else 0
    if n_ok + n_failed > 0 and pct_done > 0 and pct_done < 100:
        eta_seconds = (elapsed / pct_done) * (100 - pct_done)
        eta_str = f"{eta_seconds/3600:.0f}h {eta_seconds%3600/60:.0f}m"
    else:
        eta_str = "..."

    lines = []
    sep = "=" * 76
    lines.append("")
    lines.append(sep)
    lines.append("  PBTES PARAMETRIC SWEEP -- Live Status")
    lines.append(sep)
    started = datetime.fromtimestamp(batch_start).strftime('%Y-%m-%d %H:%M')
    lines.append("  Started: {:<20}  Elapsed: {:>6.0f}m  ETA: {:<14}".format(
        started, elapsed / 60, eta_str))
    lines.append(sep)
    lines.append("  Completed: {:>3} / {:<3}   Failed: {:>2}   Pending: {:>3}   ({:.0f}% done)".format(
        n_ok + n_failed, total, n_failed, n_pending, pct_done))
    lines.append(sep)
    lines.append("  {:50} {:>5}  {:>9}  {:>3}".format("Job", "SF%", "Time", "Err"))
    lines.append("  " + "-" * 68)

    sorted_df = df_manifest.sort_values('timestamp', ascending=False, na_position='last')
    for _, row in sorted_df.head(10).iterrows():
        sf_val = row['solar_fraction_pct']
        sf_str = f"{sf_val:.1f}" if not pd.isna(sf_val) else "  N/A"
        elapsed_val = row['elapsed_seconds']
        time_str = f"{elapsed_val/60:.0f}m" if not pd.isna(elapsed_val) else "   --"
        err_val = row['convergence_errors']
        err_str = f"{int(err_val):>3}" if not pd.isna(err_val) else " --"
        label = row.get('run_id', row['job_id'])
        label = label[:50] if isinstance(label, str) else str(label)[:50]
        status_icon = {'ok': '+', 'failed': '!', 'running': '>', 'pending': '.'}.get(row['status'], '?')
        lines.append("  {:<48}  {}{:>4}  {:>8}  {}".format(
            label[:48], status_icon, sf_str, time_str, err_str))

    lines.append(sep)

    output = "\n".join(lines)

    if is_spyder:
        try:
            from IPython.display import clear_output
            clear_output(wait=True)
        except ImportError:
            pass
    else:
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            output = "\033[2J\033[H" + output

    print(output)


def _execute_job(job_dict):
    """Worker function executed in a subprocess. Must be picklable (module-level)."""
    try:
        df_res, filename, meta = run_single_simulation(
            days=int(job_dict['days']),
            topology=job_dict['topology'],
            tank_config=job_dict['tank_config'],
            htf=job_dict['htf'],
            tag=job_dict['tag'],
            aperture=float(job_dict['aperture']),
            tank_diameter=float(job_dict['tank_diameter']),
            tank_height=float(job_dict['tank_height']),
            particle_diameter=float(job_dict['particle_diameter']),
            void_fraction=float(job_dict['void_fraction']),
            insulation_thickness=float(job_dict['insulation_thickness']),
            run_id=job_dict['run_id'],
            show_progress=False
        )
        sol_useful = df_res['solar_to_proc_kJ'].sum()
        tes_useful = df_res['tes_to_proc_kJ'].sum()
        aux_proc = df_res['aux_to_proc_kJ'].sum()
        aux_tes = df_res['aux_tes_energy_kJ'].sum() if 'aux_tes_energy_kJ' in df_res.columns else 0.0
        total_aux = aux_proc + aux_tes
        total_demand = sol_useful + tes_useful + total_aux
        sf = (sol_useful + tes_useful) / total_demand * 100.0 if total_demand > 0 else 0.0
        n_failed = int((df_res['iter_status'] == 'failed').sum()) if 'iter_status' in df_res.columns else 0
        return {
            'status': 'ok',
            'output_file': filename,
            'elapsed_seconds': 0,
            'solar_fraction_pct': round(sf, 2),
            'total_solar_kJ': round(sol_useful, 1),
            'total_aux_kJ': round(total_aux, 1),
            'total_tes_discharge_kJ': round(tes_useful, 1),
            'convergence_errors': n_failed,
            'error_message': ''
        }
    except Exception as e:
        return {
            'status': 'failed',
            'output_file': '',
            'elapsed_seconds': 0,
            'solar_fraction_pct': np.nan,
            'total_solar_kJ': 0.0,
            'total_aux_kJ': 0.0,
            'total_tes_discharge_kJ': 0.0,
            'convergence_errors': -1,
            'error_message': str(e).replace('\n', ' ')
        }


def _execute_sweeps_sequential(df_manifest, jobs_to_run, batch_start, show_progress, is_spyder):
    """Sequential execution (original mode, preserved as fallback)."""
    queued_count = len(jobs_to_run)
    for idx, job_idx in enumerate(jobs_to_run, 1):
        job = df_manifest.loc[job_idx].to_dict()
        run_id = job.get('run_id', job['job_id'])

        if show_progress:
            print(f"\n[{idx}/{queued_count}] {run_id}")

        df_manifest.at[job_idx, 'status'] = 'running'
        df_manifest.at[job_idx, 'timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_manifest_state(df_manifest)

        t0 = time.time()
        result = _execute_job(job)
        elapsed = time.time() - t0
        result['elapsed_seconds'] = round(elapsed, 1)

        if result['status'] == 'ok':
            print(f"  [OK] {elapsed:.0f}s | SF={result['solar_fraction_pct']:.1f}% | Errors={result['convergence_errors']}")
        else:
            print(f"  [FAILED] {elapsed:.0f}s: {result['error_message']}")

        for col in ['status', 'output_file', 'elapsed_seconds', 'solar_fraction_pct',
                     'total_solar_kJ', 'total_aux_kJ', 'total_tes_discharge_kJ',
                     'convergence_errors', 'error_message']:
            df_manifest.at[job_idx, col] = result[col]

        save_manifest_state(df_manifest)

        if show_progress:
            print_dashboard(df_manifest, batch_start, idx, queued_count, is_spyder=is_spyder)


def _execute_sweeps_parallel(df_manifest, jobs_to_run, batch_start, show_progress, is_spyder, n_workers):
    """Parallel execution using multiprocessing.Pool with spawn start method."""
    import multiprocessing as mp

    queued_count = len(jobs_to_run)
    job_list = []
    for job_idx in jobs_to_run:
        job = df_manifest.loc[job_idx].to_dict()
        job['_manifest_idx'] = job_idx
        job_list.append(job)

    for job in job_list:
        df_manifest.at[job['_manifest_idx'], 'status'] = 'running'
        df_manifest.at[job['_manifest_idx'], 'timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_manifest_state(df_manifest)

    print(f"\nLaunching {queued_count} jobs on {n_workers} parallel workers...")
    mp.set_start_method('spawn', force=True)

    completed = 0
    with mp.Pool(processes=n_workers) as pool:
        async_results = [pool.apply_async(_execute_job, (job,)) for job in job_list]

        for job, async_r in zip(job_list, async_results):
            try:
                t0 = time.time()
                result = async_r.get(timeout=86400)
                elapsed = time.time() - t0
                result['elapsed_seconds'] = round(elapsed, 1)
            except Exception as e:
                result = {
                    'status': 'failed',
                    'output_file': '',
                    'elapsed_seconds': 0,
                    'solar_fraction_pct': np.nan,
                    'total_solar_kJ': 0.0,
                    'total_aux_kJ': 0.0,
                    'total_tes_discharge_kJ': 0.0,
                    'convergence_errors': -1,
                    'error_message': f'Worker exception: {str(e)}'.replace('\n', ' ')
                }

            job_idx = job['_manifest_idx']
            for col in ['status', 'output_file', 'elapsed_seconds', 'solar_fraction_pct',
                         'total_solar_kJ', 'total_aux_kJ', 'total_tes_discharge_kJ',
                         'convergence_errors', 'error_message']:
                df_manifest.at[job_idx, col] = result[col]

            completed += 1
            run_id = job.get('run_id', job['job_id'])
            if result['status'] == 'ok':
                print(f"  [{completed}/{queued_count}] {run_id[:60]} [OK] "
                      f"{result['elapsed_seconds']:.0f}s SF={result['solar_fraction_pct']:.1f}%")
            else:
                print(f"  [{completed}/{queued_count}] {run_id[:60]} [FAILED] "
                      f"{result['error_message'][:80]}")

            save_manifest_state(df_manifest)
            if show_progress:
                print_dashboard(df_manifest, batch_start, completed, queued_count, is_spyder=is_spyder)


def execute_sweeps(sweep_type, days, tag, retry_failed=False, reset_manifest=False,
                   job_range=None, show_progress=True, dashboard_interval=0, parallel=1):
    """Iterates through jobs in the manifest, executes them (sequential or parallel)."""
    df_manifest = load_or_create_manifest(sweep_type, days, tag, reset=reset_manifest)

    if job_range is not None:
        grid_jobs = generate_sweep_grid(sweep_type, days, tag, job_range=job_range)
        range_job_ids = {j['job_id'] for j in grid_jobs}
        mask = df_manifest['job_id'].isin(range_job_ids)
    else:
        mask = pd.Series(True, index=df_manifest.index)

    jobs_to_run = []
    for idx, row in df_manifest.iterrows():
        if not mask.loc[idx]:
            continue
        status = row['status']
        if status == 'pending':
            jobs_to_run.append(idx)
        elif status == 'failed' and retry_failed:
            print(f"Queueing failed job for retry: {row['job_id']}")
            df_manifest.at[idx, 'status'] = 'pending'
            df_manifest.at[idx, 'error_message'] = ''
            jobs_to_run.append(idx)

    total_jobs = len(df_manifest)
    queued_count = len(jobs_to_run)
    print(f"\nManifest Status: {total_jobs} total jobs | {queued_count} queued to run.")
    print(f"Already completed: {int((df_manifest['status'] == 'ok').sum())} jobs.")
    print(f"Already failed:    {int((df_manifest['status'] == 'failed').sum())} jobs (skipping unless --retry-failed).")

    if not jobs_to_run:
        print("\nAll jobs are already processed. Nothing to do!")
        return

    batch_start = time.time()
    is_spyder = 'SPYDER' in os.environ.get('PYTHONSTARTUP', '') or 'IPython' in sys.modules

    if parallel > 1:
        print(f"Parallel mode: {parallel} workers")
        _execute_sweeps_parallel(df_manifest, jobs_to_run, batch_start, show_progress, is_spyder, parallel)
    else:
        _execute_sweeps_sequential(df_manifest, jobs_to_run, batch_start, show_progress, is_spyder)

    batch_elapsed = time.time() - batch_start
    print(f"\n{'#'*70}")
    print(f"  BATCH COMPLETED IN {batch_elapsed/3600:.2f} HOURS")
    print(f"{'#'*70}")


def print_manifest_summary():
    """Reads the current manifest from file and displays a clean summary table of results."""
    if not os.path.exists(MANIFEST_PATH):
        print(f"No manifest file found at {MANIFEST_PATH}")
        return

    df = pd.read_csv(MANIFEST_PATH)
    total = len(df)
    ok = (df['status'] == 'ok').sum()
    failed = (df['status'] == 'failed').sum()
    pending = (df['status'] == 'pending').sum()

    print(f"\n{'='*70}")
    print(f"  SWEEP SUMMARY TABLE -- {ok} succeeded | {failed} failed | {pending} pending")
    print(f"{'='*70}")

    if failed > 0:
        print("\nFailed runs:")
        for _, row in df[df['status'] == 'failed'].iterrows():
            print(f"  - {row['job_id']}: {row['error_message']}")

    print(f"\n  {'Job Label':<55} {'SF%':>6}  {'Aux_GJ':>8}  {'Status'}")
    print(f"  {'-'*76}")
    for _, row in df.iterrows():
        sf_val = row['solar_fraction_pct']
        sf_str = f"{sf_val:.1f}" if not pd.isna(sf_val) else "  N/A"
        aux_val = row['total_aux_kJ']
        aux_str = f"{aux_val/1e6:.2f}" if not pd.isna(aux_val) else "   N/A"

        label = row['job_id']
        if len(label) > 55:
            label = label[:52] + "..."

        print(f"  {label:<55} {sf_str:>6}  {aux_str:>8}  {row['status']}")
    print(f"\nSummary manifest file: {MANIFEST_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="Run a robust, resumable parametric sweep over PBTES design variables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sweep configurations:
  aperture       PTC aperture area: 500, 750, 1000, 1500, 2000, 3000 m2
  tes_volume     TES tank: D=[4,5,6,7,8,10] m x H=[3,4,5,6,8] m (30 points)
  topology       All 4 combos: Parallel/Series x direct/indirect
  physical_sens  Sensitivity to rock size (dp), void fraction (vf), and insulation thickness
  htf            Primary NaK vs comparison Air loop baseline runs
  full           Combination of all sweeps above

Checkpoints:
  Checkpointing is stored in results/parametric_manifest.csv.
  If the simulation is interrupted, running the command again will resume
  automatically. To force restart, pass the --reset-manifest flag.
        """
    )
    parser.add_argument(
        '--sweep',
        type=str,
        default='topology',
        choices=['aperture', 'tes_volume', 'topology', 'physical_sens', 'htf', 'full'],
        help="Which parameter sweep to run (default: topology)."
    )
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help="Number of simulation days per sweep point (default: 365)."
    )
    parser.add_argument(
        '--tag',
        type=str,
        default='sweep',
        help="Tag prefix for results and manifest (default: 'sweep')."
    )
    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help="Force rerun of previously failed jobs (default: skip failed)."
    )
    parser.add_argument(
        '--reset-manifest',
        action='store_true',
        help="Archive existing manifest and create a new one from scratch."
    )
    parser.add_argument(
        '--job-range',
        type=str,
        default=None,
        help="Only process jobs in slice, e.g. '0:15' (for manual parallel chunking)."
    )
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help="Suppress the progress dashboard (useful for logging to file)."
    )
    parser.add_argument(
        '--dashboard-interval',
        type=int,
        default=0,
        help="Minimum seconds between dashboard refreshes (default: refresh at every job completion)."
    )
    parser.add_argument(
        '--parallel',
        type=int,
        default=1,
        help="Number of parallel worker processes (default: 1 = sequential)."
    )

    args = parser.parse_args()

    job_range = None
    if args.job_range is not None:
        parts = args.job_range.split(':')
        if len(parts) == 2:
            job_range = (int(parts[0]), int(parts[1]))

    print(f"\n{'#'*70}")
    print(f"  PBTES PARAMETRIC SWEEP ENGINE")
    print(f"  Sweep: {args.sweep}  |  Days: {args.days}  |  Tag: {args.tag}")
    if job_range:
        print(f"  Job range: {job_range[0]}:{job_range[1]}")
    if args.parallel > 1:
        print(f"  Workers: {args.parallel} (parallel)")
    print(f"  Restart checklist: results/parametric_manifest.csv")
    print(f"{'#'*70}")

    execute_sweeps(
        sweep_type=args.sweep,
        days=args.days,
        tag=args.tag,
        retry_failed=args.retry_failed,
        reset_manifest=args.reset_manifest,
        job_range=job_range,
        show_progress=not args.no_progress,
        dashboard_interval=args.dashboard_interval,
        parallel=args.parallel
    )

    print_manifest_summary()


if __name__ == '__main__':
    main()
