"""
Economic & LCOH Sensitivity Sweep
==================================
Post-processing pipeline script.
Loads completed simulation output files (either from results/parametric_manifest.csv
or directly matching a file pattern) and sweeps them across a grid of economic variables.

Because economic parameters (discount rate, lifetime, asset costs, fuel/electricity prices)
do not impact the physical/thermodynamic state equations, we run these sweeps instantly in
post-processing, avoiding redundant hourly solvers.

Usage:
    python scripts/run_economic_sensitivity.py                              # Process completed manifest jobs
    python scripts/run_economic_sensitivity.py --files "results/*_processed.csv"  # Process specific files
"""

import sys
import os
import glob
import json
import itertools
import argparse
from datetime import datetime
import pandas as pd
import numpy as np

# Ensure parent directory is in path so 'pbtes' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pbtes.analysis.results_reader import load_results
from pbtes.analysis.postprocess import calculate_system_pump_power
from pbtes.analysis.economics import EconomicAssessment

# ── Sensitivity Parameter Grids ───────────────────────────────────────────────
DISCOUNT_RATES = [0.05, 0.08, 0.10, 0.12]
LIFETIMES = [20, 25, 30]
ELECTRICITY_PRICES = [0.06, 0.10, 0.15]
AUX_FUEL_PRICES = [0.03, 0.05, 0.08]
TANK_COSTS = [300.0, 500.0, 700.0]
HTF_COSTS = [1.0, 2.0, 4.0]

def process_file_economic_grid(filepath: str) -> list:
    """Load results, compute pump power if missing, and run the economic grid search."""
    print(f"Processing: {filepath}")
    records = []
    
    try:
        # Load the dataframe and metadata
        df, meta = load_results(filepath)
        
        # Verify that pump power is calculated
        if 'W_pump_kW' not in df.columns:
            print("  -> 'W_pump_kW' column missing. Calculating pump power...")
            df = calculate_system_pump_power(df, meta)
            
        # Extract physical parameter tags
        sim_args = meta.get('sim_args', {})
        dims = meta.get('dimensions', {})
        
        topology = meta.get('topology', BASELINE_PARAMS_DUMMY['topology'])
        tank_config = meta.get('tank_config', BASELINE_PARAMS_DUMMY['tank_config'])
        htf = meta.get('HTF', BASELINE_PARAMS_DUMMY['htf'])
        
        aperture = dims.get('aperture_area', sim_args.get('aperture_area', 1000.0))
        tank_diameter = dims.get('tank_diameter', sim_args.get('tank_diameter', 7.0))
        tank_height = dims.get('tank_height', sim_args.get('tank_height', 5.0))
        particle_diameter = dims.get('particle_diameter', sim_args.get('particle_diameter', 0.050))
        void_fraction = dims.get('void_fraction', sim_args.get('void_fraction', 0.40))
        insulation_thickness = dims.get('insulation_thickness', 1.0)
        days = sim_args.get('days', 365)
        tag = meta.get('tag', 'sweep')

        # Cartesian product of economic parameters
        econ_combinations = list(itertools.product(
            DISCOUNT_RATES, LIFETIMES, ELECTRICITY_PRICES,
            AUX_FUEL_PRICES, TANK_COSTS, HTF_COSTS
        ))

        n_combos = len(econ_combinations)
        print(f"  -> Running {n_combos} economic sensitivity variations...")
        
        for r, n, p_el, p_fuel, c_tank, c_htf in econ_combinations:
            overrides = {
                'discount_rate': r,
                'lifetime': n,
                'electricity_price_per_kwh': p_el,
                'aux_fuel_price_per_kwh': p_fuel,
                'tank_cost_per_m3': c_tank,
                'htf_cost_per_kg': c_htf
            }
            
            # Run economic assessment
            assessment = EconomicAssessment(df, meta, overrides=overrides)
            res = assessment.run_assessment()
            
            # Combine physical and economic parameters in record
            record = {
                'filepath': filepath,
                'tag': tag,
                'topology': topology,
                'tank_config': tank_config,
                'htf': htf,
                'aperture_m2': aperture,
                'tank_diameter_m': tank_diameter,
                'tank_height_m': tank_height,
                'particle_diameter_m': particle_diameter,
                'void_fraction': void_fraction,
                'insulation_thickness_m': insulation_thickness,
                'days': days,
                'discount_rate': r,
                'lifetime_years': n,
                'electricity_price_usd_per_kwh': p_el,
                'aux_fuel_price_usd_per_kwh': p_fuel,
                'tank_cost_usd_per_m3': c_tank,
                'htf_cost_usd_per_kg': c_htf,
                'capex_ptc': res['capex_ptc'],
                'capex_tes': res['capex_tes'],
                'capex_pumps': res['capex_pumps'],
                'capex_hxs': res['capex_hxs'],
                'capex_total': res['capex_total'],
                'annualized_capex': res['annualized_capex'],
                'cost_electricity': res['cost_electricity'],
                'cost_aux_fuel': res['cost_aux_fuel'],
                'cost_om': res['cost_om'],
                'opex_total': res['opex_total'],
                'q_delivered_MWh': res['q_delivered_MWh'],
                'lcoh_usd_per_MWh': res['lcoh_usd_per_MWh']
            }
            records.append(record)
            
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        traceback.print_exc()
        
    return records

BASELINE_PARAMS_DUMMY = {
    'topology': 'Parallel',
    'tank_config': 'indirect',
    'htf': 'INCOMP::NaK',
}

def main():
    parser = argparse.ArgumentParser(description="Run economic sensitivity checks on simulated CSV datasets.")
    parser.add_argument('--files', type=str, default=None,
                        help="Glob file pattern of CSVs to process (e.g. 'results/baseline_*.csv'). If omitted, reads completed jobs from the manifest.")
    parser.add_argument('--out', type=str, default='results/parametric_economic_sensitivities.csv',
                        help="Path to save the combined economic sensitivity summary (default: results/parametric_economic_sensitivities.csv).")
    args = parser.parse_args()

    files_to_process = []
    
    # 1. Gather files
    if args.files:
        matches = glob.glob(args.files)
        files_to_process = [f for f in matches if not f.endswith('_processed.csv') and not f.endswith('sensitivities.csv')]
    else:
        # Load from manifest
        manifest_path = os.path.join('results', 'parametric_manifest.csv')
        if os.path.exists(manifest_path):
            print(f"Loading successful files from manifest: {manifest_path}")
            df_manifest = pd.read_csv(manifest_path)
            # Filter successful jobs with valid output paths
            df_ok = df_manifest[(df_manifest['status'] == 'ok') & (df_manifest['output_file'].notna())]
            files_to_process = df_ok['output_file'].tolist()
        else:
            print(f"Manifest not found at {manifest_path}. Please run run_parametric.py first or specify files with --files.")
            sys.exit(1)

    # De-duplicate files
    files_to_process = list(set(files_to_process))
    # Filter files that actually exist
    files_to_process = [f for f in files_to_process if os.path.exists(f)]

    if not files_to_process:
        print("No simulation results files found to process.")
        sys.exit(1)

    print(f"Found {len(files_to_process)} simulation results files to process.")
    
    all_records = []
    for filepath in files_to_process:
        records = process_file_economic_grid(filepath)
        all_records.extend(records)

    if not all_records:
        print("No economic assessment records were generated.")
        sys.exit(0)

    # 2. Save combined sensitivities
    df_sens = pd.DataFrame(all_records)
    df_sens.to_csv(args.out, index=False)
    print(f"\nSensitivities batch finished. Saved {len(df_sens)} records to: {args.out}")

if __name__ == '__main__':
    main()
