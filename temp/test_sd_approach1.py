"""Test SD Mode 1 offdesign with pr-only tank design spec."""
import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 450
cp['ptc_A'] = 2000.0

cache = '.tespy_cache'
for i in range(1, 7):
    p = os.path.join(cache, f'base_design_{i}')
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

# Design
s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                        HTF='INCOMP::NaK', topology='Series', tank_config='direct')
s.hot_tes.profile = np.ones(20) * 520.0
s.cold_tes.profile = np.ones(20) * 440.0
s.set_operation_mode(TESmode='1', current_irr=1000, profile=s.hot_tes.profile,
                      prev_TES_lay='Charge', mode='design')
s.solve_network(mode='design', TESmode='1')
A_des = s.ptc_field_A_designed
print(f'Design: A={A_des:.0f}, Q={s.ptc_field.Q.val/1e6:.3f}MW, T02={s.conn_02.T.val:.0f}C')
print(f'  Hot_Tank Q={s.hot_tank_hx.Q.val/1e6:.3f}MW, Cold_Tank Q={s.cold_tank_hx.Q.val/1e6:.3f}MW')
print(f'  Hot_Tank Q.is_set={s.hot_tank_hx.Q.is_set}')
print()

# Offdesign at design conditions
E_vals = [1000, 900, 800]
T_vals = [(520, 440), (500, 460), (490, 490)]
for E in E_vals:
    for H, C in T_vals:
        so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                                 HTF='INCOMP::NaK', topology='Series', tank_config='direct')
        so.hot_tes.profile = np.ones(20) * float(H)
        so.cold_tes.profile = np.ones(20) * float(C)
        so.set_operation_mode(TESmode='1', current_irr=float(E),
                               profile=so.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
        try:
            so.solve_network(mode='offdesign', TESmode='1', use_init_path=True)
            conv = so.network.converged
            T2 = so.conn_02.T.val if conv else 'nan'
            print(f'E={E:4d} H={H:3d} C={C:3d}: conv={conv}, T02={T2}')
        except Exception as e:
            print(f'E={E:4d} H={H:3d} C={C:3d}: EXC {type(e).__name__}')
