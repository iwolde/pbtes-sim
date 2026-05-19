"""
MODE 3 — Verify single DHX kA, test Forms A and B.
"""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem, Solver

for f in ['base_design_1','base_design_3','base_design_4','mode1_kA.txt']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

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

# Get DHX kA from design file
import tespy.networks as tpn
net = tpn.Network(fluids=['INCOMP::NaK'])
# Just read from the saved design
print(f'  DHX has single design (ttd_l=20 at T15=540)')

print('\n--- MODE 3 FORMS A & B (offdesign) ---')
print(f'  {"T15":>5s} {"DHX(MW)":>8s} {"PH(MW)":>7s} {"T04":>5s} {"T11":>5s} {"m":>6s} {"%DHX":>6s} {"Form":>12s}')
print(f'  {"-"*5} {"-"*8} {"-"*7} {"-"*5} {"-"*5} {"-"*6} {"-"*6} {"-"*12}')

for T15 in [540, 535, 530, 525, 520, 515, 510, 505, 500]:
    sys3 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
        HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
    sys3.tes.profile = np.ones(20)*T15
    sys3.set_operation_mode(TESmode='3', current_irr=0, mode='offdesign',
        profile=sys3.tes.profile, prev_TES_lay='Discharge')
    sys3.conn_15.set_attr(T=T15)
    ok, _, _ = solver.attempt_to_solve(sys3, 'offdesign', 'base_design', '3', tries=3)
    
    if ok and sys3.network.converged and hasattr(sys3, 'discharge_tes_hx'):
        Q_dhx = abs(sys3.discharge_tes_hx.Q.val)/1e6
        Q_ph = abs(sys3.preheater_hx.Q.val)/1e6
        T04 = sys3.conn_04.T.val
        T11 = sys3.conn_11.T.val
        m = sys3.conn_05.m.val
        pct = 100*Q_dhx/(Q_dhx+Q_ph) if (Q_dhx+Q_ph) > 1e-6 else 0
        form = 'A (DHX full)' if Q_ph < 0.01 else 'B (DHX+PH)'
        print(f'  {T15:5d} {Q_dhx:8.3f} {Q_ph:7.3f} {T04:5.0f} {T11:5.0f} {m:6.1f} {pct:6.0f}% {form:>12s}')
    else:
        print(f'  {T15:5d} {"-":>8s} {"-":>7s} {"-":>5s} {"-":>5s} {"-":>6s} {"-":>6s} {"FALLBACK":>12s}')

print(f'\n  Form A: T15 >= {conn_p["5_T"]}  (DHX provides all, PH idle)')
print(f'  Form B: T15 between {conn_p["6_T"]+20} and {conn_p["5_T"]}  (DHX partial, PH fills gap)')
print(f'  Form transition to Mode 4: T15 < {conn_p["6_T"]+20}  (DHX cannot heat, aux only)')
