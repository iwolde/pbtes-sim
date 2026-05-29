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
print('Design state:')
print(f'  PTC: Q={s.ptc_field.Q.val/1e6:.3f}MW, A={s.ptc_field.A.val:.0f}, E={s.ptc_field.E.val:.0f}')
if hasattr(s, 'hot_tank_hx'):
    print(f'  Hot_Tank: Q={s.hot_tank_hx.Q.val/1e6:.3f}MW')
    print(f'  Hot_Tank pr={s.hot_tank_hx.pr.val:.4f}')
if hasattr(s, 'cold_tank_hx'):
    print(f'  Cold_Tank: Q={s.cold_tank_hx.Q.val/1e6:.3f}MW')
print(f'  Process_HX: Q={s.process_hx.Q.val/1e6:.3f}MW')
print()

# Offdesign - inspect before solve
so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                         HTF='INCOMP::NaK', topology='Series', tank_config='direct')
so.hot_tes.profile = np.ones(20) * 520.0
so.cold_tes.profile = np.ones(20) * 440.0
so.ptc_field_A_designed = A_des
so.set_operation_mode(TESmode='1', current_irr=1000,
                       profile=so.hot_tes.profile, prev_TES_lay='Charge', mode='offdesign')

print('After set_operation_mode (offdesign, before solve):')
print(f'  conn_02.T.is_set={so.conn_02.T.is_set}, val={so.conn_02.T.val}')
print(f'  conn_ht_ph.T.is_set={so.conn_ht_ph.T.is_set}, val={so.conn_ht_ph.T.val}')
print(f'  conn_05.T.is_set={so.conn_05.T.is_set}, val={so.conn_05.T.val}')
print(f'  conn_06.T.is_set={so.conn_06.T.is_set}, val={so.conn_06.T.val}')
print(f'  conn_10.T.is_set={so.conn_10.T.is_set}, val={so.conn_10.T.val}')
print(f'  PTC A.is_set={so.ptc_field.A.is_set}, val={so.ptc_field.A.val}')
print(f'  PTC E.is_set={so.ptc_field.E.is_set}, val={so.ptc_field.E.val}')

# Now try to solve
print()
print('Attempting offdesign solve...')
try:
    so.solve_network(mode='offdesign', TESmode='1', use_init_path=False)
    print(f'  Converged: {so.network.converged}')
except Exception as e:
    print(f'  EXCEPTION: {type(e).__name__}: {str(e)[:200]}')
    
print()
print('After solve attempt:')
print(f'  conn_02.T.is_set={so.conn_02.T.is_set}, val={so.conn_02.T.val}')
print(f'  conn_05.T.is_set={so.conn_05.T.is_set}, val={so.conn_05.T.val}')
print(f'  conn_06.T.is_set={so.conn_06.T.is_set}, val={so.conn_06.T.val}')
