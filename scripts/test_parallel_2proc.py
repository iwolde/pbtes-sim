"""
Stage 2: Two-Process Parallel Proof-of-Concept
================================================
Runs 2 simulations in parallel using multiprocessing.Pool with spawn start method.
Validates that TESPy and CoolProp survive process isolation on Windows.

Usage:
    python scripts/test_parallel_2proc.py
"""

import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_job(job):
    from run_simulation import run_single_simulation
    df, fname, meta = run_single_simulation(
        days=1,
        topology=job['topology'],
        tank_config=job['tank_config'],
        htf='INCOMP::NaK',
        tag='par2_test',
        aperture=job['aperture'],
        run_id=job['run_id'],
        show_progress=False
    )
    sol_useful = df['solar_to_proc_kJ'].sum() + df['tes_to_proc_kJ'].sum()
    total_aux = df['aux_to_proc_kJ'].sum()
    total_aux += df['aux_tes_energy_kJ'].sum() if 'aux_tes_energy_kJ' in df.columns else 0.0
    total_demand = sol_useful + total_aux
    sf = sol_useful / total_demand * 100.0 if total_demand > 0 else 0.0
    n_errors = int((df['iter_status'] == 'failed').sum()) if 'iter_status' in df.columns else 0
    return {
        'run_id': job['run_id'],
        'file': fname,
        'sf': round(sf, 2),
        'convergence_errors': n_errors,
        'solar_kJ': round(df['solar_to_proc_kJ'].sum() + df['tes_to_proc_kJ'].sum(), 1),
        'aux_kJ': round(total_aux, 1)
    }


if __name__ == '__main__':
    mp.set_start_method('spawn')

    jobs = [
        {
            'topology': 'Parallel',
            'tank_config': 'indirect',
            'aperture': 1000.0,
            'run_id': 'par2_test_A1000'
        },
        {
            'topology': 'Parallel',
            'tank_config': 'indirect',
            'aperture': 1500.0,
            'run_id': 'par2_test_A1500'
        },
    ]

    print("=== Stage 2: Two-Process Parallel Test ===")
    print(f"Running {len(jobs)} jobs in parallel (spawn start method)...")
    print(f"Jobs: {[j['run_id'] for j in jobs]}")

    t0 = time.time()
    with mp.Pool(processes=2) as pool:
        results = pool.map(_run_job, jobs)
    elapsed = time.time() - t0

    print(f"\nCompleted in {elapsed:.1f}s")
    for r in results:
        print(f"  {r['run_id']}: SF={r['sf']}% Errors={r['convergence_errors']} "
              f"Solar={r['solar_kJ']/1e3:.0f}MJ Aux={r['aux_kJ']/1e3:.0f}MJ")

    expected_a1000_sf = 47.2
    expected_a1500_sf = None  # We'll compare to a sequential re-run

    a1000_result = next(r for r in results if 'A1000' in r['run_id'])
    a1500_result = next(r for r in results if 'A1500' in r['run_id'])

    sf_ok = abs(a1000_result['sf'] - expected_a1000_sf) < 0.1
    errors_ok = a1000_result['convergence_errors'] == 0 and a1500_result['convergence_errors'] == 0

    print(f"\nValidation:")
    print(f"  A1000 SF={a1000_result['sf']}% vs expected {expected_a1000_sf}%: {'PASS' if sf_ok else 'FAIL'}")
    print(f"  Both 0 convergence errors: {'PASS' if errors_ok else 'FAIL'}")

    if sf_ok and errors_ok:
        print("\n*** STAGE 2 PASSED ***")
    else:
        print("\n*** STAGE 2 FAILED ***")
        sys.exit(1)
