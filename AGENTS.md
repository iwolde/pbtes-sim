# Agent Instructions — PBTES Simulation Codebase

## 1. Project Overview

Solar thermal plant with **Packed Bed Thermal Energy Storage (PBTES)** for
industrial process heat (zinc galvanizing). Uses TESPy for thermodynamic
network solving and a 1D Schumann model for the packed bed.

### Key Decisions (settled — do not change without user approval)

- **HTF**: NaK (`INCOMP::NaK` in CoolProp). Air used as comparison case.
- **Zinc pool**: Always ON. Every simulation uses the dynamic galvanizing model.
- **Pump power**: Post-processed from quasi-steady results (Ergun equation). NOT computed inline in the solver.
- **PBTES model**: Pre-validated from a prior publication. No re-validation needed.
- **Topologies**: Compare Parallel vs Series, Direct vs Indirect (2×2 matrix).
- **Plant**: Hypothetical reference design (not based on a real facility).
- **Target journals**: Journal of Energy Storage, Energy, Solar Energy (Q1).

## 2. Codebase Structure

```
codigos/
├── AGENTS.md                    ← THIS FILE — read first
├── README.md                    ← project overview + quick start
├── requirements.txt             ← pinned dependencies
├── TMY.csv                      ← weather data (Fecha/Hora, dni, temp)
├── coreV5.py                    ← backward-compat re-export shim
│
├── run_simulation.py            ← THE single simulation entry point
├── run_parametric.py            ← THE single parametric sweep entry point
│
├── pbtes/                        ← main package
│   ├── __init__.py               ← re-exports: Solver, Reporting, etc.
│   ├── config.py                 ← single source of truth for ALL parameters
│   ├── components/
│   │   └── ptc_field.py          ← PTCField (TESPy component extension)
│   ├── storage/
│   │   ├── packed_bed.py         ← ThermalEnergyStorage (1D Schumann)
│   │   └── zinc_pool.py          ← ZincPool (galvanizing process model)
│   ├── network/
│   │   └── system.py             ← SolarThermalSystem (6-mode network builder)
│   ├── simulation/
│   │   └── solver.py             ← Solver (quasi-steady orchestrator)
│   ├── reporting/
│   │   └── plots.py              ← Reporting (plots, CSV I/O)
│   ├── analysis/
│   │   ├── economics.py          ← LCOH calculator
│   │   ├── postprocess.py        ← pump power, net solar fraction
│   │   ├── convergence.py        ← error rate tables, anomaly detection
│   │   └── results_reader.py     ← load results CSVs
│   └── utils/
│
├── scripts/                      ← post-processing pipeline
│   ├── run_postprocess.py        ← pump power + LCOH from results CSV
│   ├── run_assessment_05_analysis.py
│   ├── run_assessment_06_figures.py
│   ├── run_assessment_07_synthesis.py
│   └── run_transition_matrix.py
│
├── tests/                        ← pytest suite
│   ├── conftest.py               ← shared fixtures
│   ├── test_physics.py
│   ├── test_modes.py
│   ├── test_networks.py
│   ├── test_topology.py
│   ├── test_offdesign.py
│   ├── test_transitions.py
│   └── test_zinc_pool.py
│
├── results/                      ← simulation output CSVs (gitignored)
├── .tespy_cache/                 ← TESPy design states (gitignored)
├── article_results/              ← post-processed output (gitignored)
└── .planning/                    ← project management docs
```

### Dependency graph

```
Solver (simulation/solver.py)
  ├── SolarThermalSystem (network/system.py)
  │     └── PTCField (components/ptc_field.py)
  ├── ThermalEnergyStorage (storage/packed_bed.py)
  └── ZincPool (storage/zinc_pool.py)
```

## 3. Simulation Scripts

There are exactly **two** simulation entry points:

### `run_simulation.py` — single simulation
```bash
python run_simulation.py                            # 7-day test
python run_simulation.py --days 365                 # full year
python run_simulation.py --days 365 --topology Series --tank_config direct
python run_simulation.py --days 365 --tag baseline
```

### `run_parametric.py` — parametric sweep
```bash
python run_parametric.py --sweep aperture           # aperture area
python run_parametric.py --sweep tes_volume          # tank D×H grid
python run_parametric.py --sweep topology            # all 4 topology combos
python run_parametric.py --sweep full                # everything
```

Both scripts:
- Use `baseline_config()` from `pbtes/config.py` as defaults
- Accept CLI flags for overrides
- Always use the zinc pool (no option to disable)
- Save results to `results/` with descriptive filenames
- Print monthly breakdown for runs ≥ 30 days

## 4. Results Storage Protocol

### File naming
```
results/{tag}_{topology}_{tank_config}_{htf}_{dimensions}_{days}d_{date}.csv
```
Example: `baseline_Parallel_indirect_NaK_D7.0_H5.0_A1000_365d_20260520.csv`

### CSV format
- Line 1: `# __meta__ = {JSON}` with all simulation parameters
- Remaining lines: standard CSV with one row per timestep
- Required columns: time, E, Tamb, TESmode, TES_layout, iter_status,
  T_ptc_out, T_tes_top, T_tes_bottom, tes_soc_kWh, mdot_ptc_kg_s,
  to_tes_kJ, tes_to_proc_kJ, solar_to_proc_kJ, aux_to_proc_kJ,
  T_zinc, Q_zinc_hx_kW, zinc_operating

### Reading results
```python
from pbtes.analysis.results_reader import load_results
df, meta = load_results('results/baseline_Parallel_indirect_NaK_....csv')
```

## 5. Design State Cache

TESPy design-point states are saved to `.tespy_cache/` (NOT the project root).
These directories (`base_design_1/`, `base_design_2/`, etc.) are auto-generated
by `Solver.initialize_modes()` and gitignored. They are safe to delete — they
will be regenerated on the next run.

**Never commit base_design directories.** If you see `base_design_*` in the
project root, move them to `.tespy_cache/` or delete them.

## 6. Git Workflow

### Absolute Rules

1. **NEVER commit to `main` directly.** Work on branches.
2. **Branch naming:** `feature/<what>`, `fix/<what>`, `refactor/<what>`
3. **Run tests before committing:** `python -m pytest tests/ -x --tb=short`
4. **Commit atomically.** One logical change = one commit.
5. **Message format:** `<type>: <short description>`
   Types: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`

### Commands

| Action | Command |
|--------|---------|
| Create branch | `git checkout -b <name>` |
| See current branch | `git branch` |
| Stage all changes | `git add -A` |
| Commit | `git commit -m "type: message"` |
| Push | `git push` |
| See history | `git log --oneline -10` |

## 7. Parallel Agent Rules

1. **Each agent owns its file(s).** Two agents MUST NOT edit the same file.
2. **Agents work on separate branches.** Merge to main sequentially.
3. **Before starting**: read this file (AGENTS.md) and `.planning/STATE.md`.
4. **Conflict resolution**: if work overlaps, the second agent merges main
   into their branch first, resolves conflicts, then merges back.

### File ownership (max 1 agent per file at a time)

| File | Notes |
|------|-------|
| `pbtes/config.py` | Central config — coordinate changes |
| `pbtes/storage/packed_bed.py` | Independent |
| `pbtes/storage/zinc_pool.py` | Independent |
| `pbtes/components/ptc_field.py` | Independent |
| `pbtes/network/system.py` | Depends on ptc_field |
| `pbtes/simulation/solver.py` | Depends on network + storage |
| `pbtes/reporting/plots.py` | Independent |
| `pbtes/analysis/*` | 1 agent per file |
| `run_simulation.py` | Independent |
| `run_parametric.py` | Independent |
| `tests/*` | 1 agent per test file |

## 8. Testing

```bash
python -m pytest tests/ -x --tb=short    # before every commit
python -m pytest tests/test_physics.py -v # single file
```

### Conventions
- Files in `tests/`, named `test_<what>.py`
- Use pytest fixtures (see `conftest.py`), no unittest.TestCase
- Mock TESPy networks for unit tests (they're slow)
- Shared fixtures in `tests/conftest.py` using `baseline_config()`

## 9. Coding Conventions

### Imports
```python
from pbtes import Solver                    # preferred
from pbtes.config import baseline_config    # for parameters
```

### Naming
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE`
- Private: `_prefix`

### Docstrings
- Every class and public method
- Google-style or numpy-style
- Type hints on new code

## 10. Operating Modes

| Mode | Description | Solar | TES | Aux |
|------|-------------|-------|-----|-----|
| 1 | Solar charges TES | ✓ charge | ← | – |
| 2 | Solar to process + TES discharge | ✓ process | discharge → | – |
| 3 | Solar to process only | ✓ process | standby | – |
| 4 | TES discharge to process only | – | discharge → | – |
| 5 | Auxiliary heater only | – | standby | ✓ |
| 6 | Solar charges TES + serves process | ✓ both | ← charge | – |

## 11. Energy Conventions

| Key | Description |
|-----|-------------|
| `to_tes_kJ` | Energy sent TO the TES (charging) |
| `tes_to_proc_kJ` | Energy from TES TO process (discharging) |
| `aux_to_proc_kJ` | Auxiliary heater energy to process |
| `solar_to_proc_kJ` | Direct solar to process (not via TES) |
| `ptc_total_kJ` | Total PTC energy output |

### Monthly breakdown protocol

When running simulations ≥ 30 days, ALWAYS print a monthly breakdown:

```
Month | SF% | DNI_avg | DNI_max | T_top_avg | T_top_max | T_bot_avg | T_bot_min | Q_charge_GJ | Q_discharge_GJ | Q_aux_GJ | Mode top 3
```

### Weather data
- Source: `TMY.csv` with columns: `Fecha/Hora`, `dni`, `temp`
- Timezone: UTC, no DST adjustment

## 12. Quick Reference

```bash
# Run tests
python -m pytest tests/ -x --tb=short

# Run 7-day test simulation
python run_simulation.py

# Run full-year simulation
python run_simulation.py --days 365 --tag baseline

# Run parametric sweep
python run_parametric.py --sweep full

# Post-process results (pump power + LCOH)
python scripts/run_postprocess.py results/baseline_*.csv

# Generate figures
python scripts/run_assessment_06_figures.py

# Git workflow
git checkout -b feature/my-feature
git add -A
git commit -m "feat: description"
git push
```
