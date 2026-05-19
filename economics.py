def calculate_lcoh(energy_yield_kwh, tank_volume_m3, htf_mass_kg):
    """
    Calculate Levelized Cost of Heat (LCOH) dynamically.
    
    Parameters:
    - energy_yield_kwh: Annual energy yield in kWh
    - tank_volume_m3: Volume of the TES tank in cubic meters
    - htf_mass_kg: Mass of the Heat Transfer Fluid in kg
    """
    discount_rate = 0.08
    lifetime = 25  # years
    
    # Simple CAPEX calculation
    # Base cost for solar field, piping, etc.
    base_capex = 1000000  
    # Tank cost scales with volume
    tank_cost = tank_volume_m3 * 500
    # HTF cost scales with mass
    htf_cost = htf_mass_kg * 2
    capex = base_capex + tank_cost + htf_cost
    
    # Simple OPEX calculation (e.g., 2% of CAPEX)
    opex = 0.02 * capex
    
    # Calculate discount factor sum
    discount_factor_sum = sum(1 / ((1 + discount_rate) ** year) for year in range(1, lifetime + 1))
    
    # Total discounted energy over lifetime
    discounted_energy = energy_yield_kwh * discount_factor_sum
    
    if discounted_energy == 0:
        return float('inf')
        
    lcoh = (capex + (opex * discount_factor_sum)) / discounted_energy
    return lcoh
