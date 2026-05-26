"""
Parametric Sweep Entry Point
=============================
Runs parametric sweeps over design variables by calling the single-simulation
logic from run_simulation.py in a loop.

The zinc pool is ALWAYS active. No option to disable it.

Usage:
    python run_parametric.py --sweep aperture       # aperture area sweep
    python run_parametric.py --sweep tes_volume     # tank D x H grid
    python run_parametric.py --sweep topology       # all 4 topology combos
    python run_parametric.py --sweep full           # all of the above

Optional overrides (applied as baseline for all sweep points):
    --days        Number of simulation days (default: 365)
    --tag         Result file tag prefix (default: 'sweep')

Notes:
    - Results saved to results/ with descriptive filenames per AGENTS.md protocol.
    - A summary CSV is saved alongside individual results files.
    - All sweeps use baseline_config() from pbtes/config.py as defaults.
    - For topology sweep, all 4 combos: Parallel/Series × direct/indirect.
"""

import os
import sys
import argparse
import json
import traceback
from datetime import datetime

import pandas as pd

# Add root directory to sys.path so we can import run_simulation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_simulation import run_single_simulation


# ── Sweep parameter grids ─────────────────────────────────────────────────────

# Aperture area sweep: 6 points from 500 to 3000 m²
APERTURE_SWEEP = [500.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0]

# TES volume sweep: grid of diameters × heights (m)
TES_DIAMETER_SWEEP = [4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
TES_HEIGHT_SWEEP   = [3.0, 4.0, 5.0, 6.0, 8.0]

# Topology combos: (topology, tank_config)
TOPOLOGY_COMBOS = [
    ('Parallel', 'indirect'),
    ('Parallel', 'direct'),
    ('Series',   'indirect'),
    ('Series',   'direct'),
]


# ── Sweep runners ─────────────────────────────────────────────────────────────

def run_aperture_sweep(days: int, tag: str) -> list:
    """Sweep over PTC aperture area, keeping all other params at baseline."""
    print(f"\n{'='*70}")
    print(f"  APERTURE SWEEP  ({len(APERTURE_SWEEP)} points, {days}d each)")
    print(f"{'='*70}")
    records = []
    for aperture in APERTURE_SWEEP:
        label = f"{tag}_aperture_A{aperture:.0f}"
        print(f"\n-- Aperture = {aperture:.0f} m2  (tag: {label})")
        result = _run_point(
            label=label, days=days,
            topology='Parallel', tank_config='indirect', htf='INCOMP::NaK',
            aperture=aperture
        )
        records.append(result)
    return records


def run_tes_volume_sweep(days: int, tag: str) -> list:
    """Sweep over TES tank diameter × height grid."""
    n_total = len(TES_DIAMETER_SWEEP) * len(TES_HEIGHT_SWEEP)
    print(f"\n{'='*70}")
    print(f"  TES VOLUME SWEEP  ({n_total} points = {len(TES_DIAMETER_SWEEP)}D × {len(TES_HEIGHT_SWEEP)}H, {days}d each)")
    print(f"{'='*70}")
    records = []
    for D in TES_DIAMETER_SWEEP:
        for H in TES_HEIGHT_SWEEP:
            label = f"{tag}_tes_D{D:.0f}_H{H:.0f}"
            print(f"\n-- D = {D:.1f} m, H = {H:.1f} m  (tag: {label})")
            result = _run_point(
                label=label, days=days,
                topology='Parallel', tank_config='indirect', htf='INCOMP::NaK',
                tank_diameter=D, tank_height=H
            )
            records.append(result)
    return records


def run_topology_sweep(days: int, tag: str) -> list:
    """Sweep all 4 topology combinations (Parallel/Series × direct/indirect)."""
    print(f"\n{'='*70}")
    print(f"  TOPOLOGY SWEEP  ({len(TOPOLOGY_COMBOS)} combos, {days}d each)")
    print(f"{'='*70}")
    records = []
    for topology, tank_config in TOPOLOGY_COMBOS:
        label = f"{tag}_{topology}_{tank_config}"
        print(f"\n-- Topology: {topology}, Tank config: {tank_config}  (tag: {label})")
        result = _run_point(
            label=label, days=days,
            topology=topology, tank_config=tank_config, htf='INCOMP::NaK'
        )
        records.append(result)
    return records


def run_full_sweep(days: int, tag: str) -> list:
    """Run all three sweeps (aperture, TES volume, topology)."""
    records = []
    records += run_aperture_sweep(days, tag)
    records += run_tes_volume_sweep(days, tag)
    records += run_topology_sweep(days, tag)
    return records


# ── Core runner ───────────────────────────────────────────────────────────────

def _run_point(
    label: str,
    days: int,
    topology: str = 'Parallel',
    tank_config: str = 'indirect',
    htf: str = 'INCOMP::NaK',
    aperture: float = 1000.0,
    tank_diameter: float = 7.0,
    tank_height: float = 5.0,
    particle_diameter: float = 0.050,
    void_fraction: float = 0.4,
) -> dict:
    """
    Run a single sweep point and return a summary record dict.

    Returns a dict with simulation metadata and key aggregate metrics,
    regardless of whether the run succeeded or failed.
    """
    record = {
        'label': label,
        'topology': topology,
        'tank_config': tank_config,
        'htf': htf,
        'aperture_m2': aperture,
        'tank_diameter_m': tank_diameter,
        'tank_height_m': tank_height,
        'days': days,
        'status': 'failed',
        'output_file': None,
        'solar_fraction_pct': None,
        'total_solar_kJ': None,
        'total_aux_kJ': None,
        'total_tes_discharge_kJ': None,
        'convergence_errors': None,
        'elapsed_s': None,
    }

    try:
        df, filename, meta = run_single_simulation(
            days=days,
            topology=topology,
            tank_config=tank_config,
            htf=htf,
            tag=label,
            aperture=aperture,
            tank_diameter=tank_diameter,
            tank_height=tank_height,
            particle_diameter=particle_diameter,
            void_fraction=void_fraction,
        )

        # Aggregate metrics
        sol_to_proc = df['solar_to_proc_kJ'].sum()
        tes_to_proc = df['tes_to_proc_kJ'].sum()
        aux          = df['aux_to_proc_kJ'].sum()
        total_demand = sol_to_proc + tes_to_proc + aux
        sf = (sol_to_proc + tes_to_proc) / total_demand * 100.0 if total_demand > 0 else 0.0

        n_failed = int((df['iter_status'] == 'failed').sum()) if 'iter_status' in df.columns else 0

        record.update({
            'status': 'ok',
            'output_file': filename,
            'solar_fraction_pct': round(sf, 2),
            'total_solar_kJ': round(sol_to_proc, 1),
            'total_aux_kJ': round(aux, 1),
            'total_tes_discharge_kJ': round(tes_to_proc, 1),
            'convergence_errors': n_failed,
            'elapsed_s': round(meta['sim_args']['elapsed_seconds'], 1),
        })

    except Exception as e:
        print(f"  [ERROR] Run failed: {e}")
        traceback.print_exc()
        record['error_message'] = str(e)

    return record


# ── Summary writer ────────────────────────────────────────────────────────────

def save_summary(records: list, sweep_name: str) -> str:
    """Save a summary CSV of all sweep results."""
    os.makedirs('results', exist_ok=True)
    date_str = datetime.now().strftime('%Y%m%d')
    summary_path = f"results/sweep_{sweep_name}_{date_str}.csv"

    df_summary = pd.DataFrame(records)
    df_summary.to_csv(summary_path, index=False)
    print(f"\nSweep summary saved to: {summary_path}")
    return summary_path


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run a parametric sweep over PBTES design variables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sweep modes:
  aperture    PTC aperture area: 500, 750, 1000, 1500, 2000, 3000 m²
  tes_volume  TES tank: D=[4,5,6,7,8,10] m × H=[3,4,5,6,8] m
  topology    All 4 combos: Parallel/Series × direct/indirect
  full        All three sweeps above

Example:
  python run_parametric.py --sweep topology --days 7 --tag test
  python run_parametric.py --sweep full --days 365 --tag baseline
        """
    )
    parser.add_argument(
        '--sweep',
        type=str,
        default='topology',
        choices=['aperture', 'tes_volume', 'topology', 'full'],
        help="Which sweep to run (default: topology)."
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
        help="Tag prefix for all result filenames (default: 'sweep')."
    )
    args = parser.parse_args()

    print(f"\n{'#'*70}")
    print(f"  PBTES PARAMETRIC SWEEP")
    print(f"  Sweep: {args.sweep}  |  Days: {args.days}  |  Tag: {args.tag}")
    print(f"{'#'*70}")

    sweep_fns = {
        'aperture':   run_aperture_sweep,
        'tes_volume': run_tes_volume_sweep,
        'topology':   run_topology_sweep,
        'full':       run_full_sweep,
    }
    records = sweep_fns[args.sweep](args.days, args.tag)

    # Save summary
    summary_path = save_summary(records, args.sweep)

    # Print results table
    print(f"\n{'='*70}")
    print(f"  SWEEP COMPLETE — {len(records)} point(s)")
    print(f"{'='*70}")
    ok    = [r for r in records if r['status'] == 'ok']
    failed = [r for r in records if r['status'] == 'failed']
    print(f"  Succeeded: {len(ok)} / {len(records)}")
    if failed:
        print(f"  Failed:    {len(failed)}")
        for r in failed:
            print(f"    - {r['label']}: {r.get('error_message', 'unknown error')}")
    print(f"\n  {'Label':<40} {'SF%':>6}  {'Aux_GJ':>7}  {'Status'}")
    print(f"  {'-'*64}")
    for r in records:
        sf  = f"{r['solar_fraction_pct']:.1f}" if r['solar_fraction_pct'] is not None else "  N/A"
        aux = f"{r['total_aux_kJ']/1e6:.2f}"   if r['total_aux_kJ']       is not None else "   N/A"
        print(f"  {r['label']:<40} {sf:>6}  {aux:>7}  {r['status']}")
    print(f"\n  Summary CSV: {summary_path}")


if __name__ == '__main__':
    main()
