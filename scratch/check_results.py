import os
from pbtes.analysis.results_reader import load_results
import numpy as np

results_dir = 'results'
files = [f for f in os.listdir(results_dir) if f.startswith('test_fix_pi') and f.endswith('.csv')]
if not files:
    print("No results file found!")
    exit(1)

filepath = os.path.join(results_dir, files[0])
print(f"Loading {filepath}...")
df, meta = load_results(filepath)

print("\n--- Basic Statistics ---")
print(f"Total steps: {len(df)}")
mode_counts = df['TESmode'].astype(str).value_counts()
print("\nMode distribution:")
for mode, count in mode_counts.items():
    print(f"  Mode {mode}: {count} hours ({count/len(df)*100:.1f}%)")

print("\n--- Energy Totals (GJ) ---")
q_ch = df['to_tes_kJ'].sum() / 1e6
q_dis = df['tes_to_proc_kJ'].sum() / 1e6
q_aux = df['aux_to_proc_kJ'].sum() / 1e6
print(f"  Total charged (Q_ch):    {q_ch:.2f} GJ")
print(f"  Total discharged (Q_dis): {q_dis:.2f} GJ")
print(f"  Total auxiliary (Q_aux):  {q_aux:.2f} GJ")

sol_useful = df['solar_to_proc_kJ'].sum() + df['tes_to_proc_kJ'].sum()
total_demand = sol_useful + df['aux_to_proc_kJ'].sum()
sf = (sol_useful / total_demand * 100) if total_demand > 0 else 0.0
print(f"  Solar Fraction (SF%):    {sf:.1f}%")

print("\n--- Mode 3 Discharge Details ---")
m3_df = df[df['TESmode'].astype(str) == '3']
if m3_df.empty:
    print("No Mode 3 active timesteps!")
else:
    print(f"Mode 3 active steps: {len(m3_df)} hours")
    print(f"Mode 3 T_tes_top range: {m3_df['T_tes_top'].min():.1f}C to {m3_df['T_tes_top'].max():.1f}C")
    print(f"Mode 3 T_tes_bottom range: {m3_df['T_tes_bottom'].min():.1f}C to {m3_df['T_tes_bottom'].max():.1f}C")
    print(f"Mode 3 discharged energy total: {m3_df['tes_to_proc_kJ'].sum() / 1e6:.3f} GJ")

print("\n--- Convergence Rates ---")
iter_counts = df['iter_status'].astype(str).value_counts()
print("Iteration Status:")
for status, count in iter_counts.items():
    print(f"  Status {status}: {count} steps ({count/len(df)*100:.1f}%)")
