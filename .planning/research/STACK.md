# Stack Research

**Domain:** Automated Testing and Physics Validation
**Researched:** 2026-04-27
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pytest | >=8.0.0 | Automated testing framework | Industry standard for Python. Excellent parametrization capabilities which are essential for testing the 6 operating modes and various configuration designs (Series/Parallel). |
| hypothesis | >=6.0.0 | Property-based testing | Generates vast ranges of input data automatically. Critical for verifying that physical equations (like Stanton number, heat transfer coefficients) hold true across all valid state boundaries without writing thousands of manual test cases. |
| pytest-cov | >=5.0.0 | Test coverage tracking | Essential to address the historical "0% test coverage" metric and ensure all mathematical assumptions and codebase branches are validated. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy.testing | Latest | Numerical assertions | Built into the existing `numpy` dependency. Use for `assert_allclose` to handle floating-point tolerances when validating simulation outputs and convergence stability. |
| pint | >=0.23 | Dimensional analysis | Use to validate equations and mathematical models by ensuring unit consistency across complex heat transfer and thermodynamic formulas. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| tox or nox | Test environment matrix | Useful if testing across multiple Python versions or dependency versions (e.g. testing CoolProp updates), but might be overkill if strictly bound to one environment. |

## Installation

```bash
# Dev dependencies for testing and validation
pip install pytest pytest-cov hypothesis pint
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| pytest | unittest | Only if adding third-party dependencies is strictly prohibited. `unittest` is built-in but verbose and less suited for parametrized engineering tests. |
| hypothesis | Parameterized Pytest | If property-based testing proves too complex to set up, standard `@pytest.mark.parametrize` can cover known edge cases, though it won't find unknown edge cases. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| nose / nose2 | Abandoned and deprecated by the Python community. | pytest |
| Heavy Mocking | Mocking complex physical interactions (TESPy/CoolProp) can lead to tests that pass but physically fail. | Real component tests with constrained/isolated data or dummy fluids. |

## Stack Patterns by Variant

**If testing pure mathematical equations:**
- Use `hypothesis` combined with `numpy.testing.assert_allclose`
- Because it ensures the formulas don't break on floating-point extremes or unexpected valid inputs (like very low mass flow).

**If testing TESPy network convergence:**
- Use `pytest` with `@pytest.mark.parametrize` over the 6 modes
- Because we need deterministic regression testing for specific known states (Charge, Discharge, Standby, etc.).

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| pytest-cov | coverage | Ensure coverage package is compatible with the pytest version. |
| numpy.testing | TESPy / CoolProp | TESPy uses NumPy under the hood, ensure tolerances in tests align with TESPy solver tolerances (e.g., 1e-4). |

## Sources

- Pytest Documentation — Verified parametrization features for simulation modes
- Hypothesis Documentation — Verified applicability to scientific computing and floating-point math
- Pint Documentation — Verified for thermodynamic unit consistency checks

---
*Stack research for: Automated Testing and Physics Validation*
*Researched: 2026-04-27*