import numpy as np, sys, os, pandas as pd
sys.path.insert(0, '.')
from pbtes.config import baseline_config
from pbtes.simulation.solver import Solver

tes_p, comp_p, conn_p = baseline_config()
comp_p['ptc_A'] = 1000.0  # Use the same aperture as simulation

solver = Solver(tes_p, comp_p, conn_p, HTF='INCOMP::NaK',
                system_mode='Full', 
                topology='Series', tank_config='direct',
                zinc_pool_params=None, charge_margin=1.5)

tmy = pd.read_csv('TMY.csv')
tmy['time'] = pd.to_datetime(tmy['Fecha/Hora'])
jan7 = tmy[(tmy['time'].dt.month == 1) & (tmy['time'].dt.day <= 7)]

print(f'A_ptc = {comp_p["ptc_A"]}')
print(f'E_min_process = {solver.E_min_process:.0f}')
print(f'E_min_charge  = {solver.E_min_charge:.0f}')
print(f'E_min_mode1   = {solver.E_min_mode1:.0f}')
print()

def make_fake_tes(T):
    class FakeTES:
        def __init__(self, T):
            self.profile = np.ones(20) * T
        def calculate_SoC(self, profile):
            return np.mean(profile) * 10.0  # proxy
    return FakeTES(T)

def test_modes_at_T(T):
    ht = make_fake_tes(T)
    ct = make_fake_tes(T)
    solver.solar_system = type('obj', (object,), {
        'tes': ht,
        'hot_tes': ht,
        'cold_tes': ct,
        'conexion_params': conn_p,
        'tank_config': 'direct',
        'topology': 'Series',
    })()
    solver.prev_TESmode = '4'
    
    counts = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0, '6': 0}
    for _, row in jan7.iterrows():
        irr = row['dni']
        mode = solver.get_mode(irr, ht.profile, 'Charge')
        counts[mode] += 1
        solver.prev_TESmode = mode
    return counts

for T in [490, 480, 470, 460, 450]:
    counts = test_modes_at_T(T)
    print(f'TES={T}C: M1={counts["1"]}, M2={counts["2"]}, M3={counts["3"]}, M4={counts["4"]}, M5={counts["5"]}, M6={counts["6"]}')
    print(f'  (of {len(jan7)} hours)')
