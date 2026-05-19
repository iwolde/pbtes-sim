# Feature Research

**Domain:** Solar Thermal Simulation Validations & Testing
**Researched:** 2026-04-27
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Unit Tests for Math/Physics Functions | Need to trust individual correlations (Stanton number, heat transfer coefficients). | LOW | Validate against analytical or text book solutions using `pytest`. |
| Energy & Mass Balance Checks | First Law of Thermodynamics must hold across every component and time step. | MEDIUM | Global and per-component assertions. Crucial for detecting leaks or numerical instability. |
| Automated Test Suite Runner | Need a standardized way to execute all validations. | LOW | Utilize `pytest` to structure the test suite with clear pass/fail criteria. |
| Operation Mode Invariance | Modes 1-6 must behave consistently and transitions shouldn't violate physics. | MEDIUM | Write parameterized tests for boundaries of each operation mode. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Analytical Case Validation (e.g., Schumann) | Validating the 1D PBTES model against known analytical benchmarks adds massive academic credibility. | HIGH | Compare numerical temperature profile vs Schumann model. |
| Configuration Invariance Testing | Proving mathematically that `Parallel` vs `Series` integration modes conserve energy identically under identical conditions. | MEDIUM | Runs the exact same inputs through both modes and asserts final energetic equivalence. |
| Automated Convergence Stress-Testing | Guarantees the 98% convergence rate under extreme edge-case boundaries. | HIGH | Sweeping through edge-case irradiance and temperature conditions specifically designed to try and break the solver. |
| Continuous Integration (CI) Metrics | Automatically running a miniature LCOH/Plant Factor sweep on commits to prevent regression. | HIGH | Ensures code changes don't shift economic/performance results over time. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| 3D CFD Integration for Validation | Complete spatial accuracy. | Too computationally expensive, massive overhead, breaks fast parametric sweeps. | Stick to 1D analytical/empirical correlations with fine nodal discretization. |
| Third-party Library Internal Testing | Ensuring properties are perfectly calculated. | Redundant; CoolProp and TESPy are already thoroughly validated by their authors. | Trust library outputs; validate only our specific usage, component assembly, and logic boundaries. |

## Feature Dependencies

```
[Unit Tests for Math/Physics]
    └──requires──> [Automated Test Suite Runner]

[Energy & Mass Balance Checks]
    └──requires──> [Automated Test Suite Runner]
    
[Configuration Invariance Testing]
    └──requires──> [Energy & Mass Balance Checks]

[Automated Convergence Stress-Testing] ──enhances──> [Operation Mode Invariance]
```

### Dependency Notes

- **[Unit Tests for Math/Physics] requires [Automated Test Suite Runner]:** Need a framework to execute and report on the physics validations.
- **[Energy & Mass Balance Checks] requires [Automated Test Suite Runner]:** Must be systematically tested across various scenarios.
- **[Configuration Invariance Testing] requires [Energy & Mass Balance Checks]:** To prove Parallel/Series are equivalent, both must first demonstrably obey energy conservation.
- **[Automated Convergence Stress-Testing] enhances [Operation Mode Invariance]:** Edge-case stress testing inherently pushes the boundaries of mode transition stability.

## MVP Definition

### Launch With (v1.1)

Minimum viable product — what's needed to validate the concept.

- [x] Automated Test Suite Runner — Base infrastructure to run validations (`pytest`).
- [x] Unit Tests for Math/Physics Functions — Essential to trust the core physics components (Stanton number, HTC).
- [x] Energy & Mass Balance Checks — Validates basic thermodynamic soundness.
- [x] Configuration Invariance Testing — Directly addresses the milestone requirement to validate parallel and series design.

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] Operation Mode Invariance — Validate all mode transitions.
- [ ] Analytical Case Validation (Schumann) — To cement academic credibility for the Q1 article.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Automated Convergence Stress-Testing — Too complex for MVP, current 98% baseline is sufficient.
- [ ] Continuous Integration (CI) Metrics — Adds overhead to iteration speed right now.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Automated Test Suite Runner | HIGH | LOW | P1 |
| Unit Tests for Math/Physics | HIGH | LOW | P1 |
| Energy & Mass Balance Checks | HIGH | MEDIUM | P1 |
| Configuration Invariance Testing | HIGH | MEDIUM | P1 |
| Analytical Case Validation (Schumann) | HIGH | HIGH | P2 |
| Operation Mode Invariance | MEDIUM | MEDIUM | P2 |
| Automated Convergence Stress-Testing | MEDIUM | HIGH | P3 |
| CI Metrics | MEDIUM | HIGH | P3 |

## Competitor Feature Analysis

| Feature | System Advisor Model (SAM) | TRNSYS | Our Approach |
|---------|----------------------------|--------|--------------|
| Component Validation | Pre-compiled, black-box validation. | Fortran component-level testing. | Open-source, explicit Python `pytest` functions for every equation. |
| Mass/Energy Balance | Enforced internally by solver. | Component-specific tolerance limits. | Explicit global & local assertions at every quasi-steady time step. |
| Test Runner | Proprietary UI-based tests. | External scripts required. | Standardized Python `pytest` compatible with modern CI. |

## Sources

- Project Context (`PROJECT.md`) - Milestone v1.1 Target features
- Standard Academic Modeling Practices (1D PBTES Schumann models)
- Pytest framework capabilities

---
*Feature research for: Solar Thermal Simulation Validations & Testing*
*Researched: 2026-04-27*
