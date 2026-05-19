# Project Research Summary

**Project:** Automated simulation and parametric analysis pipeline for PBTES
**Domain:** Automated Testing and Physics Validation
**Researched:** 2026-04-27
**Confidence:** HIGH

## Executive Summary

The research focuses on establishing an automated testing and validation framework for the 1D PBTES solar thermal simulation. The framework must guarantee convergence stability, energy and mass balance, and mathematical correctness of heat transfer correlations.

The recommended approach leverages `pytest` and `hypothesis` for robust property-based testing and deterministic validation of the six operating modes. This addresses historical "0% test coverage" and provides confidence in the physics models.

Key risks include over-complicating validation (e.g., attempting 3D CFD) or testing external libraries (CoolProp, TESPy) instead of internal logic. These are mitigated by adhering to explicit Python pytest validations against known analytical models (e.g., Schumann).

## Key Findings

### Recommended Stack

The testing strategy relies on industry-standard Python testing tools to cover everything from simple unit math to complex system property boundaries.

**Core technologies:**
- pytest: Automated testing framework — Industry standard, excellent parametrization for testing the 6 operating modes.
- hypothesis: Property-based testing — Generates vast ranges of input data automatically to verify physical equations across valid state boundaries.
- pytest-cov: Test coverage tracking — Essential to address 0% test coverage and ensure all branches are validated.

### Expected Features

The required validations focus on physics correctness and basic operation, while differentiating features involve complex system interactions.

**Must have (table stakes):**
- Automated Test Suite Runner — Base infrastructure to run validations (`pytest`).
- Unit Tests for Math/Physics Functions — Essential to trust the core physics components (Stanton number, HTC).
- Energy & Mass Balance Checks — Validates basic thermodynamic soundness.
- Configuration Invariance Testing — Proves mathematically that Parallel vs Series modes conserve energy identically.

**Should have (competitive):**
- Operation Mode Invariance — Validate all mode transitions.
- Analytical Case Validation (Schumann) — Validating the 1D PBTES model against known analytical benchmarks for academic credibility.

**Defer (v2+):**
- Automated Convergence Stress-Testing — Guarantees convergence under extreme boundaries.
- Continuous Integration (CI) Metrics — Automatically running miniature LCOH sweeps on commits.

### Architecture Approach

The architecture separates infrastructure from domain-specific validations to keep tests fast and maintainable.

**Major components:**
1. Test Suite Infrastructure — Orchestrates parametrized tests across 6 operating modes.
2. Physics Assertions — Global and local component mass/energy balance validations per time step.
3. Property-based Generators — Provides randomized valid state ranges for equation validation.

### Critical Pitfalls

These pitfalls represent the most likely ways the validation project could fail or become unmaintainable.

1. **Testing Third-party Libraries** — Redundant; CoolProp and TESPy are already validated. Trust library outputs and validate only specific assembly logic.
2. **Attempting 3D CFD Integration** — Too computationally expensive, breaks fast parametric sweeps. Stick to 1D analytical/empirical correlations with fine nodal discretization.
3. **Heavy Mocking** — Mocking complex physical interactions can lead to false positives. Use real component tests with isolated data.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Core Physics Validation
**Rationale:** Fundamental trust in the physics equations must be established before higher-level behavior can be evaluated.
**Delivers:** Setup of `pytest` runner, coverage tracking, and unit tests for core math/physics functions.
**Addresses:** Automated Test Suite Runner, Unit Tests for Math/Physics Functions.
**Avoids:** Heavy Mocking of complex interactions.

### Phase 2: Thermodynamic Consistency
**Rationale:** Once individual physics components are validated, the system must respect the First Law of Thermodynamics across components.
**Delivers:** Energy & Mass balance assertions and configuration invariance testing (Parallel vs Series).
**Uses:** pytest, numpy.testing, pint.
**Implements:** Test Suite Infrastructure and Physics Assertions.

### Phase 3: Mode Transitions & Benchmarking
**Rationale:** To prepare for the Q1 article, the model must transition reliably between all 6 modes and align with standard benchmarks.
**Delivers:** Operation mode invariance testing and Schumann analytical case validation.

### Phase Ordering Rationale

- Validation must start bottom-up: from individual equations to component balances to full system modes.
- This grouping ensures basic thermodynamic soundness before complex mode transitions are evaluated.
- It avoids the pitfall of building fragile mode tests on unverified mathematical foundations.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** Validating against Schumann analytical model requires deep domain knowledge and verifying benchmark data structure.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Setting up pytest and hypothesis is a standard pattern with well-documented practices.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Established standard testing libraries in Python. |
| Features | HIGH | Clear MVP boundary defined in FEATURES.md. |
| Architecture | MEDIUM | ARCHITECTURE.md missing; inferred from project context. |
| Pitfalls | MEDIUM | PITFALLS.md missing; inferred from anti-features. |

**Overall confidence:** HIGH

### Gaps to Address

- Architecture Details: Need formal review of existing `coreV5_*.py` and `mainV5_*.py` for test injection points.
- Missing Documentation: ARCHITECTURE.md and PITFALLS.md were not found during initial research synthesis.

## Sources

### Primary (HIGH confidence)
- STACK.md — Stack recommendations
- FEATURES.md — Feature prioritizations and MVP definition
- PROJECT.md — Global context