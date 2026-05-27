import pytest
import pandas as pd
from pbtes.analysis.economics import EconomicAssessment
from pbtes.config import SimulationConfig

def test_economic_assessment_basic():
    # Mock dataframe with some data
    data = {
        'W_pump_kW': [10.0, 15.0, 20.0],
        'aux_to_proc_kJ': [3600.0 * 50, 3600.0 * 100, 3600.0 * 50], # 200 kWh thermal total
        'solar_to_proc_kJ': [3600.0 * 100, 0.0, 0.0], # 100 kWh
        'tes_to_proc_kJ': [0.0, 3600.0 * 100, 3600.0 * 100] # 200 kWh
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
    
    # Run assessment
    overrides = {'electricity_price_per_kwh': 0.1, 'aux_fuel_price_per_kwh': 0.05}
    eco = EconomicAssessment(df, meta, overrides=overrides)
    results = eco.run_assessment()
    
    # Total energy delivered: 200 (aux) + 100 (solar) + 200 (tes) = 500 kWh = 0.5 MWh
    assert results['q_delivered_MWh'] == pytest.approx(0.5)
    
    # Electricity cost: total W_pump_kW = 45.0, price = 0.1 -> 4.5 USD
    assert results['cost_electricity'] == pytest.approx(4.5)
    
    # Fuel cost: total aux = 200 kWh, price = 0.05 -> 10.0 USD
    assert results['cost_aux_fuel'] == pytest.approx(10.0)
    
    # Assert LCOH calculation logic
    expected_opex = results['cost_electricity'] + results['cost_aux_fuel'] + results['cost_om']
    assert results['opex_total'] == pytest.approx(expected_opex)
    
    expected_lcoh = (results['annualized_capex'] + expected_opex) / 0.5
    assert results['lcoh_usd_per_MWh'] == pytest.approx(expected_lcoh)


