# PBTES — Packed Bed Thermal Energy Storage for Solar Galvanizing

Simulation framework for a solar thermal plant with Packed Bed Thermal Energy Storage (PBTES) providing industrial process heat to a zinc galvanizing facility.

## Overview

- **Solar field**: Parabolic Trough Collectors (PTC)
- **Storage**: 1D packed bed thermocline (Schumann model)
- **Process**: Dynamic zinc galvanizing bath (lumped capacitance)
- **Solver**: Quasi-steady coupling via TESPy thermodynamic networks
- **Modes**: 6 operating modes (charge, discharge, simultaneous, bypass, auxiliary)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Run a simulation
```bash
# 7-day test run (default)
python run_simulation.py

# Full year simulation
python run_simulation.py --days 365

# With specific configuration
python run_simulation.py --days 365 --topology Series --tank_config direct --tag baseline_series
```

### Run parametric sweep
```bash
python run_parametric.py --sweep aperture
python run_parametric.py --sweep tes_volume
python run_parametric.py --sweep full
```

### Run tests
```bash
python -m pytest tests/ -x --tb=short
```

## Project Structure

```
pbtes/                   Main package
├── config.py            Single source of truth for parameters
├── components/          PTC field model
├── storage/             Packed bed TES + zinc pool models
├── network/             TESPy network builder (6 modes)
├── simulation/          Quasi-steady solver
├── reporting/           Plots and CSV I/O
└── analysis/            Post-processing, economics, convergence

run_simulation.py        Single simulation entry point
run_parametric.py        Parametric sweep entry point
scripts/                 Assessment pipeline (figures, synthesis)
tests/                   Pytest test suite
results/                 Simulation output CSVs
```

## Configuration

All parameters are centralized in `pbtes/config.py`. Use `baseline_config()` for default parameter dictionaries.

## Key Decisions

- **HTF**: NaK (INCOMP::NaK via CoolProp) — primary; Air — comparison
- **Zinc pool**: Always enabled for production (dynamic galvanizing demand); fixed-demand mode available for testing
- **Pump power**: Post-processed from quasi-steady results (Ergun equation)
- **PBTES model**: Validated from prior publication
- **Topologies**: 2x2 matrix — Parallel/Series x Direct/Indirect
- **Operating modes**: 6 modes (see `.planning/PLANT_LAYOUTS_AND_MODES.md` for the authoritative reference)

## Documentation

| Document | Purpose |
|----------|---------|
| `AGENTS.md` | Agent workflow rules, conventions, operating modes reference |
| `TODO.md` | Current task list — what needs to be done |
| `.planning/PLANT_LAYOUTS_AND_MODES.md` | Ground truth for operating modes and plant layouts |
| `insumos paper/PROJECT_CONTEXT.md` | Full project reference (parameters, results format) |
| `insumos paper/zinc_pool_model_methodology.md` | Zinc pool physics and coupling |
