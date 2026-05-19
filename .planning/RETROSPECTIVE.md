# Retrospective

## Milestone: v1.0 — PBTES Pipeline MVP

**Shipped:** 2026-04-23
**Phases:** 4 | **Plans:** 8

### What Was Built
- Consolidated core simulation engine into `coreV5.py`, eliminating 136 bare exceptions and archiving legacy code.
- Extracted 6 duplicated TESPy network modes into a single config-driven `create_network` method.
- Replaced naive temperature limits in `get_mode` with smart control logic based on normalized SOC to maximize solar fraction.
- Implemented multi-variable dynamic relaxation for solver retries, ensuring >=98% convergence stability.
- Introduced Molten Salt as the unified HTF, removing heat exchangers in favor of direct Pipe components, supporting Parallel and Series topologies.
- Built an automated, parallel parameter-sweeping script (`parametric_sweep.py`) with dynamic LCOH integration (`economics.py`).
- Generated high-resolution, Q1 journal-ready SVG/PDF plots and a Markdown data synthesis document for academic publication.

### What Worked
- Taking time to stabilize the codebase before adding the parametric loops paid off by preventing compounding bugs.
- Using a fallback strategy for pump power allowed the model to maintain 98% convergence rates even when off-design pressure models failed.
- The use of Python's `concurrent.futures.ProcessPoolExecutor` drastically cut down the simulation time for parametric grids.

### What Was Inefficient
- Working without git installed meant that no version history/revert functionality was available locally, adding risk.

### Patterns Established
- Dynamic relaxation of TESPy solver initial guesses (`T0`, `m0`, `p0`, `h0`) on failure is the standard convergence pattern.
- High-res Matplotlib settings globally configured for publication quality (dpi=300, matching font sizings).

### Key Lessons
- Never hide exceptions during mathematical solving loops. Catching them and acting upon them yields better solver behavior than ignoring them.
- Always isolate old exploratory files to avoid confusion about the ground-truth codebase.

### Cost Observations
- Model mix: 100% sonnet for execution/verification, with opus for planning.
- Notable: Very high completion velocity when executing modular plans without worktree/git interference (though dangerous).

---

## Milestone: v1.1 — Robust Physics and Testing Framework

**Shipped:** 2026-04-29
**Phases:** 3 | **Plans:** 5

### What Was Built
- Established `pytest` runner executing independent testing suites (`test_physics.py`, `test_modes.py`, `test_transitions.py`).
- Parameterized bounds checking of Molten Salt constraints, verifying logical properties outside of the main loop.
- Built analytical Python assertions enforcing 1st and 2nd law energy balances per active configuration.
- Exhaustive NxN mode transition matrix implemented to verify that changing between states safely routes mass flows or safely falls back to Standby when divergence occurs.

### What Worked
- Avoiding `hypothesis` (fuzzing) in favor of strictly deterministic parameter grids ensured tests remained fast and understandable.
- Abstracting analytical Python equations separated the mathematical ground truths from TESPy's internal solver mechanics.

### What Was Inefficient
- Not having version control (git) locally prevents true "safety nets" during major architectural tests.

### Patterns Established
- Test modes in total isolation before attempting transition matrix sequences to prevent cross-contamination of state.
- Asserting fallback states (Mode 4) rather than strict success enforces a fault-tolerant software architecture over an overly brittle test suite.

### Key Lessons
- Topological series vs parallel layouts don't need to yield identical energy output; ensuring they accurately represent two distinct, correctly-routed physical configurations is the valid mathematical test.

### Cost Observations
- Model mix: 100% sonnet for planning, execution, and verification.
- Notable: Smaller isolated plans resulted in incredibly fast execution (<1 minute for most updates).

---

## Cross-Milestone Trends

| Metric | v1.0 | v1.1 |
|--------|------|------|
| Phases | 4 | 3 |
| Plans  | 8 | 5 |
| Tasks  | 14 | 5 |