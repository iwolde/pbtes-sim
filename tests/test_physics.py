import pytest
import CoolProp.CoolProp as CP
from pbtes import ThermalEnergyStorage
import numpy as np

# Using 'INCOMP::NaK' for Solar Salt as found in mainV5_5.py
# Using 'Water' as another fluid for testing boundaries.
@pytest.mark.parametrize("fluid, min_temp, max_temp", [
    ("INCOMP::NaK", 10 + 273.15, 700 + 273.15),
    # ("Water", 1 + 273.15, 370 + 273.15), # Commented out: CoolProp does not raise exceptions for water in the same way, it extrapolates to steam properties.
])
def test_fluid_temperature_boundaries(fluid, min_temp, max_temp):
    """
    Test that CoolProp raises a ValueError for temperatures outside the valid range for a given fluid.
    """
    # Test below the lower bound
    with pytest.raises(Exception):
        CP.PropsSI('D', 'T', min_temp - 1, 'P', 101325, fluid)

    # Test above the upper bound
    with pytest.raises(Exception):
        CP.PropsSI('D', 'T', max_temp + 1, 'P', 101325, fluid)

    # Test within bounds (should not raise an exception)
    try:
        CP.PropsSI('D', 'T', (min_temp + max_temp) / 2, 'P', 101325, fluid)
    except Exception as e:
        pytest.fail(f"PropsSI failed within valid temperature range for {fluid}: {e}")

def test_stanton_number_calculation():
    """
    Test the Stanton number calculation in ThermalEnergyStorage.
    """
    tes_params = {
        'HTF': 'INCOMP::NaK',
        'Initial temperature': 400,
        'Tank length': 10,
        'Particle diameter': 0.05,
        'Tank diameter': 3,
        'Void fraction': 0.4,
        'Solid density': 2300,
        'Solid specific heat': 1000,
        'Solid conductivity': 1.6,
        'Wall thickness': 0.02,
        'Tank conductivity': 45,
        'Insulation thickness': 0.75,
        'Insulation conductivity': 0.03,
    }
    tes = ThermalEnergyStorage(tes_params, "test_tes", dt=3600)
    
    T_in = 500
    mass_flow = 10 # kg/s

    # This will calculate all intermediate values
    tes.eq_params(T_in, mass_flow)

    # Re-calculate inputs to St formula to verify
    G = tes.mflow / tes.AT
    Re = G * tes.dp / tes.mu_f
    Pr = tes.mu_f * tes.cp_f / tes.k_f
    
    hint = (tes.k_f / tes.dp) * (0.203 * Re**(1/3) * Pr**(1/3) + 0.22 * Re**0.8 * Pr**0.4)
    hw = 1 / (1 / hint) # hw is just hint

    beta = 4 / tes.Dint
    rho_cp_line = (tes.e * tes.rho_f * tes.cp_f + (1 - tes.e) * tes.rho_s * tes.cp_s)
    u_in = G / tes.rho_f
    
    expected_St = 0.75 * hw * beta * tes.HT / (rho_cp_line * u_in)
    assert abs(tes.St - expected_St) < 1e-6
    
def test_soc_calculation():
    """
    Test that the State of Charge calculation is monotonic with temperature.
    """
    tes_params = {
        'HTF': 'INCOMP::NaK',
        'Initial temperature': 400,
        'Tank length': 10,
        'Particle diameter': 0.05,
        'Tank diameter': 3,
        'Void fraction': 0.4,
        'Solid density': 2300,
        'Solid specific heat': 1000,
        'Solid conductivity': 1.6,
        'Wall thickness': 0.02,
        'Tank conductivity': 45,
        'Insulation thickness': 0.75,
        'Insulation conductivity': 0.03,
    }
    tes = ThermalEnergyStorage(tes_params, "test_tes", dt=3600)
    
    profile_cold = np.full(20, 400.0) # 400 C
    profile_hot = np.full(20, 500.0) # 500 C

    soc_cold = tes.calculate_SoC(profile_cold)
    soc_hot = tes.calculate_SoC(profile_hot)

    assert soc_hot > soc_cold

    profile_gradient = np.linspace(400, 500, 20)
    soc_gradient = tes.calculate_SoC(profile_gradient)

    assert soc_gradient > soc_cold
    assert soc_hot > soc_gradient

