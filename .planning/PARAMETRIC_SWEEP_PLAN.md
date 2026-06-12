# Parametric Sweep Implementation Plan — Phase D
*Created: 2026-06-12 | Updated: 2026-06-12 (parallel execution integrated)*
*For Q1 journal publication (JES / Energy / Solar Energy)*

---

## 1. Research Questions the Sweeps Must Answer

The parametric sweep serves to answer **five high-level research questions**, each
mapping to one or more publication figures and a distinct scientific contribution:

| # | Research Question | Key Metric | Figures |
|---|-------------------|------------|---------|
| **RQ1** | Which configuration (PI vs SD) delivers higher solar fraction and which offers lower LCOH, and why? | SF, LCOH, mode-hours | 08, 10, 12 |
| **RQ2** | How does the solar multiple (aperture area) affect SF, LCOH, and the TES utilization regime? | SF vs A, round-trip efficiency, LCOH vs A | 10 |
| **RQ3** | What is the cost-optimal TES geometry (D × H) at the baseline solar field? What geometry maximizes SF? | LCOH vs (D,H), SF vs (D,H) contour maps | 11 |
| **RQ4** | How sensitive is SF to packed-bed physical parameters (dp, ε, insulation thickness)? | SF ± Δ% per ±20% parameter | 12 |
| **RQ5** | What is the net solar fraction and LCOH after accounting for pump parasitics (Ergun)? | Net SF, SF penalty, LCOH(techno-economic) | 10, 11, 12 |

---

## 2. Sweep Definitions — Complete Parameter Grids

### 2.1 Sweep A: Aperture Area (Solar Multiple)
**Own variable**: PTC aperture area `A_ptc`
**Fixed baseline**: PI topology, D=7.0 m, H=5.0 m, dp=0.05 m, ε=0.40

| A_ptc (m²) | Solar Multiple (SM) | Rationale |
|-------------|---------------------|-----------|
| 500 | 0.50 | Extremely undersized — aux-dominated |
| 750 | 0.75 | Undersized — marginal solar contribution |
| **1000** | **1.00** | **Baseline** |
| 1500 | 1.50 | Basic oversizing |
| 2000 | 2.00 | Significant oversizing |
| 3000 | 3.00 | Extreme oversizing — diminishing returns expected |

**SM reference**: SM = A_ptc / 1000 m² (baseline A).
**Runs per config**: 6 × 2 topologies (PI, SD) = 12 runs (if both topologies swept).
**Strategy**: Start with PI-only (6 runs), then extend best configurations to SD.

### 2.2 Sweep B: TES Volume (Diameter × Height grid)
**Own variables**: D (tank diameter), H (tank height)
**Fixed baseline**: PI topology, A_ptc=1000 m²

| D (m) | H (m) combinations |
|-------|--------------------|
| 4.0 | × 3.0, 4.0, 5.0, 6.0, 8.0 |
| 5.0 | × 3.0, 4.0, 5.0, 6.0, 8.0 |
| 6.0 | × 3.0, 4.0, 5.0, 6.0, 8.0 |
| **7.0** | × 3.0, 4.0, **5.0**, 6.0, 8.0 |
| 8.0 | × 3.0, 4.0, 5.0, 6.0, 8.0 |
| 10.0 | × 3.0, 4.0, 5.0, 6.0, 8.0 |

**Total grid points**: 6 D × 5 H = **30 points**.
**Runs per config**: 30 × 2 (PI, SD) = 60 if both topologies swept.
**Strategy**: PI-only grid first (30 runs), then SD at selected interesting points.

### 2.3 Sweep C: Topology Comparison (PI vs SD)
**Own variable**: topology / tank_config
| Config | Modes | Notes |
|--------|-------|-------|
| PI (Parallel, indirect) | 4-mode (2,3,4,5,6) | Baseline, HX decoupling, 2 pumps active in charge/discharge |
| SD (Series, direct) | 4-mode (1,2,3,4) | Two-tank direct-contact, 1 pump, upstream Hot Tank |

**Fixed**: A_ptc=1000 m², D=7.0 m, H=5.0 m (baseline geometry).
**Runs**: 2.

### 2.4 Sweep D: Physical Sensitivities (Packed Bed Parameters)
**Own variables**: dp (particle diameter), ε (void fraction), insulation thickness
**Fixed baseline**: PI, A_ptc=1000 m², D=7.0 m, H=5.0 m

| Parameter | Baseline | Low | High | Range reasoning |
|-----------|----------|-----|------|-----------------|
| dp (mm) | 50 | 30 | 100 | 30–100 mm = typical rock/ceramic range |
| ε | 0.40 | 0.35 | 0.50 | Void fraction practical range |
| Insulation (m) | 1.0 | 0.50 | 1.50 | From thin conventional to thick premium |

**Runs**: 9 (3 parameters × 3 levels, non-baseline points).

### 2.5 Sweep E: HTF Comparison
**Own variable**: HTF fluid
| HTF | CoolProp string | Purpose |
|-----|-----------------|---------|
| Solar Salt | INCOMP::NaK | Primary — commercial, high-density |
| Air | Air | Reference — low-cost, low-density |

**Fixed**: PI, baseline geometry.
**Runs**: 2.

---

## 3. Total Simulation Inventory

| Sweep | Configs | Runs | Days × Run | CPU-h/run (est.) | Total CPU-h |
|-------|---------|------|------------|------------------|-------------|
| A: Aperture | PI + SD | 12 | 365 | ~1.5 | ~18 |
| B: TES Volume | PI | 30 | 365 | ~1.5 | ~45 |
| C: Topology | PI + SD | 2 | 365 | ~1.5 | ~3 |
| D: Physical Sens | PI | 9 | 365 | ~1.5 | ~13.5 |
| E: HTF | PI | 2 | 365 | ~1.5 | ~3 |
| **Total** | | **55** | | | **~82.5** |

### 3.1 Estimated Wall-Clock Time by Parallelism Level

| Sweep | N=1 (seq) | N=4 | N=8 |
|-------|-----------|-----|-----|
| Topology (4 jobs × 7d test) | ~2 h | ~0.6 h | ~0.5 h |
| Aperture (6 jobs × 365d) | ~9 h | ~2.5 h | ~1.5 h |
| TES Volume (30 jobs × 365d) | ~45 h | ~12 h | ~6 h |
| **Full sweep (55 jobs × 365d)** | **~82 h (3.4 d)** | **~22 h** | **~11 h** |

---

## 4. Parallel Execution Architecture

### 4.1 Why Process Parallelism (Not Threads)

TESPy and CoolProp present the following concurrency risks:

| Risk | Severity | Mechanism |
|------|----------|-----------|
| **Cache collision** | **HIGH** | Two processes with same `(topology, tank_config)` share `'.tespy_cache/Parallel_indirect/'`. They race on `shutil.rmtree`, `network.save()`, and `network.load()`. |
| **No cache isolation** | **HIGH** | `Solver.__init__` hardcodes cache path as `f'.tespy_cache/{topology}_{tank_config}'`. No CLI flag or env var exists to separate caches. |
| **Aggressive cleanup** | **MEDIUM** | `initialize_modes()` wipes all design dirs under the cache at startup. One process could delete another's in-progress writes. |
| **CoolProp global state** | **LOW** | Uses only `cp.PropsSI()` (high-level), not `AbstractState`. Process isolation eliminates this risk. |
| **TESPy internal state** | **UNKNOWN** | `network.solve()` internals are opaque; may hold C/Fortran state. Process isolation eliminates shared-memory risk. |

**Decision**: Use Python's `multiprocessing` with `spawn` start method (Windows-safe). Each worker is an independent OS process with its own memory space, CoolProp state, and TESPy context. The only collision surface — the filesystem — is controlled via per-run cache isolation.

### 4.2 Cache Isolation Mechanism

**Current (collision-prone):**
```
Solver(cache_dir='.tespy_cache/Parallel_indirect/')
   ├── base_design_1/  ← two runs write to the same files
   └── base_design_2/
```

**Proposed (isolated):**
```
Solver(cache_dir='.tespy_cache/{run_id}/')
   ├── base_design_1/  ← only this run touches these
   └── base_design_2/
```

Where `run_id` is a deterministic string derived from job parameters, e.g.:
```
Parallel_indirect_NaK_D7.0_H5.0_A1000
```

This is **deterministic** (same job → same cache → resumable across restarts) and **unique per job** (no two jobs share a cache dir).

### 4.3 Code Changes for Cache Isolation

**File: `pbtes/simulation/solver.py`** — accept `_run_id` in constructor:
```python
# line 37: replace hardcoded path
run_id = kwargs.get('_run_id', f'{topology}_{tank_config}')
self._cache_dir = f'.tespy_cache/{run_id}'
```

**File: `run_simulation.py`** — add `--run-id` CLI flag and pass to Solver:
```python
parser.add_argument('--run-id', type=str, default=None,
    help='Isolation key for design cache (auto-generated from params if omitted)')
```

**File: `run_parametric.py`** — auto-generate `run_id` from job params before each call to `run_single_simulation`.

### 4.4 Thread-Safe Manifest Updates

- **Only the main process writes** to `parametric_manifest.csv`
- Worker processes return results via the pool's return value
- The main process atomically updates the manifest using `.tmp` rename pattern (already implemented in `save_manifest_state`)
- **Results CSVs are inherently safe**: each job writes to a unique filename (deterministic naming), no collision possible
- **Error propagation**: worker exceptions are caught inside the worker function, serialized as a structured error dict, and returned to the main process for logging

### 4.5 Spyder Integration & Progress Display

The parametric sweep is designed to be launched from **Spyder's IPython console**.
The following UI elements provide real-time feedback during execution:

**Progress bar (per-job):** `tqdm` wraps each simulation, showing:
- Elapsed time for the current simulation
- Estimated remaining time for the current simulation (based on elapsed days / total days ratio)
- Iterations-per-second equivalent (days simulated per second)

**Dashboard refresh (per-batch):** At each job completion, a compact summary table
prints to the console (clearing previous output via `\r` or IPython `clear_output`):

```
╔══════════════════════════════════════════════════════════════════════════╗
║  PBTES PARAMETRIC SWEEP — Live Status                                   ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Batch start:  2026-06-12 14:30   Elapsed: 4h 12m   ETA remaining: 7h 50m
║  Workers:      8 (parallel)
╠══════════════════════════════════════════════════════════════════════════╣
║  Completed:    14 / 55    Failed: 1    Running: 8    Pending: 32
╠══════════════════════════════════════════════════════════════════════════╣
║  Job                              SF%     Status   Time      Errors     ║
║  ───────────────────────────────  ──────  ───────  ────────  ─────────  ║
║  Parallel_indirect_A1000_D7_H5   54.5%   ok        1h 23m    0         ║
║  Parallel_indirect_A1500_D7_H5   62.1%   ok        1h 31m    3         ║
║  Series_direct_A1000_D7_H5       55.4%   ok        1h 18m    0         ║
║  Parallel_indirect_A500_D7_H5     FAIL   failed    0h 12m   —          ║
║  Parallel_indirect_A2000_D7_H5    —      running   2h 05m   —          ║
║  ...                                                                   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

**Implementation approach:**
- Use `tqdm` for per-job progress (wraps the inner timestep loop in `Solver.run_quasi_steady_simulation`). Works natively in Spyder's IPython console with `tqdm.auto`.
- Use ANSI escape codes or `IPython.display.clear_output(wait=True)` to refresh the dashboard between jobs. Keeps a single block of output rather than scrolling thousands of lines.
- The dashboard reads from `parametric_manifest.csv` (always up-to-date, even if the main process dies — the dashboard is reconstructible).
- In parallel mode, only the **main process** prints the dashboard (workers are silent). Worker progress bars are suppressed; instead, each worker reports completion via the pool return value and the main process updates the dashboard.
- Add a `--no-progress` flag to disable all progress output (useful for logging to file or running in headless environments).
- Add a `--dashboard-interval` flag (default: every job completion) to control refresh frequency.

**Dependency:** `tqdm` is already a common dependency (add to `requirements.txt` if not present).

### 4.6 Crash Resilience & Restart Behavior

The sweep engine must survive unexpected shutdowns (power loss, OS crash, Spyder
kernel restart) and resume correctly on the next invocation.

**Design principle:** Each job is an atomic unit. If a job does NOT complete
(writes no valid output CSV with a final timestep), it is treated as
unfinished and restarted from scratch on the next run. There is **no mid-job
checkpointing** — the complexity of saving/restoring TES temperature profiles,
zinc pool state, and timestep indices across crashes is not justified given
that a 365-day simulation takes ~1.5 hours.

**State machine per job in `parametric_manifest.csv`:**

```
                    ┌──────────────────────────┐
                    │                          │
                    ▼                          │
  ┌─────────┐   job    ┌─────────┐   success   ┌──────────┐
  │ pending │ ───────► │ running │ ──────────► │    ok    │
  └─────────┘  queued  └─────────┘             └──────────┘
       ▲                    │                        │
       │                    │ crash/kill             │
       │                    ▼                        │
       │              ┌──────────┐                   │
       └──────────────│ running  │  (on restart:     │
          reset to     │ (stale) │   reset→pending)   │
          pending      └──────────┘                   │
                                                      │
       ┌─────────┐  exception  ┌─────────┐            │
       │ pending │ ◄────────── │ failed  │ ◄──────────┘
       └─────────┘  retry flag └─────────┘  exception
```

**Startup sequence (every invocation of `run_parametric.py`):**

1. Load `parametric_manifest.csv`. If it doesn't exist, generate the full sweep grid.
2. Scan for jobs with `status == 'running'`:
   - These are **stale** — the previous run was interrupted.
   - Reset them to `status = 'pending'`.
   - Delete any partial output CSV associated with the job (the filename is deterministic from `job_id`).
   - Set `error_message = 'Interrupted execution — restarting'`.
3. Scan for orphaned `.tespy_cache/{run_id}/` directories of interrupted jobs:
   - If a `run_id` belongs to a job now marked `pending`, delete its cache directory.
   - This prevents corrupted design states from a mid-solve crash from poisoning the restart.
4. Scan for orphaned `.tmp` manifest files (`parametric_manifest.csv.tmp`):
   - If present, the previous manifest write was interrupted. Compare `.tmp` to the real manifest — if `.tmp` is newer, recover from it. Otherwise delete it.
5. Save the cleaned manifest.
6. Proceed with execution: all `pending` jobs (including reset ones) are queued.

**What happens on crash during a running job:**
- The output CSV is partially written. Since `run_single_simulation` writes the CSV only after ALL timesteps complete (line 269-281 in `run_parametric.py`), a partial CSV cannot exist unless the write itself is interrupted. If a partial CSV exists, it will have fewer rows than expected (8760 for 365-day run) — the startup scan detects this and deletes it.
- The design cache (`base_design_1/` through `base_design_6/`) under `.tespy_cache/{run_id}/` may contain partially-written files. The startup `initialize_modes()` already handles corrupted cache dirs with `rmtree` + rename fallback.
- The manifest shows `status = 'running'` (written before the job started). On restart, this is reset → `pending`.

**What survives a crash:**
- All completed jobs (`status = 'ok'`) and their output CSVs — untouched.
- All failed jobs (`status = 'failed'`) — preserved, unless `--retry-failed` is passed.
- The manifest itself — the `.tmp` rename pattern (line 214-219 of `run_parametric.py`) ensures atomic writes, so the manifest is never corrupted.

**Recovery test protocol:**
1. Start a sweep with 7-day test jobs.
2. After 2 jobs complete and 2 are running, kill the Python process (`taskkill /F /PID`).
3. Re-run the same command.
4. Verify: the 2 completed jobs show `ok` and are skipped; the 2 killed jobs show `pending` and restart from scratch; the manifest has no corruption.

### 4.7 Fallback Position

If TESPy has an unresolvable issue with `multiprocessing` (e.g., C extension state cannot survive `spawn`), use **filesystem-level parallelism**:

```bash
# Split manifest into N chunks manually, run as separate OS processes
python run_parametric.py --sweep full --days 365 --tag chunk1 --job-range 0:17 &
python run_parametric.py --sweep full --days 365 --tag chunk2 --job-range 18:35 &
python run_parametric.py --sweep full --days 365 --tag chunk3 --job-range 36:54 &
wait
```

This requires adding a `--job-range` flag to `run_parametric.py` (filter manifest to a slice of pending jobs) and is guaranteed safe — each OS process has completely independent memory, CoolProp, and TESPy state.

---

## 5. Staged Testing Protocol for Parallel Execution

**Rule**: Execute stages sequentially — only advance when the current stage passes
validation against the Stage 0 baseline.

### Stage 0: Sequential Baseline (Control)
```
python run_parametric.py --sweep topology --days 7 --tag stage0
```
**Validation**: All runs pass. Record `solar_fraction_pct`, `total_solar_kJ`,
`total_aux_kJ`, `convergence_errors` for each job. These are the **reference
values** that all subsequent stages must match **exactly** (≤0.01% tolerance on SF).

### Stage 1: Cache Isolation Without Parallelism
Add `--run-id` to `run_simulation.py`, thread to `Solver.__init__`, auto-generate
unique IDs in `run_parametric.py`. Delete shared caches first. Run sequentially:
```
python run_parametric.py --sweep topology --days 7 --tag stage1
```
**Pass condition**: 100% metric agreement with Stage 0. Any deviation → stop and
debug (investigate TESPy internal RNG or first-timestep sensitivity). Use
`np.random.seed()` at each Solver init if needed.

### Stage 2: Two-Process Manual Parallelism
Run 2 jobs simultaneously via a **standalone script** (do NOT modify
`run_parametric.py` yet). Use PI topology with different aperture areas (same
topology/tank_config → historically most collision-prone). This validates that
`spawn` works with TESPy/CoolProp:
```
python scripts/test_parallel_2proc.py
```
**Pass condition**: Both jobs match Stage 0 references exactly. Zero file errors.

### Stage 3: Full-Sweep Parallelism Integration
Modify `run_parametric.py` to support `--parallel N`. Run topology sweep (4 jobs)
with N=3 workers (tests N < total scenario):
```
python run_parametric.py --sweep topology --days 7 --tag stage3 --parallel 3
```
**Pass condition**: 100% metric agreement + manifest integrity + no stale `.tmp` files.

### Stage 4: Stress Test — Maximum Contention
Run aperture sweep (6 jobs, same topology, same tank_config, different aperture)
with 6 parallel workers. This maximizes filesystem stress:
```
python run_parametric.py --sweep aperture --days 7 --tag stage4 --parallel 6
```
**Pass condition**: All 6 jobs match Stage 0. Zero file errors.

### Stage 5: Full-Scale Production
```
python run_parametric.py --sweep tes_volume --days 365 --tag prod --parallel 8
```
**Pass condition**: ≥95% convergence per job. No inter-job interference. Manifest complete.

---

## 6. Implementation Roadmap (Execution Order)

The roadmap is a single sequence — each phase depends on the previous. The parallel
testing stages (§5) gate the production sweep phases.

### Phase P.0: Code Preparation (do once, first)
```
[ ] P0.1: Add --run-id to run_simulation.py + Solver.__init__
[ ] P0.2: Auto-generate run_id in run_parametric.py from job params
[ ] P0.3: Add --job-range to run_parametric.py (filter manifest to slice)
[ ] P0.4: Implement crash-recovery startup sequence (stale 'running' → 'pending',
          partial CSV cleanup, orphaned cache deletion, .tmp manifest recovery)
[ ] P0.5: Implement Spyder progress dashboard (tqdm per-job + summary table refresh)
[ ] P0.6: Verify: Stage 0 + Stage 1 (sequential isolation → identical results)
```

### Phase P.1: Parallel Test Script (standalone)
```
[ ] P1.1: Create scripts/test_parallel_2proc.py
[ ] P1.2: Run Stage 2 → confirm 2 parallel jobs match Stage 0
```

### Phase P.2: Integrate Parallelism into run_parametric.py
```
[ ] P2.1: Add --parallel N flag to run_parametric.py
[ ] P2.2: Implement mp.Pool executor in execute_sweeps()
[ ] P2.3: Worker exception serialization + manifest-safe write
[ ] P2.4: Suppress worker progress bars in parallel mode (main process only displays dashboard)
[ ] P2.5: Preserve sequential fallback (--parallel 1 or omitted)
[ ] P2.6: Run Stage 3 → 4 jobs / 3 workers
[ ] P2.7: Run Stage 4 → 6 jobs / 6 workers stress test
[ ] P2.8: Run crash-recovery test (kill mid-sweep, restart, verify resume)
```

### Phase D.1: Baseline Runs (prerequisites for all figures)
```
[ ] D1.1: RUN_PI_BASELINE:  python run_simulation.py --days 365 --tag baseline --run-id baseline_PI
[ ] D1.2: RUN_SD_BASELINE:  python run_simulation.py --days 365 --topology Series --tank_config direct --tag baseline --run-id baseline_SD
[ ] D1.3: POST_PROCESS:     python scripts/run_postprocess.py results/baseline_*.csv
```

### Phase D.2: Primary Sweeps (A + B = 36 runs — run in parallel)
```
[ ] D2.1: SWEEP_APERTURE:   python run_parametric.py --sweep aperture --days 365 --tag pub --parallel 6
[ ] D2.2: SWEEP_TES_VOL:    python run_parametric.py --sweep tes_volume --days 365 --tag pub --parallel 8
```

### Phase D.3: Secondary Sweeps (C + D + E = 13 runs — run in parallel)
```
[ ] D3.1: TOPOLOGY:         Covered by baseline runs D1.1 + D1.2
[ ] D3.2: SWEEP_PHYSICAL:   python run_parametric.py --sweep physical_sens --days 365 --tag pub --parallel 4
[ ] D3.3: SWEEP_HTF:        python run_parametric.py --sweep htf --days 365 --tag pub --parallel 2
```

### Phase D.4: Economic Post-Processing
```
[ ] D4.1: POST_PROCESS_ALL: python scripts/run_postprocess.py results/pub_*.csv
[ ] D4.2: ECON_SENS:        python scripts/run_economic_sensitivity.py
[ ] D4.3: AGGREGATE:        python scripts/run_aggregate_metrics.py (new script)
```

### Phase D.5: Figures (rewrite `run_assessment_06_figures.py`)
```
[ ] D5.1: FIG_01-07:  Baseline figures (from baseline CSVs)
[ ] D5.2: FIG_08-12:  Parametric figures (from sweep CSVs via manifest)
[ ] D5.3: FIG_13-17:  Sensitivity/advanced figures
```

### Phase D.6: Synthesis & Paper
```
[ ] D6.1: RUN_SYNTHESIS:    python scripts/run_assessment_07_synthesis.py
[ ] D6.2: DRAFT_SECTIONS:   Write case study (§4), results (§5), discussion (§7), conclusions (§8)
```

---

## 7. Post-Processing Pipeline

### 7.1 Unit Processing (per-run)
```
[raw CSV] → run_postprocess.py → [_processed CSV with W_pump_kW column]
         → economics.py → [LCOH, CAPEX/OPEX breakdown]
         → exergoeconomics.py → [η_ex, c_p, exergy destruction]
```

### 7.2 Aggregate Metric Extraction

For each run, extract these into the manifest:

| Metric | Source Column(s) | Formula |
|--------|------------------|---------|
| **SF_thermal** | `solar_to_proc_kJ`, `tes_to_proc_kJ`, `aux_to_proc_kJ`, `aux_tes_energy_kJ` | (Q_solar + Q_tes) / (Q_solar + Q_tes + Q_aux_proc + Q_aux_tes) |
| **SF_net** | SF_thermal, `W_pump_kW` | SF corrected for pump parasitics |
| **Q_charge_GJ** | `to_tes_kJ` | Σ / 1e6 |
| **Q_discharge_GJ** | `tes_to_proc_kJ` | Σ / 1e6 |
| **Q_aux_proc_GJ** | `aux_to_proc_kJ` | Σ / 1e6 |
| **Q_aux_tes_GJ** | `aux_tes_energy_kJ` | Σ / 1e6 (note: column stores Joules, named kJ) |
| **Q_ptc_GJ** | `ptc_total_kJ` | Σ / 1e6 |
| **Round-trip efficiency** | Q_discharge / Q_charge | — |
| **Mode-hours** | `TESmode` | Count per mode |
| **Convergence rate** | `iter_status` | N_converged / N_total |
| **T_tes_top_mean** | `T_tes_top` | mean (operational hours only) |
| **T_tes_bottom_mean** | `T_tes_bottom` | mean (operational hours only) |
| **Zinc pool T_mean** | `T_zinc` | mean |
| **LCOH** | economics.py | annualized CAPEX + OPEX / MWh_delivered |
| **η_exergy** | exergoeconomics.py | Ex_product / Ex_fuel |

### 7.3 Aggregated Output Table
The `parametric_manifest.csv` is the primary tracker. A new script
`scripts/run_aggregate_metrics.py` reads the manifest, loads each CSV,
computes all aggregate metrics, and writes `results/parametric_metrics.csv`.

---

## 8. Figures — What We Produce and From Which Data

| Fig# | Title | Sweep Data Source | Type | Axes |
|------|-------|-------------------|------|------|
| **01** | Plant schematic (PI + SD) | None (drawing) | Diagram | — |
| **02** | Annual DNI + T_amb profile | TMY.csv | Time-series | Date vs DNI, Date vs T_amb |
| **03** | TES temperature colormap (year) | Baseline PI CSV | Colormesh | Date vs z, T color |
| **04** | Summer week profile | Baseline PI CSV | Multi-panel time-series | Hour vs P, mode, T, SoC |
| **05** | Winter week profile | Baseline PI CSV | Multi-panel time-series | Hour vs P, mode, T, SoC |
| **06** | Monthly energy breakdown | Baseline PI/SD CSVs | Stacked bar | Month vs Q (solar/tes/aux) |
| **07** | Zinc pool temperature (year) | Baseline PI CSV | Time-series | Date vs T_zinc |
| **08** | PI vs SD SF comparison | Topology sweep | Bar chart | Config vs SF |
| **09** | SF vs aperture area (PI + SD) | Sweep A | XY scatter/line | A vs SF, colored by topology |
| **10** | LCOH vs aperture area | Sweep A + economics | XY scatter | A vs LCOH (or SM vs LCOH) |
| **11** | SF contour (D × H) | Sweep B | Filled contour | D vs H, fill=SF |
| **12** | LCOH contour (D × H) | Sweep B + economics | Filled contour | D vs H, fill=LCOH |
| **13** | Sensitivity tornado | Sweep D + economics | Horizontal bar | Parameter vs ΔSF / ΔLCOH |
| **14** | HTF comparison (NaK vs Air) | Sweep E | Bar / table | HTF vs SF, LCOH |
| **15** | Mode transition Sankey | Sweep A (selected SM) | Sankey diagram | Mode_i → Mode_j flow width |
| **16** | Round-trip efficiency vs SM | Sweep A | XY scatter | SM vs η_roundtrip |
| **17** | LCOH vs SF (Pareto front) | Sweeps A+B combined | Scatter | SF vs LCOH, colored by config |

Figure production script: `scripts/run_assessment_06_figures.py` — needs full rewrite
to read from `parametric_manifest.csv` and `parametric_metrics.csv` rather than
hardcoded file paths.

---

## 9. Scientific Narrative — The Story the Sweeps Tell

### 9.1 SF vs Solar Multiple (Sweep A)
Expected pattern: SF rises steeply from SM=0.5 to SM=1.5, then saturates at
SM > 2.0 (diminishing returns). PI should outperform SD at low SM (HX allows
partial charging), but SD may catch up at high SM (direct contact eliminates
HX ΔT penalty).

**Key insight**: The economically optimal SM balances marginal SF gain against
CAPEX. LCOH should show a minimum at some SM between 1.0 and 2.0.

### 9.2 TES Volume Trade Space (Sweep B)
Expected pattern: SF rises monotonically with both D and H (larger tank = more
energy stored), but with decreasing marginal returns. LCOH has a U-shaped
response — too small (SF low, aux high) and too large (CAPEX dominates) are
both suboptimal.

**Key insight**: The 30-point D×H grid maps the exact (D,H) that minimizes LCOH.
A Pareto frontier SF vs LCOH is extractable from these points.

### 9.3 Physical Sensitivity (Sweep D)
Expected pattern: dp has mild effect through pressure drop (Ergun, pump power)
and HTC (Wakao-Kaguei correlation). Insulation thickness primarily affects
standby losses (Mode 4 hours). Void fraction affects both energy density and
pressure drop.

**Key insight**: Quantifies robustness — if all sensitivities are <5% SF
change for ±20% parameter variation, the design is robust.

### 9.4 PI vs SD (Sweep C)
Expected: SD likely has higher SF (direct contact, no HX ΔT penalty) but also
higher CAPEX (two tanks) and higher pump power (direct bed pressure drop × longer
flow path). PI has lower CAPEX (single tank, standard HX) but lower SF due to HX
ΔT penalty.

**Key insight**: The winner depends on the metric — SF favors SD, LCOH may favor PI.
Externalized costs (pump electricity) may shift the balance.

---

## 10. Expected Quantitative Outcomes (Hypotheses to Verify)

1. **SF(PI, A=1000) ≈ 45-55%** — consistent with 54.5% at A=1500 in test run
2. **SF(SD, A=1000) ≈ 50-60%** — SD should be slightly higher due to no-HX penalty
3. **SF saturates at SM ≈ 2.0** — <5% SF gain from SM 2.0 to SM 3.0
4. **LCOH minimum at SM ≈ 1.2-1.8** — CAPEX penalty outweighs SF gain beyond this
5. **Optimal (D,H) ≈ (7-8 m, 5-6 m)** at baseline A
6. **SF sensitivity to dp < 3%** — particle size affects pump power more than SF
7. **Air HTF SF << Solar Salt SF** — low density → low energy density → poor storage
8. **SD LCOH > PI LCOH** — two-tank CAPEX likely dominates despite higher SF

---

## 11. Code Changes Required

### 11.1 Parallelism, Progress & Crash Resilience (Phase P.0–P.2, prerequisite)
- [ ] `pbtes/simulation/solver.py`: accept `_run_id` for isolated cache path
- [ ] `pbtes/simulation/solver.py`: add optional `tqdm` progress bar wrapping the timestep loop in `run_quasi_steady_simulation()` — shows elapsed time, estimated remaining time, days/second rate
- [ ] `run_simulation.py`: add `--run-id` CLI flag; add `--no-progress` flag
- [ ] `run_parametric.py`: auto-generate `run_id` per job; add `--parallel N` + `--job-range` + `--no-progress` + `--dashboard-interval` flags; `mp.Pool` executor in `execute_sweeps()`; crash-recovery startup sequence (stale running→pending, partial CSV cleanup, orphaned cache deletion, .tmp manifest recovery); Spyder dashboard (IPython `clear_output` + summary table + tqdm-driven time estimates)
- [ ] `requirements.txt`: add `tqdm` if not already present
- [ ] New: `scripts/test_parallel_2proc.py`: standalone 2-process proof-of-concept

### 11.2 Post-Processing
- [ ] `pbtes/analysis/postprocess.py`: ensure `calculate_system_pump_power` handles both PI and SD; add `calculate_aggregate_metrics(df, meta) → dict`
- [ ] `pbtes/analysis/economics.py`: replace stub HX cost functions with UA-based correlations; add PTC cost = f(area) from literature; add contingency/indirect cost factors
- [ ] New: `scripts/run_aggregate_metrics.py`: read manifest, load each CSV, compute full metric set, write `parametric_metrics.csv`

### 11.3 Figures
- [ ] `scripts/run_assessment_06_figures.py`: full rewrite — read from manifest/metrics CSVs; use `results_reader.load_results()`; implement all 17 figures with journal-quality formatting (serif fonts, 300 DPI, SVG/PDF output, TeX math rendering)

---

## 12. Manuscript Integration — Which Section Gets Which Sweep

| Paper Section | Sweep | Figures | Key Message |
|---------------|-------|---------|-------------|
| **5.1** Baseline | Baseline PI | 02–07 | The system works: SF, mode distribution, TES dynamics |
| **5.2** Topology | Sweep C | 08 | PI vs SD: tradeoffs quantified |
| **5.3** Solar Multiple | Sweep A | 09, 10, 16 | Diminishing returns, optimal SM |
| **5.4** TES Sizing | Sweep B | 11, 12 | (D,H) optimal geometry identified |
| **5.5** Physical Robustness | Sweep D | 13 | Design is robust to parameter uncertainty |
| **5.6** HTF comparison | Sweep E | 14 | Solar Salt vs Air: magnitude of benefit |
| **6.1** Economics | All + post | 10, 12, 17 | LCOH minima, Pareto frontier |
| **6.2** Sensitivity | Sweep D + econ grid | 13 | Which economic parameters dominate? |

---

## 13. Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| **Cache collision under parallelism** | High | Solved by per-run isolated cache dirs via `--run-id` + gated by Stage 2/3/4 tests |
| **TESPy fails under `spawn` multiprocessing** | Medium | Fallback to `--job-range` + separate OS processes (no shared memory); gated by Stage 2 |
| **Air HTF simulation diverges** | High | If Air fails, do analytical comparison instead |
| **Design-point sensitivity to RNG/initial conditions** | Low | Use `np.random.seed()` per Solver init if Stage 1 shows divergence |
| **82 CPU-hours exceeds available time** | Medium | With N=8 parallelism → ~11 wall-clock hours (runs overnight); priority order: Aperture first, then TES volume subset to 15 interesting points if needed |
| **Economic sensitivity grid explodes** | Low | Economics is post-processed — instantaneous; already handled |
| **Windows file locking (antivirus, indexing)** | Low | Native Windows platform; if it occurs, exclude `.tespy_cache/` from antivirus scans |
| **Spyder kernel dies mid-sweep** | Medium | Crash-recovery startup resets `running`→`pending`, deletes partial CSVs and orphaned caches; re-running the same command resumes from the last completed job |
| **Power loss during manifest write** | Low | `.tmp` atomic rename pattern already in place; startup recovers from `.tmp` if newer than main manifest |

---

## 14. Summary of Deliverables

| Deliverable | Format | Location |
|-------------|--------|----------|
| Sweep manifest with all 55+ runs | CSV | `results/parametric_manifest.csv` |
| Enriched metrics manifest | CSV | `results/parametric_metrics.csv` |
| Economic sensitivity grid | CSV | `results/parametric_economic_sensitivities.csv` |
| 17 publication-quality figures | SVG + PDF | `article_results/06_figures/` |
| Exergoeconomic summary | CSV + MD | `article_results/07_synthesis/` |
| Article synthesis document | MD | `article_results/07_synthesis/ARTICLE_SYNTHESIS.md` |
| Parallel 2-process test script | Python | `scripts/test_parallel_2proc.py` |
