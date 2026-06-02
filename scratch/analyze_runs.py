import os
import sys
import pandas as pd
import numpy as np
import json

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pbtes.analysis.results_reader import load_results

def analyze_csv(filepath):
    print(f"\n==================================================")
    print(f"ANALYSIS FOR: {filepath}")
    print(f"==================================================")
    
    # Load data using results_reader
    df, meta = load_results(filepath)
    
    total_steps = len(df)
    print(f"Total steps: {total_steps}")
    
    # Convergence Status counts
    print("\nConvergence Status:")
    status_counts = df['iter_status'].value_counts()
    for status, count in status_counts.items():
        pct = count / total_steps * 100
        print(f"  {status}: {count} ({pct:.2f}%)")
        
    # Operating Mode counts
    print("\nOperating Mode counts:")
    mode_counts = df['TESmode'].value_counts()
    for mode, count in mode_counts.items():
        pct = count / total_steps * 100
        print(f"  Mode {mode}: {count} ({pct:.2f}%)")
        
    # Temperature statistics
    print("\nTemperature Statistics (°C):")
    print(f"  TES Top:    avg = {df['T_tes_top'].mean():.1f}, min = {df['T_tes_top'].min():.1f}, max = {df['T_tes_top'].max():.1f}")
    print(f"  TES Bottom: avg = {df['T_tes_bottom'].mean():.1f}, min = {df['T_tes_bottom'].min():.1f}, max = {df['T_tes_bottom'].max():.1f}")
    if 'T_zinc' in df.columns:
        print(f"  T_zinc:     avg = {df['T_zinc'].mean():.1f}, min = {df['T_zinc'].min():.1f}, max = {df['T_zinc'].max():.1f}")
    
    # Energy sums (GJ)
    print("\nEnergy Statistics (GJ):")
    to_tes = df['to_tes_kJ'].sum() / 1e6
    tes_to_proc = df['tes_to_proc_kJ'].sum() / 1e6
    solar_to_proc = df['solar_to_proc_kJ'].sum() / 1e6
    aux_to_proc = df['aux_to_proc_kJ'].sum() / 1e6
    
    print(f"  Charged to TES:       {to_tes:.1f} GJ")
    print(f"  Discharged from TES:  {tes_to_proc:.1f} GJ")
    print(f"  Direct solar to proc: {solar_to_proc:.1f} GJ")
    print(f"  Auxiliary heater:     {aux_to_proc:.1f} GJ")
    
    # Solar fraction
    sol_useful = solar_to_proc + tes_to_proc
    total_proc = sol_useful + aux_to_proc
    sf = (sol_useful / total_proc * 100) if total_proc > 0 else 0
    print(f"  Calculated Solar Frac: {sf:.2f}%")
    
    # Let's inspect the step logs when convergence failed
    failed_steps = df[df['iter_status'] != 'converged']
    print(f"\nNon-converged steps count: {len(failed_steps)}")
    if len(failed_steps) > 0:
        print("First 5 non-converged steps:")
        print(failed_steps[['time', 'E', 'Tamb', 'TESmode', 'iter_status']].head(5))

print("Analyzing PI baseline...")
analyze_csv("results/PI_90d_Parallel_indirect_NaK_D7.0_H5.0_A1000_90d_20260602.csv")

print("\nAnalyzing SD baseline...")
analyze_csv("results/SD_90d_Series_direct_NaK_D7.0_H5.0_A1000_90d_20260602.csv")
