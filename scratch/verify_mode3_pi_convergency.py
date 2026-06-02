import sys
import os
import numpy as np

sys.path.append(r'c:\Users\iwold\OneDrive - Universidad Católica de Chile\Postdoc\Galvanizing solar PBTES\codigos')

from pbtes.config import baseline_config
from pbtes.simulation.solver import Solver
from pbtes.network.system import SolarThermalSystem

print("--- MODE 3 PI CONVERGENCE TEST ---")
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

print("Initializing design modes...")
solver.initialize_modes()
print(f"mode6_design_available: {solver.mode6_design_available}")
print(f"discharge_hx_kA: {solver.discharge_hx_kA:.1f} W/K")
print(f"discharge_tes_m_design: {solver.discharge_tes_m_design:.3f} kg/s")

# Let's perform a temperature sweep from 480 C to 580 C in steps of 2 C
# to see if Mode 3 offdesign converges cleanly and behaves as expected in Regime A and B.
print("\n--- Sweeping TES_top temperatures in Offdesign Mode 3 ---")
temperatures = np.arange(480, 582, 2.0)
results = []

for T_top in temperatures:
    # 1D Schumann bed profile: we can mock it by setting the top node to T_top,
    # and ramping down to T_bot = 400 C.
    profile = np.linspace(T_top, 400.0, 20)
    
    # Create SolarThermalSystem
    sys_o = SolarThermalSystem(
        rows=1,
        tes_params=tes_params,
        component_params=component_params,
        conexion_params=conexion_params,
        HTF='INCOMP::NaK',
        topology='Parallel',
        tank_config='indirect'
    )
    
    # Pass designed variables
    sys_o.discharge_hx_kA = solver.discharge_hx_kA
    sys_o.tes_charge_m = solver.discharge_tes_m_design
    
    # Set operation mode
    sys_o.set_operation_mode(
        TESmode='3',
        current_irr=0,
        profile=profile,
        prev_TES_lay='Charge',
        mode='offdesign'
    )
    
    # Manually configure the TES profile top connection just like in Solver
    sys_o.conn_15.set_attr(T=T_top)
    sys_o.conn_04.set_attr(T0=T_top - 15.0)
    sys_o.conn_16.set_attr(T0=T_top - 70.0)
    
    # Attempt to solve
    success = False
    error_msg = ""
    try:
        sys_o.solve_network(mode='offdesign', TESmode='3', use_init_path=True)
        success = sys_o.network.converged
    except Exception as e:
        success = False
        error_msg = str(e)
        
    if success:
        # Determine regime
        q_preheater = sys_o.preheater_hx.Q.val
        regime = "Regime A (Q_aux=0)" if abs(q_preheater) < 1.0 else f"Regime B (Q_aux={-q_preheater/1000.0:.1f} kW)"
        t_proc_in = sys_o.conn_05.T.val
        t_proc_out = sys_o.conn_06.T.val
        m_proc = sys_o.conn_05.m.val
        m_tes = sys_o.conn_15.m.val
        print(f"T_top = {T_top:.1f}°C: CONVERGED | {regime} | T_proc_in = {t_proc_in:.1f}°C | m_tes = {m_tes:.2f} kg/s")
        results.append((T_top, True, regime, t_proc_in, m_tes))
    else:
        print(f"T_top = {T_top:.1f}°C: FAILED! {error_msg}")
        results.append((T_top, False, "", 0.0, 0.0))

print("\n--- Summary ---")
all_converged = all(r[1] for r in results if r[0] >= 485.0)
print(f"All points >= 485°C converged: {all_converged}")
