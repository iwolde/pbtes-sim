# External Integrations

## Data Input Sources

### Weather Data (CSV)
| File | Columns | Purpose |
|------|---------|---------|
| TMY.csv | Fecha/Hora (datetime), dni (irradiance), 	emp (ambient temp) | Typical Meteorological Year data for simulation |

- **Format:** CSV with Spanish column names
- **Year normalization:** All timestamps normalized to 2022
- **Usage:** Loaded via Solver.load_data() method

### Fluid Property Data (via CoolProp)
| Fluid ID | Type | Application |
|----------|------|-------------|
| INCOMP::NaK | Incompressible fluid | Primary HTF in parabolic trough |
| Air | Ideal gas | TES heat transfer fluid |
| Water | Pure fluid | Backup HTF |
| CO2 | Pure fluid | Backup working fluid |

## Simulation Outputs

### CSV Export with Embedded Metadata
- **Format:** Custom CSV with __meta__ header row containing JSON
- **Metadata includes:**
  - System mode (Full, No TES, No solar)
  - HTF selection
  - TES parameters (tank dimensions, material properties)
  - Component parameters (efficiencies, collector specs)
  - Connection parameters (temperatures, pressures)
  - Simulation arguments (days, CSV source)

### Analysis Outputs
| Output Directory | Contents |
|-----------------|----------|
| nalysis_out/ | Convergence analysis, error rates, physical anomaly detection |

### Analysis Files Generated
- summary_overall.csv - Global error statistics
- ate_by_*.csv/png - Error rates by hour, mode, layout
- heatmap_hour_vs_*.csv/png - Heatmaps of error rates
- 	op_windows_6h.csv - Problematic time windows
- error_events.csv - Detailed error records
- correlations_error_vs_features.csv - Statistical correlations
- phys_flags.csv - Physical anomaly flags
- phys_anomalies_events.csv - Physical anomaly records
- meta.json - Simulation metadata

## Physics Calculations

### CoolProp Property Lookup
Used for computing thermophysical properties:
- D - Density (kg/m3)
- C - Specific heat capacity (J/kg K)
- L - Thermal conductivity (W/m K)
- V - Dynamic viscosity (Pa s)

### SciPy Numerical Methods
- scipy.optimize.brentq - Root finding for transcendental eigenvalue equation
- scipy.interpolate.interp1d - Interpolation for temperature profiles

## No External API Integrations

This codebase operates **offline** with:
- No cloud services
- No external REST APIs
- No webhooks
- No authentication providers
- No database connections

## File I/O Patterns

### Input Files
`
TMY.csv           # Weather data (user-provided)
`

### Output Files
`
test3.csv, test4.csv, testx.csv   # Simulation results (user-defined names)
Result_HTF[*]_diam[*].csv         # Parametric sweep results
base_design_[1-6]                 # TESPy design point files (binary)
`

## TESPy Component Library

Internal integration with TESPy components:
- 	espy.networks - Network container and solver
- 	espy.connections - Connection management
- 	espy.components - Physical components (heat exchangers, sources, sinks, etc.)
- 	espy.components.heat_exchangers.parabolic_trough.ParabolicTrough - Solar collector model

## Internal Coupling

### TESPy-TES Coupling
- TESPy network solves main cycle (PTC, HX, process)
- Custom Python TES model interfaces via temperature/mass flow boundaries
- Iterative coupling until convergence (max 20 iterations)
- Fallback modes when convergence fails

### State Management
- System state tracked via SolarThermalSystem and ThermalEnergyStorage classes
- No persistent database; all state in memory during simulation
