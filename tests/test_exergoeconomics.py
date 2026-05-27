import pytest
import pandas as pd
from pbtes.analysis.exergoeconomics import ExergoeconomicAssessment

def test_exergoeconomic_assessment():
    # Mock dataframe with some data
    data = {
        'W_pump_kW': [10.0],
        'E': [900.0], # W/m2 DNI
        'Tamb': [20.0], # deg C -> 293.15 K
        'T_zinc': [450.0], # deg C -> 723.15 K
        'aux_to_proc_kJ': [0.0], 
        'solar_to_proc_kJ': [3600.0 * 100], # 100 kWh
        'tes_to_proc_kJ': [0.0]
    }
    df = pd.DataFrame(data)
    
    # Mock meta
    meta = {
        'sim_args': {
            'aperture_area': 1000.0,
            'tank_diameter': 7.0,
            'tank_height': 5.0
        }
    }
    
    # 900 W/m2 * 1000 m2 = 900,000 W = 900 kW
    # Over 1 hour = 900 kWh solar incident.
    
    exergo = ExergoeconomicAssessment(df, meta)
    
    # Force time_step to 3600s
    exergo.cfg.solver.time_step = 3600.0
    
    results = exergo.run_exergoeconomic_assessment()
    
    # Carnot factor: 1 - 293.15 / 723.15 = 1 - 0.4053 = 0.5946
    # Delivered exergy = 100 kWh * 0.5946 = 59.46 kWh
    assert results['total_Ex_product_MWh'] == pytest.approx(0.05946, rel=1e-3)
    
    # Petela factor: T_sun = 5770K, T0 = 293.15K
    # 1 - (4/3)*(293.15/5770) + (1/3)*(293.15/5770)^4 = 1 - 0.0677 + ... = 0.9323
    # Incident exergy = 900 kWh * 0.9323 = 839.0 kWh
    assert results['total_Ex_solar_MWh'] == pytest.approx(0.839, rel=1e-2)
    
    # Exergy efficiency: 59.46 / 839.0 = 7.08%
    assert results['eta_exergy'] == pytest.approx(7.08, rel=1e-2)
    
    # f_factor = Z / (Z + C_D)
    # Z > 0, so f_factor should be > 0 and <= 1
    assert 0.0 < results['exergoeconomic_f_factor'] <= 1.0
