"""Mode 3 regimes — clean sweep."""
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

# Design: one DHX, one kA
sys_d = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys_d.tes.profile = np.ones(20)*540
sys_d.set_operation_mode(TESmode='3', mode='design', profile=sys_d.tes.profile, prev_TES_lay='Discharge')
sys_d.conn_15.set_attr(T=540)
sys_d.solve_network(mode='design', TESmode='3')
kA = sys_d.discharge_tes_hx.kA.val
print(f'DHX kA = {kA:.0f} W/K')
print(f'Single HX, computed once at design (T15=540, T04=520, T05=520, Q_DHX=-1MW, Q_PH=0)')
print()

# Offdesign sweep
solver = Solver(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
solver.initialize_modes()
solver.current_irr = 0

print(f'{"T15":>6s} {"T04":>6s} {"T11":>6s}  {"DHX(MW)":>9s} {"PH(MW)":>9s}  {"REGIME":>14s}')
print(f'{"-"*6} {"-"*6} {"-"*6}  {"-"*9} {"-"*9}  {"-"*14}')
for T15 in [560, 550, 540, 530, 520, 510, 505, 500, 495]:
    sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys.tes.profile = np.ones(20)*T15
    sys.set_operation_mode(TESmode='3', mode='offdesign', profile=sys.tes.profile, prev_TES_lay='Discharge')
    sys.conn_15.set_attr(T=T15)
    ok, _, _ = solver.attempt_to_solve(sys, 'offdesign', 'base_design', '3', tries=3)
    if ok and sys.network.converged:
        t04 = sys.conn_04.T.val
        t11 = sys.conn_11.T.val
        qd = sys.discharge_tes_hx.Q.val/1e6
        qp = sys.preheater_hx.Q.val/1e6
        # In TESPy SimpleHeatExchanger: Q = m*(h_out-h_in)
        # Q > 0: fluid gains heat (PH heats). Q < 0: fluid loses heat (PH cools).
        if abs(qp) < 0.005:
            r = 'A (100% DHX)'
        elif qp < 0 and t04 > 520:
            r = 'INVALID (PH cools)'
        elif qp > 0 and t04 <= 520:
            r = 'B (DHX+PH heat)'
        elif t04 <= t11:
            r = 'INVIABLE (reverse)'
        else:
            r = 'OK'
        print(f'{T15:6d} {t04:6.0f} {t11:6.0f}  {qd:9.3f} {qp:9.3f}  {r:>14s}')
    else:
        print(f'{T15:6d} {"-":>6s} {"-":>6s}  {"-":>9s} {"-":>9s}  FAIL')
