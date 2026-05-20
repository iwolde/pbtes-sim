"""Debug mode selection — run one sunny step manually."""
import os, shutil, numpy as np, pandas as pd
for d in ['.tespy_cache']:
    if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)

from coreV5 import Solver
from pbtes.config import baseline_config, zinc_pool_config
tp, cp, np_ = baseline_config()
zp = zinc_pool_config()

s = Solver(tes_params=tp, component_params=cp, conexion_params=np_,
    HTF='INCOMP::NaK', topology='Parallel', tank_config='indirect', zinc_pool_params=zp)
s.initialize_modes()
s.tes_params['Initial temperature'] = tp['Initial temperature']

# Simulate one sunny hour
s.solar_system.tes.profile = np.ones(20) * 490
tmy = pd.read_csv('TMY.csv')
tmy['Fecha/Hora'] = pd.to_datetime(tmy['Fecha/Hora'])
tmy['Fecha/Hora'] = tmy['Fecha/Hora'].apply(lambda x: x.replace(year=2022))

for idx in range(10):
    row = tmy.iloc[idx]
    E = row['dni']
    mode = s.get_system_mode(E)
    soc = s.solar_system.tes.calculate_SoC(s.solar_system.tes.profile)
    soc_e = s.solar_system.tes.calculate_SoC(np.ones(20)*400)
    soc_f = s.solar_system.tes.calculate_SoC(np.ones(20)*560)
    soc_n = (soc - soc_e) / max(soc_f - soc_e, 1e-3)
    dwell = getattr(s, '_mode_dwell', '?')
    print(f'h={idx:2d} E={E:5.0f} mode={mode} soc_norm={soc_n:.3f} prev={s.prev_TESmode} dwell={dwell}')
    s.prev_TESmode = mode
    s._mode_dwell = 0  # force no dwell for testing
