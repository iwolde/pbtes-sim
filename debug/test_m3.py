"""Test Mode 3 offdesign via proper pipeline."""
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

# Test offdesign at various T15 (TES top temp)
for T_tes in [540, 530, 520, 510, 505, 500, 495]:
    s2 = SolarThermalSystem(tes_params=dict(tp), component_params=dict(cp),
        conexion_params=dict(np_), HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    s2.tes.profile = np.ones(20) * T_tes
    s2.set_operation_mode(TESmode='3', current_irr=0, mode='offdesign',
        profile=s2.tes.profile, prev_TES_lay='Discharge')
    s2.conn_15.set_attr(T=T_tes)
    ok, _, _ = s.attempt_to_solve(s2, 'offdesign', '.tespy_cache/base_design', '3', tries=3)
    if ok and s2.network.converged:
        qd = s2.discharge_tes_hx.Q.val / 1e6 if hasattr(s2, 'discharge_tes_hx') else 0
        qp = s2.preheater_hx.Q.val / 1e6 if s2.preheater_hx.Q.val else 0
        t04 = s2.conn_04.T.val if hasattr(s2, 'conn_04') else 0
        print(f'T15={T_tes}: OK  DHX={qd:.2f}MW PH={qp:.2f}MW T04={t04:.0f}')
    else:
        print(f'T15={T_tes}: FAILED (mode={s.current_mode})')
