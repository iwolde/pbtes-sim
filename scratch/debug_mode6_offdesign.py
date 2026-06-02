import sys
import os
import numpy as np

sys.path.append(r'c:\Users\iwold\OneDrive - Universidad Católica de Chile\Postdoc\Galvanizing solar PBTES\codigos')

from pbtes.config import baseline_config, zinc_pool_config
from pbtes.simulation.solver import Solver

tes_params, component_params, conexion_params = baseline_config()
zinc_params = zinc_pool_config()

# Set to exact state at Jan 1st 08:00
component_params['ptc_A'] = 1000.0
tes_params['Initial temperature'] = 460.0

solver = Solver(
    tes_params=tes_params,
    component_params=component_params,
    conexion_params=conexion_params,
    HTF='INCOMP::NaK',
    system_mode='Full',
    topology='Parallel',
    tank_config='indirect',
    zinc_pool_params=zinc_params
)

print("Initializing design states...")
solver.initialize_modes()
print(f"DESIGNED CHARGE HX kA: {solver.charge_hx_kA}")

print("\n--- RUNNING DEBUG MODE 6 OFFDESIGN SOLVE ---")
# Setup the state manually
sys6 = solver.solar_system # Wait, solar_system is now sys6 because it was initialized last in initialize_modes!
sys6.tes.profile = np.ones(20) * 458.18 # uniform profile close to 458 C

sys6.set_operation_mode(
    TESmode='6',
    current_irr=869.54,
    profile=sys6.tes.profile,
    prev_TES_lay='Charge',
    mode='offdesign'
)

# Print active connections and their properties
print("\nActive conns in sys6 network:")
for c in sys6.network.conns.index:
    conn = sys6.network.conns.loc[c, 'object']
    print(f"  {c}: T={conn.T.val} | T0={conn.T.val0} | m={conn.m.val} | m0={conn.m.val0} | p={conn.p.val} | p0={conn.p.val0}")

print("\nRunning network.solve(mode='offdesign') with iterinfo=True...")
try:
    sys6.network.set_attr(iterinfo=True)
    sys6.network.solve(mode='offdesign', design_path=os.path.join('.tespy_cache', 'base_design_6'), max_iter=40)
    print("SUCCESSFULLY CONVERGED!")
except Exception as e:
    print(f"FAILED TO CONVERGE: {e}")

print("\nConnection properties after solve attempt:")
for c in sys6.network.conns.index:
    conn = sys6.network.conns.loc[c, 'object']
    print(f"  {c}: T={conn.T.val} | T0={conn.T.val0} | m={conn.m.val} | m_SI={conn.m.val_SI} | p={conn.p.val} | p_SI={conn.p.val_SI}")

