"""Systematic mode-by-mode audit. Mode 4 first (simplest)."""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem

for f in ['base_design_4']:
    if os.path.exists(f):
        try:
            if os.path.isfile(f): os.remove(f)
            else: shutil.rmtree(f, ignore_errors=True)
        except: pass

tes_p = {'Initial temperature':400,'Tank lenght':10,'Tank diameter':4,
    'Particle diameter':0.05,'Void fraction':0.4,'Solid density':2500,
    'Solid specific heat':1000,'Solid conductivity':1.5,
    'Wall thinckness':0.05,'Tank conductivity':15,
    'Insulation thickness':0.5,'Insulation conductivity':0.035,
    'HTF':'INCOMP::NaK'}
comp_p = {'ptc_A':2500,'ptc_aoi':0,'ptc_doc':1,'ptc_tamb':20,
    'eta_opt':0.75,'ptc_c_1':0,'ptc_c_2':0,'ptc_E':1000,
    'ptc_iam_1':0,'ptc_iam_2':0,'PR_Q':-1e6}
conn_p = {'5_T':520,'6_T':480,'6_p':50,'6_f':{'INCOMP::NaK':1},
    '13_p':5,'13_f':{'INCOMP::NaK':1},'15_p':5,'15_f':{'INCOMP::NaK':1}}

sys = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys.tes.profile = np.ones(20)*400
sys.set_operation_mode(TESmode='4', mode='design', profile=sys.tes.profile, prev_TES_lay='Charge')
print('=== MODE 4 DESIGN ===')
print(f'Components: {list(sys.network.comps.index)}')
print(f'Connections: {list(sys.network.conns.index)}')
try:
    sys.solve_network(mode='design', TESmode='4')
    print(f'Converged: {sys.network.converged}')
    print(f'  T04={sys.conn_04.T.val:.0f} T05={sys.conn_05.T.val:.0f} T06={sys.conn_06.T.val:.0f}')
    print(f'  m={sys.conn_06.m.val:.1f} kg/s')
    print(f'  Q_PH={sys.preheater_hx.Q.val/1e6:.2f} MW  Q_PR={sys.process_hx.Q.val/1e6:.2f} MW')
except Exception as e:
    print(f'FAILED: {str(e)[:100]}')

print('\n=== MODE 4 OFFDESIGN ===')
sys2 = SolarThermalSystem(tes_params=tes_p, component_params=comp_p, conexion_params=conn_p,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect')
sys2.tes.profile = np.ones(20)*400
sys2.set_operation_mode(TESmode='4', mode='offdesign', profile=sys2.tes.profile, prev_TES_lay='Charge')
try:
    sys2.solve_network(mode='offdesign', design_path='base_design_4', TESmode='4')
    print(f'Converged: {sys2.network.converged}')
    if sys2.network.converged:
        print(f'  T04={sys2.conn_04.T.val:.0f} T05={sys2.conn_05.T.val:.0f} T06={sys2.conn_06.T.val:.0f}')
        print(f'  m={sys2.conn_06.m.val:.1f} kg/s')
except Exception as e:
    print(f'FAILED: {str(e)[:100]}')
