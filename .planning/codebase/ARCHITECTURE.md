# PBTES Solar Plant Codebase - Architecture

## Overview

This is a **quasi-steady simulation framework** for Parabolic Bowl Thermal Energy System (PBTES) design and analysis. The system models a concentrated solar power plant with thermal energy storage using a packed-bed sensible heat storage system.

## Architectural Pattern

### Design Pattern: **Hybrid Physics-Based + Engineering Tool Integration**

The architecture combines:
1. **Custom 1D thermal storage models** (TES packed bed) 
2. **TESPy (Thermal Engineering Systems in Python)** for steady-state process network modeling
3. **Iterative coupling** between TES and main cycle

## Layer Architecture

### Layer 1: Configuration and Entry (mainV5_*.py)
**Responsibility**: Parameter setup, simulation orchestration, analysis execution

Key parameters:
- tes_params: Thermal energy storage geometry and material properties
- component_params: Solar field and heat exchanger specifications  
- conexion_params: Operating conditions (temperatures, pressures, fluids)
- HTF: Heat transfer fluid selection (NaK, CO2, Water)

### Layer 2: Core Simulation Engine (coreV5_5.py)

#### 2.1 SolarThermalSystem Class
- Wraps TESPy Network for steady-state modeling
- Handles multiple network configurations (Modes 1-6)
- Components: Parabolic trough collector, heat exchangers, cycle closer

#### 2.2 ThermalEnergyStorage Class  
- 1D packed bed model with nodal discretization
- Eigenvalue-based transient solution using integral transform method
- Heat loss calculation with wall and insulation resistance
- State management (charge/discharge/standby)

#### 2.3 Solver Class
- Quasi-steady simulation driver
- Mode selection based on irradiance and TES state
- Iterative coupling between TES and main cycle
- Convergence checking with fallback strategies

### Layer 3: Analysis and Reporting

#### 3.1 Reporting Class
- Time-series visualization (colormaps, daily profiles)
- Cumulative energy analysis
- TES temperature profile plotting
- CSV I/O with metadata preservation

#### 3.2 errors_analysis Module
- Convergence failure analysis
- Physical anomaly detection (mass flow, energy, temperature)
- Statistical correlations with operating conditions

## Data Flow

### Quasi-Steady Simulation Loop

For each time step (hourly):
1. Load weather data (DNI, Tamb)
2. Determine operation mode (get_system_mode)
   - Mode 1: High irradiance, Solar + TES charge
   - Mode 2: Mid irradiance, Solar to process only
   - Mode 3: Low irradiance, TES discharge to process
   - Mode 4: Standby (no solar, no TES activity)
   - Mode 5: TES re-stratification (auxiliary)
   - Mode 6: High irradiance, Full TES charge
3. Set network configuration (set_operation_mode)
4. Iterative TES coupling (_iterate_tes_coupling)
   - Initialize TES inlet from current profile
   - For each iteration (max 20):
     - Solve TESPy network (attempt_to_solve)
     - Read TES inlet conditions from HX outlet
     - Update TES temperature profile (update_temperature_profile)
     - Apply heat loss (calc_heat_loss)
     - Check convergence (_check_tes_convergence)
     - Fallback to alternative mode if failed
   - Store final profile
5. Collect signals (_collect_step_signals)
6. Store results

### Key Data Structures

**TES Temperature Profile**:
- 20-node discretization along tank height
- Normalized coordinates x in [0, 1]
- Temperature values in degrees C

**Simulation Results** (per timestep):
- time: datetime
- E: float (Irradiance W/m2)
- Tamb: float (Ambient temperature degrees C)
- TES_profiles: list (Temperature profiles)
- TES_layout: str (charge/discharge/standby)
- TESmode: int (1-6 operation mode)
- tes_soc_kWh: float (State of charge)
- Energies (kJ): to_tes_kJ, tes_to_proc_kJ, solar_to_proc_kJ, aux_to_proc_kJ, ptc_total_kJ
- Temperatures (degrees C): T_ptc_out, T_tes_top, T_tes_bottom
- Mass flows (kg/s): mdot_ptc_kg_s, mdot_tes_charge_kg_s, mdot_tes_discharge_kg_s
- Convergence info: iter_status, attempt_count, network_converged

## Key Abstractions

### 1. TESPy Network Abstraction
The SolarThermalSystem class provides a clean interface to TESPys component-based modeling:
- Components: ParabolicTrough, SimpleHeatExchanger, HeatExchanger, CycleCloser, Splitter, Merge
- Connections: Labeled fluid streams with temperature, pressure, mass flow, enthalpy
- Modes: design (sizing) and offdesign (performance prediction)

### 2. TES State Machine
- STANDBY: No flow, heat loss only
- CHARGE: Hot fluid enters from top, heats storage
- DISCHARGE: Hot fluid extracted from top, cold enters from bottom
- RESTRATIFY: Auxiliary heating for temperature restoration

### 3. Mode Switching Logic
The get_mode() function implements decision logic based on:
- Current irradiance (E)
- TES temperature profile extremes (T_tes_top, T_tes_bottom)
- Process temperature requirements
- Previous mode (hysteresis prevention)

## Entry Points

### Primary Entry Point
python mainV5_5.py

Executes:
1. Design mode simulation
2. Offdesign mode initialization  
3. Full quasi-steady simulation (365 days)
4. Performance metrics computation
5. Result visualization and export

### Analysis Entry Point
python errors_analysis.py --in results_annual.csv --out ./analysis_out

### Direct API Usage
from coreV5_5 import Solver, Reporting

solver = Solver(tes_params, component_params, conexion_params, HTF)
solver.initialize_modes()
results = solver.run_quasi_steady_simulation(days_to_simulate=365)
metrics = solver.compute_performance_metrics()

report = Reporting()
report.plot_TES_profile_colormap(df_results)
report.save_simulation_to_csv(df_results, filepath='output.csv')

## Dependencies

| Package | Purpose |
|---------|---------|
| TESPy | Steady-state process modeling |
| CoolProp | Thermophysical property calculations |
| NumPy | Numerical computations |
| SciPy | Optimization, interpolation |
| Pandas | Data handling |
| Matplotlib | Visualization |
| tqdm | Progress tracking |

## Design Decisions and Constraints

1. Quasi-Steady Assumption: Each hour modeled as steady-state with TES transient
2. 1D TES Model: Temperature stratification only along height
3. Fixed Time Step: 1-hour discretization from weather data
4. Mode-Based Network Switching: Six discrete operating configurations
5. Iterative Convergence: TES outlet temperature iterated until less than 5 percent change over 3 iterations
