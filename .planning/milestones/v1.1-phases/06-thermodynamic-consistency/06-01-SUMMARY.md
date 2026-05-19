---
phase: 06-thermodynamic-consistency
plan: 01
subsystem: physics-tests
tags: [tests, physics, topology, energy-balance]
requires: []
provides: [thermodynamic-consistency-tests, extreme-boundary-tests]
affects: [tests/test_physics.py, tests/test_modes.py]
tech-stack:
  added: []
  patterns: [pytest, independent-assertions]
key-files:
  created: []
  modified:
    - tests/test_physics.py
    - tests/test_modes.py
key-decisions:
  - Used independent calculation of fluid property enthalpy to verify 1st law of thermodynamics without relying entirely on TESPy's black-box solvers.
  - Implemented assertion limits for 2nd law checks explicitly preventing heat flowing from cold to hot.
  - Validated Parallel vs Series configuration topologies by explicitly testing node variations (presence of splitters).
  - Pushed boundary values to their extremes (`PR_Q = -1e12`) to assert the solver correctly errors out and fails safely via a raised exception.
metrics:
  duration: 5m
  completed_date: "2026-04-28"
---

# Phase 06 Plan 01: Thermodynamic Consistency Testing Summary

## Objective
Implemented thermodynamic consistency tests for energy balances (1st and 2nd law) and validated topological configurations with extreme bounds.

## What Was Done
1. **Added Energy Balances Check (PHYS-02):**
   - Added `test_energy_balances` inside `tests/test_physics.py`.
   - Verified that total energy entering from fluid equals the total stored energy inside the `ThermalEnergyStorage` to a reasonable tolerance level (1st Law).
   - Validated that the final node profile temperature stays within logical bounds (2nd Law).
2. **Topology Extreme Bounds (CONF-01):**
   - Added `test_topology_extreme_bounds` inside `tests/test_modes.py`.
   - Proved that Series and Parallel layouts enforce different explicit topological components (e.g. tracking `conn_04` inside Parallel mode that Series skips).
   - Showed the solver safely catches non-physical values through an intentional `PR_Q = -1e12` request which predictably throws a `RuntimeError` due to CoolProp/TESPy divergence limits.

## Deviations from Plan
None - plan executed exactly as written.

## Threat Flags
None.

## Known Stubs
None.

## Self-Check: PASSED
- [x] All automated tests executed via `pytest`.
- [x] Assertions implemented without direct reliance on TESPy internal verification methods.
- [x] `test_topology_extreme_bounds` properly isolates bounds using `pytest.raises`.
