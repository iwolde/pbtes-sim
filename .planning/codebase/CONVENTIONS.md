# Code Conventions

## Language & Style

- **Language:** Python 3.9+
- **Line length:** Not enforced; typical ~80-120 chars
- **Indentation:** 4 spaces (standard)

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `SolarThermalSystem`, `ThermalEnergyStorage` |
| Functions | snake_case | `calculate_stanton_number` |
| Variables | snake_case | `mass_flow`, `solar_irradiance` |
| Constants | SCREAMING_SNAKE | `GRAVITY`, `SOLAR_CONSTANT` |
| Parameters | snake_case | `tes_params`, `conexion_params` |

## Code Organization

### Core Modules
- `coreV5_*.py` - Main simulation engine (~2800 lines, multiple versions)
- `mainV5_*.py` - Entry points with configuration
- `errors_analysis.py` - Post-processing validation

### Configuration Pattern
Dictionary-based configuration used throughout:

```python
tes_params = {
    'tank_height': 10,
    'tank_diameter': 5,
    'fluid_mass': 1000,
}

component_params = {
    'receiver': {...},
    'heat_exchanger': {...},
}

conexion_params = {
    'pipe_diameter': 0.1,
    'insulation_thickness': 0.05,
}
```

### Six Operating Modes
Network creation split across methods:
- `create_network1()` - Solar + TES charging
- `create_network2()` - Solar to process only
- `create_network3()` - TES discharge
- `create_network4()` - Standby
- `create_network5()` - TES re-stratification
- `create_network6()` - Full TES charge

## Error Handling

**Current State:** Problematic - 136 bare `except Exception:` handlers found.

**Pattern (problematic):**
```python
try:
    # operation
except Exception:
    pass  # Silent failure
```

**Preferred pattern:**
```python
try:
    result = operation()
except ValueError as e:
    logger.error(f"Invalid parameter: {e}")
    raise
except RuntimeError as e:
    logger.warning(f"Solver did not converge: {e}")
```

## Physics Calculations

Key functions documented with docstrings:
- Stanton number calculation
- Heat transfer coefficients
- Thermal energy storage dynamics
- Solar radiation models

## Comments

Mixed English/Spanish:
```python
# Calcular eficiencia # Calculate efficiency
# Presión en Pa # Pressure in Pa
```

## Dependencies

```python
import numpy as np
import scipy.integrate
import pandas as pd
import matplotlib.pyplot as plt
from tespy.networks import Network
from tespy.components import Source, Sink, Pipe, HeatExchangerSimple
from CoolProp.HumidAirProp import HAPropsSI
```

## Recommendations

1. Extract 6 `create_network` methods into configuration-driven approach
2. Replace bare exceptions with specific error handling
3. Add type hints for function signatures
4. Consolidate coreV5 versions into single module
5. Standardize comment language
