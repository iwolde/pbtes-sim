"""Test: SD Mode 1 solved as design mode (no cache), with proper PTC params."""
import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 450

E_vals = [1000, 900, 800]
T_vals = [(520, 440), (500, 460), (490, 490)]

print('=== SD M1: offdesign setup, solve as design ===')
for pt in [2000, 1000]:
    cp['ptc_A'] = float(pt)
    print(f'\nPTC A={pt}:')
    for E in E_vals:
        for H, C in T_vals:
            s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                                    HTF='INCOMP::NaK', topology='Series', tank_config='direct')
            s.hot_tes.profile = np.ones(20) * float(H)
            s.cold_tes.profile = np.ones(20) * float(C)
            s.set_operation_mode(TESmode='1', current_irr=float(E),
                                  profile=s.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')
            # Set PTC E (like the solver does)
            s.ptc_field.set_attr(E=float(E))
            try:
                s.network.set_attr(iterinfo=False)
                s.network.solve(mode='design', max_iter=200)
                conv = s.network.converged
                T2 = s.conn_02.T.val if conv else 'nan'
                Q = s.ptc_field.Q.val/1e6 if conv else 0
                print(f'{'OK' if conv else 'NO'} E={E:4d} H={H:3d} C={C:3d}: T02={T2} Q={Q:.3f}MW')
            except Exception as e:
                print(f'EX E={E:4d} H={H:3d} C={C:3d}: {type(e).__name__}')
