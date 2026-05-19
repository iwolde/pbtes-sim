# Project

## What This Is
A robust, automated simulation and parametric analysis pipeline for evaluating the PBTES (Packed Bed Thermal Energy Storage) concept for high-temperature industrial solar heat.

## Core Value
To provide accurate, convergence-stable data (temperatures, metrics, economics) using Molten Salt as a unified HTF for a Q1 academic article, eliminating current codebase instabilities and manual workflows.

## Key Decisions
| Decision | Rationale | Outcome |
|----------|-----------|---------|
| HTF: Molten Salt | Avoid heat exchangers and unify the fluid | ✓ Good |
| Refactor First | Core engine has 136 bare exceptions and 0% test coverage; parametric sweeps require 98%+ convergence stability | ✓ Good |
| Pressure / Pump | Try to include pressure with Molten Salt, fallback to mass-flow post-processing if convergence fails | ✓ Good |
| Control Logic | Evolve beyond simple temperature limits to maximize solar fraction | ✓ Good |
| Automated Sweeps | Manual runs are too slow for an academic article's parametric analysis | ✓ Good |
| Simple LCOH | A Levelized Cost of Heat based on CAPEX/OPEX is sufficient for the article | ✓ Good |
| Extract Network Modes | Refactor 6 duplicated create_network methods into a single parameterized method | ✓ Good |
| Parallel/Series | Support both Series and Parallel configurations cleanly with Pipe components | ✓ Good |

## Current Milestone: v1.1 Robust Physics and Testing Framework

**Goal:** Ensure the simulation runs flawlessly with correct physical/mathematical models and comprehensive testing.

**Target features:**
- Validate parallel and series configuration design.
- Guarantee convergence across all operation modes.
- Implement physics and mathematical validations for every equation system and assumption.
- Propose and run testing scripts to assess advances and missing components.
- Build on top of previous implementation plans.

## Current Milestone: v1.2 Physics Validation and Simulation Hardening

**Goal:** Execute the established tests, fix bugs, and strictly validate the equation systems for both Parallel and Series configurations in steady and quasi-steady states.

**Target features:**
- Execute the automated test suite and debug identified physical or convergence anomalies.
- Explicitly separate and validate the equation systems for Series and Parallel configurations.
- Ensure every operational mode yields physically feasible and thermodynamically sound results in steady-state (single time step).
- Validate the full quasi-steady state simulation over time, ensuring real-world engineering feasibility.
- Refine physical boundaries and component integrations based on strict thermodynamics.

## Requirements

### Validated
- ✓ [Simulation engine baseline] — Existing code
- ✓ [TESPy network integration] — Existing code
- ✓ [CoolProp / HTF models] — Existing code
- ✓ CORE-01: Refactor simulation to eliminate bare exceptions and loud failures — v1.0
- ✓ CORE-02: Map thermodynamic boundaries to achieve ≥98% solver convergence — v1.0
- ✓ CORE-03: Improve control logic to maximize solar fraction and minimize auxiliary heat — v1.0
- ✓ ARCH-01: Support existing Parallel configuration cleanly — v1.0
- ✓ ARCH-02: Implement Series integration configuration — v1.0
- ✓ ARCH-03: Replace air with Molten Salt inside PBTES (remove heat exchangers) — v1.0
- ✓ METRICS-01: Calculate pump power (pressure modeling or mass-flow fallback) — v1.0
- ✓ ANALYSIS-01: Implement automated parametric sweep script — v1.0
- ✓ ANALYSIS-02: Produce publication-quality graphs — v1.0
- ✓ ANALYSIS-03: Formulate narrative for the scientific article based on results — v1.0
- ✓ ECON-01: Implement Simple LCOH economic model — v1.0
- ✓ CONF-01: Validate parallel vs series topological connections mathematically to ensure they are properly designed — v1.1
- ✓ CONF-02: Ensure mode transitions explicitly cover mass flow routing conditions, avoiding non-convergence — v1.1
- ✓ PHYS-01: Validate CoolProp constraint limits against Molten Salt (Solar Salt) boundaries — v1.1
- ✓ PHYS-02: Ensure analytical energy balances hold (1st and 2nd law) for each solver iteration — v1.1
- ✓ PHYS-03: Validate mathematical suppositions and control logic explicitly in the code — v1.1
- ✓ TEST-01: Propose and implement automated unit tests for single operation modes using `pytest` — v1.1
- ✓ TEST-02: Implement integration tests running transient scenarios across mode transitions — v1.1
- ✓ TEST-03: Run testing scripts to assess the advances and identify missing components or unhandled exceptions — v1.1

### Active
(None yet — initialize next milestone to add requirements)

### Out of Scope
- [Detailed Financial Model] — Simple LCOH is sufficient for the scope of the article
- [Weather-based predictive control logic] — Explicitly deferred to avoid forecasting complexity for this article

## Context

Shipped v1.1 Robust Physics and Testing Framework.
The simulation engine is now backed by comprehensive `pytest` suites.
Fundamental physics boundaries (Molten Salt limits) and explicit 1st and 2nd law energy balances are analytically verified for each iteration.
An exhaustive NxN dynamic mode transition test ensures that changing between any active state correctly routes mass flows or safely falls back to standby, confirming stability across Series and Parallel topologies.
Codebase remains ~46k LOC, now robustly tested against physical expectations.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-29 after v1.1 milestone*