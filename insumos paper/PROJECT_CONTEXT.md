# PBTES Simulation Project — Complete Context
*Single authoritative reference for humans and AI agents.*
*Updated: 2026-05-21 | HTF: NaK + Air | Zinc pool: dynamic (always ON)*

---

## 1. What This Project Is

A **quasi-steady simulation framework** for a hypothetical solar industrial heat plant
that supplies a **zinc galvanizing process** using:

1. **Parabolic Trough Collectors (PTC)** — solar field
2. **Packed Bed Thermal Energy Storage (PBTES)** — rock/ceramic pebble tank
3. **Dynamic zinc pool model** — lumped-capacitance galvanizing bath
4. **TESPy** — thermodynamic network solver (steady-state at each timestep)

The research goal is a **Q1 journal paper** (Journal of Energy Storage / Energy / Solar Energy)
comparing four system topologies and performing parametric sensitivity analysis on
solar multiple and TES volume, with full economic analysis (LCOH).

### Scientific novelty
- First system-level simulation coupling PBTES with a dynamic galvanizing process model
- Comparison of Parallel vs Series and Direct vs Indirect configurations
- NaK as HTF (vs Air comparison)
- Pre-validated PBTES model (from a prior publication — no re-validation needed)

---

## 2. System Description

### 2.1 Solar Field — Parabolic Trough Collector (PTC)
- Model: efficiency-based with IAM polynomial and thermal loss polynomial
- Optical efficiency: η_opt = 0.816
- Loss polynomial: Q_loss = c₁·ΔT + c₂·ΔT² (c₁=0.0622 W/m²K, c₂=0.00023 W/m²K²)
- IAM: 1 + iam₁·θ + iam₂·θ² (iam₁=−1.59×10⁻³, iam₂=9.77×10⁻⁵)
- Design aperture: **1000 m²** (baseline); sweep: 500–3000 m²
- Design DNI: 900 W/m², design ambient: 20°C, design AOI: 20°

### 2.2 Heat Transfer Fluid (HTF)
- **Primary**: NaK (`INCOMP::NaK` in CoolProp) — sodium-potassium alloy
- **Comparison**: Air — used in parametric sweeps for low-cost reference
- Operating range: 300–600°C, nominal pressure ~5 bar

### 2.3 Packed Bed TES (PBTES)
- Geometry: D=7.0 m, H=5.0 m (baseline); sweep D×H grid
- Fill: rock/ceramic pebbles, dp=50 mm, ε=0.4, ρ_s=3500 kg/m³, cp_s=968 J/(kg·K)
- Physics: 1D Schumann model (analytical eigenvalue solution)
- Pre-validated from a prior publication — **do not re-validate**
- SoC = ∫ρ·cp·T dV normalized between cold (400°C uniform) and hot (560°C uniform) reference states

### 2.4 Zinc Pool (Galvanizing Process)
- Lumped-capacitance model: 150,000 kg of molten zinc
- Target temperature: 450°C, cp_zinc = 512 J/(kg·K)
- Heat losses: UA_loss = 500 W/K to ambient
- Operating schedule: 8 am–8 pm, Mon–Fri (12 h/day, 5 days/week)
- Steel throughput: 5,000 kg/h at 25°C → 450°C
- **Always ON** in every simulation — there is no option to disable it

### 2.5 Four Topologies (2×2 matrix)
| | **Indirect** (HX between PTC and TES) | **Direct** (PTC fluid enters TES) |
|---|---|---|
| **Parallel** | HTF splits to process and TES simultaneously | Same but direct contact |
| **Series** | TES always in series with process HX | Same but direct contact (upstream Hot Tank, downstream Cold Tank) |

All four must be simulated for the paper. Baseline is Parallel/indirect.

#### Direct Configuration Key Implementation Details
1. **Direct-Contact Modeling**: In the direct configuration, primary NaK flows directly through the packed bed rock tanks (Hot Tank and Cold Tank) without any intermediate heat exchangers. These are modeled inside the TESPy network as `SimpleHeatExchanger` (pipe) components.
2. **Series/Direct Mode 1 Charging**: 
   - The Hot Tank is located upstream of the process (receives the high-temperature PTC outlet at ~560°C). The Cold Tank is located downstream of the process (receives the process return at ~480°C).
   - The coupling variables set on the TESPy connections are the Hot Tank outlet (`conn_ht_ph.T`) and the Cold Tank outlet (`conn_10.T`), which are set to the bottom temperatures calculated iteratively by the 1D Schumann rock bed model.
   - To prevent over-specification, the process inlet connection `conn_05` is **not** set to a fixed temperature of 520°C in TESPy since the `Q_preheater = 0` constraint already forces `T_05` to equal the Hot Tank outlet temperature.
3. **Mode 3 Discharging (Parallel Mixing)**: 
   - To prevent convergence issues and maintain network simplicity, both the Parallel/Direct and Series/Direct Mode 3 discharging layouts are modeled **analytically (Option A)** rather than using splitting/mixing valve components in TESPy.
   - The mixing valve ratio `r = m_hot / m_cold` is solved analytically at each timestep based on current tank top temperatures `T_hot` and `T_cold` to hit the target `T_target = 520°C`.
   - TESPy only solves the simple process-only loop (identical to Mode 4), using the pre-calculated auxiliary heater load `Q_preheater` (if the blended temperature `T_mix < 520°C`).
   - The Hot Tank and Cold Tank Schumann models are then updated independently with their respective analytical mass flows `m_hot` and `m_cold`.

---

## 3. Operating Modes

The solver selects one of 6 operating modes each timestep based on irradiance, SoC, and temperatures.
See `.planning/PLANT_LAYOUTS_AND_MODES.md` for the authoritative reference with full diagrams.

| Mode | Name | Solar | TES Action | Aux | Topology | When Selected |
|------|------|:-----:|:----------:|:---:|:--------:|---------------|
| **1** | Solar charges TES + process | ✓ | Charge ← | — | Both | E > E_charge, SoC < 0.99, T_ptc > T_tes_top |
| **2** | Solar to process only | ✓ | Standby | — | Both | E > E_process, TES full or charge not viable |
| **3** | TES discharge to process | — | Discharge → | — | Both | E < E_process, SoC > 0.10, T_top in 500–580°C |
| **4** | Standby (auxiliary only) | — | Standby | ✓ | Both | No sun, SoC < 0.05 (exhausted) |
| **5** | High-T solar charges TES | ✓ | Charge ← | ✓ | **Parallel only** | E > E_charge, T_top > 520°C, SoC < 0.90 |
| **6** | Solar charges TES + process (decoupled) | ✓ | Charge ← | ✓* | **Parallel only** | E > E_process, SoC < 0.40, T_top < 470°C |

\*Mode 6: process runs on an independent auxiliary-heated cycle while PTC charges TES.

**Mode selection thresholds** (from `config.py`):
- E_min_process = Q_proc / (A_ptc × η_opt) → ~49 W/m² at baseline
- E_min_charge = 1.5 × E_min_process → ~74 W/m²
- SoC_mode6_sticky = 0.80, SoC_mode4_threshold = 0.05, etc.

---

## 4. Simulation Approach

### 4.1 Quasi-steady coupling
Each 1-hour timestep:
1. Select operating mode based on irradiance, SoC, temperatures
2. Build TESPy network for that mode (or reuse offdesign)
3. Solve TESPy → get fluid temperatures, mass flows, heat duties
4. Step the 1D Schumann PBTES model with inlet T and mass flow
5. Step the zinc pool model
6. Record all outputs to results DataFrame

### 4.2 TESPy design/offdesign
- Each mode has a **design-point solution** (stored in `.tespy_cache/base_design_N/`)
- Subsequent timesteps use **offdesign** with the design as reference
- If offdesign fails → fallback: re-run design at current conditions
- Cache is ephemeral — safe to delete, auto-regenerated on next run

### 4.3 Weather data
- File: `TMY.csv` (Typical Meteorological Year)
- Columns: `Fecha/Hora` (datetime), `dni` (W/m²), `temp` (°C)
- Timezone: UTC, no DST adjustment
- Year is fixed to 2022 for datetime consistency

### 4.4 Pump power (post-processed, NOT inline)
- NOT computed by TESPy during simulation
- Post-processed from mass flow results using the **Ergun equation**
- Script: `scripts/run_postprocess.py`

---

## 5. Codebase Structure

```
codigos/
├── AGENTS.md                     ← Agent rules (read first — always)
├── README.md                     ← Quick start
├── requirements.txt              ← Pinned Python dependencies
├── TMY.csv                       ← Weather data
├── coreV5.py                     ← Backward-compat shim (re-exports from pbtes/)
│
├── run_simulation.py             ← THE single simulation entry point
├── run_parametric.py             ← THE single parametric sweep entry point
│
├── pbtes/                        ← Main Python package
│   ├── __init__.py
│   ├── config.py                 ← Single source of truth for ALL parameters
│   ├── components/
│   │   └── ptc_field.py          ← PTCField (TESPy component)
│   ├── storage/
│   │   ├── packed_bed.py         ← ThermalEnergyStorage (1D Schumann model)
│   │   └── zinc_pool.py          ← ZincPool (galvanizing model)
│   ├── network/
│   │   └── system.py             ← SolarThermalSystem (6-mode network builder)
│   ├── simulation/
│   │   └── solver.py             ← Solver (quasi-steady orchestrator)
│   ├── reporting/
│   │   └── plots.py              ← Reporting (plots, CSV I/O)
│   └── analysis/
│       ├── economics.py          ← LCOH calculator
│       ├── exergoeconomics.py    ← Exergoeconomic analysis
│       ├── postprocess.py        ← Pump power, net solar fraction
│       ├── convergence.py        ← [TODO] Error rate tables, anomaly detection
│       └── results_reader.py     ← load_results() — reads CSV + meta header
│
├── scripts/                      ← Post-processing pipeline
│   ├── run_postprocess.py        ← Pump power + LCOH from results CSV
│   ├── run_exergoeconomics.py    ← Exergoeconomic post-processing
│   ├── run_assessment_05_analysis.py
│   ├── run_assessment_06_figures.py
│   ├── run_assessment_07_synthesis.py
│   └── run_transition_matrix.py
│
├── tests/                        ← pytest suite (10 test files)
│   ├── conftest.py               ← Shared fixtures + cache-clearing
│   ├── test_physics.py
│   ├── test_modes.py
│   ├── test_networks.py
│   ├── test_topology.py
│   ├── test_offdesign.py         ← KNOWN FAIL — Mode 1 convergence
│   ├── test_transitions.py
│   ├── test_zinc_pool.py
│   ├── test_economics.py
│   └── test_exergoeconomics.py
│
├── .planning/                    ← Project management
│   ├── STATE.md                  ← Current phase and status (read before starting)
│   ├── ROADMAP.md                ← Publication pipeline phases A–D
│   ├── REQUIREMENTS.md           ← Publication requirements
│   └── PAPER_OUTLINE.md         ← Target journal paper structure
│
├── results/                      ← Simulation output CSVs (gitignored)
│   └── README.md                 ← Results naming convention
└── .tespy_cache/                 ← TESPy design states (gitignored, auto-generated)
```

### Dependency graph
```
run_simulation.py / run_parametric.py
    └── Solver (simulation/solver.py)
          ├── SolarThermalSystem (network/system.py)
          │     └── PTCField (components/ptc_field.py)
          ├── ThermalEnergyStorage (storage/packed_bed.py)
          └── ZincPool (storage/zinc_pool.py)
```

---

## 6. Key Parameters (Baseline)

All live in [`pbtes/config.py`](file:///c:/Users/iwold/OneDrive%20-%20Universidad%20Cat%C3%B3lica%20de%20Chile/Postdoc/Galvanizing%20solar%20PBTES/codigos/pbtes/config.py) — never hardcode these elsewhere.

### TES
| Parameter | Value | Unit |
|-----------|-------|------|
| Tank height | 5.0 | m |
| Tank diameter | 7.0 | m |
| Particle diameter | 0.050 | m |
| Void fraction ε | 0.40 | — |
| Solid density | 3,500 | kg/m³ |
| Solid cp | 968 | J/(kg·K) |
| Grid points | 20 | nodes |

### PTC
| Parameter | Value | Unit |
|-----------|-------|------|
| Aperture area | 1,000 | m² |
| Optical efficiency | 0.816 | — |
| Design DNI | 900 | W/m² |

### Process
| Parameter | Value | Unit |
|-----------|-------|------|
| Heat demand | 450,000 | W |
| T_inlet (conn 5) | 520 | °C |
| T_outlet (conn 6) | 480 | °C |

### Zinc Pool
| Parameter | Value | Unit |
|-----------|-------|------|
| Zinc mass | 150,000 | kg |
| Target temperature | 450 | °C |
| UA_loss | 500 | W/K |
| Steel throughput | 5,000 | kg/h |

### Economics
| Parameter | Value |
|-----------|-------|
| Discount rate | 8% |
| Plant lifetime | 25 years |
| Tank cost | 500 USD/m³ |
| O&M | 2% CAPEX/year |

---

## 7. How to Run Simulations

### Single simulation
```bash
# Quick 7-day test
python run_simulation.py

# Full year, baseline topology
python run_simulation.py --days 365 --tag baseline

# Custom topology
python run_simulation.py --days 365 --topology Series --tank_config direct --tag series_direct

# All CLI options
python run_simulation.py --help
```

### Parametric sweep
```bash
# Topology comparison (4 combos × 1 day — fast test)
python run_parametric.py --sweep topology --days 7 --tag test

# Full publication sweeps (365 days each — slow)
python run_parametric.py --sweep aperture   --days 365 --tag pub
python run_parametric.py --sweep tes_volume --days 365 --tag pub
python run_parametric.py --sweep topology   --days 365 --tag pub
python run_parametric.py --sweep full       --days 365 --tag pub
```

### Parametric sweep grids
| Sweep | Values |
|-------|--------|
| `aperture` | 500, 750, 1000, 1500, 2000, 3000 m² |
| `tes_volume` | D: 4,5,6,7,8,10 m × H: 3,4,5,6,8 m (30 points) |
| `topology` | Parallel/indirect, Parallel/direct, Series/indirect, Series/direct |

### From Python (for parametric scripting)
```python
from run_simulation import run_single_simulation
df, filename, meta = run_single_simulation(
    days=365, topology='Parallel', tank_config='indirect',
    htf='INCOMP::NaK', tag='my_run', aperture=1500.0
)
```

### Read results
```python
from pbtes.analysis.results_reader import load_results
df, meta = load_results('results/baseline_Parallel_indirect_NaK_D7.0_H5.0_A1000_365d_20260520.csv')
print(meta['sim_args'])   # all simulation parameters
print(df.columns.tolist())  # all output columns
```

---

## 8. Results Format

### File naming
```
results/{tag}_{topology}_{tank_config}_{htf}_{D}_{H}_{A}_{days}d_{date}.csv
```
Example: `baseline_Parallel_indirect_NaK_D7.0_H5.0_A1000_365d_20260520.csv`

### CSV structure
- **Line 1**: `# __meta__ = {JSON}` — simulation parameters and metadata
- **Remaining lines**: Standard CSV, one row per hour

### Required columns
| Column | Description |
|--------|-------------|
| `time` | Timestamp |
| `E` | DNI (W/m²) |
| `Tamb` | Ambient temperature (°C) |
| `TESmode` | Operating mode (1–6) |
| `TES_layout` | Charge / Discharge / Standby |
| `iter_status` | converged / failed |
| `T_ptc_out` | PTC outlet temperature (°C) |
| `T_tes_top` | TES top temperature (°C) |
| `T_tes_bottom` | TES bottom temperature (°C) |
| `tes_soc_kWh` | TES state of charge (kWh) |
| `mdot_ptc_kg_s` | PTC mass flow (kg/s) |
| `to_tes_kJ` | Energy to TES per step (kJ) |
| `tes_to_proc_kJ` | Energy from TES to process (kJ) |
| `solar_to_proc_kJ` | Direct solar to process (kJ) |
| `aux_to_proc_kJ` | Auxiliary heater to process (kJ) |
| `T_zinc` | Zinc pool temperature (°C) |
| `Q_zinc_hx_kW` | Heat to zinc pool (kW) |
| `zinc_operating` | Whether zinc plant is operating |

### Key derived metrics
```python
sf = (df['solar_to_proc_kJ'] + df['tes_to_proc_kJ']).sum() / \
     (df['solar_to_proc_kJ'] + df['tes_to_proc_kJ'] + df['aux_to_proc_kJ']).sum()
# Solar fraction (0–1)
```

---

## 9. Testing

```bash
# Full suite (recommended before every commit)
python -m pytest tests/ -x --tb=short

# Skip known physics failures (fast CI check)
python -m pytest tests/ --ignore=tests/test_offdesign.py --tb=short -q

# Single file
python -m pytest tests/test_zinc_pool.py -v
```

### Current test status (2026-05-21)
- **10 test files** covering physics, modes, networks, topology, offdesign, transitions, zinc pool, economics, exergoeconomics
- `test_offdesign.py::test_mode1_offdesign` — **KNOWN FAIL** (physics, not code)
- `test_transitions.py::test_mass_flow_routing_mode1` — **xfail** (same physics issue)
- `conftest.py` automatically clears `.tespy_cache` before each session (prevents cache poisoning)

---

## 10. Git Workflow

### Absolute rules
1. **Never commit to `main` directly** — always work on a branch
2. **Branch naming**: `feature/<what>`, `fix/<what>`, `refactor/<what>`
3. **Run tests before committing**: `python -m pytest tests/ -x --tb=short`
4. **Commit atomically**: one logical change per commit
5. **Message format**: `<type>: <short description>` (types: feat, fix, refactor, test, docs, chore)

### Standard workflow
```bash
git checkout main
git pull origin main
git checkout -b fix/my-fix
# ... make changes ...
python -m pytest tests/ -x --tb=short   # must pass
git add -A
git commit -m "fix: description"
git push origin fix/my-fix
# Then merge to main when done
git checkout main
git merge fix/my-fix --no-ff -m "feat: merge description"
git push origin main
```

---

## 11. Project State & Phases

### What is complete

| Phase | Description | Status |
|-------|-------------|--------|
| A: Foundation | Codebase cleanup, AGENTS.md, planning documents | Done |
| B: Bug Fixes | Critical bug fixes, unified run_simulation.py | Done |

### Current: Phase C — Physics & Convergence

**Known issues** (see `TODO.md` for full list):
1. Mode 1 offdesign diverges for NaK
2. Mode 6 design fails with "too many parameters"
3. Full-year simulation convergence < 95%

### Future: Phase D — Results & Publication

- Run all 4 topologies × 365 days
- Run HTF comparison (NaK vs Air)
- Run parametric sweeps (aperture + TES volume)
- Generate 14+ figures
- Compute LCOH and exergoeconomic analysis
- Write paper

---

## 12. Agent Methodology

### Before starting any work
1. **Read `AGENTS.md`** — non-negotiable, contains all workflow rules
2. **Read `.planning/STATE.md`** — current phase, known issues, last commit
3. **Run tests** — `python -m pytest tests/ -x --tb=short` — confirm baseline
4. **Create a branch** — never work on main

### File ownership (max 1 agent per file)
| File | Owner |
|------|-------|
| `pbtes/config.py` | Coordinate — central config |
| `pbtes/network/system.py` | Convergence agent |
| `pbtes/simulation/solver.py` | Convergence agent |
| `pbtes/storage/packed_bed.py` | Independent |
| `pbtes/storage/zinc_pool.py` | Independent |
| `pbtes/reporting/plots.py` | Figures agent |
| `pbtes/analysis/economics.py` | Economics agent |
| `pbtes/analysis/exergoeconomics.py` | Exergoeconomics agent |
| `pbtes/analysis/convergence.py` | [TODO — create first] |
| `run_simulation.py` | Independent |
| `run_parametric.py` | Independent |

### Scope discipline
- **Convergence agent**: touch ONLY `system.py` and `solver.py` — do not touch scripts, results format, or physics of packed bed
- **Figures agent**: touch ONLY `plots.py` and `scripts/run_assessment_06_figures.py`
- **If in doubt**: read AGENTS.md section 7 (Agent Rules)

### When done
1. Run tests
2. Commit atomically with descriptive message
3. Update `TODO.md` and `.planning/STATE.md`
4. Update `AGENTS.md` if structure/conventions changed
5. Merge to main and push

---

## 13. Key Design Decisions (Settled — Do Not Revisit)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HTF | NaK (`INCOMP::NaK`) primary | Available in CoolProp, appropriate temperature range |
| HTF comparison | Air | Low-cost reference for parametric comparison |
| Zinc pool | Always ON | Core novelty of the paper |
| Pump power | Post-processed (Ergun) | Not inline — avoids convergence complications |
| PBTES model | Pre-validated | From prior publication, no re-validation needed |
| Plant | Hypothetical reference | No real facility baseline required |
| Target journals | JES, Energy, Solar Energy | Q1, appropriate scope |
| Topologies | Parallel/Series × Direct/Indirect | 4 combos for comparison |
| Air HTF | Comparison case only | Not primary |

---

## 14. Common Pitfalls

| Pitfall | How to avoid |
|---------|-------------|
| `.tespy_cache` poisoned by diverged run | Tests auto-clear it; manually: `Remove-Item .tespy_cache\* -Recurse -Force` |
| `base_design_*` directories in root | They should ONLY exist in `.tespy_cache/` — check `.gitignore` |
| `mode1_kA.txt` file appearing | **Fixed** — no longer written. If it appears, there's a regression |
| Editing `main` directly | Never. Always branch. |
| Changing physics without tests | Add a test first, then change |
| Running 365-day sweep before convergence is fixed | Use `--days 7` for iteration |
| Using `from coreV5 import` in new code | Use `from pbtes.xxx import` instead |

---

## 15. Quick Reference Commands

```bash
# Test
python -m pytest tests/ -x --tb=short

# 7-day smoke test
python run_simulation.py

# Full year baseline
python run_simulation.py --days 365 --tag baseline

# Topology sweep (7-day test)
python run_parametric.py --sweep topology --days 7 --tag test

# Post-process results
python scripts/run_postprocess.py results/baseline_*.csv

# Generate figures
python scripts/run_assessment_06_figures.py

# Git: create branch
git checkout -b fix/convergence

# Git: push
git add -A
git commit -m "fix: description"
git push origin fix/convergence
```
