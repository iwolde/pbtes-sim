"""Debug Mode 3 Q_hx sign convention and coupling loop failure."""
from coreV5 import SolarThermalSystem, Solver
import numpy as np
import os, shutil

for f in ['base_design_1', 'base_design_2', 'base_design_3', 'base_design_4',
           'base_design_5', 'base_design_6', 'mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f):
                os.remove(f)
            else:
                shutil.rmtree(f, ignore_errors=True)
        except:
            pass

tes_p = {
    'Initial temperature': 400, 'Tank lenght': 10, 'Tank diameter': 3,
    'Particle diameter': 0.05, 'Void fraction': 0.4, 'Solid density': 2500,
    'Solid specific heat': 1000, 'Solid conductivity': 1.5,
    'Wall thinckness': 0.05, 'Tank conductivity': 15,
    'Insulation thickness': 0.2, 'Insulation conductivity': 0.05,
    'HTF': 'INCOMP::NaK'
}
comp_p = {
    'ptc_A': 2500, 'ptc_aoi': 0, 'ptc_doc': 1, 'ptc_tamb': 20,
    'eta_opt': 0.75, 'ptc_c_1': 0, 'ptc_c_2': 0, 'ptc_E': 1000,
    'ptc_iam_1': 0, 'ptc_iam_2': 0, 'PR_Q': -1e6
}
conn_p = {
    '5_T': 520, '6_T': 480, '6_p': 50,
    '6_f': {'INCOMP::NaK': 1}, '13_p': 5,
    '13_f': {'INCOMP::NaK': 1}, '15_p': 5,
    '15_f': {'INCOMP::NaK': 1}
}

# Design Mode 3
sys = SolarThermalSystem(
    tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect'
)
sys.set_operation_mode(TESmode='3', profile=np.ones(20)*540,
                       prev_TES_lay='Discharge', mode='design')
sys.conn_15.set_attr(T=540)
sys.solve_network(mode='design', TESmode='3')
print('Design Mode 3: converged =', sys.network.converged)

# Offdesign with same system
sys.set_operation_mode(TESmode='3', current_irr=0, profile=np.ones(20)*520,
                       prev_TES_lay='Discharge', mode='offdesign')
sys.conn_15.set_attr(T=520)

solver = Solver(
    tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect'
)
solver.current_irr = 0
ok, att, err_msg = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '3', tries=5)
print(f'attempt_to_solve: ok={ok}, converged={sys.network.converged}')
print(f'  attempts: {att}, error: {err_msg}')

if sys.network.converged:
    Q_dhx = sys.discharge_tes_hx.Q.val
    cond = 0 < Q_dhx
    print(f'  Q_dhx = {Q_dhx/1e6:.4f} MW')
    print(f'  0 < Q_dhx = {cond}')
    print(f'  T15={sys.conn_15.T.val:.1f} T16={sys.conn_16.T.val:.1f}')
    print(f'  T11={sys.conn_11.T.val:.1f} T04={sys.conn_04.T.val:.1f}')
    print(f'  m15={sys.conn_15.m.val:.2f} m11={sys.conn_11.m.val:.2f}')
else:
    print('  Network did not converge')
    print(f'  current_mode = {solver.current_mode}')
