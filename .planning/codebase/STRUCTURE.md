# PBTES Solar Plant Codebase - Structure

## Root Directory Layout

`
codigos/                          # Project root
|
+-- .planning/                    # Planning and documentation
|   +-- codebase/                 # Codebase documentation
|       +-- ARCHITECTURE.md       # System architecture
|       +-- STRUCTURE.md          # This file
|
+-- .opencode/                    # IDE/agent configuration
|   +-- agents/                   # Agent definitions
|   +-- command/                  # Command definitions
|
+-- coreV5_*.py                  # Core simulation engine (versions)
+-- mainV5_*.py                  # Entry points / drivers
+-- errors_analysis.py            # Post-simulation analysis
|
+-- base_design_*/                # TESPy design case outputs
+-- analysis_out/                # Error analysis results
+-- report/                      # Report generation
|
+-- Try*/                         # Experimental variants
+-- Old versions/                # Historical versions (v3.x, v4.x)
|
+-- *.csv                        # Data files (TMY, results)
+-- plant_layout.drawio           # Process flow diagram
`

## Directory Purposes

### .planning/codebase/
**Purpose**: Architecture and structure documentation for codebase understanding

### coreV5_*.py Files
**Purpose**: Core simulation engine containing the main classes

| File | Description |
|------|-------------|
| coreV5_5.py | Latest (v5.5) - Full implementation with all 6 modes |
| coreV5_4.py | Previous version - Mode 3 fixes |
| coreV5_3.py | Earlier version - Mode handling |
| coreV5_2.py | Earlier version |
| coreV5_.py  | Original v5 version |

### mainV5_*.py Files  
**Purpose**: Entry points that configure and run simulations

| File | Description |
|------|-------------|
| mainV5_5.py | Current main driver - Full workflow |
| mainV5_4.py | Earlier version |
| mainV5_3.py | Earlier version |
| mainV5_2.py | Earlier version |

### Try*/ Directories
**Purpose**: Experimental workspace variants
- Each contains copies of coreV5_5.py and mainV5_5.py
- Used for parallel experiments with different parameters
- Contains own base_design_* folders and TMY.csv

### Old versions/
**Purpose**: Historical version archive for reference

### base_design_*/
**Purpose**: TESPy design case outputs (JSON)
- base_design_1 through base_design_6
- Store steady-state solution for each operating mode
- Used as starting point for offdesign calculations

### analysis_out/
**Purpose**: Error analysis and statistics output

| File Type | Description |
|-----------|-------------|
| rate_by_*.csv/png | Error rates by hour, mode, layout, irradiance |
| heatmap_hour_vs_*.csv/png | 2D error distributions |
| phys_*.csv/png | Physical anomaly detection results |
| error_events.csv | Detailed failure events |
| correlations_error_vs_features.csv | Statistical correlations |
| summary_overall.csv | Global statistics |
| top_windows_6h.csv | Problematic time windows |

### report/
**Purpose**: Report generation
- report.tex: LaTeX report template
- figures/: Generated visualization images

## Key File Locations

### Core Engine
- **Primary**: coreV5_5.py (2800 lines)
- **Entry Point**: mainV5_5.py (239 lines)

### Analysis Tools
- **Error Analysis**: errors_analysis.py (732 lines)

### Data Files
- **Weather Data**: TMY.csv (Typical Meteorological Year)
- **Results**: 
esults_annual.csv, 	est*.csv
- **Parametric Studies**: Result_HTF[*.csv

### Configuration
- **Process Diagram**: plant_layout.drawio

## Naming Conventions

### Python Files
| Pattern | Example | Meaning |
|---------|---------|---------|
| coreV*_*.py | coreV5_5.py | Core engine, major.minor version |
| mainV*_*.py | mainV5_5.py | Entry point, matching core version |
| errors_analysis.py | - | Standalone analysis tool |

### Directories
| Pattern | Example | Meaning |
|---------|---------|---------|
| base_design_* | base_design_1 | TESPy design case for mode N |
| Try* | Try1, Try2 | Experimental workspaces |
| Old versions/ | - | Archived versions |

### Variables (coreV5_5.py)
| Pattern | Example | Meaning |
|---------|---------|---------|
| conn_* | conn_01, conn_02 | TESPy connections |
| tes_params | tes_params['Tank diameter'] | TES configuration dict |
| component_params | component_params['ptc_A'] | Component specifications |
| conexion_params | conexion_params['5_T'] | Connection boundary conditions |
| *_hx | process_hx, charge_tes_hx | Heat exchanger components |
| mdot_*_kg_s | mdot_ptc_kg_s | Mass flow rates |
| T_* | T_ptc_out, T_tes_top | Temperatures |
| *_kJ | to_tes_kJ, ptc_total_kJ | Energy quantities |
| *_kWh | tes_soc_kWh | Energy storage |
| TES_* | TESmode, TES_layout | TES operation state |

### TESPy Components
| Label | Component Type | Purpose |
|-------|----------------|---------|
| PTCField | ParabolicTrough | Solar collector |
| Process_HX | SimpleHeatExchanger | Process heat delivery |
| Preheater_HX | SimpleHeatExchanger | Preheat stage |
| Charge_TES_HX | HeatExchanger | TES charging |
| Discharge_TES_HX | HeatExchanger | TES discharging |
| CycleCloser | CycleCloser | Cycle boundary |
| Splitter1 | Splitter | Flow splitting |
| Merge2 | Merge | Flow merging |

### Connection Labels
| Label | Path | Description |
|-------|------|-------------|
| 01_CC_PTC | CycleCloser to PTC | Hot stream to solar field |
| 02_PTC_* | PTC to next | Heated fluid |
| 04_* | Various | Intermediate streams |
| 05_PH_PR | Preheater to Process | Process inlet |
| 06_PR_CC | Process to CycleCloser | Return stream |
| 09_SP1_CHX | Splitter to Charge HX | TES charging branch |
| 10_CHX_MG2 | Charge HX to Merge | TES return |
| 13_CHSC_CHX | Source to Charge HX | TES HTF inlet |
| 14_CHX_CHSK | Charge HX to Sink | TES HTF outlet |

## Code Organization (coreV5_5.py)

### Class Order (2800 lines total)

1. **PTCField** (lines ~30-88)
   - Subclass of TESPy ParabolicTrough
   - Multi-row scaling

2. **ThermalEnergyStorage** (lines ~89-458)
   - TES state machine
   - 1D transient model
   - Heat loss calculation

3. **SolarThermalSystem** (lines ~459-1240)
   - TESPy network wrapper
   - create_network1-6 methods
   - set_operation_mode

4. **Solver** (lines ~1262-2207)
   - Main simulation driver
   - Mode selection
   - Iteration management

5. **Reporting** (lines ~2207-2800)
   - Visualization
   - CSV I/O

## Dependencies Graph

`
mainV5_5.py
    |
    +-- coreV5_5 (Solver, Reporting)
    |       |
    |       +-- TESPy (tespy.networks, components, connections)
    |       +-- CoolProp (thermo properties)
    |       +-- NumPy, SciPy, Pandas, Matplotlib
    |
    +-- Pandas (results handling)

errors_analysis.py
    |
    +-- Pandas, NumPy, Matplotlib, SciPy
`

## Key Locations Quick Reference

| Purpose | Location |
|---------|----------|
| Latest core engine | coreV5_5.py |
| Main entry point | mainV5_5.py |
| TES model | coreV5_5.py:ThermalEnergyStorage class |
| TESPy networks | coreV5_5.py:SolarThermalSystem class |
| Simulation driver | coreV5_5.py:Solver class |
| Visualization | coreV5_5.py:Reporting class |
| Error analysis | errors_analysis.py |
| Weather data | TMY.csv |
| Design cases | base_design_1/ through base_design_6/ |
| Results | test*.csv, results_annual.csv |
| Analysis output | analysis_out/ |
