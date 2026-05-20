"""
Single Simulation Entry Point
==============================
Runs a single solar thermal plant simulation with Packed Bed Thermal Energy Storage (PBTES)
and dynamic zinc pool.

Usage:
    python run_simulation.py                            # 7-day test
    python run_simulation.py --days 365                 # full year
    python run_simulation.py --days 365 --topology Series --tank_config direct
    python run_simulation.py --days 365 --tag baseline
"""

import os
import sys
import argparse
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pbtes.config import baseline_config, zinc_pool_config
from pbtes.simulation.solver import Solver
from pbtes.reporting.plots import Reporting


def print_monthly_breakdown(df):
    if 'time' not in df.columns:
        return
    df = df.copy()
    df['time'] = pd.to_datetime(df['time'])
    df['month'] = df['time'].dt.month
    
    print("\n" + "="*125)
    print(" MONTHLY PERFORMANCE BREAKDOWN")
    print("="*125)
    print(f"{'Month':<6} | {'SF%':<5} | {'DNI_avg':<7} | {'DNI_max':<7} | {'T_top_avg':<9} | {'T_top_max':<9} | {'T_bot_avg':<9} | {'T_bot_min':<9} | {'Q_ch_GJ':<7} | {'Q_dis_GJ':<8} | {'Q_aux_GJ':<8} | {'Mode top 3'}")
    print("-"*125)
    
    # Group by month (1 to 12)
    for m in sorted(df['month'].unique()):
        m_df = df[df['month'] == m]
        if m_df.empty:
            continue
            
        # Solar Fraction SF%
        sol_useful = m_df['solar_to_proc_kJ'].sum() + m_df['tes_to_proc_kJ'].sum()
        total_demand = sol_useful + m_df['aux_to_proc_kJ'].sum()
        sf = (sol_useful / total_demand * 100) if total_demand > 0 else 0.0
        
        # DNI
        dni_avg = m_df['E'].mean()
        dni_max = m_df['E'].max()
        
        # TES temperatures
        t_top_avg = m_df['T_tes_top'].mean()
        t_top_max = m_df['T_tes_top'].max()
        t_bot_avg = m_df['T_tes_bottom'].mean()
        t_bot_min = m_df['T_tes_bottom'].min()
        
        # Energy in GJ (1 GJ = 1,000,000 kJ)
        q_ch = m_df['to_tes_kJ'].sum() / 1e6
        q_dis = m_df['tes_to_proc_kJ'].sum() / 1e6
        q_aux = m_df['aux_to_proc_kJ'].sum() / 1e6
        
        # Mode top 3
        mode_counts = m_df['TESmode'].astype(str).value_counts()
        total_modes = len(m_df)
        mode_pct = [f"{mode} ({count/total_modes*100:.0f}%)" for mode, count in mode_counts.head(3).items()]
        mode_str = ", ".join(mode_pct)
        
        month_name = pd.Timestamp(2022, m, 1).strftime('%B')[:3]
        
        print(f"{month_name:<6} | {sf:5.1f} | {dni_avg:7.1f} | {dni_max:7.1f} | {t_top_avg:9.1f} | {t_top_max:9.1f} | {t_bot_avg:9.1f} | {t_bot_min:9.1f} | {q_ch:7.1f} | {q_dis:8.1f} | {q_aux:8.1f} | {mode_str}")
    print("="*125 + "\n")


def run_single_simulation(
    days=7,
    topology='Parallel',
    tank_config='indirect',
    htf='INCOMP::NaK',
    tag='baseline',
    aperture=1000.0,
    tank_diameter=7.0,
    tank_height=5.0,
    particle_diameter=0.050,
    void_fraction=0.4
):
    # Load baseline parameters
    tes_params, component_params, conexion_params = baseline_config()
    zinc_params = zinc_pool_config()

    # Apply overrides
    component_params['ptc_A'] = aperture
    tes_params['Tank diameter'] = tank_diameter
    tes_params['Tank length'] = tank_height
    tes_params['Particle diameter'] = particle_diameter
    tes_params['Void fraction'] = void_fraction

    # Apply HTF overrides if they differ from baseline
    if htf != 'INCOMP::NaK':
        tes_params['HTF'] = htf
        conexion_params['6_f'] = {htf: 1}
        conexion_params['13_f'] = {htf: 1}
        conexion_params['15_f'] = {htf: 1}

    # Initialize the Solver
    print(f"\nInitializing solver...")
    print(f"  Topology:    {topology}")
    print(f"  Tank Config: {tank_config}")
    print(f"  HTF:         {htf}")
    print(f"  Aperture:    {aperture} m²")
    print(f"  TES Tank:    {tank_diameter}m D x {tank_height}m H")
    
    solver = Solver(
        tes_params=tes_params,
        component_params=component_params,
        conexion_params=conexion_params,
        HTF=htf,
        system_mode='Full',
        topology=topology,
        tank_config=tank_config,
        zinc_pool_params=zinc_params
    )

    # Initialize TESPy modes
    print("\nInitializing cycle design states...")
    solver.initialize_modes()

    # Run quasi-steady simulation
    print(f"\nRunning {days}-day simulation...")
    t_start = time.time()
    results_list = solver.run_quasi_steady_simulation(
        days_to_simulate=days,
        csv='TMY.csv'
    )
    elapsed = time.time() - t_start
    print(f"Simulation finished in {elapsed:.1f} seconds.")

    # Process and format results
    df = pd.DataFrame(results_list)
    
    # Map raw solver output fields to required CSV fields
    df['T_zinc'] = df['zinc_pool_temp']
    df['Q_zinc_hx_kW'] = df['process_hx_Q_kW']
    df['zinc_operating'] = df['time'].apply(lambda t: solver.zinc_pool.is_operating(t))

    # Reorder/select columns to comply with the results storage protocol
    required_cols = [
        'time', 'E', 'Tamb', 'TESmode', 'TES_layout', 'iter_status',
        'T_ptc_out', 'T_tes_top', 'T_tes_bottom', 'tes_soc_kWh', 'mdot_ptc_kg_s',
        'to_tes_kJ', 'tes_to_proc_kJ', 'solar_to_proc_kJ', 'aux_to_proc_kJ',
        'T_zinc', 'Q_zinc_hx_kW', 'zinc_operating'
    ]
    
    # Ensure all required columns are present in the final DF
    for c in required_cols:
        if c not in df.columns:
            df[c] = np.nan
            
    final_df = df[required_cols].copy()

    # Construct clean file name
    htf_clean = htf.replace('INCOMP::', '')
    dimensions = f"D{tank_diameter:.1f}_H{tank_height:.1f}_A{aperture:.0f}"
    date_str = datetime.now().strftime("%Y%m%d")
    
    os.makedirs('results', exist_ok=True)
    filename = f"results/{tag}_{topology}_{tank_config}_{htf_clean}_{dimensions}_{days}d_{date_str}.csv"

    # Save CSV with the leading __meta__ line
    meta = {
        'tag': tag,
        'topology': topology,
        'tank_config': tank_config,
        'HTF': htf,
        'dimensions': {
            'aperture_area': aperture,
            'tank_diameter': tank_diameter,
            'tank_height': tank_height,
            'particle_diameter': particle_diameter,
            'void_fraction': void_fraction
        },
        'tes_params': tes_params,
        'component_params': component_params,
        'conexion_params': conexion_params,
        'zinc_params': zinc_params,
        'sim_args': {
            'days': days,
            'elapsed_seconds': elapsed,
            'date': date_str
        }
    }

    # Use Reporting's metadata saving logic
    rep = Reporting()
    rep.save_simulation_to_csv(
        final_df,
        filepath=filename,
        params=meta
    )
    print(f"\nResults successfully saved to: {filename}")

    # Print monthly breakdown if simulation duration is >= 30 days
    if days >= 30:
        print_monthly_breakdown(final_df)

    return final_df, filename, meta


def main():
    parser = argparse.ArgumentParser(description="Run a single quasi-steady simulation of the plant.")
    parser.add_argument('--days', type=int, default=7, help="Number of days to simulate.")
    parser.add_argument('--topology', type=str, default='Parallel', choices=['Parallel', 'Series'],
                        help="Thermodynamic cycle topology.")
    parser.add_argument('--tank_config', type=str, default='indirect', choices=['indirect', 'direct'],
                        help="Storage tank integration config.")
    parser.add_argument('--htf', type=str, default='INCOMP::NaK', help="CoolProp fluid name for the primary loops.")
    parser.add_argument('--tag', type=str, default='baseline', help="Descriptive tag for the simulation run.")
    
    # Overrides for physical dimensions
    parser.add_argument('--aperture', type=float, default=1000.0, help="PTC field aperture area in m².")
    parser.add_argument('--tank_diameter', type=float, default=7.0, help="TES internal tank diameter in m.")
    parser.add_argument('--tank_height', type=float, default=5.0, help="TES packed bed height (Tank length) in m.")
    parser.add_argument('--particle_diameter', type=float, default=0.050, help="Packed bed particle diameter in m.")
    parser.add_argument('--void_fraction', type=float, default=0.4, help="Packed bed void fraction (porosity).")
    
    args = parser.parse_args()

    run_single_simulation(
        days=args.days,
        topology=args.topology,
        tank_config=args.tank_config,
        htf=args.htf,
        tag=args.tag,
        aperture=args.aperture,
        tank_diameter=args.tank_diameter,
        tank_height=args.tank_height,
        particle_diameter=args.particle_diameter,
        void_fraction=args.void_fraction
    )


if __name__ == '__main__':
    main()
