import numpy as np, sys, os
sys.path.insert(0, '.')
from pbtes.config import baseline_config

tes_p, comp_p, conn_p = baseline_config()
E_proc = abs(comp_p['PR_Q']) / (comp_p['ptc_A'] * comp_p['eta_opt'])
E_charge = E_proc * 1.5
E_mode1 = max(E_charge * 1.1, 600)

print(f'E_min_process  = {E_proc:.0f} W/m2')
print(f'E_min_charge   = {E_charge:.0f} W/m2')
print(f'E_min_mode1    = {E_mode1:.0f} W/m2')
print()

E_vals = [1006, 995, 900, 827, 800]
Ttop_vals = [450, 470, 480, 490, 500, 510, 520, 530]
print('charge_viable = T_ptc_est > TES_top + 30')
print()
for E in E_vals:
    irr_frac = min(E/900, 1.2)
    T_ptc_est = 480 + irr_frac * 80
    print(f'E={E:4.0f}, T_ptc_est={T_ptc_est:.0f}C:')
    for Ttop in Ttop_vals:
        cv = T_ptc_est > Ttop + 30
        need = Ttop + 30
        if cv:
            print(f'  Ttop={Ttop:3.0f}: charge_viable (est={T_ptc_est:.0f} > {need:.0f})')
    print()
