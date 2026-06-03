import pandas as pd
from pbtes.analysis.results_reader import load_results

df, meta = load_results('results/pi_test_Parallel_indirect_NaK_D7.0_H5.0_A1500_7d_20260603.csv')

print("Mode distribution:")
print(df['TESmode'].value_counts())

print("\nConvergence status distribution:")
if 'iter_status' in df.columns:
    print(df['iter_status'].value_counts())

print("\nTransitions:")
# Print the mode and status for non-4/non-2 modes
df_solar = df[df['TESmode'].isin(['1', '3', '5', '6'])]
if not df_solar.empty:
    print(df_solar[['time', 'E', 'TESmode', 'iter_status', 'T_ptc_out', 'T_tes_top', 'T_tes_bottom']].head(20))
else:
    print("No solar charging/discharging modes were active.")
