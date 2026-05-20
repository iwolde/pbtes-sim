"""Quick check of 3-day results."""
import pandas as pd
df = pd.read_csv('results/debug3_Parallel_indirect_NaK_D7.0_H5.0_A1000_3d_20260520.csv', skiprows=1)
print('Modes:', df['TESmode'].value_counts().to_dict())
print(f'Hours with E > 551: {(df["E"] > 551).sum()} / {len(df)}')
print(f'Solar to proc: {df["solar_to_proc_kJ"].sum()/1e6:.0f} GJ')
print(f'to_tes: {df["to_tes_kJ"].sum()/1e6:.0f} GJ')
print(f'T_top mean: {df["T_tes_top"].mean():.0f}C')
