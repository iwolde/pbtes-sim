"""
Assessment 01 — Baseline Annual Simulation
Runs a full 365-day simulation for the Parallel topology using NaK HTF.
Saves results to article_results/01_baseline/
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coreV5 import Solver, Reporting
import pandas as pd
import time

# ─── HTF ───────────────────────────────────────────────────────────────
HTF = 'INCOMP::NaK'
HTF_TES = 'INCOMP::NaK'

# ─── TES parameters ───────────────────────────────────────────────────
tes_params = {
    'HTF': HTF_TES,
    'Initial temperature': 490,   # °C
    'Tank lenght': 5,             # m
    'Particle diameter': 50e-3,   # m
    'Tank diameter': 7,           # m
    'Void fraction': 0.4,
    'Solid density': 3500,        # kg/m³
    'Solid specific heat': 968,   # J/(kg·K)
    'Solid conductivity': 1.6,    # W/(m·K)
    'Wall thinckness': 20e-3,     # m
    'Tank conductivity': 45,      # W/(m·K)
    'Insulation thickness': 750e-3,  # m
    'Insulation conductivity': 0.03, # W/(m·K)
}

# ─── Component parameters ─────────────────────────────────────────────
component_params = {
    'pump_eta_s': 0.85,
    'comp_eta_s': 0.8,
    'ptc_pr': 1,
    'ptc_aoi': 20,
    'ptc_doc': 1,
    'ptc_tamb': 20,
    'ptc_A': 1000,           # m² — solar field aperture area
    'eta_opt': 0.816,
    'ptc_c_1': 0.0622,
    'ptc_c_2': 0.00023,
    'ptc_E': 900,
    'ptc_iam_1': -1.59e-3,
    'ptc_iam_2': 9.77e-5,
    'PR_pr': 1,
    'PR_Q': -450000,         # W — process heat demand (negative = heat removed)
    'PH_pr': 1,
}

# ─── Connection parameters ────────────────────────────────────────────
conexion_params = {
    '5_T': 520,
    '6_T': 480,
    '6_p': 50,
    '6_f': {HTF: 1},
    '13_p': 5,
    '13_f': {HTF_TES: 1},
    '15_p': 5,
    '15_f': {HTF_TES: 1}
}

# ─── Output directory ─────────────────────────────────────────────────
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'article_results', '01_baseline')
os.makedirs(OUT_DIR, exist_ok=True)


def run_baseline(topology='Parallel', days=3):
    tag = topology.lower()
    print(f'\n{"="*60}')
    print(f' Baseline simulation — topology={topology}, days={days}')
    print(f'{"="*60}')

    solver = Solver(
        tes_params=tes_params,
        component_params=component_params,
        conexion_params=conexion_params,
        HTF=HTF,
        system_mode='Full',
        topology=topology
    )

    print('Initializing design modes…')
    solver.initialize_modes()

    print(f'Running {days}-day quasi-steady simulation…')
    t0 = time.time()
    result = solver.run_quasi_steady_simulation(
        days_to_simulate=days,
        csv='TMY.csv',
    )
    elapsed = time.time() - t0
    print(f'Simulation done in {elapsed:.1f} s')

    print('Computing performance metrics…')
    metrics = solver.compute_performance_metrics()

    df = pd.DataFrame(result)

    # Save CSV
    report = Reporting()
    csv_path = os.path.join(OUT_DIR, f'baseline_{tag}.csv')
    report.save_simulation_to_csv(
        df,
        filepath=csv_path,
        solver=solver,
        tes_params=tes_params,
        component_params=component_params,
        conexion_params=conexion_params,
        sim_args={'days_to_simulate': days, 'csv': 'TMY.csv',
                  'topology': topology, 'elapsed_s': elapsed},
        extra_meta={'metrics': metrics}
    )
    print(f'Results saved -> {csv_path}')
    print(f'  rows: {len(df)}, columns: {list(df.columns)[:8]}…')

    return df, metrics


if __name__ == '__main__':
    # Run only Parallel for now (the stabilized code path)
    # Use 3 days for testing; pass --full for 365 days
    import sys
    test_days = 3
    if '--full' in sys.argv:
        test_days = 365
    run_baseline('Parallel', days=test_days)
    print('\n✅ Assessment 01 complete.')
