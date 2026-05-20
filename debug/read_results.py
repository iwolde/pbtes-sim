"""Read 7-day assessment results."""
import pandas as pd, numpy as np
df = pd.read_csv('results/m3fix_Parallel_indirect_NaK_D7.0_H5.0_A1000_7d_20260520.csv', skiprows=1)
print('=== MODE DISTRIBUTION ===')
print(df['TESmode'].value_counts().to_string())
print()

print('=== DNI STATS ===')
print(f'Mean: {df["E"].mean():.0f}, Max: {df["E"].max():.0f}')
print(f'Hours > 551 (E_min_process): {(df["E"] > 551).sum()} of {len(df)}')
print(f'Hours > 827 (E_min_charge): {(df["E"] > 827).sum()} of {len(df)}')
print()

print('=== FIRST 24 HOURS (E and mode) ===')
for i in range(24):
    row = df.iloc[i]
    print(f'  {str(row["time"])[:13]}: E={row["E"]:5.0f} mode={row["TESmode"]}')

print()
print('=== ENERGY ===')
s = df['solar_to_proc_kJ'].sum()
t = df['tes_to_proc_kJ'].sum()
a = df['aux_to_proc_kJ'].sum()
sf = (s + t) / max(s + t + a, 1) * 100
print(f'SF: {sf:.1f}%')
print(f'to_tes: {df["to_tes_kJ"].sum()/1e6:.0f} GJ')
print(f'solar_to_proc: {df["solar_to_proc_kJ"].sum()/1e6:.0f} GJ')
print(f'TES top mean: {df["T_tes_top"].mean():.0f}C, max: {df["T_tes_top"].max():.0f}C')
