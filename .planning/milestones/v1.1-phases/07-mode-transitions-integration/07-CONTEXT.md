# Phase 7: Mode Transitions & Integration - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Guarantee stable convergence and physical validity during dynamic transitions between the 6 operating modes. Test the robustness of the system when moving from any state to any other state, ensuring the system safely handles invalid transitions or routes flow appropriately.

</domain>

<decisions>
## Implementation Decisions

### Transition Matrix Strategy
- **D-01:** Test all NxN mode combinations to catch edge-case routing errors. This exhaustive matrix will ensure that unexpected mode switches do not cause physical or mathematical anomalies.

### TES State Preservation
- **D-02:** Run true transient steps, passing the actual 1D array between modes during tests to preserve thermal inertia. Do not mock the TES thermal state.

### Convergence Fallback Handling
- **D-03:** If a transition fails to converge, the tests should assert that the system successfully catches the failure and falls back to Standby (Mode 4). Do not fail the test entirely for an expected convergence failure, as long as it handles the failure safely.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase Status
- `.planning/phases/06-thermodynamic-consistency/06-CONTEXT.md` — Relies on independent Python analytical equations and the understanding that topologies are fixed per run.
- `.planning/phases/05-core-physics-unit-testing/05-CONTEXT.md` — Relies on pytest test structure and the deprecation of Mode 5.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_modes.py` provides the framework for isolated mode tests and can be extended or used as a baseline for the transition matrix.
- `coreV5.py` and its fallback logic to Mode 4 when convergence fails.

### Established Patterns
- Loud exceptions for physical anomalies.
- Using `pytest.mark.parametrize` to run through combinations.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches based on the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-mode-transitions-integration*
*Context gathered: 2026-04-28*