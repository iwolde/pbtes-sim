# Phase 5: Core Physics & Unit Testing - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensure fundamental physical properties and math functions are tested and correct at the component level. Guarantee that the equation systems for the operational modes (excluding Mode 5) are correctly stated with logical assumptions and robust convergence properties.

</domain>

<decisions>
## Implementation Decisions

### Testing Framework and Approach
- **D-01:** Standardize on `pytest` using `pytest.mark.parametrize` grids to test the physical equations and bounds. We will avoid Hypothesis (fuzzing) in favor of deterministic boundary validations.
- **D-02:** Test the operating modes in **complete isolation**. Each mode test should build and teardown its environment to verify the core equations without cross-contamination.

### Mode 5 Deprecation / Physics Validation
- **D-03:** Completely avoid/deprecate Mode 5 (the legacy Re-stratification loop). 
- **D-04:** Focus physics validation explicitly on ensuring that every remaining mode (1, 2, 3, 4, 6) is correctly stated in the equation system, with logical mathematical assumptions and verified, stable convergence.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Codebase Status
- `.planning/research/STACK.md` — Libraries selected for validation (pytest, numpy.testing).
- `.planning/research/FEATURES.md` — Core features expected of the physics testing framework.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `errors_analysis.py` can provide analytical baselines that the unit tests can assert against.

### Established Patterns
- The single, parameterized `create_network` method in `coreV5.py` will allow `pytest` to easily initialize isolated network instances for testing the specific modes.

</code_context>

<specifics>
## Specific Ideas

- "Avoid mode 5 completely, focus on that every mode is correctly stated in the equation system with logical assumptions and correct convergency"

</specifics>

<deferred>
## Deferred Ideas

- Sequential transition testing (Testing how state carries over from Mode 2 to Mode 3) has been deferred to Phase 7.

</deferred>

---

*Phase: 05-core-physics-unit-testing*
*Context gathered: 2026-04-27*