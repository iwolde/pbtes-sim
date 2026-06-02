import sys
import os
import time
import pandas as pd
import numpy as np

sys.path.append(r'c:\Users\iwold\OneDrive - Universidad Católica de Chile\Postdoc\Galvanizing solar PBTES\codigos')

from pbtes.config import baseline_config, zinc_pool_config
from pbtes.simulation.solver import Solver

tes_params, component_params, conexion_params = baseline_config()
zinc_params = zinc_pool_config()

# Override initial temperature of the tank to 540.0 °C
tes_params['Initial temperature'] = 540.0
# Set aperture to 1000.0 m2
component_params['ptc_A'] = 1000.0

print("Initializing solver with T_init = 540.0 °C...")
solver = Solver(
    tes_params=tes_params,
    component_params=component_params,
    conexion_params=conexion_params,
    HTF='INCOMP::NaK',
    system_mode='Full',
    topology='Parallel',
    tank_config='indirect',
    zinc_pool_params=zinc_params
)

print("Initializing design states...")
solver.initialize_modes()
solver.tes_params['Initial temperature'] = 540.0 # restore

print("Running 7-day transient simulation...")
t0 = time.time()
results = solver.run_quasi_steady_simulation(days_to_simulate=7, csv='TMY.csv')
elapsed = time.time() - t0
print(f"Simulation completed in {elapsed:.1f} seconds.")

df = pd.DataFrame(results)

# Analyze performance
total_steps = len(df)
failed_steps = df[df['iter_status'] == 'failed']
num_fails = len(failed_steps)
print(f"\nTimesteps simulated: {total_steps}")
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
print(f"\nEnergy breakdown (GJ):")
print(f"  Direct solar to process: {solar_to_proc_GJ:.3f} GJ")
print(f"  TES discharging to process: {tes_to_proc_GJ:.3f} GJ")
print(f"  Auxiliary heater: {aux_to_proc_GJ:.3f} GJ")
print(f"  Total charging to TES: {total_charge_GJ:.3f} GJ")

print(f"\nTES final temperature profile:")
print(f"  TES Top: {df['T_tes_top'].iloc[-1]:.2f} °C")
print(f"  TES Bottom: {df['T_tes_bottom'].iloc[-1]:.2f} °C")

# Check if there were any Mode 3 activations
m3_df = df[df['TESmode'] == 3]
if not m3_df.empty:
    print(f"\nMode 3 details (first 10 occurrences):")
    print(m3_df[['time', 'T_tes_top', 'T_tes_bottom', 'tes_to_proc_kJ', 'aux_to_proc_kJ', 'iter_status']].head(10))
