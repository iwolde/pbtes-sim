"""
Parametric Sweep Entry Point (Robust & Resumable)
===================================================
Runs parametric sweeps over design and physical variables by calling the single-simulation
logic from run_simulation.py in a loop.

Features:
  - Manifest Checkpointing: Keeps state in results/parametric_manifest.csv. If stopped,
    re-running will automatically resume from the last pending simulation.
  - Fault Tolerance: If a simulation fails due to a solver convergence error or physics singularity,
    it logs the failure and traceback, saves state, and continues to the next run.
  - Automatically resets interrupted runs (left in state 'running' from a crash/kill).

Usage:
    python run_parametric.py --sweep topology       # Parallel vs Series, direct vs indirect
    python run_parametric.py --sweep aperture       # aperture area sweep
    python run_parametric.py --sweep tes_volume     # tank D x H grid (30 points)
    python run_parametric.py --sweep physical_sens  # particle diameter, void fraction, insulation
    python run_parametric.py --sweep htf            # primary NaK vs Air baseline
    python run_parametric.py --sweep full           # all of the sweeps combined

Optional overrides and controls:
    --days          Number of simulation days per sweep point (default: 365)
    --tag           Result file tag prefix (default: 'sweep')
    --retry-failed  Force-retry failed simulations instead of skipping them
    --reset-manifest Archive the existing manifest and start a fresh sweep grid
"""

import os
import sys
import argparse
import json
import traceback
import time
from datetime import datetime
import pandas as pd
import numpy as np

# Add root directory to sys.path so we can import run_simulation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_simulation import run_single_simulation

# ── Baseline Parameter Definition ─────────────────────────────────────────────
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

# ── Sweep parameter grids ─────────────────────────────────────────────────────
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

# ── Manifest & State Management ───────────────────────────────────────────────

MANIFEST_PATH = os.path.join('results', 'parametric_manifest.csv')

def get_job_id(job: dict) -> str:
    """Generate a unique job ID string based on all configuration parameters."""
    htf_clean = job['htf'].replace('INCOMP::', '')
    return (
        f"{job['tag']}_{job['topology']}_{job['tank_config']}_{htf_clean}_"
        f"D{job['tank_diameter']:.1f}_H{job['tank_height']:.1f}_A{job['aperture']:.0f}_"
        f"dp{job['particle_diameter']:.3f}_vf{job['void_fraction']:.2f}_ins{job['insulation_thickness']:.2f}_"
        f"{job['days']}d"
    )

def generate_sweep_grid(sweep_type: str, days: int, tag: str) -> list:
    """Generate a list of unique job dictionaries for the requested sweep type."""
    jobs = []

    def create_job(**overrides):
        job = BASELINE_PARAMS.copy()
        job.update(overrides)
        job['days'] = days
        job['tag'] = tag
        job['job_id'] = get_job_id(job)
        return job

    # 1. Aperture Area Sweep
    if sweep_type in ['aperture', 'full']:
        for ap in APERTURE_SWEEP:
            jobs.append(create_job(aperture=ap))

    # 2. TES Tank Diameter & Height Grid (30 points)
    if sweep_type in ['tes_volume', 'full']:
        for D in TES_DIAMETER_SWEEP:
            for H in TES_HEIGHT_SWEEP:
                jobs.append(create_job(tank_diameter=D, tank_height=H))

    # 3. Topologies Comparison (4 combinations)
    if sweep_type in ['topology', 'full']:
        for top, tc in TOPOLOGY_COMBOS:
            jobs.append(create_job(topology=top, tank_config=tc))

    # 4. Packed Bed Physical Sensitivities (Sequential variations from baseline)
    if sweep_type in ['physical_sens', 'full']:
        for dp in PARTICLE_SWEEP:
            jobs.append(create_job(particle_diameter=dp))
        for vf in VOID_SWEEP:
            jobs.append(create_job(void_fraction=vf))
        for ins in INSULATION_SWEEP:
            jobs.append(create_job(insulation_thickness=ins))

    # 5. HTF comparison baseline
    if sweep_type in ['htf', 'full']:
        for h in HTF_SWEEP:
            jobs.append(create_job(htf=h))

    # Remove duplicate combinations while maintaining sequence order
    seen = set()
    unique_jobs = []
    for j in jobs:
        # Create a unique parameter signature key
        key = (
            j['topology'], j['tank_config'], j['htf'], j['aperture'],
            j['tank_diameter'], j['tank_height'], j['particle_diameter'],
            j['void_fraction'], j['insulation_thickness'], j['days'], j['tag']
        )
        if key not in seen:
            seen.add(key)
            unique_jobs.append(j)

    return unique_jobs

def load_or_create_manifest(sweep_type: str, days: int, tag: str, reset: bool = False) -> pd.DataFrame:
    """Load existing manifest, reset interrupted jobs, append new grid combinations, or create a fresh one."""
    os.makedirs('results', exist_ok=True)
    grid_jobs = generate_sweep_grid(sweep_type, days, tag)
    df_grid = pd.DataFrame(grid_jobs)

    # Initialize metadata and tracking columns
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
            
            # Reset any job that was left as 'running' (interrupted run)
            running_mask = df_existing['status'] == 'running'
            if running_mask.any():
                print(f"  -> Resetting {running_mask.sum()} interrupted 'running' job(s) back to 'pending'.")
                df_existing.loc[running_mask, 'status'] = 'pending'
                df_existing.loc[running_mask, 'error_message'] = 'Interrupted execution'

            # Ensure all grid jobs are present in the manifest
            # Use job_id as the primary key
            merged_list = []
            existing_jobs = {row['job_id']: row.to_dict() for _, row in df_existing.iterrows()}
            
            for _, grid_row in df_grid.iterrows():
                jid = grid_row['job_id']
                if jid in existing_jobs:
                    merged_list.append(existing_jobs[jid])
                else:
                    merged_list.append(grid_row.to_dict())
            
            df_manifest = pd.DataFrame(merged_list)
            # Save right away to persist any resets
            df_manifest.to_csv(MANIFEST_PATH, index=False)
            return df_manifest
        except Exception as e:
            print(f"[Warning] Failed to parse existing manifest: {e}. Recreating...")
            
    if reset and os.path.exists(MANIFEST_PATH):
        archive_path = f"{os.path.splitext(MANIFEST_PATH)[0]}_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.rename(MANIFEST_PATH, archive_path)
        print(f"Archived existing manifest to: {archive_path}")

    # Create new manifest file
    print(f"Creating a new manifest with {len(df_grid)} jobs.")
    df_grid.to_csv(MANIFEST_PATH, index=False)
    return df_grid

def save_manifest_state(df_manifest: pd.DataFrame):
    """Write the manifest dataframe atomically to disk to prevent loss of state."""
    # Write to a temp file first, then replace (prevents file corruption on sudden stops)
    temp_path = MANIFEST_PATH + ".tmp"
    df_manifest.to_csv(temp_path, index=False)
    if os.path.exists(temp_path):
        if os.path.exists(MANIFEST_PATH):
            os.remove(MANIFEST_PATH)
        os.rename(temp_path, MANIFEST_PATH)

# ── Core Sweep Execution Loop ─────────────────────────────────────────────────

def execute_sweeps(sweep_type: str, days: int, tag: str, retry_failed: bool = False, reset_manifest: bool = False):
    """Iterates through jobs in the manifest, executes them safely, and captures results."""
    df_manifest = load_or_create_manifest(sweep_type, days, tag, reset=reset_manifest)

    # Filter pending jobs (and failed if retry_failed is specified)
    jobs_to_run = []
    for idx, row in df_manifest.iterrows():
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

    # Keep track of start time for the entire batch
    batch_start = time.time()

    for idx, job_idx in enumerate(jobs_to_run, 1):
        job = df_manifest.loc[job_idx].to_dict()
        jid = job['job_id']
        
        print(f"\n[{idx}/{queued_count}] Running simulation: {jid}")
        print(f"  Params: Topology={job['topology']}, Tank Config={job['tank_config']}, HTF={job['htf']}, "
              f"Aperture={job['aperture']} m2, D={job['tank_diameter']}m, H={job['tank_height']}m, "
              f"dp={job['particle_diameter']:.3f}m, vf={job['void_fraction']:.2f}, ins={job['insulation_thickness']:.2f}")

        # Update status to 'running'
        df_manifest.at[job_idx, 'status'] = 'running'
        df_manifest.at[job_idx, 'timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_manifest_state(df_manifest)

        t0 = time.time()
        try:
            # Execute single simulation
            df_res, filename, meta = run_single_simulation(
                days=int(job['days']),
                topology=job['topology'],
                tank_config=job['tank_config'],
                htf=job['htf'],
                tag=job['tag'],
                aperture=float(job['aperture']),
                tank_diameter=float(job['tank_diameter']),
                tank_height=float(job['tank_height']),
                particle_diameter=float(job['particle_diameter']),
                void_fraction=float(job['void_fraction']),
                insulation_thickness=float(job['insulation_thickness']),
            )

            # Compute thermodynamic metrics
            sol_useful = df_res['solar_to_proc_kJ'].sum()
            tes_useful = df_res['tes_to_proc_kJ'].sum()
            aux_proc   = df_res['aux_to_proc_kJ'].sum()
            aux_tes    = df_res['aux_tes_energy_kJ'].sum() if 'aux_tes_energy_kJ' in df_res.columns else 0.0
            
            total_aux    = aux_proc + aux_tes
            total_demand = sol_useful + tes_useful + total_aux
            sf = (sol_useful + tes_useful) / total_demand * 100.0 if total_demand > 0 else 0.0
            
            n_failed = int((df_res['iter_status'] == 'failed').sum()) if 'iter_status' in df_res.columns else 0
            elapsed = time.time() - t0

            # Update manifest on success
            df_manifest.at[job_idx, 'status'] = 'ok'
            df_manifest.at[job_idx, 'elapsed_seconds'] = round(elapsed, 1)
            df_manifest.at[job_idx, 'output_file'] = filename
            df_manifest.at[job_idx, 'solar_fraction_pct'] = round(sf, 2)
            df_manifest.at[job_idx, 'total_solar_kJ'] = round(sol_useful, 1)
            df_manifest.at[job_idx, 'total_aux_kJ'] = round(total_aux, 1)
            df_manifest.at[job_idx, 'total_tes_discharge_kJ'] = round(tes_useful, 1)
            df_manifest.at[job_idx, 'convergence_errors'] = n_failed
            df_manifest.at[job_idx, 'error_message'] = ''
            
            print(f"  [SUCCESS] Finished in {elapsed:.1f}s | Solar Fraction: {sf:.1f}% | Errors: {n_failed}")

        except Exception as e:
            elapsed = time.time() - t0
            err_msg = str(e)
            tb_str = traceback.format_exc()
            print(f"  [FAILED] Simulation failed in {elapsed:.1f}s: {err_msg}")
            
            # Record error details
            df_manifest.at[job_idx, 'status'] = 'failed'
            df_manifest.at[job_idx, 'elapsed_seconds'] = round(elapsed, 1)
            df_manifest.at[job_idx, 'error_message'] = err_msg.replace('\n', ' ')

        # Incrementally persist manifest state
        save_manifest_state(df_manifest)

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
    print(f"  SWEEP SUMMARY TABLE — {ok} succeeded | {failed} failed | {pending} pending")
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
        
        # Truncate label for display
        label = row['job_id']
        if len(label) > 55:
            label = label[:52] + "..."
            
        print(f"  {label:<55} {sf_str:>6}  {aux_str:>8}  {row['status']}")
    print(f"\nSummary manifest file: {MANIFEST_PATH}")


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run a robust, resumable parametric sweep over PBTES design variables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sweep configurations:
  aperture       PTC aperture area: 500, 750, 1000, 1500, 2000, 3000 m²
  tes_volume     TES tank: D=[4,5,6,7,8,10] m × H=[3,4,5,6,8] m (30 points)
  topology       All 4 combos: Parallel/Series × direct/indirect
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
    
    args = parser.parse_args()

    print(f"\n{'#'*70}")
    print(f"  PBTES PARAMETRIC SWEEP ENGINE")
    print(f"  Sweep: {args.sweep}  |  Days: {args.days}  |  Tag: {args.tag}")
    print(f"  Restart checklist: results/parametric_manifest.csv")
    print(f"{'#'*70}")

    # Run the sweeps loop
    execute_sweeps(
        sweep_type=args.sweep,
        days=args.days,
        tag=args.tag,
        retry_failed=args.retry_failed,
        reset_manifest=args.reset_manifest
    )

    # Output summary results
    print_manifest_summary()

if __name__ == '__main__':
    main()
