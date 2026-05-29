import numpy as np, os, shutil, sys
sys.path.insert(0, '.')
from pbtes.network.system import SolarThermalSystem
from pbtes.config import baseline_config

tp, cp, cn = baseline_config()
tp['Initial temperature'] = 490

cache = '.tespy_cache'
for i in range(1, 7):
    p = os.path.join(cache, f'base_design_{i}')
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

# Design
s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                        HTF='INCOMP::NaK', topology='Series', tank_config='direct')
s.hot_tes.profile = np.ones(20) * 540.0
s.cold_tes.profile = np.ones(20) * 440.0
s.set_operation_mode(TESmode='3', current_irr=0, profile=s.hot_tes.profile,
                      prev_TES_lay='Charge', mode='design')
if hasattr(s, 'conn_15'): s.conn_15.set_attr(T=540)
s.solve_network(mode='design', TESmode='3')

# Offdesign WITH conn_06.T (simulating zinc pool)
for T06 in [480, 490, 500]:
    so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                             HTF='INCOMP::NaK', topology='Series', tank_config='direct')
    so.hot_tes.profile = np.ones(20) * 490.0
    so.cold_tes.profile = np.ones(20) * 490.0
    so.set_operation_mode(TESmode='3', current_irr=0, profile=so.hot_tes.profile,
                           prev_TES_lay='Charge', mode='offdesign')
    so.conn_06.set_attr(T=float(T06))  # zinc pool constraint
    try:
        so.solve_network(mode='offdesign', TESmode='3', use_init_path=True)
        print(f'T06={T06}: conv={so.network.converged}, T04={so.conn_04.T.val:.0f}C')
    except Exception as e:
        print(f'T06={T06}: FAIL {type(e).__name__}: {str(e)[:80]}')
