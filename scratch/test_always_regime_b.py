import sys
import os
import numpy as np

sys.path.append(r'c:\Users\iwold\OneDrive - Universidad Católica de Chile\Postdoc\Galvanizing solar PBTES\codigos')

from pbtes.config import baseline_config
from pbtes.simulation.solver import Solver
from pbtes.network.system import SolarThermalSystem

print("--- MODE 3 PI 'ALWAYS REGIME B' CONVERGENCE TEST ---")
tes_params, component_params, conexion_params = baseline_config()

# Setup Solver
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

temperatures = np.arange(480, 582, 2.0)
results = []

for T_top in temperatures:
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
    
    sys_o.conn_15.set_attr(T=T_top)
    
    # FORCE REGIME B ALWAYS (conn_05.T fixed to 520 C, preheater_hx.Q free)
    sys_o.conn_05.set_attr(T=520.0)
    sys_o.preheater_hx.set_attr(Q='var')
    
    # Starting values for offdesign
    sys_o.conn_04.set_attr(T0=T_top - 10.0)
    sys_o.conn_16.set_attr(T0=T_top - 40.0)
    
    success = False
    error_msg = ""
    try:
        sys_o.solve_network(mode='offdesign', TESmode='3', use_init_path=True)
        success = sys_o.network.converged
    except Exception as e:
        success = False
        error_msg = str(e)
        
    if success:
        q_preheater = sys_o.preheater_hx.Q.val
        # If q_preheater is negative, it means we have cooling, so actual Q_aux is 0
        q_aux_actual = max(0.0, q_preheater)
        t_proc_in_actual = sys_o.conn_04.T.val
        print(f"T_top = {T_top:.1f}°C: CONVERGED | Q_preheater = {q_preheater/1000.0:.1f} kW | Actual Q_aux = {q_aux_actual/1000.0:.1f} kW | Actual T_proc_in = {t_proc_in_actual:.1f}°C")
        results.append((T_top, True))
    else:
        print(f"T_top = {T_top:.1f}°C: FAILED! {error_msg}")
        results.append((T_top, False))

print("\n--- Summary ---")
all_converged = all(r[1] for r in results if r[0] >= 485.0)
print(f"All points >= 485°C converged: {all_converged}")
