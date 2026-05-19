# Phase 6: Thermodynamic Consistency - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensure the 1st and 2nd laws of thermodynamics hold across all system components and configurations (Series vs Parallel). Add automated tests for energy and mass balances in each solver iteration, checking both logical consistency and physical bounds.

</domain>

<decisions>
## Implementation Decisions

### Validation Mechanism (Energy Balances)
- **D-01:** Assert balances using independent Python analytical equations to keep checks independent of TESPy's internal black box.

### Mass Flow Routing Consistency
- **D-02:** Rely on TESPy's internal mass balance errors during network solve for mass flow consistency.

### Boundary Extremes
- **D-03:** Push the solver with extreme, non-physical boundary values in the tests to ensure it handles them correctly by crashing loudly and safely as intended.

### Topology Structure
- **D-04:** The topology of each configuration (parallel or series) enforces a concrete, fixed layout of the system.
- **D-05:** The two configurations are NOT meant to be strictly equivalent in energy generation. Tests should reflect that they are two different layouts meant to be compared for their benefits, rather than enforcing identical energy outputs.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase Status
- `.planning/phases/05-core-physics-unit-testing/05-CONTEXT.md` — Relies on pytest test structure and the isolation of test modes.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The newly created `tests/test_physics.py` and `tests/test_modes.py` will house these validations.

### Established Patterns
- Loud exceptions for physical anomalies.

</code_context>

<specifics>
## Specific Ideas

- "The topology of each configuration (either parallel or series) enforces a concrete layout of the system, that must not change. Every mode defined in the configuration is just saying what part of the plant is on and operating in which sense, but in a specific configuration (either parallel or series) the layout is fixed. They are not meant to be equivalent in energy generation, but actually we are comparing 2 different layouts and evaluating the benefits of each."

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-thermodynamic-consistency*
*Context gathered: 2026-04-27*