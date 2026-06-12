# TODO — PBTES Simulation Project

*Last updated: 2026-06-10*

---

## Phase C: Physics & Convergence (Complete)

### Convergence Fixes

- [x] **INHOUSE_PTC_FIELD**: Integrate in-house PTC model with backward compatibility.
- [x] **MODE1_OFFDESIGN**: Fix Mode 1 offdesign divergence for Solar Salt.
- [x] **MODE6_DESIGN**: Fix Mode 6 design failure.
- [x] **CONV_ALL_LAYOUTS**: Converge all modes for PI (4-mode) and SD configurations.
- [x] **CONV_RATE_95**: Achieve >= 95% timestep convergence (100% across all layouts).
- [x] **EBAL_CHECK**: Verify monthly energy balance error < 1%.
- [x] **WINTER_CONTROL_LOGIC**: Winter logic with tank heating blankets.
- [x] **HEAT_LOSS_BUG_CORRECTION**: Corrected PBTES spatial discretization and area bugs.
- [x] **PI_MODE1_TCONSTRAINT**: Removed conn_05.T=520°C lock for PI Mode 1 offdesign; PTC outlet now floats up to ~560°C based on DNI. (Implemented in `pbtes/network/system.py`.)
- [x] **PI_4MODE_SCHEME**: 4-mode PI scheme (drop Mode 1, broaden Modes 5/6) designed, implemented, and verified:
  - Mode 5: `TES_bot < T_ptc_est − 20°C, SoC < 0.90` (high-T series charge)
  - Mode 6: `SoC < 0.80` (dedicated PTC→TES with aux process)
  - DNI-aware conn_02.T anchor for Mode 5 offdesign
  - In-house PTC gated (keeps 6-mode); standard PTC uses 4-mode
  - **Full-year simulation**: SF=54.5%, 100% convergence, PI now on par with SD
- [x] **DESIGN_PATH_BUG**: Fixed `design_path` not recalculated on Mode 4 fallback (`solver.py:1578`).
- [x] **STALE_COMPONENT_CLEANUP**: `create_network` now `delattr`s all component references from previous modes to prevent stale attributes contaminating the new network.
- [x] **MODE4_FALLBACK_INIT_PATH**: Changed Mode 4 fallback from `use_init_path=True` to `False` — Mode 4 doesn't need warm-start and its cache lacks HX CSVs.
- [x] **MODE5_COUPLING_SWITCH**: Fixed `_iterate_tes_coupling` to also check `hasattr(system, 'high_t_charge_hx')` alongside `charge_tes_hx` (`solver.py:872`).

### Known Minor Issues (Phase D)

- [ ] **TPTC_OUT_COLUMN**: `T_ptc_out` always reads 520°C in CSV — `_collect_step_signals` reads from PTC component (design value), not `conn_02.T` anchor for Mode 5.
- [ ] **AUX_TES_UNIT_BUG**: `aux_tes_energy_kJ` actually stores Joules (variable name misleading).
- [ ] **SOC_MODE3_HARDCODE**: `soc_mode3_minimum` hardcoded at 0.02 in `get_mode()` vs config value 0.10.
- [ ] **CONVERGENCE_PY**: Create `pbtes/analysis/convergence.py` for error rate tables and diagnostics.
- [ ] **PI_A1000_YEARLY**: Baseline PI 365-day run at A=1000 m².
- [ ] **SD_YEARLY**: Series/Direct 365-day run.


### Code Infrastructure

- [ ] **CREATE_CONVERGENCE_PY**: Create `pbtes/analysis/convergence.py`
  - Error rate tables per mode and configuration
  - Anomaly detection for failed timesteps
  - Convergence diagnostics (iteration counts, residual history)

- [ ] **TEST_COVERAGE**: Review and expand test coverage for PI and SD topologies

### HTF Comparison

- [ ] **AIR_BASELINE**: Run full-year simulation with Air as HTF (Parallel/Indirect)
- [ ] **AIR_COMPARISON**: Compare Solar Salt vs Air results — solar fraction, temperatures, convergence

---

## Phase D: Results & Publication (In Progress — see `.planning/PARAMETRIC_SWEEP_PLAN.md`)

### Phase D.1: Baseline Runs

- [ ] **RUN_PI_BASELINE**: Baseline PI 365-day run (A=1000 m², D=7.0 m, H=5.0 m)
- [ ] **RUN_SD_BASELINE**: Baseline SD 365-day run
- [ ] **POST_PROCESS_BASELINE**: Pump power + LCOH for baseline runs

### Phase D.2: Primary Sweeps (Aperture + TES Volume = 36 runs)

- [ ] **SWEEP_APERTURE**: Aperture area sweep (500–3000 m², 6 points × 2 topologies = 12 runs) — 365d
- [ ] **SWEEP_TES_VOLUME**: TES D×H grid (6D × 5H = 30 points) — PI, 365d

### Phase D.3: Secondary Sweeps

- [ ] **SWEEP_PHYSICAL**: Physical sensitivity (dp, ε, insulation) — 9 runs
- [ ] **SWEEP_HTF**: HTF comparison (NaK vs Air) — 2 runs

### Phase D.4: Economic Post-Processing

- [ ] **LCOH_ALL**: Compute LCOH for all sweep points
- [ ] **ECON_SENSITIVITY**: Economic sensitivity grid (discount rate, lifetime, prices)
- [ ] **EXERGOECONOMICS**: Exergoeconomic analysis for PI and SD

### Phase D.5: Figures (17 figures — see PARAMETRIC_SWEEP_PLAN.md §5)

- [ ] **FIG_01**: Plant schematic (PI + SD)
- [ ] **FIG_02**: Annual DNI + T_amb
- [ ] **FIG_03**: TES temperature colormap (year)
- [ ] **FIG_04**: Summer week profile
- [ ] **FIG_05**: Winter week profile
- [ ] **FIG_06**: Monthly energy breakdown
- [ ] **FIG_07**: Zinc pool temperature (year)
- [ ] **FIG_08**: PI vs SD SF
- [ ] **FIG_09**: SF vs aperture area
- [ ] **FIG_10**: LCOH vs aperture area (or SM)
- [ ] **FIG_11**: SF contour (D × H)
- [ ] **FIG_12**: LCOH contour (D × H)
- [ ] **FIG_13**: Sensitivity tornado
- [ ] **FIG_14**: HTF comparison (NaK vs Air)
- [ ] **FIG_15**: Mode transition Sankey
- [ ] **FIG_16**: Round-trip efficiency vs SM
- [ ] **FIG_17**: LCOH vs SF Pareto front

### Phase D.6: Synthesis & Paper

- [ ] **RUN_SYNTHESIS**: Generate ARTICLE_SYNTHESIS.md
- [ ] **DRAFT_INTRO**: Section 1 — Introduction
- [ ] **DRAFT_CASE**: Section 4 — Case study
- [ ] **DRAFT_RESULTS**: Section 5 — Results
- [ ] **DRAFT_DISCUSSION**: Section 7 — Discussion
- [ ] **DRAFT_CONCLUSIONS**: Section 8 — Conclusions
- [x] **DRAFT_SYSTEM**: Section 2 (article_methodology.txt)
- [x] **DRAFT_MODELS**: Section 3 (article_methodology.txt)
- [x] **DRAFT_ECON**: Section 6 (article_methodology.txt)

---

## Ongoing / Maintenance

- [ ] Keep `AGENTS.md` up to date when changing codebase structure or conventions
- [ ] Update `TODO.md` when completing or adding tasks
- [ ] Update `.planning/STATE.md` when project status changes
- [ ] Run `python -m pytest tests/ -x --tb=short` before every commit
- [ ] Never commit to `main` directly — always work on branches

---

## Legend

| Marker | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Completed |
