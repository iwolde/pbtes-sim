# Roadmap

## Phases
- [x] **Phase 8: Parallel & Series Equation Validation** - System equations strictly separated and validated for both configurations (completed 2026-04-30)
- [ ] **Phase 9: Steady-State Mode Bug Fixing** - All operation modes yield correct, bug-free results in a single time step
- [ ] **Phase 10: Physics & Engineering Feasibility** - System operates within realistic thermodynamic bounds and engineering constraints
- [ ] **Phase A: Foundation & Agent Methodology** - Codebase cleanup, AGENTS.md rewrite, planning documents for publication pipeline
- [ ] **Phase B: Bug Fixes & Script Consolidation** - Critical bug fixes, unified run_simulation.py entry point
- [ ] **Phase C: Results Generation** - Baseline annual simulation, topology/HTF comparison, parametric sweep
- [ ] **Phase D: Publication Output** - Figures, synthesis tables, LCOH analysis, paper draft support

## Phase Details

### Phase 8: Parallel & Series Equation Validation
**Goal**: System equations are strictly separated and validated for both Parallel and Series configurations.
**Depends on**: None
**Requirements**: CONF-01, CONF-02
**Success Criteria** (what must be TRUE):
  1. The solver successfully runs the Parallel configuration without cross-contamination of Series equations.
  2. The solver successfully runs the Series configuration without cross-contamination of Parallel equations.
  3. Equation outputs for both topologies match theoretical thermodynamic expectations.
**Plans**: 1 plans
- [x] 08-01-PLAN.md — Strictly separate and validate both Parallel and Series configuration equations

### Phase 9: Steady-State Mode Bug Fixing
**Goal**: All operation modes yield correct, bug-free results in a single steady-state time step.
**Depends on**: Phase 8
**Requirements**: BUG-01, BUG-02
**Success Criteria** (what must be TRUE):
  1. The automated test suite executes completely with zero failures for steady-state scenarios.
  2. Running any single operation mode (1-6) for a single time step produces correct thermodynamic states.
  3. Identified convergence anomalies in previous tests are patched and no longer fail.
**Plans**: 2 plans
- [ ] 09-01-PLAN.md — Test Execution and Bug Fixing
- [ ] 09-02-PLAN.md — Assertion Hardening and Final Verification

### Phase 10: Physics & Engineering Feasibility
**Goal**: System simulation operates within realistic thermodynamic bounds and engineering constraints across the full quasi-steady state run.
**Depends on**: Phase 9
**Requirements**: PHYS-01, PHYS-02
**Success Criteria** (what must be TRUE):
  1. Full quasi-steady state simulations complete without violating Molten Salt temperature boundaries.
  2. Component states (heat exchangers, pumps, flow rates) remain within standard engineering operational limits throughout the simulation.
  3. Full system energy balances strictly hold for the entire transient simulation period.
**Plans**: TBD

### Phase A: Foundation & Agent Methodology
**Goal**: Clean up codebase, rewrite AGENTS.md, establish planning documents and conventions for the publication pipeline.
**Depends on**: Phase 8 (completed)
**Requirements**: None (infrastructure phase)
**Success Criteria** (what must be TRUE):
  1. AGENTS.md is up-to-date with current architecture, conventions, and workflow rules.
  2. Planning documents (STATE, ROADMAP, REQUIREMENTS, PAPER_OUTLINE) reflect the publication pipeline.
  3. Legacy dead code and unused scripts are identified and cleaned up.
**Plans**: TBD

### Phase B: Bug Fixes & Script Consolidation
**Goal**: Fix critical simulation bugs and consolidate all simulation entry points into a single `run_simulation.py`.
**Depends on**: Phase A
**Requirements**: BUG-01, BUG-02
**Success Criteria** (what must be TRUE):
  1. All 6 operation modes produce correct thermodynamic states in single-step tests.
  2. `run_simulation.py` replaces `sim_year.py`, `sim_week.py`, `sim_zinc.py` as the unified entry point.
  3. Test suite passes with zero failures (`pytest tests/ -x`).
**Plans**: TBD

### Phase C: Results Generation
**Goal**: Generate all simulation results needed for the publication: baseline annual run, topology/HTF comparisons, and parametric sweeps.
**Depends on**: Phase B
**Requirements**: PUB-01, PUB-02, PUB-03, PUB-06, PUB-07
**Success Criteria** (what must be TRUE):
  1. Full 365-day baseline simulation converges ≥ 95% of timesteps.
  2. Monthly energy balance error < 1%.
  3. All results stored as CSV in `results/` with metadata headers.
  4. Parallel vs Series and Direct vs Indirect comparisons completed.
  5. NaK vs Air HTF comparison completed.
  6. Parametric sweep over solar multiple and TES volume completed.
**Plans**: TBD

### Phase D: Publication Output
**Goal**: Produce all figures, synthesis tables, and LCOH analysis for the paper draft.
**Depends on**: Phase C
**Requirements**: PUB-04, PUB-05
**Success Criteria** (what must be TRUE):
  1. All 13+ key figures generated in SVG/PDF at 300 DPI.
  2. LCOH values within ±30% of literature benchmarks.
  3. Sensitivity analysis (tornado chart) completed.
  4. All outputs organized in `figures/` and `results/` directories.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 8. Parallel & Series Equation Validation | 1/1 | Complete   | 2026-05-04 |
| 9. Steady-State Mode Bug Fixing | 0/0 | Not started | - |
| 10. Physics & Engineering Feasibility | 0/0 | Not started | - |
| A. Foundation & Agent Methodology | 0/0 | **In progress** | - |
| B. Bug Fixes & Script Consolidation | 0/0 | Not started | - |
| C. Results Generation | 0/0 | Not started | - |
| D. Publication Output | 0/0 | Not started | - |
