"""Test Mode 3 offdesign convergence with PH as gap-filler."""
import os, shutil, numpy as np
for f in ['base_design_1','base_design_2','base_design_3','base_design_4',
           'base_design_5','base_design_6','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

from coreV5 import SolarThermalSystem, Solver

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

solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()
solver.current_irr = 0
print('=== All designs created ===')
print('TANK BOTTOM:', solver.solar_system.tes.profile[-1])

# Test offdesign at multiple T15
for T_tes in [540, 530, 520, 510, 505]:
    sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys.set_operation_mode(TESmode='3', profile=np.ones(20)*T_tes,
                           prev_TES_lay='Discharge', mode='offdesign')
    sys.conn_15.set_attr(T=T_tes)
    
    ok, _, _ = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '3', tries=5)
    if ok and sys.network.converged:
        Q_dhx = sys.discharge_tes_hx.Q.val / 1e6
        Q_ph = sys.preheater_hx.Q.val / 1e6
        T04 = sys.conn_04.T.val
        T05 = sys.conn_05.T.val
        T16 = sys.conn_16.T.val
        m_proc = sys.conn_05.m.val
        print(f'T15={T_tes}: OK HDX={Q_dhx:.2f}MW PH={Q_ph:.2f}MW | T04={T04:.0f} T16={T16:.0f} dotm={m_proc:.1f}')
    else:
        print(f'T15={T_tes}: FAIL (mode={solver.current_mode})')
