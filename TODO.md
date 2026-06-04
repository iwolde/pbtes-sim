# TODO — PBTES Simulation Project

*Last updated: 2026-06-04*

---

## Phase C: Physics & Convergence (In Progress)

### Convergence Fixes

- [x] **INHOUSE_PTC_FIELD**: Integrate in-house PTC model (`ptc_model.py`) with backward compatibility (`use_inhouse_ptc` in `config.py`), covering Parallel/Indirect and Series/Direct configurations with full tests passing.
- [x] **MODE1_OFFDESIGN**: Fix Mode 1 offdesign divergence for Solar Salt
  - Symptom: TESPy mass flow hits sentinel `-1e12 kg/s`
  - Location: `pbtes/simulation/solver.py` → `attempt_to_solve()`, `pbtes/network/system.py`
  - Root cause: Solar Salt fluid properties pushed out of valid range during offdesign iteration
  - Approach: Better initial guesses, tighter bounds, staged initialization, temperature clamping

- [x] **MODE6_DESIGN**: Fix Mode 6 design failure
  - Symptom: `ValueError: too many parameters: 13 required, 14 supplied`
  - Location: `pbtes/network/system.py` → Mode 6 network setup
  - Root cause: One parameter over-specified in the Mode 6 network
  - Approach: Remove the redundant parameter (likely a connection T or Q that conflicts)

- [x] **CONV_PARALLEL_INDIRECT**: Converge all 6 modes for Parallel/Indirect (baseline)
- [x] **CONV_SERIES_INDIRECT**: Converge all 6 modes for Series/Indirect
- [x] **CONV_PARALLEL_DIRECT**: Converge all 6 modes for Parallel/Direct
- [x] **CONV_SERIES_DIRECT**: Converge all modes for Series/Direct (Redesigning and implementing direct PBTES coupling)
  - [x] **SD_MODE1_DIRECT_COUPLING**: Implement `SimpleHeatExchanger` closed-loop model for Mode 1 with direct coupling of `conn_ht_ph.T` and `conn_10.T` from the Schumann model, bypassing the `conn_05` setpoint constraint.
  - [x] **SD_MODE3_ANALYTICAL_MIXING**: Implement Option A analytical mixing for Mode 3 parallel discharging outside TESPy, running process-only TESPy network, and updating Schumann beds independently.
- [x] **CONV_RATE_95**: Achieve >= 95% timestep convergence rate for full-year simulation (100% transient convergence verified across all 4 layouts!)
- [x] **EBAL_CHECK**: Verify monthly energy balance error < 1%
- [x] **WINTER_CONTROL_LOGIC**: Implement seasonal winter control logic, insulated heating blankets, and PI Mode 6 Regimes A/B (Completed 90-day simulation and verified exergy & thermal solar fractions for both Parallel/Indirect and Series/Direct layouts)
- [x] **HEAT_LOSS_BUG_CORRECTION**: Corrected spatial discretization (dz vs HT) and convective area boundaries in PBTES heat loss calculations (reduced standby losses to realistic 1/20th levels)


### Code Infrastructure

- [ ] **CREATE_CONVERGENCE_PY**: Create `pbtes/analysis/convergence.py`
  - Error rate tables per mode and configuration
  - Anomaly detection for failed timesteps
  - Convergence diagnostics (iteration counts, residual history)

- [ ] **TEST_COVERAGE**: Review and expand test coverage for all 4 topologies
  - Add mode-specific tests for Series configurations
  - Add mode-specific tests for Direct configurations

### HTF Comparison

- [ ] **AIR_BASELINE**: Run full-year simulation with Air as HTF (Parallel/Indirect)
- [ ] **AIR_COMPARISON**: Compare Solar Salt vs Air results — solar fraction, temperatures, convergence

---

## Phase D: Results & Publication (Not Started)

### Full-Year Simulations

- [ ] **RUN_PARALLEL_INDIRECT**: Baseline 365-day run (Parallel/Indirect, Solar Salt, A=1000 m²)
- [ ] **RUN_SERIES_INDIRECT**: Series/Indirect 365-day run
- [ ] **RUN_PARALLEL_DIRECT**: Parallel/Direct 365-day run
- [ ] **RUN_SERIES_DIRECT**: Series/Direct 365-day run

### Parametric Sweeps

- [ ] **SWEEP_APERTURE**: Aperture area sweep (500, 750, 1000, 1500, 2000, 3000 m²) — 365d each
- [ ] **SWEEP_TES_VOLUME**: TES DxH grid (6D x 5H = 30 points) — 365d each
- [ ] **SWEEP_TOPOLOGY**: All 4 topology combos — 365d each (if not done above)

### Economic Analysis

- [ ] **LCOH_BASELINE**: Compute LCOH for baseline configuration
- [ ] **LCOH_TOPOLOGY**: Compare LCOH across all 4 topologies
- [ ] **LCOH_SENSITIVITY**: Sensitivity analysis — solar multiple, TES volume, discount rate
- [ ] **EXERGOECONOMICS**: Run exergoeconomic analysis for all topologies

### Figures (minimum 14)

- [ ] **FIG_SYSTEM_SCHEMATIC**: Parallel + Series plant layouts
- [ ] **FIG_ANNUAL_DNI**: DNI and ambient temperature year-long profile
- [ ] **FIG_TES_COLORMAP**: TES temperature profile colormap (full year)
- [ ] **FIG_SUMMER_DAY**: Summer day profile (powers, temps, modes)
- [ ] **FIG_WINTER_DAY**: Winter day profile
- [ ] **FIG_MONTHLY_ENERGY**: Monthly energy breakdown (stacked bar)
- [ ] **FIG_ZINC_POOL**: Zinc pool temperature year-long profile
- [ ] **FIG_PARALLEL_VS_SERIES**: SF comparison across topologies
- [ ] **FIG_DIRECT_VS_INDIRECT**: Tank config comparison
- [ ] **FIG_NAK_VS_AIR**: HTF comparison (Solar Salt vs Air)
- [ ] **FIG_SF_VS_SM**: Solar fraction vs solar multiple
- [ ] **FIG_LCOH_VS_VOLUME**: LCOH vs TES volume
- [ ] **FIG_TORNADO**: Sensitivity tornado chart
- [ ] **FIG_MODE_TRANSITIONS**: Operating mode transition matrix / Sankey

### Paper Draft

- [ ] **DRAFT_INTRO**: Section 1 — Introduction (decarbonization, PBTES, gap)
- [x] **DRAFT_SYSTEM**: Section 2 — System description (Drafted in article_methodology.txt)
- [x] **DRAFT_MODELS**: Section 3 — Mathematical models (Drafted in article_methodology.txt)
- [ ] **DRAFT_CASE**: Section 4 — Case study
- [ ] **DRAFT_RESULTS**: Section 5 — Results
- [x] **DRAFT_ECON**: Section 6 — Economic analysis (Drafted in article_methodology.txt)
- [ ] **DRAFT_DISCUSSION**: Section 7 — Discussion
- [ ] **DRAFT_CONCLUSIONS**: Section 8 — Conclusions

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
