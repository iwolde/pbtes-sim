import os
import sys
import pandas as pd
import numpy as np

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pbtes.analysis.results_reader import load_results

filepath = "results/PI_90d_Parallel_indirect_NaK_D7.0_H5.0_A1000_90d_20260602.csv"
df, meta = load_results(filepath)

# Filter for charging modes (1, 6)
ch_df = df[df['TESmode'].astype(str).isin(['1', '6'])]

print(f"Total charging steps (Mode 1 or 6): {len(ch_df)}")
if len(ch_df) > 0:
    print("\nFirst 15 charging steps:")
    print(ch_df[['time', 'TESmode', 'E', 'T_ptc_out', 'T_tes_top', 'T_tes_bottom', 'mdot_tes_charge_kg_s', 'to_tes_kJ']].head(15))
    
    print("\nSummary statistics during charging:")
    print(f"  Avg Irradiance: {ch_df['E'].mean():.1f} W/m²")
    print(f"  Avg T_ptc_out:  {ch_df['T_ptc_out'].mean():.1f} °C")
    print(f"  Avg T_tes_top:  {ch_df['T_tes_top'].mean():.1f} °C")
    print(f"  Avg T_tes_bot:  {ch_df['T_tes_bottom'].mean():.1f} °C")
    print(f"  Avg Charge mass flow: {ch_df['mdot_tes_charge_kg_s'].mean():.2f} kg/s")
    print(f"  Avg Charge heat rate (kW): {(ch_df['to_tes_kJ']/3600).mean():.1f} kW")
else:
    print("No charging steps found!")
