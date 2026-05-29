from pbtes.analysis.results_reader import load_results
df, _ = load_results('results/sd_v5_Series_direct_NaK_D7.0_H5.0_A1000_7d_20260528.csv')
print(df['TESmode'].value_counts())
s = df['solar_to_proc_kJ'].sum() + df['tes_to_proc_kJ'].sum()
t = s + df['aux_to_proc_kJ'].sum()
print(f'SF%: {s/t*100:.1f}')
print(f'to_tes GJ: {df["to_tes_kJ"].sum()/1e6:.1f}')
print(f'tes_to_proc GJ: {df["tes_to_proc_kJ"].sum()/1e6:.1f}')
