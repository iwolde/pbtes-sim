# Roadmap

## Phases

- [x] **Phase A: Foundation & Agent Methodology** — Codebase cleanup, AGENTS.md, planning documents
- [x] **Phase B: Bug Fixes & Script Consolidation** — Critical bug fixes, unified run_simulation.py entry point
- [ ] **Phase C: Physics & Convergence** — Fix Mode 1 offdesign, Mode 6 design, converge all modes for all 4 topologies
- [ ] **Phase D: Results & Publication** — Full-year runs, parametric sweeps, figures, LCOH, paper draft

## Phase Details

### Phase A: Foundation & Agent Methodology
**Goal**: Clean up codebase, rewrite AGENTS.md, establish planning documents and conventions for the publication pipeline.
**Success Criteria**:
  1. AGENTS.md is up-to-date with current architecture, conventions, and workflow rules.
  2. Planning documents (STATE, ROADMAP, REQUIREMENTS, PAPER_OUTLINE) reflect the publication pipeline.
  3. Legacy dead code and unused scripts are identified and cleaned up.
**Status**: Complete

### Phase B: Bug Fixes & Script Consolidation
**Goal**: Fix critical simulation bugs and consolidate all simulation entry points into a single `run_simulation.py`.
**Success Criteria**:
  1. All 6 operation modes produce correct thermodynamic states in single-step tests.
  2. `run_simulation.py` replaces legacy scripts as the unified entry point.
  3. Test suite passes with zero failures (excluding known physics issues).
**Status**: Complete

### Phase C: Physics & Convergence
**Goal**: Fix TESPy solver convergence for all modes across all 4 topologies. Reach ≥95% convergence rate.
**Depends on**: Phase B
**Requirements**: PUB-01, PUB-02, PUB-03, PUB-06, PUB-07
**Success Criteria**:
  1. Full 365-day baseline simulation converges ≥ 95% of timesteps.
  2. Monthly energy balance error < 1%.
  3. All 6 modes converge for Parallel, Series, Direct, and Indirect configurations.
  4. Mode 6 design passes (no "too many parameters" error).
  5. Mode 1 offdesign converges for NaK fluid.
  6. All results stored as CSV in `results/` with metadata headers.
**Tasks**: See `TODO.md` — Phase C section.
**Status**: In progress

### Phase D: Publication Output
**Goal**: Produce all figures, synthesis tables, LCOH analysis, exergoeconomic analysis, and paper draft.
**Depends on**: Phase C
**Requirements**: PUB-04, PUB-05
**Success Criteria**:
  1. All 13+ key figures generated in SVG/PDF at 300 DPI.
  2. LCOH values within ±30% of literature benchmarks.
  3. Sensitivity analysis (tornado chart) completed.
  4. HTF comparison (NaK vs Air) completed.
  5. All outputs organized in `article_results/`.
**Tasks**: See `TODO.md` — Phase D section.
**Status**: Not started

## Progress

| Phase | Status |
|-------|--------|
| A. Foundation & Agent Methodology | Complete |
| B. Bug Fixes & Script Consolidation | Complete |
| C. Physics & Convergence | In progress |
| D. Publication Output | Not started |
