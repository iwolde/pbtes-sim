import os
import sys
import pandas as pd

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pbtes.analysis.results_reader import load_results

def analyze_file(name, filepath):
    print(f"\n==================================================")
    print(f"ANALYZING CONVERGENCE FOR: {name}")
    print(f"File: {filepath}")
    print(f"==================================================")
    
    try:
        df, meta = load_results(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return
        
    total_steps = len(df)
    if 'iter_status' in df.columns:
        converged_steps = (df['iter_status'] == 'converged').sum()
        failed_steps = (df['iter_status'] == 'failed').sum()
        conv_rate = (converged_steps / total_steps) * 100
        print(f"Total timesteps:   {total_steps}")
        print(f"Converged steps:   {converged_steps} ({conv_rate:.2f}%)")
        print(f"Failed steps:      {failed_steps} ({100 - conv_rate:.2f}%)")
    else:
        print("iter_status column not found in results!")
        
    if 'TESmode' in df.columns:
        print("\nMode distribution:")
        mode_counts = df['TESmode'].value_counts()
        for mode, count in mode_counts.items():
            print(f"  Mode {mode}: {count} hours ({count/total_steps*100:.1f}%)")
            
    # Calculate energy sums
    to_tes_MWh = df['to_tes_kJ'].sum() / 3.6e6
    tes_to_proc_MWh = df['tes_to_proc_kJ'].sum() / 3.6e6
    solar_to_proc_MWh = df['solar_to_proc_kJ'].sum() / 3.6e6
    aux_to_proc_MWh = df['aux_to_proc_kJ'].sum() / 3.6e6
    aux_tes_MWh = df.get('aux_tes_energy_kJ', pd.Series([0]*len(df))).sum() / 3.6e6
    
    total_demand_MWh = solar_to_proc_MWh + tes_to_proc_MWh + aux_to_proc_MWh + aux_tes_MWh
    sf_calc = (solar_to_proc_MWh + tes_to_proc_MWh) / (solar_to_proc_MWh + tes_to_proc_MWh + aux_to_proc_MWh + aux_tes_MWh) * 100
    
    print("\nEnergy Balance (MWh):")
    print(f"  Energy to TES:        {to_tes_MWh:.2f} MWh")
    print(f"  Energy from TES:      {tes_to_proc_MWh:.2f} MWh")
    print(f"  Direct solar to proc: {solar_to_proc_MWh:.2f} MWh")
    print(f"  Aux heater to proc:   {aux_to_proc_MWh:.2f} MWh")
    print(f"  Tank aux heater (w):  {aux_tes_MWh:.2f} MWh")
    print(f"  Total Heat Demand:    {total_demand_MWh:.2f} MWh")
    print(f"  Calculated Solar Frac: {sf_calc:.2f}%")
    
    if 'W_pump_kW' in df.columns:
        total_pump_MWh = df['W_pump_kW'].sum() / 1000.0
        print(f"  Pumping electricity:  {total_pump_MWh:.2f} MWh")
        
def main():
    import glob
    pi_files = glob.glob("results/PI_yearly_2000m2_Parallel_indirect_NaK_D7.0_H5.0_A2000_365d_*_processed.csv")
    sd_files = glob.glob("results/SD_yearly_2000m2_Series_direct_NaK_D7.0_H5.0_A2000_365d_*_processed.csv")
    
    if pi_files:
        analyze_file("Parallel / Indirect (PI)", pi_files[0])
    else:
        print("PI processed file not found.")
        
    if sd_files:
        analyze_file("Series / Direct (SD)", sd_files[0])
    else:
        print("SD processed file not found.")

if __name__ == '__main__':
    main()
