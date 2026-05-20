"""Test Mode 5 offdesign."""
import os, shutil, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for d in ['.tespy_cache']:
    if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)

from pbtes.config import baseline_config
from pbtes.simulation.solver import Solver
from pbtes.network.system import SolarThermalSystem

tp, cp, np_ = baseline_config()
init_t = tp['Initial temperature']; tp['Initial temperature'] = init_t

s = Solver(tes_params=tp, component_params=cp, conexion_params=np_,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
s.initialize_modes()
s.tes_params['Initial temperature'] = init_t
s.current_irr = 0

for E in [1000, 800, 600]:
    for T_bot in [400, 500]:
        s2 = SolarThermalSystem(tes_params=dict(tp), component_params=dict(cp),
            conexion_params=dict(np_), HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        s2.tes.profile = np.ones(20) * T_bot
        s2.set_operation_mode(TESmode='5', current_irr=E, mode='offdesign',
            profile=s2.tes.profile, prev_TES_lay='Charge')
        s2.conn_13.set_attr(T=T_bot)
        ok, _, _ = s.attempt_to_solve(s2, 'offdesign', '.tespy_cache/base_design', '5', tries=3)
        if ok and s2.network.converged:
            t02 = s2.conn_02.T.val if hasattr(s2, 'conn_02') else 0
            t14 = s2.conn_14.T.val if hasattr(s2, 'conn_14') else 0
            Q = s2.ptc_field.Q.val / 1e6 if s2.ptc_field.Q.val else 0
            print(f'E={E} T_bot={T_bot}: OK  T02={t02:.0f} T14={t14:.0f} Q={Q:.2f}MW')
        else:
            print(f'E={E} T_bot={T_bot}: FAILED')
