import pytest
import pandas as pd
from datetime import datetime
from pbtes.simulation.winter_logic import WinterLogic
from pbtes.storage.packed_bed import ThermalEnergyStorage
from pbtes.config import baseline_config

def test_winter_logic_dates():
    wl = WinterLogic()
    
    # Southern hemisphere winter: June (6), July (7), August (8)
    assert wl.is_winter(pd.Timestamp("2026-06-15 12:00:00")) is True
    assert wl.is_winter(pd.Timestamp("2026-07-01 00:00:00")) is True
    assert wl.is_winter(pd.Timestamp("2026-08-31 23:00:00")) is True
    
    # Summer/Autumn/Spring
    assert wl.is_winter(pd.Timestamp("2026-01-15 12:00:00")) is False
    assert wl.is_winter(pd.Timestamp("2026-05-15 12:00:00")) is False
    assert wl.is_winter(pd.Timestamp("2026-09-15 12:00:00")) is False
    assert wl.is_winter(pd.Timestamp("2026-12-25 12:00:00")) is False

    # Check setpoint values
    assert wl.get_tank_setpoint(pd.Timestamp("2026-06-15 12:00:00")) == 300.1
    assert wl.get_tank_setpoint(pd.Timestamp("2026-01-15 12:00:00")) == 450.0

def test_heated_blanket_calc():
    # Load default params
    tes_params, _, _ = baseline_config()
    tes = ThermalEnergyStorage(tes_params, "test_tes", dt=3600)
    
    # Initialize profile with low temperature (e.g. 290 °C)
    profile = [290.0] * len(tes.profile)
    dt = 3600.0
    T_amb = 15.0
    T_set = 300.1
    
    # Run heat loss calculation with heater
    new_profile = tes.calc_heat_loss(profile, dt, T_amb, T_set=T_set)
    
    # Every node should be clamped to T_set
    for temp in new_profile:
        assert temp == pytest.approx(T_set)
        
    # Check that auxiliary energy was computed and is positive
    assert tes.last_aux_energy_J > 0.0
    
    # Check manual verification of one layer
    energy_kJ = tes.last_aux_energy_J / 1000.0
    print(f"Mock auxiliary heater energy: {energy_kJ:.2f} kJ")

def test_heated_blanket_inactive():
    tes_params, _, _ = baseline_config()
    tes = ThermalEnergyStorage(tes_params, "test_tes", dt=3600)
    
    # Initialize profile at high temperature (e.g. 500 °C)
    profile = [500.0] * len(tes.profile)
    dt = 3600.0
    T_amb = 15.0
    T_set = 300.1
    
    # Without heater setpoint or when temperatures are far above setpoint
    new_profile = tes.calc_heat_loss(profile, dt, T_amb, T_set=T_set)
    
    # Auxiliary energy should be 0.0
    assert tes.last_aux_energy_J == 0.0
