import sys
import os
import pandas as pd

sys.path.append(r'c:\Users\iwold\OneDrive - Universidad Católica de Chile\Postdoc\Galvanizing solar PBTES\codigos')
from pbtes.analysis.results_reader import load_results

df, meta = load_results('results/test_mode3_fix_Parallel_indirect_NaK_D7.0_H5.0_A1000_7d_20260602.csv')

print("=== META ===")
print(meta)
print("\n=== TOP 20 TIMESTEPS ===")
print(df[['time', 'E', 'Tamb', 'TESmode', 'T_tes_top', 'T_tes_bottom', 'to_tes_kJ', 'tes_to_proc_kJ', 'iter_status']].head(20))

print("\n=== MODE COUNTS ===")
print(df['TESmode'].value_counts())

print("\n=== ANY MODE 1, 3, 5, 6 ACTIVES? ===")
active_modes = df[df['TESmode'].isin([1, 3, 5, 6])]
if not active_modes.empty:
    print(active_modes[['time', 'E', 'TESmode', 'T_tes_top', 'T_tes_bottom', 'to_tes_kJ', 'tes_to_proc_kJ', 'iter_status']])
else:
    print("None!")
