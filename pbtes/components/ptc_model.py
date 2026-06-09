import numpy as np
import CoolProp.CoolProp as cp

def properties_salt(T_prom_K, P_Pa, fluid='INCOMP::NaK'):
    """
    Returns cp [kJ/(kg·K)], mu [Pa·s], rho [kg/m³] for the fluid at T_prom_K and P_Pa.
    """
    try:
        specific_heat = cp.PropsSI('C', 'T', T_prom_K, 'P', P_Pa, fluid) / 1000.0
        viscosity = cp.PropsSI('V', 'T', T_prom_K, 'P', P_Pa, fluid)
        density = cp.PropsSI('D', 'T', T_prom_K, 'P', P_Pa, fluid)
    except Exception as e:
        # Fallback to standard Solar Salt properties if CoolProp fails
        # properties of Sodium-Potassium Nitrate (Solar Salt) at 450 °C (723.15 K)
        # cp ~ 1.5 kJ/kgK, mu ~ 0.002 Pa s, rho ~ 1850 kg/m3
        specific_heat = 1.5
        viscosity = 0.002
        density = 1850.0
    return specific_heat, viscosity, density

def eq_time(day_of_year):
    """
    Equation of time (EoT) in minutes.
    day_of_year: array or scalar (Julian day)
    """
    B = np.radians((360 / 365) * (day_of_year - 1))
    EoT = 229.2 * (0.000075 + 0.001868 * np.cos(B) - 0.032077 * np.sin(B)
                   - 0.014615 * np.cos(2 * B) - 0.04089 * np.sin(2 * B))
    return EoT

def solar_angles(lat, lon, day_of_year, hour_civil, mer_estandar=-60.0):
    """
    Calculates solar angles.
    All inputs and returned angles are in radians/degrees.
    """
    # Solar time and hour angle
    EoT = eq_time(day_of_year)
    hora_solar = hour_civil + (lon - mer_estandar) / 15.0 + EoT / 60.0
    omega = (hora_solar - 12.0) * 15.0   # degrees

    phi_rad = np.radians(lat)
    omega_rad = np.radians(omega)

    # Solar declination
    delta_s = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365))
    delta_s_rad = np.radians(delta_s)

    # Zenith angle
    cos_theta_z = (np.cos(phi_rad) * np.cos(delta_s_rad) * np.cos(omega_rad) +
                   np.sin(phi_rad) * np.sin(delta_s_rad))
    cos_theta_z = np.clip(cos_theta_z, -1.0, 1.0)
    theta_z = np.arccos(cos_theta_z)

    # Incidence angle (single-axis tracking)
    cos_theta_z_sq = np.cos(theta_z)**2
    cos_delta_s_sq = np.cos(delta_s_rad)**2
    sin_omega_sq = np.sin(omega_rad)**2
    arg_theta_i = np.sqrt(cos_theta_z_sq + cos_delta_s_sq * sin_omega_sq)
    arg_theta_i = np.clip(arg_theta_i, 0.0, 1.0)
    theta_i = np.arccos(arg_theta_i)

    # Azimuthal solar angle
    num = np.cos(theta_z) * np.sin(phi_rad) - np.sin(delta_s_rad)
    den = np.sin(theta_z) * np.cos(phi_rad)
    mask_zero = np.abs(np.sin(theta_z)) < 1e-10
    
    cociente = np.divide(num, den, where=~mask_zero, out=np.zeros_like(num))
    cociente = np.clip(cociente, -1.0, 1.0)
    gamma_s_abs = np.arccos(cociente)
    gamma_s = np.where(omega >= 0, gamma_s_abs, -gamma_s_abs)
    
    if isinstance(theta_z, np.ndarray):
        gamma_s[mask_zero] = 0.0
    elif mask_zero:
        gamma_s = 0.0

    return omega, theta_i, theta_z, gamma_s

def calculate_IAM(theta_i):
    """
    Calculate Incidence Angle Modifier based on sigmoidal Gompertz model.
    theta_i: angle in radians.
    """
    a = 1.00914330410119790216
    b = -6.88272949701514402676
    c = 0.68276514312435032661
    d = -0.00000000000007107747
    IAM = d + (a - d) * np.exp(-np.exp(-b * (theta_i - c)))
    return IAM


class PTCFieldModel:
    """
    In-house Parabolic Trough Collector Field Model.
    Designed to calculate outlet temperature and mass flow rate.
    """
    def __init__(self, params):
        self.params = params
        
        # Sizing / loop configuration placeholders
        self.N_PTC_real = None
        self.N_loops_real = None
        self.m_dot_PTC_real = None
        self.A_tot = None
        self.is_designed = False

    def design_solar_field(self, A_config, htf_fluid='INCOMP::NaK'):
        """
        Sizing of loops based on the design point: Dec 21 solar noon.
        """
        lat = self.params.get('latitude', -33.4375)
        lon = self.params.get('longitude', -70.65)
        mer_estandar = self.params.get('mer_estandar', -60.0)
        
        # Design point conditions
        T_ms_in = 420.0 + 273.15   # 420 °C in K
        T_ms_out = 560.0 + 273.15  # 560 °C in K
        T_ms_prom = 0.5 * (T_ms_in + T_ms_out)
        P_ms_in = 10e05            # 10 bar in Pa
        
        cp_ms, mu_ms, rho_ms = properties_salt(T_ms_prom, P_ms_in, htf_fluid)
        
        W_PTC = self.params.get('w_aperture', 6.77)
        L_PTC = self.params.get('l_module', 4.0)
        d_in_PTC = self.params.get('d_in', 0.065)
        
        A_PTC = W_PTC * L_PTC
        A_tubo_trans = np.pi / 4 * d_in_PTC**2
        
        rho_mirror = self.params.get('rho_mirror', 0.90)
        tau_pyrex = self.params.get('tau_pyrex', 0.945)
        alpha_abs = self.params.get('alpha_absorber', 0.94)
        GAMMA_PTC = self.params.get('gamma_intercept', 0.92)
        Fe_soil = self.params.get('fe_soil', 0.92)
        eta_o = rho_mirror * tau_pyrex * alpha_abs * GAMMA_PTC
        
        # Design solar angles
        _, theta_i_design, _, _ = solar_angles(lat, lon, 355, 12.0, mer_estandar)
        Gb_design = self.params.get('ptc_E', 900.0) / 1000.0  # W/m2 to kW/m2
        Tamb_design = self.params.get('ptc_tamb', 20.0) + 273.15
        
        Gbn_design = Gb_design * np.cos(theta_i_design)
        IAM_design = calculate_IAM(theta_i_design)
        
        # Reynolds calculation
        if Gbn_design >= 0.8:
            Re_design = 1.2e05
        elif 0.5 <= Gbn_design < 0.8:
            Re_design = 1e05
        else:
            Re_design = 8e04
            
        m_dot_PTC_design = Re_design * mu_ms * A_tubo_trans / d_in_PTC
        
        # Useful power and losses per module
        Q_dot_sun_design = eta_o * Fe_soil * A_PTC * Gbn_design * IAM_design
        DELTAT_design_loss = T_ms_prom - Tamb_design
        
        Q_dot_loss_length_design = (0.00154 * DELTAT_design_loss**2 + 0.2021 * DELTAT_design_loss - 24.899
                             + (0.00036 * DELTAT_design_loss**2 + 0.2029 * DELTAT_design_loss + 24.899)
                             * (Gbn_design / 0.9)) / 1000  # kW/m
        Q_dot_loss_design = Q_dot_loss_length_design * L_PTC
        Q_dot_PTC_design = Q_dot_sun_design - Q_dot_loss_design
        
        # Modules per loop
        DELTAT_c_design = Q_dot_PTC_design / (m_dot_PTC_design * cp_ms)
        DELTAT_ms_PTC = T_ms_out - T_ms_in
        N_PTC_design = DELTAT_ms_PTC / DELTAT_c_design
        N_PTC_real = int(np.ceil(N_PTC_design))
        if N_PTC_real % 2 != 0:
            N_PTC_real += 1
            
        m_dot_PTC_real = m_dot_PTC_design * (N_PTC_real / N_PTC_design)
        
        # Loop area and scaling to meet A_config
        A_loop = N_PTC_real * A_PTC
        N_loops_real = A_config / A_loop
            
        self.N_PTC_real = N_PTC_real
        self.N_loops_real = N_loops_real
        self.m_dot_PTC_real = m_dot_PTC_real
        self.A_tot = N_loops_real * N_PTC_real * A_PTC
        self.is_designed = True
        
        print(f"[In-house PTC Design] Sizing complete: N_loops={N_loops_real:.4f}, N_modules/loop={N_PTC_real}, m_dot/loop={m_dot_PTC_real:.3f} kg/s, A_tot={self.A_tot:.1f} m2")

    def solve_quasi_steady(self, T_in_C, P_in_bar, Tamb_C, DNI_W_m2, timestamp, htf_fluid='INCOMP::NaK', m_dot_field=None):
        """
        Runs hourly solver.
        Returns:
          T_out_C: float (outlet temperature of the field in °C)
          m_tot: float (total mass flow of the field in kg/s)
        """
        if not self.is_designed:
            A_config = self.params.get('ptc_A', 1500.0)
            self.design_solar_field(A_config, htf_fluid)
            
        lat = self.params.get('latitude', -33.4375)
        lon = self.params.get('longitude', -70.65)
        mer_estandar = self.params.get('mer_estandar', -60.0)
        
        day_of_year = timestamp.dayofyear
        hour_civil = timestamp.hour + timestamp.minute / 60.0
        
        # Solar angles and IAM
        _, theta_i, _, _ = solar_angles(lat, lon, day_of_year, hour_civil, mer_estandar)
        cos_theta_i = np.cos(theta_i)
        
        # DNI in kW/m²
        Gb_h = DNI_W_m2 / 1000.0
        Gbn_h = Gb_h * cos_theta_i
        
        # Check operation limit (DNI threshold)
        operando_mask = (Gbn_h >= 0.45)
        
        # optical efficiency parameters
        rho_mirror = self.params.get('rho_mirror', 0.90)
        tau_pyrex = self.params.get('tau_pyrex', 0.945)
        alpha_abs = self.params.get('alpha_absorber', 0.94)
        GAMMA_PTC = self.params.get('gamma_intercept', 0.92)
        Fe_soil = self.params.get('fe_soil', 0.92)
        eta_o = rho_mirror * tau_pyrex * alpha_abs * GAMMA_PTC
        
        W_PTC = self.params.get('w_aperture', 6.77)
        L_PTC = self.params.get('l_module', 4.0)
        A_PTC = W_PTC * L_PTC
        
        IAM = calculate_IAM(theta_i)
        
        # Solar heat collected per module
        Q_sun_h = eta_o * Fe_soil * A_PTC * Gbn_h * IAM if operando_mask else 0.0
        
        # Inlet parameters in K and Pa
        T_ms_in = T_in_C + 273.15
        Tamb = Tamb_C + 273.15
        P_ms_in = P_in_bar * 1e5
        
        mode = self.params.get('ptc_mode', 'constant_T_out')
        
        if not operando_mask:
            # Field not operating: return inlet temp and zero flow
            return T_in_C, 0.0

        if mode == 'constant_m_dot' or m_dot_field is not None:
            # CASE 1: Constant mass flow, variable outlet temperature
            if m_dot_field is not None:
                m_dot_loop = m_dot_field / self.N_loops_real
            else:
                m_dot_loop = self.m_dot_PTC_real
            T_ms_out_h = T_ms_in + 40.0 # first estimate
            
            tol = 0.001
            max_iter = 200
            error = 1.0
            iteracion = 0
            
            while error > tol and iteracion < max_iter:
                T_ms_out_prev = T_ms_out_h
                T_ms_prom_h = 0.5 * (T_ms_in + T_ms_out_h)
                
                cp_h, mu_h, rho_h = properties_salt(T_ms_prom_h, P_ms_in, htf_fluid)
                DELTAT_loss_h = T_ms_prom_h - Tamb
                
                Q_loss_length_h = (0.00154 * DELTAT_loss_h**2 + 0.2021 * DELTAT_loss_h - 24.899
                                   + (0.00036 * DELTAT_loss_h**2 + 0.2029 * DELTAT_loss_h + 24.899)
                                   * (Gbn_h / 0.9)) / 1000
                Q_loss_h = Q_loss_length_h * L_PTC
                Q_PTC_h = Q_sun_h - Q_loss_h
                
                T_ms_out_h = T_ms_in + self.N_PTC_real * Q_PTC_h / (m_dot_loop * cp_h)
                
                error = abs(T_ms_out_h - T_ms_out_prev) / max(abs(T_ms_out_prev), 1e-6)
                iteracion += 1
                
            T_out_C = T_ms_out_h - 273.15
            if T_out_C > 599.0:
                T_out_C = 599.0
            m_tot = self.N_loops_real * m_dot_loop
            
            # Sanity check: if solar gains are negative or net heating is negative, clamp to T_in
            if T_out_C < T_in_C:
                T_out_C = T_in_C
                m_tot = 0.0
                
            return T_out_C, m_tot
            
        else:
            # CASE 2: Constant outlet temperature, variable mass flow
            T_ms_out = (self.params.get('ptc_T_out_target', 560.0) if 'ptc_T_out_target' in self.params else 560.0) + 273.15
            
            if T_ms_in >= T_ms_out:
                return T_in_C, 0.0
                
            T_prom_fijo = 0.5 * (T_ms_in + T_ms_out)
            cp_fijo, mu_fijo, rho_fijo = properties_salt(T_prom_fijo, P_ms_in, htf_fluid)
            
            DELTAT_target = T_ms_out - T_ms_in
            m_dot_min = 0.2 * self.m_dot_PTC_real
            m_dot_max = self.m_dot_PTC_real
            
            DELTAT_loss_h2 = T_prom_fijo - Tamb
            Q_loss_length_h2 = (0.00154 * DELTAT_loss_h2**2 + 0.2021 * DELTAT_loss_h2 - 24.899
                                + (0.00036 * DELTAT_loss_h2**2 + 0.2029 * DELTAT_loss_h2 + 24.899)
                                * (Gbn_h / 0.9)) / 1000
            Q_loss_h2 = Q_loss_length_h2 * L_PTC
            Q_PTC_h2 = Q_sun_h - Q_loss_h2
            
            if Q_PTC_h2 <= 0:
                return T_in_C, 0.0
                
            Q_loop_h2 = self.N_PTC_real * Q_PTC_h2
            m_dot_required = Q_loop_h2 / (cp_fijo * DELTAT_target)
            
            if m_dot_required >= m_dot_min:
                m_dot_loop = min(m_dot_required, m_dot_max)
                if m_dot_required > m_dot_max:
                    # Capped mass flow: outlet temperature drops
                    T_out_K = T_ms_in + Q_loop_h2 / (m_dot_max * cp_fijo)
                else:
                    T_out_K = T_ms_out
                
                T_out_C = T_out_K - 273.15
                if T_out_C > 599.0:
                    T_out_C = 599.0
                m_tot = self.N_loops_real * m_dot_loop
                return T_out_C, m_tot
            else:
                # Irradiance too low to maintain minimum mass flow
                return T_in_C, 0.0
