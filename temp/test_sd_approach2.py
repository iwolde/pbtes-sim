"""Approach 2: Use DESIGN mode instead of offdesign for SD Mode 1."""
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

E_vals = [1000, 900, 800]
T_vals = [(520, 440), (500, 460), (490, 490)]

print('=== SD Mode 1 as DESIGN (no cache) ===')
for E in E_vals:
    for H, C in T_vals:
        s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                                HTF='INCOMP::NaK', topology='Series', tank_config='direct')
        s.hot_tes.profile = np.ones(20) * float(H)
        s.cold_tes.profile = np.ones(20) * float(C)
        s.set_operation_mode(TESmode='1', current_irr=float(E),
                              profile=s.hot_tes.profile, prev_TES_lay='Charge', mode='design')
        try:
            s.solve_network(mode='design', TESmode='1')
            conv = s.network.converged
            T2 = s.conn_02.T.val if conv else 'nan'
            Q = s.ptc_field.Q.val/1e6 if conv else 0
            print(f'E={E:4d} H={H:3d} C={C:3d}: conv={conv}, T02={T2}, Q={Q:.3f}MW')
        except Exception as e:
            print(f'E={E:4d} H={H:3d} C={C:3d}: EXC {type(e).__name__}: {str(e)[:60]}')
