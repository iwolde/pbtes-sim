import sys
import os
import numpy as np

# Add workspace root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pbtes.config import baseline_config
from pbtes.simulation.solver import Solver
from pbtes.network.system import SolarThermalSystem

tes_params, component_params, conexion_params = baseline_config()

solver = Solver(
    tes_params=tes_params,
    component_params=component_params,
    conexion_params=conexion_params,
    HTF='INCOMP::NaK',
    system_mode='Full',
    topology='Parallel',
    tank_config='indirect',
    zinc_pool_params=None
)

print("Initializing design modes...")
solver.initialize_modes()
print(f"mode6_design_available: {solver.mode6_design_available}")
