# Phase 8: Parallel & Series Equation Validation - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

System equations are strictly separated and validated for both Parallel and Series configurations. This phase ensures that the mathematical and thermodynamic models uniquely map to each topology without cross-contamination.

</domain>

<decisions>
## Implementation Decisions

### Validation Approach
- **D-01:** Run tests with specific inputs designed to fail if cross-contamination occurs (Input-specific failure tests).

### Theoretical Baselines
- **D-02:** Calculate expected values analytically in Python during the test (Dynamic analytical bounds) rather than relying on static CSV files.

### Test Execution Boundaries
- **D-03:** Instantiate a completely new Solver and System for each topology test (Independent instances) to prevent state bleed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase Status
- `.planning/codebase/ARCHITECTURE.md` — Reference for network structure and mode boundaries.
- `.planning/codebase/STRUCTURE.md` — Overview of test/script directories.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing `pytest` infrastructure in `tests/test_physics.py` and `tests/test_modes.py`.
- `coreV5.py` parameterized `create_network` containing series and parallel configuration branches.

### Established Patterns
- Isolated test cases building new instances of `SolarThermalSystem` per parameterization.

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

*Phase: 08-parallel-series-equation-validation*
*Context gathered: 2026-04-29*