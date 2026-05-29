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

# Design as original
s = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                        HTF='INCOMP::NaK', topology='Series', tank_config='direct')
s.hot_tes.profile = np.ones(20) * 520.0
s.cold_tes.profile = np.ones(20) * 440.0
s.set_operation_mode(TESmode='1', current_irr=1000, profile=s.hot_tes.profile,
                      prev_TES_lay='Charge', mode='design')
s.solve_network(mode='design', TESmode='1')
A_des = s.ptc_field_A_designed
print(f'Design: A={A_des:.0f}')

# Test: solve same network in DESIGN mode and OFFDESIGN mode
print()
print('=== Solve SAME network in both modes (no cache loading) ===')

# Fresh network, design constraints
so = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                         HTF='INCOMP::NaK', topology='Series', tank_config='direct')
so.hot_tes.profile = np.ones(20) * 520.0
so.cold_tes.profile = np.ones(20) * 440.0

# Set up as design mode
so.set_operation_mode(TESmode='1', current_irr=1000, profile=so.hot_tes.profile,
                       prev_TES_lay='Charge', mode='design')
try:
    so.solve_network(mode='design', TESmode='1')
    print(f'Design solve: conv={so.network.converged}, T02={so.conn_02.T.val:.0f}C')
except Exception as e:
    print(f'Design solve FAIL: {type(e).__name__}: {str(e)[:80]}')

# Fresh network, offdesign (NO design cache)
cache = '.tespy_cache'
for i in range(1, 7):
    p = os.path.join(cache, f'base_design_{i}')
    if os.path.exists(p): shutil.rmtree(p, ignore_errors=True)

so2 = SolarThermalSystem(rows=1, tes_params=tp, component_params=cp, conexion_params=cn,
                          HTF='INCOMP::NaK', topology='Series', tank_config='direct')
so2.hot_tes.profile = np.ones(20) * 520.0
so2.cold_tes.profile = np.ones(20) * 440.0
so2.set_operation_mode(TESmode='1', current_irr=1000, profile=so2.hot_tes.profile,
                        prev_TES_lay='Charge', mode='offdesign')

# Manually set PTC A for consistency
so2.ptc_field.set_attr(A=A_des, E=1000)

# Clear Q from tank HXs
if hasattr(so2, 'hot_tank_hx'):
    so2.hot_tank_hx.set_attr(Q=None)
if hasattr(so2, 'cold_tank_hx'):
    so2.cold_tank_hx.set_attr(Q=None)

# Don't use design cache
print()
print('=== Offdesign WITHOUT design cache ===')
print(f'Before solve: conn_02.T.is_set={so2.conn_02.T.is_set}')
print(f'  conn_ht_ph.T.is_set={so2.conn_ht_ph.T.is_set}, val={so2.conn_ht_ph.T.val}')
print(f'  conn_10.T.is_set={so2.conn_10.T.is_set}, val={so2.conn_10.T.val}')
print(f'  hot_tank_hx.Q.is_set={so2.hot_tank_hx.Q.is_set}')
print(f'  PTC A.is_set={so2.ptc_field.A.is_set}, val={so2.ptc_field.A.val}')

try:
    so2.network.solve(mode='offdesign', max_iter=200)
    print(f'After solve: conv={so2.network.converged}')
    if so2.network.converged:
        print(f'  T02={so2.conn_02.T.val:.0f}C, T05={so2.conn_05.T.val:.0f}C, T06={so2.conn_06.T.val:.0f}C')
        print(f'  m_dot={so2.conn_02.m.val:.2f} kg/s')
except Exception as e:
    print(f'FAIL: {type(e).__name__}: {str(e)[:120]}')
