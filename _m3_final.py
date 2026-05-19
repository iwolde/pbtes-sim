"""
Mode 3 expanded: free T05 only, keep T06=480, PH Q=0.
When T15 > 540: T05 = T04 = T15-20 > 520. Process runs hotter.
Mass flow lowers automatically (m = 1MW / (h_T05 - h_480)).
Net DOF: +1 (T05 free) -1 (PH Q=0) = 0 change.
"""
import os, shutil, numpy as np
for f in ['base_design_3','base_design_4']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

from coreV5 import SolarThermalSystem, Solver

tes_p = {'Initial temperature':400,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':2500,
    'Solid specific heat':1000,'Solid conductivity':1.5,'Wall thinckness':0.05,
    'Tank conductivity':15,'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,'eta_opt':0.75,
    'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-1e6}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()
solver.current_irr = 0

print('Regime A+: free T05, keep T06=480, PH Q=0')
print(f'{"T15":>6s} {"T04":>6s} {"T05":>6s} {"T06":>6s} {"T11":>6s}  {"DHX":>8s} {"PH":>8s}  {"m":>6s} {"status":>10s}')
print(f'{"-"*6} {"-"*6} {"-"*6} {"-"*6} {"-"*6}  {"-"*8} {"-"*8}  {"-"*6} {"-"*10}')
for T15 in [580, 570, 560, 550, 540, 530]:
    sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys.tes.profile = np.ones(20)*T15
    sys.set_operation_mode(TESmode='3', mode='offdesign',
        profile=sys.tes.profile, prev_TES_lay='Discharge')
    sys.conn_15.set_attr(T=T15)
    # Expand Regime A: free T05, PH Q=0
    sys.conn_05.set_attr(T=None)
    sys.preheater_hx.set_attr(Q=0)
    
    ok, _, _ = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '3', tries=3)
    if ok and sys.network.converged:
        t04 = sys.conn_04.T.val; t05 = sys.conn_05.T.val
        t06 = sys.conn_06.T.val; t11 = sys.conn_11.T.val
        qd = sys.discharge_tes_hx.Q.val/1e6
        qp = sys.preheater_hx.Q.val if sys.preheater_hx.Q.val else 0
        m = sys.conn_05.m.val
        status = "OK"
        if t05 > 520 and abs(qp) < 0.01:
            status = "REGIME A+"
        elif abs(qp) < 0.01:
            status = "REGIME A"
        else:
            status = "OK"
        print(f'{T15:6d} {t04:6.0f} {t05:6.0f} {t06:6.0f} {t11:6.0f}  {qd:8.3f} {qp:8.3f}  {m:6.1f} {status:>10s}')
    else:
        print(f'{T15:6d} {"-":>6s} {"-":>6s} {"-":>6s} {"-":>6s}  {"-":>8s} {"-":>8s}  {"-":>6s} {"FAIL":>10s}')

# Also test original Regime B for comparison
print(f'\nRegime B (standard): T05=520 fixed, T06=480 fixed, PH free')
print(f'{"T15":>6s} {"T04":>6s} {"T05":>6s} {"T06":>6s} {"T11":>6s}  {"DHX":>8s} {"PH":>8s}  {"m":>6s}')
print(f'{"-"*6} {"-"*6} {"-"*6} {"-"*6} {"-"*6}  {"-"*8} {"-"*8}  {"-"*6}')
for T15 in [540, 530, 520, 510, 505, 500]:
    sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys.tes.profile = np.ones(20)*T15
    sys.set_operation_mode(TESmode='3', mode='offdesign',
        profile=sys.tes.profile, prev_TES_lay='Discharge')
    sys.conn_15.set_attr(T=T15)
    ok, _, _ = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '3', tries=3)
    if ok and sys.network.converged:
        t04 = sys.conn_04.T.val; t05 = sys.conn_05.T.val
        t06 = sys.conn_06.T.val; t11 = sys.conn_11.T.val
        qd = sys.discharge_tes_hx.Q.val/1e6; qp = sys.preheater_hx.Q.val/1e6
        m = sys.conn_05.m.val
        print(f'{T15:6d} {t04:6.0f} {t05:6.0f} {t06:6.0f} {t11:6.0f}  {qd:8.3f} {qp:8.3f}  {m:6.1f}')
    else:
        print(f'{T15:6d} {"-":>6s} {"-":>6s} {"-":>6s} {"-":>6s}  {"-":>8s} {"-":>8s}  {"-":>6s}')
