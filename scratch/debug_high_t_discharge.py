import sys
import os
import numpy as np

sys.path.append(r'c:\Users\iwold\OneDrive - Universidad Católica de Chile\Postdoc\Galvanizing solar PBTES\codigos')

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

solver.initialize_modes()

T_top = 560.0
profile = np.linspace(T_top, 400.0, 20)

sys_o = SolarThermalSystem(
    rows=1,
    tes_params=tes_params,
    component_params=component_params,
    conexion_params=conexion_params,
    HTF='INCOMP::NaK',
    topology='Parallel',
    tank_config='indirect'
)

sys_o.discharge_hx_kA = solver.discharge_hx_kA
sys_o.tes_charge_m = solver.discharge_tes_m_design

sys_o.set_operation_mode(
    TESmode='3',
    current_irr=0,
    profile=profile,
    prev_TES_lay='Charge',
    mode='offdesign'
)

# Manually configure the TES profile top connection just like in Solver
sys_o.conn_15.set_attr(T=T_top)

# Set starting values carefully
sys_o.conn_04.set_attr(T0=T_top - 10.0)
sys_o.conn_16.set_attr(T0=T_top - 40.0)

print("\nConnections before solve:")
for c in sys_o.network.conns.index:
    conn = sys_o.network.conns.loc[c, 'object']
    print(f"  Connection: {c}")
    print(f"    Source: {conn.source.label} -> Target: {conn.target.label}")
    print(f"    Fluid: {conn.fluid.val} | Fluid0: {conn.fluid.val0}")
    print(f"    T: {conn.T.val} | T0: {conn.T.val0}")
    print(f"    p: {conn.p.val} | p0: {conn.p.val0}")
    print(f"    m: {conn.m.val} | m0: {conn.m.val0}")

print("\nStarting network solve with max_iter=100...")
try:
    sys_o.network.solve(mode='offdesign', design_path=os.path.join('.tespy_cache', 'base_design_3'), max_iter=100, init_path=os.path.join('.tespy_cache', 'base_design_3'))
except Exception as e:
    print(f"\nSolve failed: {e}")
