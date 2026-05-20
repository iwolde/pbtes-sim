"""Test Mode 5 design."""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for d in ['.tespy_cache']:
    if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)

from pbtes.config import baseline_config
from pbtes.network.system import SolarThermalSystem

tp, cp, np_ = baseline_config()
init_t = tp['Initial temperature']; tp['Initial temperature'] = 490

s2 = SolarThermalSystem(tes_params=dict(tp), component_params=dict(cp),
    conexion_params=dict(np_), HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')

import numpy as np
s2.tes.profile = np.ones(20) * 490
profile = s2.tes.profile
prev = 'Charge'

# Create network Mode 5 + design
s2.create_network(mode=5, design_mode='design')

# Set operation-specific params
TES_bot = 490
T14_val = min(TES_bot + 60, 580)
s2.conn_14.set_attr(T=T14_val)
s2.conn_10.set_attr(T=None)
s2.preheater_hx.set_attr(pr=1.0)
# CHX ttd_l already set by design block

# The CC is the returned fluid
s2.conn_06.set_attr(T=480)  # boundary already set by design block
s2.process_hx.set_attr(Q=-450000)  # boundary already set by design block

try:
    s2.network.solve('design', max_iter=100)
    converged = s2.network.results['iterations'] < 100
    print(f"Converged: {converged}")

    for c_name in ['conn_01','conn_02','conn_05','conn_06','conn_10','conn_13','conn_14']:
        c = getattr(s2, c_name, None)
        if c:
            print(f"  {c_name}: T={c.T.val:.1f}°C, m={c.m.val_SI:.1f} kg/s, "
                  f"p={c.p.val_SI:.1f} bar, h={c.h.val_SI/1000:.1f} kJ/kg")
    print(f"PTC Q={s2.ptc_field.Q.val/1e6:.2f} MW, E={s2.ptc_field.E.val:.0f} W/m2")
    print(f"CHX Q={s2.charge_tes_hx.Q.val/1e6:.2f} MW, kA={getattr(s2.charge_tes_hx, 'kA', None)}")
except Exception as e:
    print(f"Error: {e}")
