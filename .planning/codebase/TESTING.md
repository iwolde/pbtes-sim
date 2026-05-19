# Testing

## Current State

**0% test coverage** - No test files exist in the codebase.

## Validation Infrastructure

### Post-Hoc Validation
`errors_analysis.py` provides manual validation:
- Residual error analysis
- Convergence monitoring
- Performance metrics calculation

### Manual Testing Pattern
Testing performed via main entry point execution:
```bash
python mainV5_5.py
```

Results validated through:
- CSV output files
- Visual plots via matplotlib
- Manual inspection of results

## Recommended Test Strategy

### Framework
pytest with fixtures

### Key Test Areas

1. **ThermalEnergyStorage Class**
   - Initialization and parameter validation
   - Temperature distribution calculation
   - Charging/discharging behavior
   - Convergence criteria

2. **Solver Convergence Logic**
   - Mode selection accuracy
   - Temperature change tolerance (<5%)
   - Maximum iteration handling

3. **Network Creation**
   - Each of 6 modes creates valid TESPy network
   - Component connections
   - Parameter ranges

4. **Physics Calculations**
   - Stanton number
   - Heat transfer coefficients
   - Solar radiation models

### Fixtures

```python
@pytest.fixture
def tes_params():
    return {
        'tank_height': 10,
        'tank_diameter': 5,
        'fluid_mass': 1000,
    }

@pytest.fixture
def empty_network():
    nw = Network()
    return nw
```

### CI/CD

No CI/CD currently configured. Recommended:
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest tests/ -v --cov=coreV5
```

## Testing Recommendations

1. Start with unit tests for physics calculation functions
2. Add integration tests for TESPy network creation
3. Create fixtures for common configurations
4. Add property-based testing for solver convergence
5. Automate error_analysis.py as part of CI pipeline
