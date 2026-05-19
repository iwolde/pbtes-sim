# Technology Stack

## Languages & Runtime

- **Primary Language:** Python 3.9+
- **Runtime Environment:** Standard Python interpreter (tested on Windows)

## Core Dependencies

### Thermal Systems Modeling
| Package | Version | Purpose |
|---------|---------|---------|
| **TESPy** | Latest | Thermal Engineering Systems in Python - Component library for modeling solar thermal systems, heat exchangers, pumps, and thermodynamic cycles |
| **CoolProp** | Latest | Thermophysical properties library for working fluids (provides fluid property calculations) |

### Scientific Computing
| Package | Version | Purpose |
|---------|---------|---------|
| **NumPy** | Latest | Numerical computing - array operations, linear algebra, mathematical functions |
| **SciPy** | Latest | Scientific computing - optimization (brentq solver), interpolation (interp1d) |

### Data Handling
| Package | Version | Purpose |
|---------|---------|---------|
| **pandas** | Latest | Data manipulation and time-series analysis |

### Visualization
| Package | Version | Purpose |
|---------|---------|---------|
| **matplotlib** | Latest | Plotting library for 2D/3D graphics and visualizations |

### Progress Tracking
| Package | Version | Purpose |
|---------|---------|---------|
| **tqdm** | Latest | Progress bar for long-running simulations |

## Configuration & Metadata

- **JSON:** Native Python json module for simulation metadata serialization
- **CSV:** Native pandas CSV I/O for time-series data input/output
- **Data Files:**
  - TMY.csv - Typical Meteorological Year weather data (DNI, temperature)
  - Simulation results stored as CSV with embedded JSON metadata

## Project Structure

### Main Modules
`
codigos/
├── mainV5_5.py       # Main entry point and parameter configuration
├── coreV5_5.py        # Core simulation engine (2800 lines)
├── errors_analysis.py # Convergence analysis and physical anomaly detection
├── TMY.csv           # Weather data input
├── Try1/, Try2/, Try3/ # Development iterations
└── Old versions/     # Historical versions (v3.0 - v4.2)
`

### Core Classes
1. **Solver** - Orchestrates quasi-steady simulations
2. **SolarThermalSystem** - TESPy network builder with 6 operation modes
3. **ThermalEnergyStorage** - Packed-bed TES with 1D temperature profile
4. **Reporting** - Visualization and results export

## Heat Transfer Fluids (via CoolProp)

### Primary HTF (Solar Field)
- INCOMP::NaK - Sodium-Potassium eutectic (high temperature)
- Water - Water (backup)
- CO2 - Carbon dioxide (backup)

### TES HTF
- Air - Air as heat transfer fluid in storage

## Operating Modes

The system implements 6 distinct operation modes controlled by irradiance and TES state:
- Mode 1: High irradiance - PTC to process + TES charge
- Mode 2: Mid irradiance - PTC to process only
- Mode 3: Low irradiance - TES discharge to process
- Mode 4: Standby - No active charge/discharge
- Mode 5: Re-stratification - TES auxiliary charging
- Mode 6: Mid-high irradiance - PTC to TES only

## Unit Conventions

- **Temperature:** Celsius (C)
- **Pressure:** bar
- **Enthalpy:** kJ/kg
- **Energy:** kJ (step), GWh/MWh (cumulative)
- **Power:** W, kW
- **Mass flow:** kg/s
- **Time step:** 3600 seconds (1 hour)
