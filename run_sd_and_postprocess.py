"""
Resumes the yearly simulation task by running the Series/Direct (SD) simulation
and then running the post-processing script on both PI and SD outputs.
"""
import os
import sys
import time
import glob

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_simulation import run_single_simulation
from scripts.run_postprocess import process_file

def main():
    print("======================================================================")
    print("RESUMING YEARLY SIMULATION COMPARISON (Running SD and post-processing)")
    print("======================================================================")
    
    # 1. Run Series / Direct Layout (SD)
    print("\nRunning SD Layout Simulation (Series/Direct)...")
    start_sd = time.time()
    sd_df, sd_filename, sd_meta = run_single_simulation(
        days=365,
        topology='Series',
        tank_config='direct',
        htf='INCOMP::NaK',
        tag='SD_yearly_2000m2',
        aperture=2000.0
    )
    sd_elapsed = time.time() - start_sd
    print(f"SD Simulation completed in {sd_elapsed/60.0:.2f} minutes.")
    print("======================================================================")
    
    # 2. Find PI filename from results dir
    pi_files = glob.glob("results/PI_yearly_2000m2_Parallel_indirect_NaK_D7.0_H5.0_A2000_365d_*.csv")
    pi_files = [f for f in pi_files if '_processed' not in f]
    if not pi_files:
        print("Error: Could not find PI simulation output CSV!")
        return
    pi_filename = pi_files[0]
    print(f"Found PI results file: {pi_filename}")
    
    # 3. Post-process both result files
    print("\nPost-processing PI results...")
    process_file(pi_filename)
    
    print("\nPost-processing SD results...")
    process_file(sd_filename)
    
    print("\n======================================================================")
    print("RESUMPTION TASK COMPLETED!")
    print("======================================================================")

if __name__ == '__main__':
    main()
