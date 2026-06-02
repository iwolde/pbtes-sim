"""
Orchestrate sequential 365-day simulations of the Parallel/Indirect (PI) and Series/Direct (SD) configurations 
with a total PTC aperture area of 2000 m².

Post-processes both files to compute pump power and net/thermal solar fractions.
"""
import os
import sys
import time

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_simulation import run_single_simulation
from scripts.run_postprocess import process_file

def main():
    print("======================================================================")
    print("STARTING PBTES YEARLY COMPARISON SIMULATION (A = 2000 m²)")
    print("======================================================================")
    
    # 1. Run Parallel / Indirect Layout (PI)
    print("\n[1/4] Running PI Layout Simulation (Parallel/Indirect)...")
    start_pi = time.time()
    pi_df, pi_filename, pi_meta = run_single_simulation(
        days=365,
        topology='Parallel',
        tank_config='indirect',
        htf='INCOMP::NaK',
        tag='PI_yearly_2000m2',
        aperture=2000.0
    )
    pi_elapsed = time.time() - start_pi
    print(f"PI Simulation completed in {pi_elapsed/60.0:.2f} minutes.")
    
    # 2. Run Series / Direct Layout (SD)
    print("\n[2/4] Running SD Layout Simulation (Series/Direct)...")
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
    
    # 3. Post-process PI results
    print("\n[3/4] Post-processing PI results (pump power and summary metrics)...")
    process_file(pi_filename)
    
    # 4. Post-process SD results
    print("\n[4/4] Post-processing SD results (pump power and summary metrics)...")
    process_file(sd_filename)
    
    print("\n======================================================================")
    print("YEARLY SIMULATIONS AND POST-PROCESSING COMPLETED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == '__main__':
    main()
