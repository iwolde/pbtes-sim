import sys
import os
import pandas as pd
import numpy as np

sys.path.append(r'c:\Users\iwold\OneDrive - Universidad Católica de Chile\Postdoc\Galvanizing solar PBTES\codigos')

from pbtes.analysis.results_reader import load_results

new_results_file = 'results/test_mode3_fix_Parallel_indirect_NaK_D7.0_H5.0_A1000_7d_20260602.csv'
df, meta = load_results(new_results_file)

total_steps = len(df)
failed_steps = df[df['iter_status'] == 'failed']
num_fails = len(failed_steps)

print("="*60)
print(" ANALYSIS OF NEW 7-DAY PARALLEL INDIRECT SIMULATION (FIXED MODE 3)")
print("="*60)
print(f"Total hours: {total_steps}")
print(f"Failed steps: {num_fails} ({(num_fails/total_steps)*100:.2f}%)")

mode_counts = df['TESmode'].astype(int).value_counts().sort_index()
print("\nActive hours per mode:")
for mode, count in mode_counts.items():
    print(f"  Mode {mode}: {count} hours ({count/total_steps*100:.1f}%)")

sol_useful = df['solar_to_proc_kJ'].sum() + df['tes_to_proc_kJ'].sum()
total_demand = sol_useful + df['aux_to_proc_kJ'].sum()
sf = (sol_useful / total_demand * 100) if total_demand > 0 else 0.0
print(f"\nThermal Solar Fraction (SF%): {sf:.2f}%")

solar_to_proc_GJ = df['solar_to_proc_kJ'].sum() / 1e6
tes_to_proc_GJ = df['tes_to_proc_kJ'].sum() / 1e6
aux_to_proc_GJ = df['aux_to_proc_kJ'].sum() / 1e6
total_charge_GJ = df['to_tes_kJ'].sum() / 1e6

print(f"\nEnergy flows (GJ):")
print(f"  Direct solar to process: {solar_to_proc_GJ:.3f} GJ")
print(f"  TES discharging to process: {tes_to_proc_GJ:.3f} GJ")
print(f"  Auxiliary heater: {aux_to_proc_GJ:.3f} GJ")
print(f"  Total charging to TES: {total_charge_GJ:.3f} GJ")

print(f"\nTES final temperature profile:")
print(f"  TES Top: {df['T_tes_top'].iloc[-1]:.2f} °C")
print(f"  TES Bottom: {df['T_tes_bottom'].iloc[-1]:.2f} °C")

# Look at Mode 3 hours details
m3_df = df[df['TESmode'] == 3]
print(f"\nMode 3 hours: {len(m3_df)}")
if not m3_df.empty:
    print(m3_df[['time', 'T_tes_top', 'T_tes_bottom', 'tes_to_proc_kJ']].head(15))
