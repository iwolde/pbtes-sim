"""
Mode 3 Regime A expansion: when T15 > 540, free T05 and T06,
let DHX provide all 1 MW at higher process temperatures.
"""
import os, shutil, numpy as np
for f in ['base_design_3','base_design_4']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

from coreV5 import SolarThermalSystem
from tespy.connections import Ref

tes_p = {'Initial temperature':400,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':2500,
    'Solid specific heat':1000,'Solid conductivity':1.5,'Wall thinckness':0.05,
    'Tank conductivity':15,'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,'eta_opt':0.75,
    'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-1e6}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

# Design (unchanged — compute kA at T15=540)
sys_d = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys_d.tes.profile = np.ones(20)*540
sys_d.set_operation_mode(TESmode='3', mode='design', profile=sys_d.tes.profile, prev_TES_lay='Discharge')
sys_d.conn_15.set_attr(T=540)
sys_d.solve_network(mode='design', TESmode='3')
kA = sys_d.discharge_tes_hx.kA.val
print(f'Design: kA={kA:.0f} W/K')

# Test: Regime A+ at T15=560 with T05 and T06 freed
print(f'\n{"T15":>6s} {"mode":>10s} {"T04":>6s} {"T05":>6s} {"T06":>6s} {"T11":>6s}  {"DHX":>8s} {"PH":>8s}  {"res":>8s}')
print(f'{"-"*6} {"-"*10} {"-"*6} {"-"*6} {"-"*6} {"-"*6}  {"-"*8} {"-"*8}  {"-"*8}')

for T15 in [570, 560, 550, 540, 530]:
    for approach in ['standard', 'expanded']:
        sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
            HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
        sys.tes.profile = np.ones(20)*T15
        
        if approach == 'standard':
            # Current behavior: T05=520, T06=480 fixed, PH free
            sys.set_operation_mode(TESmode='3', mode='offdesign',
                profile=sys.tes.profile, prev_TES_lay='Discharge')
            sys.conn_15.set_attr(T=T15)
        else:
            # Expanded Regime A: free T05, T06, set PH Q=0
            sys.create_network(mode=3)
            sys.tes.set_state('discharge')
            sys.conn_04.set_attr(T=Ref(sys.conn_15, 1, 20))
            sys.conn_11.set_attr(T=None)
            sys.conn_16.set_attr(T=None)
            sys.conn_05.set_attr(T=None)   # FREE T05
            sys.conn_06.set_attr(T=None)   # FREE T06
            sys.preheater_hx.set_attr(Q=0) # PH idle
            sys.conn_15.set_attr(T=T15, p=conn_p['15_p'], fluid=conn_p['15_f'])
        
        try:
            sys.solve_network(mode='offdesign', design_path='base_design_3', TESmode='3')
            if sys.network.converged:
                t04 = sys.conn_04.T.val; t05 = sys.conn_05.T.val
                t06 = sys.conn_06.T.val; t11 = sys.conn_11.T.val
                qd = sys.discharge_tes_hx.Q.val/1e6; qp = sys.preheater_hx.Q.val/1e6 if sys.preheater_hx.Q.val else 0
                m = sys.conn_05.m.val
                print(f'{T15:6d} {approach:>10s} {t04:6.0f} {t05:6.0f} {t06:6.0f} {t11:6.0f}  {qd:8.3f} {qp:8.3f}  {m:8.1f}')
            else:
                print(f'{T15:6d} {approach:>10s} {"-":>6s} {"-":>6s} {"-":>6s} {"-":>6s}  {"-":>8s} {"-":>8s}  NO_CONV')
        except Exception as e:
            print(f'{T15:6d} {approach:>10s} {"-":>6s} {"-":>6s} {"-":>6s} {"-":>6s}  {"-":>8s} {"-":>8s}  {str(e)[:30]}')
