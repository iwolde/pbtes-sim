# Agent Instructions — PBTES Simulation Codebase

## 1. Codebase Architecture

This project simulates a solar thermal plant with Packed Bed Thermal Energy Storage
(PBTES) for industrial process heat (zinc galvanizing). It uses the TESPy library
for thermodynamic network solving.

### Current structure (monolithic → modularizing)

```
codigos/
├── coreV5.py          ← 3008-line monolith. DO NOT ADD TO IT.
│                        Contains classes: PTCField, ThermalEnergyStorage,
│                        ZincPool, SolarThermalSystem, Solver, Reporting.
│
├── sim_year.py        ← 365-day simulation entry point
├── sim_week.py        ← weekly simulation
├── sim_zinc.py        ← simulation with zinc pool process model
├── sim_archive.py     ← archive/legacy simulation runner
├── tests/             ← pytest test suite
├── scripts/           ← assessment/analysis pipeline scripts
├── economics.py       ← LCOH calculator (standalone)
├── errors_analysis.py ← convergence analytics (standalone)
├── TMY.csv            ← Typical Meteorological Year weather data
│   Columns: Fecha/Hora, dni, temp
└── base_design_*/     ← TESPy auto-saved design states (gitignored)
```

### Current modular structure (EXTRACTED — May 2026)

```
codigos/
├── coreV5.py                ← 38-line re-export shim (backward compatible)
│
├── pbtes/                    ← main package
│   ├── __init__.py           ← Public API: Solver, Reporting, etc.
│   ├── components/
│   │   ├── __init__.py
│   │   └── ptc_field.py      ← PTCField (TESPy component extension)
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── packed_bed.py     ← ThermalEnergyStorage (1D Schumann model)
│   │   └── zinc_pool.py      ← ZincPool (galvanizing process model)
│   ├── network/
│   │   ├── __init__.py
│   │   └── system.py         ← SolarThermalSystem (6-mode network builder)
│   ├── simulation/
│   │   ├── __init__.py
│   │   └── solver.py         ← Solver (quasi-steady orchestrator)
│   ├── reporting/
│   │   ├── __init__.py
│   │   └── plots.py          ← Reporting (plots, CSV I/O)
│   ├── analysis/             ← future: convergence.py, economics.py
│   └── utils/                ← future: shared helpers
│
├── sim_year.py, sim_week.py, sim_zinc.py, sim_archive.py
├── main.py                   ← parametric sweeps
├── economics.py, errors_analysis.py
├── scripts/                  ← assessment pipeline
└── tests/                    ← unit/integration tests
```

### Dependency graph (bottom-up)

```
                   ┌────────────────────┐
                   │    Solver          │  (orchestrates everything)
                   │ simulation/solver  │
                   └───────┬────────────┘
          ┌────────────────┼──────────────────┐
          │                │                   │
    ┌─────▼──────┐  ┌──────▼───────┐  ┌───────▼──────────┐
    │SolarThermal │  │ThermalEnergy │  │ZincPool          │
    │System       │  │Storage       │  │storage/zinc_pool │
    │network/sys  │  │storage/pb    │  └──────────────────┘
    └─────┬───────┘  └──────────────┘
          │
    ┌─────▼──────┐
    │ PTCField   │
    │components/ │
    └────────────┘
```

## 2. Git Workflow Rules

### ABSOLUTE RULES — agents MUST follow these

1. **NEVER commit to `main` directly.** All work happens on branches.
2. **Every change starts with `git checkout -b <descriptive-name>`.**
   - Branch naming: `feature/<what>`, `fix/<what>`, `refactor/<what>`
   - Example: `refactor/extract-thermal-storage`, `fix/tes-coupling-onvergence`
3. **Run tests BEFORE committing.** At minimum: `python -m pytest tests/ -x`
4. **Commit atomically.** One logical change = one commit.
5. **Commit message format:** `<type>: <short description>`
   - Types: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`

### Safe experimentation (for the user)

```bash
# Before any risky change:
git checkout -b experiment/my-idea

# If it works:
git checkout main
git merge experiment/my-idea

# If it breaks:
git checkout main
git branch -D experiment/my-idea   # delete the broken branch
```

**You can never permanently break anything.** `main` always holds the last
known-good state. Any branch can be deleted with no impact on `main`.

### Git commands reference

| Action | Command |
|--------|---------|
| Create branch | `git checkout -b <name>` |
| See current branch | `git branch` |
| Switch branch | `git checkout <name>` |
| See what changed | `git status`, `git diff` |
| Stage all changes | `git add -A` |
| Commit staged | `git commit -m "type: message"` |
| Push to GitHub | `git push` |
| Pull from GitHub | `git pull` |
| See history | `git log --oneline -10` |

## 3. Parallel Agent Work Rules

When multiple agents work simultaneously:

1. **Each agent owns its file(s).** Two agents MUST NOT edit the same file.
   See the file ownership map below.
2. **Agents work on separate branches.** Merge sequentially.
3. **If work overlaps**, the second agent merges `main` into their branch first
   (`git checkout my-branch; git merge main`), resolves conflicts, then merges
   back.

### File ownership map for modularization

| File to modify | Max 1 agent at a time | Notes |
|---|---|---|
| `coreV5.py` (extracting from) | Yes — read-only by all but one | Extract one class at a time |
| `pbtes/storage/packed_bed.py` | 1 agent | Independent module |
| `pbtes/storage/zinc_pool.py` | 1 agent | Independent module |
| `pbtes/components/ptc_field.py` | 1 agent | Independent module |
| `pbtes/network/system.py` | 1 agent | Depends on ptc_field |
| `pbtes/simulation/solver.py` | 1 agent | Depends on network + storage |
| `pbtes/reporting/plots.py` | 1 agent | Can work in parallel with solver |
| `pbtes/reporting/io.py` | 1 agent | Independent |
| `sim_*.py` scripts | 1 agent each | Can all work in parallel |
| `tests/` | 1 agent per test file | Can all work in parallel |

## 4. Testing Requirements

### Before committing
```bash
python -m pytest tests/ -x --tb=short
```

### Test file conventions
- Test files in `tests/` directory
- Naming: `test_<what>.py`
- Use pytest fixtures, no unittest.TestCase
- Mock TESPy networks for unit tests (they're slow)

### Current test files
- `tests/test_physics.py` — physical validation (energy balance, T limits)
- `tests/test_modes.py` — mode transition coverage
- `tests/test_networks.py` — network creation for each mode
- `tests/test_topology.py` — Parallel vs Series validation
- `tests/test_offdesign.py` — off-design solver behavior
- `tests/test_transitions.py` — NxN mode transition matrix

## 5. Coding Conventions

### Imports
- `from pbtes import Solver` (future)
- `from coreV5 import Solver` (current)
- Always import at top of file
- No wildcard imports (`from x import *`)

### Naming
- Classes: PascalCase (`SolarThermalSystem`)
- Functions/methods: snake_case (`run_quasi_steady_simulation`)
- Variables: snake_case (`tes_params`, `component_params`)
- Constants: UPPER_SNAKE (`HTF`, `DAYS`)
- Private methods: `_prefix` (`_iterate_tes_coupling`)

### Docstrings
- Every class and public method must have a docstring
- Format: Google-style or numpy-style

### Type hints (new code only)
- Not required for existing code
- New modules should use type hints

## 6. Yearly Simulation Reporting Protocol

When running a yearly (365-day) simulation, ALWAYS include a monthly breakdown
showing these metrics, averaged per month plus min/max:

```
Month | SF% | DNI_avg | DNI_max | T_top_avg | T_top_max | T_bot_avg | T_bot_min | Q_charge_GJ | Q_discharge_GJ | Q_aux_GJ | Mode top 3
```

Where:
- SF%     = solar fraction for the month
- DNI_avg = mean irradiance (W/m2)
- DNI_max = max irradiance (W/m2)
- T_top_avg = average TES top temperature (C)
- T_top_max = max TES top temperature during month (C)
- T_bot_avg = average TES bottom temperature (C)
- T_bot_min = minimum TES bottom temperature during month (C)
- Q_charge_GJ = energy stored in TES during month (GJ)
- Q_discharge_GJ = energy discharged from TES during month (GJ)
- Q_aux_GJ = auxiliary energy used during month (GJ)
- Mode top 3 = three most frequent modes with hours

### Energy conventions
- to_tes_kJ: energy sent TO the TES (charging)
- tes_to_proc_kJ: energy from TES TO process (discharging)
- aux_to_proc_kJ: auxiliary heater energy to process
- solar_to_proc_kJ: direct solar to process (not via TES)

### Input data assumptions
- Weather data from TMY.csv with cols: Fecha/Hora, dni, temp
- Month determined by datetime.month
- Timezone: UTC, no DST adjustment needed

### Monthly breakdown code template
```python
from datetime import datetime

times = [r.get('time') for r in results]
if times and isinstance(times[0], datetime):
    print(f'\n--- Monthly Breakdown ---')
    print(f' Mo |  SF% | DNI_avg | DNI_max | Ttop_avg | Ttop_max | Tbot_avg | Tbot_min | Qchg_GJ | Qdch_GJ | Qaux_GJ | Top modes')
    print(f'----|------|---------|---------|----------|----------|----------|----------|---------|---------|---------|----------')
    for month in range(1, 13):
        idx = [i for i, t in enumerate(times) if t.month == month]
        if not idx: continue
        mon_irr = [irr[i] for i in idx]
        s  = sum(results[i].get('solar_to_proc_kJ',0) for i in idx) / 1e6
        t  = sum(results[i].get('tes_to_proc_kJ',0) for i in idx) / 1e6
        a  = sum(results[i].get('aux_to_proc_kJ',0) for i in idx) / 1e6
        qc = sum(results[i].get('to_tes_kJ',0) for i in idx) / 1e6
        qd = sum(results[i].get('tes_to_proc_kJ',0) for i in idx) / 1e6
        sf = (s + t) / max(s + t + a, 1) * 100
        tops = [results[i].get('T_tes_top', np.nan) for i in idx]
        bots = [results[i].get('T_tes_bottom', np.nan) for i in idx]
        tops_v = [v for v in tops if not np.isnan(v)]
        bots_v = [v for v in bots if not np.isnan(v)]
        mcounts = {}
        for i in idx:
            m = str(results[i].get('TESmode', '?'))
            mcounts[m] = mcounts.get(m, 0) + 1
        top3 = sorted(mcounts.items(), key=lambda x: -x[1])[:3]
        mode_str = ' '.join(f'{md}:{hr}h' for md, hr in top3)
        print(f' {month:2d} | {sf:4.1f} | {np.mean(mon_irr):7.0f} | {np.max(mon_irr):7.0f} | '
              f'{np.mean(tops_v):8.0f} | {np.max(tops_v) if tops_v else 0:8.0f} | '
              f'{np.mean(bots_v):8.0f} | {np.min(bots_v) if bots_v else 0:8.0f} | '
              f'{qc:7.0f} | {qd:7.0f} | {a:7.0f} | {mode_str}')
```

## 7. Key Technical Details

### Solver class (coreV5.py:1274)
Main simulation orchestrator. Key methods:
- `initialize_modes()` — solves design-point for all 6 modes, saves to base_design_*
- `run_quasi_steady_simulation(days, csv)` — runs hourly time-stepping
- `compute_performance_metrics()` — returns solar fraction
- `results` — list of per-timestep dicts (populated after `run_quasi_steady_simulation`)

### SolarThermalSystem (coreV5.py:651)
Builds TESPy networks. 6 modes:
- Mode 1: Solar charges TES directly (PTC → TES → back to PTC)
- Mode 2: Solar goes to process, TES also discharges to process
- Mode 3: Solar goes to process only
- Mode 4: TES discharges to process only (standby/no sun)
- Mode 5: Aux heater to process only
- Mode 6: Solar charges TES + serves process simultaneously

### ThermalEnergyStorage (coreV5.py:169)
1D packed bed model using Schumann equations. Methods:
- `update_temperature_profile(T_in, mass_flow, initial_profile)` — advances one timestep
- `calc_heat_loss(profile, dt, T_amb)` — thermal losses to ambient
- `calculate_SoC(profile)` — state of charge

### ZincPool (coreV5.py:558)
Dynamic zinc galvanizing process model:
- Tracks zinc bath temperature with heat input/loss
- Operating hours: 8am-8pm, Mon-Fri
- Consumes thermal energy proportionally to steel throughput

## 8. Quick Reference

```bash
# Run all tests
python -m pytest tests/ -x --tb=short

# Run a single test file
python -m pytest tests/test_physics.py -v

# Run a 3-day test simulation
python scripts/run_assessment_01_baseline.py

# Run a full 365-day simulation (SLOW — ~hours)
python scripts/run_assessment_01_baseline.py --full

# See git status
git status

# Create a branch for new work
git checkout -b feature/my-feature

# Commit changes
git add -A
git commit -m "feat: description"

# Push to GitHub
git push
```
