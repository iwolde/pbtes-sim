"""
Assessment 02 — Parametric Sweep (Tank Geometry D × L)
Runs a grid of annual simulations varying tank diameter and length.
Saves a single CSV with solar fraction, LCOH, and energy metrics for each point.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import concurrent.futures
import pandas as pd
import numpy as np
import math
import time
import traceback
from coreV5 import Solver
import economics

# ─── HTF ───────────────────────────────────────────────────────────────
HTF = 'INCOMP::NaK'
HTF_TES = 'INCOMP::NaK'

# ─── Base parameters (same as baseline) ───────────────────────────────
base_tes_params = {
    'HTF': HTF_TES,
    'Initial temperature': 490,
    'Tank lenght': 5,
    'Particle diameter': 50e-3,
    'Tank diameter': 7,
    'Void fraction': 0.4,
    'Solid density': 3500,
    'Solid specific heat': 968,
    'Solid conductivity': 1.6,
    'Wall thinckness': 20e-3,
    'Tank conductivity': 45,
    'Insulation thickness': 750e-3,
    'Insulation conductivity': 0.03,
}

base_component_params = {
    'pump_eta_s': 0.85,
    'comp_eta_s': 0.8,
    'ptc_pr': 1,
    'ptc_aoi': 20,
    'ptc_doc': 1,
    'ptc_tamb': 20,
    'ptc_A': 1000,
    'eta_opt': 0.816,
    'ptc_c_1': 0.0622,
    'ptc_c_2': 0.00023,
    'ptc_E': 900,
    'ptc_iam_1': -1.59e-3,
    'ptc_iam_2': 9.77e-5,
    'PR_pr': 1,
    'PR_Q': -450000,
    'PH_pr': 1,
}

base_conexion_params = {
    '5_T': 520,
    '6_T': 480,
    '6_p': 50,
    '6_f': {HTF: 1},
    '13_p': 5,
    '13_f': {HTF_TES: 1},
    '15_p': 5,
    '15_f': {HTF_TES: 1}
}

# ─── Sweep grid ───────────────────────────────────────────────────────
DIAMETERS = np.linspace(3, 10, 6)   # 6 points: 3, 4.4, 5.8, 7.2, 8.6, 10
LENGTHS   = np.linspace(2, 8, 6)    # 6 points: 2, 3.2, 4.4, 5.6, 6.8, 8
DAYS      = 365                      # full year

# ─── Output ───────────────────────────────────────────────────────────
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'article_results', '02_parametric')
os.makedirs(OUT_DIR, exist_ok=True)


def run_single(args):
    """Run one annual simulation for a given (D, L) pair. Returns a dict."""
    diameter, length = args
    tag = f"D={diameter:.1f}_L={length:.1f}"
    print(f"  ▶ Starting {tag}")
    t0 = time.time()

    tes_params = base_tes_params.copy()
    component_params = base_component_params.copy()
    conexion_params = base_conexion_params.copy()

    tes_params['Tank diameter'] = diameter
    tes_params['Tank lenght'] = length

    solar_fraction = 0.0
    energy_yield_kwh = 0.0
    n_errors = 0
    status = 'ok'

    try:
        solver = Solver(
            tes_params=tes_params,
            component_params=component_params,
            conexion_params=conexion_params,
            HTF=HTF,
            system_mode='Full',
            topology='Parallel'
        )
        solver.initialize_modes()

        result = solver.run_quasi_steady_simulation(
            days_to_simulate=DAYS,
            csv='TMY.csv',
        )

        metrics = solver.compute_performance_metrics()
        solar_fraction = metrics.get('solar_fraction', 0.0)

        df = pd.DataFrame(result)
        if 'tes_to_proc_kJ' in df.columns and 'solar_to_proc_kJ' in df.columns:
            energy_yield_kwh = (df['tes_to_proc_kJ'].sum() + df['solar_to_proc_kJ'].sum()) / 3600
        else:
            energy_yield_kwh = 1_000_000 * solar_fraction

        if 'iter_status' in df.columns:
            n_errors = int((df['iter_status'] != 'converged').sum())

    except Exception as e:
        status = f'FAILED: {e}'
        traceback.print_exc()

    elapsed = time.time() - t0

    volume_m3 = math.pi * ((diameter / 2) ** 2) * length
    htf_density = 1900  # typical molten salt density
    htf_mass_kg = volume_m3 * tes_params['Void fraction'] * htf_density

    lcoh = economics.calculate_lcoh(energy_yield_kwh, volume_m3, htf_mass_kg)

    row = {
        'Tank diameter (m)': diameter,
        'Tank length (m)': length,
        'Solar Fraction': solar_fraction,
        'Energy Yield (kWh)': energy_yield_kwh,
        'Tank Volume (m3)': volume_m3,
        'HTF Mass (kg)': htf_mass_kg,
        'LCOH ($/kWh)': lcoh,
        'N error steps': n_errors,
        'Runtime (s)': elapsed,
        'Status': status,
    }
    print(f"  ✔ {tag}  SF={solar_fraction:.2%}  LCOH={lcoh:.4f}  [{elapsed:.0f}s]")
    return row


def main():
    tasks = [(d, l) for d in DIAMETERS for l in LENGTHS]
    print(f"\n{'='*60}")
    print(f" Parametric sweep: {len(tasks)} runs ({len(DIAMETERS)} D × {len(LENGTHS)} L)")
    print(f"{'='*60}")

    results = []

    # Sequential (safer for TESPy/CoolProp which can be thread-unsafe)
    for t in tasks:
        res = run_single(t)
        results.append(res)
        # Save incrementally so partial results survive crashes
        df_partial = pd.DataFrame(results)
        df_partial.to_csv(os.path.join(OUT_DIR, 'parametric_sweep.csv'), index=False)

    df = pd.DataFrame(results)
    csv_path = os.path.join(OUT_DIR, 'parametric_sweep.csv')
    df.to_csv(csv_path, index=False)
    print(f"\n✅ Parametric sweep complete → {csv_path}")
    print(f"   Total runs: {len(df)}")
    print(f"   Failed: {(df['Status'] != 'ok').sum()}")


if __name__ == '__main__':
    main()
