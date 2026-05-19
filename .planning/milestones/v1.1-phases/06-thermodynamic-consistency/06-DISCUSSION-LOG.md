# Phase 6: Thermodynamic Consistency - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 6-Thermodynamic Consistency
**Areas discussed:** Validation Mechanism (Energy Balances), Topology Invariance (Series vs Parallel), Mass Flow Routing Consistency, Boundary Extremes, Topology Structure

---

## Validation Mechanism (Energy Balances)

| Option | Description | Selected |
|--------|-------------|----------|
| Analytical Python Assertions (Recommended) | Assert balances using independent Python analytical equations. | ✓ |
| TESPy Internal Diagnostics | Extract internal TESPy energy diagnostics. | |

**User's choice:** Analytical Python Assertions (Recommended)
**Notes:** 

---

## Topology Invariance (Series vs Parallel)

| Option | Description | Selected |
|--------|-------------|----------|
| Aggregated Total Energy (Recommended) | Compare aggregated total energy over the simulation. | ✓ (Initially) |
| Strict Step-by-Step Equivalence | Require step-by-step exact equivalence (might fail due to numerical noise). | |

**User's choice:** Later clarified that the configurations are NOT strictly equivalent, but represent fixed layouts to be compared.
**Notes:** 

---

## Mass Flow Routing Consistency

| Option | Description | Selected |
|--------|-------------|----------|
| Junction Assertions (Recommended) | Assert mass_in == mass_out at every junction using dummy boundary values. | |
| TESPy Solvers | Rely on TESPy's internal mass balance errors during network solve. | ✓ |

**User's choice:** TESPy Solvers
**Notes:** 

---

## Boundary Extremes

| Option | Description | Selected |
|--------|-------------|----------|
| Test failure cases (Recommended) | Test with extreme, physically impossible values to ensure the solver crashes loudly as intended. | ✓ |
| Expected bounds only | Only test within the bounds of expected, physical operating conditions. | |

**User's choice:** Test failure cases (Recommended)
**Notes:** 

---

## Topology Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit verification (Recommended) | Manually construct and verify the connection lists for Series vs Parallel modes before running. | |
| Implicit verification | Trust the `create_network` output and only test the energy results. | |

**User's choice:** "The topology of each configuration (either parallel or series) enforces a concrete layout of the system, that must not change. Every mode defined in the configuration is just saying what part of the plant is on and operating in which sense, but in a specific configuration (either parallel or series) the layout is fixed. They are not meant to be equivalent in energy generation, but actually we are comparing 2 different layouts and evaluating the benefits of each."
**Notes:** This clarifies that series and parallel are two fixed layouts being compared, not identical equivalents.

---