"""Verify kA consistency across charging modes."""
import os, shutil, numpy as np
from coreV5 import SolarThermalSystem, Solver

for f in ['base_design_1','base_design_5','base_design_6','mode1_kA.txt']:
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

print('kA from Mode 1 (stored by solver):', solver.charge_hx_kA)

# Check what kA is stored in each design file
import pandas as pd
for mode in ['1', '5', '6']:
    try:
        df = pd.read_csv(f'base_design_{mode}/components/HeatExchanger.csv')
        kA = df[df['variable'] == 'kA']['value'].values[0]
        print(f'base_design_{mode} stored kA: {kA}')
    except Exception as e:
        print(f'base_design_{mode}: ERROR - {e}')
