"""
core.py

This module contains:
1) The SolarThermalSystem class, which builds and solves a TESPy network
   with supercritical CO2 as the working fluid, a pump, a parabolic
   trough collector, and a simple process heat exchanger.

2) The Reporting class, which handles plotting of results from a parametric
   analysis or time-step simulation.

All methods are commented with details on their purpose and functionality.
"""
import tespy.networks as tpn
import tespy.connections as tpcn
import tespy.components as tpc
from tespy.components.heat_exchangers.parabolic_trough import ParabolicTrough
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tqdm import tqdm
import time
import pandas as pd
import numpy as np
import json, os
from copy import deepcopy
import CoolProp.CoolProp as cp
from scipy.optimize import brentq
from scipy.interpolate import interp1d

class PTCField(ParabolicTrough):
    """
    A parabolic trough collector field composed of several parallel rows.

    This subclass internally divides the inlet mass flow among the rows,
    calculates as if there's only one row, and then scales Q, Qloss, etc.
    by the number of rows.
    """

    def __init__(self, label, rows=1, modules=1, **kwargs):
        """
        Parameters
        ----------
        label : str
            The label for the collector.
        rows : int
            Number of identical parallel rows in the solar field.
        kwargs :
            Any additional keyword arguments you want to pass to
            the parent ParabolicTrough constructor (e.g. collector geometry).
        """
        super().__init__(label, **kwargs)
        self.rows = rows
        self.modules = modules

        # We'll store the "single module pr" here if the user sets it
        self.pr_module = None

    def calc_parameters(self):
        """
        Override the parent's calculation routine to:
          - Temporarily reduce mass flow to 1/rows,
          - Call parent calculations,
          - Scale the results by rows,
          - Restore total flow at the outlet.
        """
        # 1) Store total inlet mass flow and total area
        
        if not hasattr(self, 'in_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'target', None) == self:
                    self.in_conn = obj
                    break
        
        if not hasattr(self, 'in_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'target', None) == self:
                    self.in_conn = obj
                    break
        
        if not hasattr(self, 'in_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'target', None) == self:
                    self.in_conn = obj
                    break
        
        if not hasattr(self, 'in_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'target', None) == self:
                    self.in_conn = obj
                    break
        
        if not hasattr(self, 'in_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'target', None) == self:
                    self.in_conn = obj
                    break
        total_m_in = self.in_conn.m.val_SI





        
        # 2) Scale both mass flow and area for a single-row
        if self.rows > 1:
            # Inlet flow
            self.in_conn.m.val_SI = total_m_in / self.rows


        # 3) Run the usual collector calculation (for the scaled single-row)
        super().calc_parameters()

        # 4) Scale Q and Q_loss from single-row to total field
        if self.rows > 1:
            # self.Q is a ComponentProperties object
            self.Q.val_SI *= self.rows
            # self.Q_loss may not always be present, so check first
            if hasattr(self, 'Q_loss'):
                self.Q_loss.val_SI *= self.rows

        # 5) Restore the total mass flow and total area on the outlet and component
        
        if not hasattr(self, 'out_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'source', None) == self:
                    self.out_conn = obj
                    break
        
        if not hasattr(self, 'out_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'source', None) == self:
                    self.out_conn = obj
                    break
        
        if not hasattr(self, 'out_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'source', None) == self:
                    self.out_conn = obj
                    break
        
        if not hasattr(self, 'out_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'source', None) == self:
                    self.out_conn = obj
                    break
        
        if not hasattr(self, 'out_conn'):
            import gc
            for obj in gc.get_objects():
                if type(obj).__name__ == 'Connection' and getattr(obj, 'source', None) == self:
                    self.out_conn = obj
                    break
        self.out_conn.m.val_SI = total_m_in





      
class ThermalEnergyStorage:
    """
    Manages the thermal energy storage with capability to store, release, or maintain energy,
    simulating temperature profiles and managing energy state.
    """

    def __init__(self, tes_params, name, dt):
        """
        

        Parameters
        ----------
        dt : Int
            Time step.
        tes_params : Dict
            DESCRIPTION.
        name : Str
            TES name.

        Returns
        -------
        None.

        """
        """
        Initializes the thermal energy storage unit.
        :param capacity: float, the energy storage capacity in kWh.
        :param initial_temperature: float, the initial temperature of the storage in degrees Celsius.
        :param name: str, name of the TES module.
        """

        self.dt = dt  # seconds

        self.name = name
        self.state = 'charge'  # default state
        self.inlet = 'top'
        self.outlet = 'bottom'
        self.valve_state = 'off'  # Valve controlling the TES flow
    
        self.initial_temperature = tes_params['Initial temperature']
        self.HT = tes_params['Tank lenght']
        self.Dint = tes_params['Tank diameter']
        self.dp = tes_params['Particle diameter']
        self.e = tes_params['Void fraction']
        self.rho_s = tes_params['Solid density']
        self.cp_s = tes_params['Solid specific heat']
        self.k_s = tes_params['Solid conductivity']
        self.wst = tes_params['Wall thinckness']
        self.kst = tes_params['Tank conductivity']
        self.wins = tes_params['Insulation thickness']
        self.kins = tes_params['Insulation conductivity']
        self.HTF = tes_params['HTF']
        self.AT = 0.25 * self.Dint**2 * np.pi  # m2 - Ãrea transversal del estanque
        self.Aphi = 0.25 * (25.4e-3*2)**2* np.pi  # m2 - Ãrea transversal del tubo de descarga
        
        self.HTF_P = 102325
        
        self.xev = np.linspace(0,1,20)
        self.init = np.ones_like(self.xev)*(self.initial_temperature)
        self.profile = self.init
        self.t_max = self.initial_temperature
        self.t_min = self.initial_temperature
        self.tout = self.initial_temperature
        self.mflow = 0
        self.V_in = 0

    def air_params(self):
        self.init = np.clip(self.init, 300.1, 600.0)
        self.tout = max(self.tout, 300.1)
        Tav = np.average(self.init)+273.15
        # Propiedades del fluido - Calculados a temperatura media
        self.rho_f = cp.PropsSI('D', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.cp_f = cp.PropsSI('C', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.k_f = cp.PropsSI('L', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.mu_f = cp.PropsSI('V', 'T', Tav, 'P', self.HTF_P, self.HTF)
        
        self.rho_out = cp.PropsSI('D', 'T', self.tout+273.15, 'P', self.HTF_P, self.HTF)
        
    def eq_params(self, T_in, mass_flow):
        """
        

        Parameters
        ----------
        T_in : Float
            Inlet Temperature.
        V_in : Float
            Inlet Velocity.

        Returns
        -------
        None.

        """
 
        self.t_in = T_in
        
        self.mflow = mass_flow  # kg/s
        #print(self.mflow)
        
        self.air_params()
        
        # Flujo mÃ¡sico por unidad de Ã¡rea al interior del TES
        G = self.mflow / self.AT 
        # CÃ¡lculo de alpha y k_eff
        Re = G*self.dp/self.mu_f  # Reynolds
        Pr = self.mu_f * self.cp_f / self.k_f  # Prandtl
        ff = 6*(1-self.e)/self.dp  # m - Factor de forma roca - fluido
        rho_cp_line = (self.e * self.rho_f * self.cp_f + (1-self.e) * self.rho_s * self.cp_s) # Capacitancia equivalente
        self.kappa = self.e * (self.rho_f * self.cp_f) / rho_cp_line  # Factor kappa (adimensional de interÃ©s para el modelo)
        u_in = G / (self.rho_f)  # m/s - Velocidad intersticial
        hv = ff * (self.k_f/self.dp) * 1.32 * Re**0.59 * Pr**(1/3)  # W/m3 K - Coef. de transferencia de calor volumÃ©trica (Tesis Daniel Orellana)
        k_line = (self.e *self.k_f + (1-self.e)*self.k_s) # Conductividad promedio
        k_eff = k_line + ((1-self.e) * (self.rho_s*self.cp_s) * (G*self.cp_f/rho_cp_line))**2/hv  # Conductividad efectiva (Ver ec. 7 de Paper 1)
        alpha = k_eff / rho_cp_line  # CÃ¡lculo de alpha
        self.Pe = u_in * self.HT / alpha  # CÃ¡lculo de PÃ©clet que cambia con el tiempo (adimensional de interÃ©s para el modelo)
        self.a = self.kappa * self.Pe / 2
        if self.a > 15.0:
            self.a = 15.0
            self.Pe = self.a * 2 / self.kappa
        elif self.a < -15.0:
            self.a = -15.0
            self.Pe = self.a * 2 / self.kappa
       
        # Resistencia interna
        hint = (self.k_f/self.dp) * (0.203 * Re**(1/3) * Pr**(1/3) + 0.22 * Re**0.8 * Pr**0.4)
        Rint = 1/hint
        # Coeficiente de transferencia de calor
        hw = 1/Rint
        # Stanton
        self.beta = 4/self.Dint
        self.St = 0.75*hw*self.beta*self.HT/(rho_cp_line*u_in)
        self.b = -(self.St + self.a**2/self.Pe)
        
        self.tau = u_in*self.dt/self.HT
        

    def _eq(self, ev, a):
        """
        EcuaciÃ³n trascendental para obtener autovalores

        Parameters
        ----------
        ev : TYPE
            DESCRIPTION.
        a : TYPE
            DESCRIPTION.

        Returns
        -------
        eq : TYPE
            DESCRIPTION.

        """
    
        # solve transcendental eq : ev + a * tan(ev) = 0
        eq1 = ev / a
        eq2 = np.tan(ev)
        eq = eq1 + eq2
    
        return eq    
    
    def solve_eq(self, Nroots, a):
        """
        Algoritmo de bÃºsqueda de raÃ­ces

        Parameters
        ----------
        Nroots : Roots number.
        a : Parameter a.

        Returns
        -------
        rts : Roots.

        """
        
        # Allocate space
        rts = np.zeros(Nroots)
        # Margin to stay away from poles
        margin = 1e-5
        # First solution
        left = 0
        right = np.pi / (2)
        _ = brentq(self._eq, left, right - margin, args=(a))
        for i in range(1, Nroots+1):
            left = (2*i - 1)*np.pi/(2)
            right = (2*i + 1)*np.pi/(2)
            rts[i-1] = brentq(self._eq, left + margin, right - margin, args=(a))
    
        return rts    

    def calc_solution(self):
        """
        FunciÃ³n que evalÃºa la soluciÃ³n dadas las condiciones de un paso de tiempo

        Returns
        -------
        sol : List
            DESCRIPTION.

        """
        theta = (self.t_in-self.t_min)/(self.t_max-self.t_min)
        init = (self.init-self.t_min)/(self.t_max-self.t_min)
        ############# Sol. Estacionaria
        # Definir constantes de la soluciÃ³n estacionaria
        k1 = np.longdouble(0.5 * (self.kappa * self.Pe - np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        k2 = np.longdouble(0.5 * (self.kappa * self.Pe + np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        C2 = theta * k1 * np.exp(k1) / (k1*np.exp(k1) - k2*np.exp(k2))
        C1 = theta - C2
        # SoluciÃ³n estacionaria
        Mx = lambda x : C1*np.exp(k1*x) + C2*np.exp(k2*x)
    
        ############# Sol. Transiente        
        # Calcular autovalores
        lbd = self.solve_eq(200, self.a)
        # Definir la functiÃ³n Kernel
        fn = np.sqrt(2) * np.sqrt((lbd**2 + self.a**2)/(lbd**2 + self.a**2 + self.a))
        Knx = lambda x : fn[:, None] * np.sin(lbd[:, None]*x)
        # Transformada integral de la soluciÃ³n inicial
        # 1, Interpolar datos de la condiciÃ³n inicial
        xint = np.linspace(0, 1, 200)
        t0_int = interp1d(self.xev, init, bounds_error=False, fill_value='extrapolate')(xint)
        phi0 = (t0_int - Mx(xint)) / np.exp(self.a*xint)
        phi0n = np.trapz(Knx(xint)*phi0, x=xint, axis=1)
        # 2, SoluciÃ³n del problema de autovalores
        phin = phi0n[:, None] * np.exp(-lbd[:, None]**2 * self.tau / self.Pe)
        # 3, SoluciÃ³n del problema transiente
        Nxt = np.exp(self.a*self.xev[:, None] + self.b*self.tau) * (np.sum(phin * Knx(self.xev), axis=0)[:, None])
    
        ############# Sol.
        sol = Mx(self.xev)[:, None] + Nxt
    
        return sol
    
    def update_temperature_profile(self, T_in, mass_flow, initial_profile):
        # Clamp to valid CoolProp range
        initial_profile = np.clip(np.array(initial_profile), 300.1, 600.0)
        T_in = max(T_in, 300.1)
        """
        Updates the temperature profile of the TES for the given time.

        Parameters
        ----------
        dt : TYPE
            Time step.
        mass_flow : Float
            Inlet mass flow [kg/s].
        T_in : Float
            Inlet Temperature [Â°C].

        Returns
        -------
        None.

        """
        
        self.init = initial_profile
        self.t_max = max(self.profile.max(), T_in)
        self.t_min = min(self.profile.min(), T_in)
        self.eq_params(T_in, mass_flow)
        self.profile = self.calc_solution().reshape((len(self.xev)))*(self.t_max-self.t_min) + self.t_min
        self.init = self.profile
        self.tout = self.profile[-1]
        return self.profile
    
    def calc_heat_loss(self, profile, dt, T_amb):
        # Clamp profile to valid CoolProp range for NaK before any use
        profile = np.clip(np.array(profile), 300.1, 600.0)
        """
        Update the temperature profile of a stratified TES packed bed over a time step dt.
        
        The packed bed consists of a solid matrix and a fluid. Fluid properties (density and cp)
        are calculated using CoolProp at the current layer temperature. The effective thermal capacity 
        (mass*cp) for each layer is computed from the contributions of both the fluid and the solid.

        Returns:
            np.array: Updated temperature profile (in Â°C) after dt seconds.
            
        Notes:
            - Each layer has a volume V_layer = A_cross * dz, with dz = height / n_layers and 
              A_cross = Ï€*(diameter/2)Â².
            - The effective thermal capacity of a layer is computed as:
                  C_eff = V_layer * [epsilon * (fluid_density*fluid_cp) + (1-epsilon)*(solid_density*solid_cp)]
              where the fluid properties are computed at the layer temperature (converted to Kelvin).
            - For heat loss, the thermal resistance is given by:
                  R_total = wall_thickness/(wall_k*A) + ins_thickness/(ins_k*A)
              with the effective area A determined as follows:
                  Top layer: A = (top surface area) + (lateral wall area of the layer)
                  Bottom layer: A = (lateral wall area of the layer) [no bottom surface]
                  Interior layers: A = (lateral wall area of the layer)
            - The heat loss Q_loss (in Watts) is computed by:
                  Q_loss = (T_layer - ambient_temp) / R_total
            - Temperature drop dT = Q_loss*dt/C_eff, with T_new = T_old - dT.
        """
        n_layers = len(profile)
        dz = self.HT / n_layers
        A_cross = np.pi * (self.Dint / 2)**2  # Cross-sectional area of the tank
        volume_layer = A_cross * dz          # Volume of each layer
        
        new_T_profile = np.zeros_like(profile)
        
        # Loop over each layer (top to bottom)
        for i, T in enumerate(profile):
            T = max(T, 300.1)  # clamp to CoolProp valid range for NaK (>300C)
            T_K = T + 273.15
            fluid_density = cp.PropsSI('D', 'T', T_K, 'P', self.HTF_P, self.HTF)  # kg/mÂ³
            fluid_cp = cp.PropsSI('C', 'T', T_K, 'P', self.HTF_P, self.HTF)         # J/kgÂ·K
            
            # Compute effective thermal capacity (J/K) for the layer:
            # (fluid and solid contributions weighted by their volume fractions)
            effective_capacity = volume_layer * (self.e * fluid_density * fluid_cp +
                                                 (1 - self.e) * self.rho_s * self.cp_s)
            
            # Determine the effective heat loss area for this layer:
            if i == 0:
                # Top layer: loss via top surface + lateral wall area of the layer
                area = A_cross + (np.pi * self.Dint * dz)
            elif i == n_layers - 1:
                # Bottom layer: loss only via lateral wall (no bottom heat loss)
                area = np.pi * self.Dint * dz
            else:
                # Interior layers: lateral wall area only
                area = np.pi * self.Dint * dz
            
            # Compute the thermal resistances (K/W) through the wall and insulation:
            R_wall = np.log((self.Dint+self.wst)/(self.Dint)) / (np.pi*self.HT*self.kst)
            R_ins  = np.log((self.Dint+self.wst+self.wins)/(self.Dint+self.wst)) / (np.pi*self.HT*self.kins)
            h_conv = 4 #W/m2 K
            R_conv = 1/(h_conv * area)
            
            #print(R_wall, R_ins)
            R_total = R_wall + R_ins + R_conv
            
            # Calculate heat loss (W). Positive when layer temperature is above ambient.
            Q_loss = (T - T_amb) / R_total
            
            # Compute temperature change dT (Â°C) for the time step dt
            dT = (Q_loss * dt) / effective_capacity

            
            new_T_profile[i] = T - dT
            
        return new_T_profile

    
    def set_state(self, new_state):
        """
        Sets the operational state of the TES and switches the inlet and outlet if changing from charge to discharge and vice versa.
        :param new_state: str, the new state of the TES ('charge', 'discharge', 'standby').
        """
        
        if new_state != self.state: 
            if new_state in ['charge', 'discharge']:
                # Switch inlet and outlet when changing between charge and discharge
                self.inlet, self.outlet = self.outlet, self.inlet
                self.profile = np.flip(self.profile)
        self.state = new_state

    def calculate_SoC(self, profile):
        """
        Calculate the energy stored in a TES unit by integrating the temperature profile.
        
        :param tes_temps: List of temperatures from each TES unit
        :return: List of energy stored in each TES unit
        """

        # Use dynamic properties at T_avg to get accurate property values
        T_avg_C = np.mean(profile)
        T_avg_K = T_avg_C + 273.15
        T_ref = 300.0  # Base discharge temperature
        
        try:
            rho_f = cp.PropsSI('D', 'T', T_avg_K, 'P', self.HTF_P, self.HTF)
            cp_f  = cp.PropsSI('C', 'T', T_avg_K, 'P', self.HTF_P, self.HTF)
        except Exception:
            # Fallback if CoolProp fails
            self.air_params()
            rho_f = self.rho_out
            cp_f = self.cp_f
            
        Cp_pb = self.cp_s * self.e + cp_f * (1 - self.e)   # J/(kg·K) effective
        rho_pb = self.rho_s * (1 - self.e) + rho_f * self.e
        volume = np.pi * (self.Dint / 2)**2 * self.HT
        dT = np.array(profile) - T_ref
        SoC = volume * rho_pb * Cp_pb * np.mean(dT)
        return max(SoC / 3.6e6, 0.0)  # kWh


class ZincPool:
    """
    Lumped-capacitance model of a galvanizing zinc bath.

    Tracks the pool temperature via a single-node energy balance:
        m_pool * cp_zinc * dT/dt = Q_hx - Q_loss - Q_parts

    Parameters
    ----------
    mass : float
        Mass of zinc in the bath (kg). Default 150 metric tons.
    temp_initial : float
        Initial zinc pool temperature (C). Default 450.
    cp : float
        Specific heat of molten zinc (J/kg.K). Default 512.
    UA_loss : float
        Heat loss coefficient to ambient (W/K). Default 500.
    target_temp : float
        Target operating temperature (C). Default 450.
    ttd_hx : float
        Terminal temperature difference for process HX. The hot-side
        outlet (NaK leaving the HX) must be at least T_zinc + ttd_hx.
        Default 20 K.
    op_start_hour : int
        Hour of day when production starts (0-23). Default 8.
    op_end_hour : int
        Hour of day when production ends (0-23). Default 20.
    op_days_per_week : int
        Number of operating days per week (1=Mon only, 5=Mon-Fri).
        Default 5.
    mass_steel_per_hour : float
        Steel mass processed per hour (kg/hr). Default 5000.
    cp_steel : float
        Specific heat of steel (J/kg.K). Default 460.
    T_steel_inlet : float
        Temperature of steel parts entering the bath (C). Default 25.
    """

    def __init__(self, params=None):
        p = params or {}
        self.mass = p.get('mass', 150e3)
        self.temperature = p.get('temp_initial', 450)
        self.cp = p.get('cp_zinc', 512)
        self.UA = p.get('UA_loss', 500)
        self.target = p.get('target_temp', 450)
        self.TTD = p.get('ttd_hx', 20)
        self.op_start = p.get('op_start_hour', 8)
        self.op_end = p.get('op_end_hour', 20)
        self.op_days = p.get('op_days_per_week', 5)
        self.mass_steel = p.get('mass_steel_per_hour', 5000)
        self.cp_steel = p.get('cp_steel', 460)
        self.T_steel_in = p.get('T_steel_inlet', 25)

    def is_operating(self, timestamp):
        """Check if the production line is running at this hour."""
        hour_ok = self.op_start <= timestamp.hour < self.op_end
        day_ok = timestamp.weekday() < self.op_days
        return hour_ok and day_ok

    def heat_to_parts_kW(self, timestamp):
        """Heat extracted by cold steel parts being dipped (kW)."""
        if not self.is_operating(timestamp):
            return 0.0
        Q_J_per_hour = (
            self.mass_steel * self.cp_steel
            * (self.temperature - self.T_steel_in)
        )
        return Q_J_per_hour / 3600.0 / 1000.0

    def heat_loss_kW(self, T_amb):
        """Heat loss to ambient through tank walls (kW)."""
        return self.UA * (self.temperature - T_amb) / 1000.0

    def process_outlet_temp(self):
        """NaK temperature required at process HX outlet to drive heat
        transfer into the zinc pool (zinc temperature + TTD)."""
        return self.temperature + self.TTD

    def update(self, Q_in_kW, dt_s, T_amb, timestamp):
        Q_parts = self.heat_to_parts_kW(timestamp)
        Q_loss = self.heat_loss_kW(T_amb)
        # Cap heat input to prevent overheating
        Q_needed = Q_loss + Q_parts + (
            (self.target - self.temperature) * self.mass * self.cp
            / (1000.0 * dt_s)
        )
        Q_used = max(0.0, min(Q_in_kW, Q_needed)) if self.temperature >= self.target else Q_in_kW
        net_kW = Q_used - Q_loss - Q_parts
        dT = net_kW * 1000.0 * dt_s / (self.mass * self.cp)
        self.temperature += dT
        return self.temperature


class SolarThermalSystem:
    """
    The SolarThermalSystem class encapsulates a steady-state TESPy network with:
      - A Pump (for circulating CO2 at high pressure)
      - A ParabolicTrough collector (using TESPy's built-in class)
      - A simple HeatExchanger for process demand

    It is designed for parametric/time-step analyses in which you can vary
    the DNI (irradiance) at each solve. 
    """

    def __init__(self, rows=1, modules=1, 
                 tes_params=None, 
                 component_params = None, 
                 conexion_params=None,
                 HTF=None,
                 topology='Parallel',
                 tank_config='indirect'):
        """
        Constructor initializes placeholders for the network, components, 
        and connections. Actual creation of these will occur in other methods.
        """
        self.HTF = HTF
        self.topology = topology
        self.tank_config = tank_config  # 'direct' or 'indirect'
        self.rows = rows
        self.modules = modules
        
        self.tes_params = tes_params
        self.TES_dt = 3600
        
        self.component_params = component_params 
        self.conexion_params = conexion_params
        self.network = None
        self.pump = None
        self.ptc_field = None
        self.process_hx = None
        self.cycle_closer = None
        self.discharge_hx = None 

        self.conn_pump_to_ptc = None
        self.conn_ptc_to_hx = None
        self.conn_hx_to_cc = None
        self.conn_cc_to_pump = None
        self.conn_pump_to_dhx = None
        self.conn_dhx_to_ph = None

        self.results = {}
        self.tes = ThermalEnergyStorage(self.tes_params, name='TES', dt=self.TES_dt)
        
        self.ptc_field_A = self.component_params['ptc_A']

        self._zinc_pool_T06 = None


    def create_network(self, mode: int, design_mode: str = 'design'):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        
        In 'design' mode: all component parameters (Q, ttd, A, E, T, pr) are set.
        In 'offdesign' mode: only structural parameters (p, fluid, pr) are set;
                             thermal parameters come from stored design.
        """
        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600])

        # 3) Create and add components
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')

        if mode in [1, 5, 6]:
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
            else:
                self.charge_tes_hx = tpc.SimpleHeatExchanger(label='Charge_TES_Pipe')
            if mode == 1 and getattr(self, 'topology', 'Parallel') == 'Parallel':
                self.splitter1 = tpc.nodes.splitter.Splitter(label='Splitter1')
                self.merge2 = tpc.nodes.merge.Merge(label='Merge2')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
                self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        elif mode == 3:
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_04 = tpcn.Connection(self.discharge_tes_hx, 'out2', self.preheater_hx, 'in1', label='04_DHX_PH')
                self.conn_11 = tpcn.Connection(self.cycle_closer, 'out1', self.discharge_tes_hx, 'in2', label='11_CC_DHX')
                self.conn_15 = tpcn.Connection(self.tes_dch_source, 'out1', self.discharge_tes_hx, 'in1', label='15_DCHSC_DHX')
                self.conn_16 = tpcn.Connection(self.discharge_tes_hx, 'out1', self.tes_dch_sink, 'in1', label='16_DHX_DCHSK')
                self.network.add_conns(self.conn_04, self.conn_05, self.conn_06, self.conn_11, self.conn_15, self.conn_16)
                for conn in [self.conn_04, self.conn_05, self.conn_06, self.conn_11, self.conn_15, self.conn_16]:
                    conn.set_attr(T0=520, h0=700, m0=30, p0=5)
                self.conn_15.set_attr(p=self.conexion_params['15_p'], fluid=self.conexion_params['15_f'])
                self.discharge_tes_hx.set_attr(pr1=1.0, pr2=1.0)
            else:
                self.conn_04 = tpcn.Connection(self.discharge_tes_hx, 'out1', self.preheater_hx, 'in1', label='04_DHX_PH')
                self.conn_11 = tpcn.Connection(self.cycle_closer, 'out1', self.discharge_tes_hx, 'in1', label='11_CC_DHX')
                self.network.add_conns(self.conn_04, self.conn_05, self.conn_06, self.conn_11)
                for conn in [self.conn_04, self.conn_05, self.conn_06, self.conn_11]:
                    conn.set_attr(T0=500, h0=714, m0=35, p0=5)
                self.discharge_tes_hx.set_attr(pr=0.98)

        elif mode == 4:
            self.conn_04 = tpcn.Connection(self.cycle_closer, 'out1', self.preheater_hx, 'in1', label='04_CC_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            self.network.add_conns(self.conn_04, self.conn_05, self.conn_06)
            for conn in [self.conn_04, self.conn_05, self.conn_06]:
                conn.set_attr(T0=500, h0=714, m0=35, p0=5)

        elif mode == 5:
            self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
            self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.charge_tes_hx, 'in1', label='02_PTC_CHX')
            self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.preheater_hx, 'in1', label='10_CHX_PH')
            self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
            self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer, 'in1', label='06_PR_CC')
            if getattr(self, 'tank_config', 'indirect') == 'indirect':
                self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                self.network.add_conns(self.conn_01, self.conn_02, self.conn_10, self.conn_05, self.conn_06, self.conn_13, self.conn_14)
                for c in [self.conn_01,self.conn_02,self.conn_10,self.conn_05,self.conn_06,self.conn_13,self.conn_14]:
                    c.set_attr(T0=550, h0=700, m0=30, p0=5)
            else:
                self.network.add_conns(self.conn_01, self.conn_02, self.conn_10, self.conn_05, self.conn_06)
                for c in [self.conn_01,self.conn_02,self.conn_10,self.conn_05,self.conn_06]:
                    c.set_attr(T0=550, h0=700, m0=30, p0=5)

        elif mode == 6:
            if getattr(self, 'topology', 'Parallel') == 'Series':
                self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.preheater_hx, 'in1', label='02_PTC_PH_Series')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR_Series')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.charge_tes_hx, 'in1', label='06_PR_CHX_Series')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC_Series')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10, self.conn_13, self.conn_14]:
                        conn.set_attr(T0=500, h0=700, m0=2)
                else:
                    self.network.add_conns(self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10)
                    for conn in [self.conn_01, self.conn_02, self.conn_05, self.conn_06, self.conn_10]:
                        conn.set_attr(T0=500, h0=700, m0=2)
            else:
                self.cycle_closer2 = tpc.CycleCloser(label='CycleCloser2')
                self.conn_01 = tpcn.Connection(self.cycle_closer, 'out1', self.ptc_field, 'in1', label='01_CC_PTC')
                self.conn_02 = tpcn.Connection(self.ptc_field, 'out1', self.charge_tes_hx, 'in1', label='02_PTC_CHX')
                self.conn_10 = tpcn.Connection(self.charge_tes_hx, 'out1', self.cycle_closer, 'in1', label='10_CHX_CC')
                self.conn_04 = tpcn.Connection(self.cycle_closer2, 'out1', self.preheater_hx, 'in1', label='04_CC2_PH')
                self.conn_05 = tpcn.Connection(self.preheater_hx, 'out1', self.process_hx, 'in1', label='05_PH_PR')
                self.conn_06 = tpcn.Connection(self.process_hx, 'out1', self.cycle_closer2, 'in1', label='06_PR_CC2')
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_13 = tpcn.Connection(self.tes_ch_source, 'out1', self.charge_tes_hx, 'in2', label='13_CHSC_CHX')
                    self.conn_14 = tpcn.Connection(self.charge_tes_hx, 'out2', self.tes_ch_sink, 'in1', label='14_CHX_CHSK')
                    conns = [self.conn_01, self.conn_02, self.conn_10, self.conn_04, self.conn_05, self.conn_06, self.conn_13, self.conn_14]
                else:
                    conns = [self.conn_01, self.conn_02, self.conn_10, self.conn_04, self.conn_05, self.conn_06]
                self.network.add_conns(*conns)
                for conn in conns: conn.set_attr(T0=500, h0=700, m0=5)
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.conn_02.set_attr(p=self.conexion_params['6_p'], fluid=self.conexion_params['6_f'])
                    self.charge_tes_hx.set_attr(pr1=1.0, pr2=1.0)


        # === STRUCTURAL parameters (always applied, design + offdesign) ===
        
        
        # PTC pressure drop (Series only)
        if mode in [1, 2, 5, 6]:
            if getattr(self, 'topology', 'Parallel') == 'Series':
                self.ptc_field.set_attr(pr=1.0)
        
            self.conn_01.set_attr(p=self.conexion_params['6_p'], fluid=self.conexion_params['6_f'])
        
        # Secondary loop connection pressure and fluid (always)
        if mode in [1, 5, 6] and hasattr(self, 'conn_13'):
            self.conn_13.set_attr(p=self.conexion_params['13_p'], fluid=self.conexion_params['13_f'])
        if mode == 3 and hasattr(self, 'conn_15'):
            self.conn_15.set_attr(p=self.conexion_params['15_p'], fluid=self.conexion_params['15_f'])
        
            if hasattr(self, 'conn_06') and self.conn_06 is not None:
                self.conn_06.set_attr(
                    p=self.conexion_params['6_p'],
                    fluid=self.conexion_params['6_f']
                )
        
            if mode == 1 and hasattr(self, 'conn_09') and self.conn_09 is not None:
                self.conn_09.set_attr(p=self.conexion_params['6_p'])
            elif mode in [5, 6] and hasattr(self, 'conn_02') and self.conn_02 is not None:
                self.conn_02.set_attr(p=self.conexion_params['6_p'])
        
            if hasattr(self, 'conn_06') and self.conn_06 is not None:
                self.conn_06.set_attr(
                    p=self.conexion_params['6_p'],
                    fluid=self.conexion_params['6_f']
                )
        
        # HX pressure drops (structural; skip for M6 Parallel - uses conn p anchors)
        is_m6_par = (mode == 6 and getattr(self, 'topology', 'Parallel') == 'Parallel')
        if mode in [1, 5, 6] and hasattr(self, 'charge_tes_hx'):
            if getattr(self, 'tank_config', 'indirect') == 'indirect' and not is_m6_par:
                self.charge_tes_hx.set_attr(pr1=0.98, pr2=0.98)
            elif getattr(self, 'tank_config', 'indirect') != 'indirect' and not is_m6_par:
                self.charge_tes_hx.set_attr(pr=0.98)
        
        # Process pressure drop (always, structural)
        self.process_hx.set_attr(pr=1.0)
        
        # === BOUNDARY CONDITIONS (always applied) ===
        if hasattr(self, 'conn_05') and self.conn_05 is not None:
            self.conn_05.set_attr(T=self.conexion_params['5_T'])
        if hasattr(self, 'conn_06') and self.conn_06 is not None and not is_m6_par:
            self.conn_06.set_attr(T=self.conexion_params['6_T'])
        if not is_m6_par:
            self.process_hx.set_attr(Q=self.component_params['PR_Q'])
        
        # === DESIGN-ONLY parameters (component sizing) ===
        if design_mode == 'design':            
            # PTC design parameters (skip M6 Par - independent cycle)
            if mode in [1, 5, 6] and not is_m6_par:
                self.ptc_field.set_attr(
                    aoi=self.component_params['ptc_aoi'], 
                    doc=self.component_params['ptc_doc'],
                    Tamb=self.component_params['ptc_tamb'], 
                    A=self.component_params['ptc_A'], 
                    eta_opt=self.component_params['eta_opt'], 
                    c_1=self.component_params['ptc_c_1'], 
                    c_2=self.component_params['ptc_c_2'], 
                    E=self.component_params['ptc_E'],
                    iam_1=self.component_params['ptc_iam_1'], 
                    iam_2=self.component_params['ptc_iam_2']
                )
            
            # HX thermal design parameter (force kA computation)
            if mode in [1, 5] and hasattr(self, 'charge_tes_hx'):
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.charge_tes_hx.set_attr(ttd_l=20)
            if mode == 3 and hasattr(self, 'discharge_tes_hx'):
                if getattr(self, 'tank_config', 'indirect') == 'indirect':
                    self.discharge_tes_hx.set_attr(ttd_l=20)
        
        if mode in [2, 3, 4, 6]:
            pass

    def set_operation_mode(self, TESmode='4', 
                           current_irr=0,
                           profile=None,
                           prev_TES_lay = 'Charge',
                           mode = 'design'):
        """
        mode 1: High irradiation, PTC to process and to TES
        mode 2: Mid irradiation, PTC to process, TES in standby
        mode 3: Low irradiation, TES to process
        mode 4: Low irradiation, TES in standby (auxiliary heater supplies process)
        mode 6: Mid to high irradiation, PTC full to TES (auxiliary heater supplies process)
        """
        if prev_TES_lay == 'Charge':
            TES_top = profile[0]
            TES_bot = profile[-1]
        elif prev_TES_lay == 'Discharge':
            TES_top = profile[-1]
            TES_bot = profile[0]

        if TESmode == '1':
            self.create_network(mode=1, design_mode='design')
            self.tes.set_state('charge')
            
            TES_bot = self.tes.profile[-1]
            
            if tank_cfg == 'indirect':
                self.conn_14.set_attr(T=TES_bot + 40)
            
            self.preheater_hx.set_attr(Q=0)
            
            if mode == 'design':
                self.conn_05.set_attr(T=self.conexion_params['5_T'])
                self.conn_06.set_attr(T=self.conexion_params['6_T'])
                if getattr(self, 'topology', 'Parallel') == 'Series':
                    self.ptc_field.set_attr(A='var')
            else:
                self.conn_06.set_attr(T=self.conexion_params['6_T'])
                self.ptc_field.set_attr(E=current_irr)
                if getattr(self, 'topology', 'Parallel') == 'Series':
                    self.process_hx.set_attr(Q=None)
                    if hasattr(self, 'ptc_field_A_designed'):
                        self.ptc_field.set_attr(A=self.ptc_field_A_designed)
                else:
                    self.conn_05.set_attr(T=self.conexion_params['5_T'])
        
        elif TESmode == '2':
            # All flow from PTC to process
            self.create_network(mode=2, design_mode=mode)
            self.preheater_hx.set_attr(Q=0, pr=1.0)
            if mode == 'design':
                self.ptc_field.set_attr(
                    aoi=self.component_params['ptc_aoi'], doc=self.component_params['ptc_doc'],
                    Tamb=self.component_params['ptc_tamb'], A='var',
                    eta_opt=self.component_params['eta_opt'], c_1=self.component_params['ptc_c_1'],
                    c_2=self.component_params['ptc_c_2'], E=self.component_params['ptc_E'],
                    iam_1=self.component_params['ptc_iam_1'], iam_2=self.component_params['ptc_iam_2'])
            else:
                self.ptc_field.set_attr(
                    E=current_irr, A='var',
                    eta_opt=self.component_params['eta_opt'],
                    aoi=self.component_params.get('ptc_aoi', 0),
                    doc=self.component_params.get('ptc_doc', 1),
                    Tamb=self.component_params.get('ptc_tamb', 20),
                    c_1=self.component_params.get('ptc_c_1', 0),
                    c_2=self.component_params.get('ptc_c_2', 0),
                    iam_1=self.component_params.get('ptc_iam_1', 0),
                    iam_2=self.component_params.get('ptc_iam_2', 0))
                # Set initial guess for A to avoid solver stall
                A_guess = 1e6 / (max(current_irr, 100) * self.component_params['eta_opt'])
                self.ptc_field.A.val = A_guess
        elif TESmode == '3':
            from tespy.connections import Ref
            self.create_network(mode=3, design_mode='design')
            self.tes.set_state('discharge')
            
            self.conn_04.set_attr(T=Ref(self.conn_15, 1, 20))
            self.conn_11.set_attr(T=None)
            self.conn_16.set_attr(T=None)
            
            # Regime selection (offdesign only)
            if mode != 'design':
                t_ph_out = self.conexion_params['5_T']
                TES_top = profile[-1] if prev_TES_lay == 'Discharge' else profile[0]
                if TES_top >= t_ph_out:
                    self.conn_05.set_attr(T=None)
            self.preheater_hx.set_attr(Q=0, pr=1.0)

        elif TESmode == '4':
            self.create_network(mode=4, design_mode='design')
             
        elif TESmode == '5':
            # Mode 5: Series high-T charge (PTC -> HX -> PH -> PR -> CC)
            # Uses its own high-temperature charge HX (sized via ttd_l)
            self.create_network(mode=5, design_mode='design')
            self.tes.set_state('charge')
            
            TES_bot = self.tes.profile[-1]
            if tank_cfg == 'indirect':
                T14_val = min(TES_bot + 60, 580)
                self.conn_14.set_attr(T=T14_val)
            self.conn_10.set_attr(T=TES_bot if tank_cfg == 'direct' else None)
            self.preheater_hx.set_attr(pr=1.0)
            
            if mode == 'offdesign':
                self.ptc_field.set_attr(E=current_irr)

        elif TESmode == '6':
            is_m6par = (getattr(self, 'topology', 'Parallel') == 'Parallel')
            self.create_network(mode=6, design_mode='design')
            self.tes.set_state('charge')
            
            TES_bot = self.tes.profile[-1]
            
            if is_m6par:
                self.process_hx.set_attr(Q=self.component_params['PR_Q'])
                self.conn_05.set_attr(T=self.conexion_params['5_T'])
                self.conn_06.set_attr(T=self.conexion_params['6_T'])
                if mode == 'design':
                    self.ptc_field.set_attr(
                        A=self.component_params['ptc_A'], E=self.component_params['ptc_E'],
                        eta_opt=self.component_params['eta_opt'],
                        aoi=self.component_params.get('ptc_aoi', 0),
                        doc=self.component_params.get('ptc_doc', 1),
                        Tamb=self.component_params.get('ptc_tamb', 20),
                        c_1=self.component_params.get('ptc_c_1', 0),
                        c_2=self.component_params.get('ptc_c_2', 0),
                        iam_1=self.component_params.get('ptc_iam_1', 0),
                        iam_2=self.component_params.get('ptc_iam_2', 0)
                    )
                else:
                    self.ptc_field.set_attr(E=current_irr)
            if tank_cfg == 'indirect':
                self.conn_14.set_attr(T=TES_bot + 40)
            
            if is_m6par:
                self.conn_02.set_attr(T=self.conexion_params['5_T'])
                if mode == 'design':
                    self.ptc_field.set_attr(
                        A=self.component_params['ptc_A'], E=self.component_params['ptc_E'],
                        eta_opt=self.component_params['eta_opt'],
                        aoi=self.component_params.get('ptc_aoi', 0),
                        doc=self.component_params.get('ptc_doc', 1),
                        Tamb=self.component_params.get('ptc_tamb', 20),
                        c_1=self.component_params.get('ptc_c_1', 0),
                        c_2=self.component_params.get('ptc_c_2', 0),
                        iam_1=self.component_params.get('ptc_iam_1', 0),
                        iam_2=self.component_params.get('ptc_iam_2', 0)
                    )
                else:
                    self.ptc_field.set_attr(
                        E=current_irr, A=self.component_params['ptc_A'],
                        eta_opt=self.component_params['eta_opt'],
                        aoi=self.component_params.get('ptc_aoi', 0),
                        doc=self.component_params.get('ptc_doc', 1),
                        Tamb=self.component_params.get('ptc_tamb', 20),
                        c_1=self.component_params.get('ptc_c_1', 0),
                        c_2=self.component_params.get('ptc_c_2', 0),
                        iam_1=self.component_params.get('ptc_iam_1', 0),
                        iam_2=self.component_params.get('ptc_iam_2', 0)
                    )
                self.process_hx.set_attr(Q=self.component_params['PR_Q'])
                self.conn_05.set_attr(T=self.conexion_params['5_T'])
                self.conn_06.set_attr(T=self.conexion_params['6_T'])
                if not hasattr(self, 'charge_hx_kA'):
                    try:
                        with open('mode1_kA.txt', 'r') as f:
                            self.charge_hx_kA = float(f.read())
                    except: pass
                if hasattr(self, 'charge_hx_kA'):
                    self.charge_tes_hx.set_attr(kA=self.charge_hx_kA)
            else:
                if not hasattr(self, 'charge_hx_kA'):
                    try:
                        with open('mode1_kA.txt', 'r') as f:
                            self.charge_hx_kA = float(f.read())
                    except: pass
                if hasattr(self, 'charge_hx_kA') and self.charge_hx_kA:
                    self.charge_tes_hx.set_attr(kA=self.charge_hx_kA)
                if mode == 'design':
                    self.ptc_field.set_attr(A='var')
                else:
                    self.ptc_field.set_attr(E=current_irr)
                    self.process_hx.set_attr(Q=None)
                    if hasattr(self, 'ptc_field_A_designed'):
                        self.ptc_field.set_attr(A=self.ptc_field_A_designed)

        else:   
            raise ValueError(f"Unknown mode {TESmode}")
 
 
    def solve_network(self, mode='design', design_path="base_design", TESmode='1', use_init_path=False):
        """
        Attempts to solve the network in the specified mode (default: 'design').
        Raises an exception if the solver fails.
        
        Args:
            mode (str): 'design' or 'offdesign' (TESPy modes).
            use_init_path (bool): if True, warm-start offdesign from design solution.
        """

        name = f'base_design_{TESmode}'        
        if mode == 'design':

            self.network.solve(mode=mode, max_iter=100)
            import shutil, os, time
            abs_name = os.path.abspath(name)
            if os.path.exists(abs_name):
                try:
                    if os.path.isfile(abs_name):
                        os.remove(abs_name)
                    else:
                        import uuid
                        new_name = abs_name + "_old_" + uuid.uuid4().hex[:6]
                        os.rename(abs_name, new_name)
                except Exception as e:
                    print(f"Could not rename {abs_name}: {e}")
            self.network.save(name)
            # Persist designed values for cross-mode use
            if (hasattr(self, 'ptc_field') and self.ptc_field is not None
                    and self.ptc_field.A.val is not None):
                self.ptc_field_A_designed = self.ptc_field.A.val
            if (TESmode == '1' and hasattr(self, 'charge_tes_hx')
                    and self.charge_tes_hx.kA.val is not None):
                self.charge_hx_kA = self.charge_tes_hx.kA.val
                # Store kA to file for cross-mode use
                try:
                    with open('mode1_kA.txt', 'w') as f:
                        f.write(str(self.charge_hx_kA))
                except: pass
        else:
            kwargs = {'mode': mode, 'max_iter': 200, 'design_path': f'base_design_{TESmode}'}
            if use_init_path:
                kwargs['init_path'] = f'base_design_{TESmode}'
            self.network.solve(**kwargs)
            #if not self.network.converged:
            #    raise RuntimeError("TESPy solver did not converge.")

class Solver:
    """
    Runs a quasi-steady simulation of the SolarThermalSystem over time-series data.
    """
    def __init__(self, 
                 tes_params,
                 component_params,
                 conexion_params,
                 HTF,
                 system_mode='Full', 
                 topology='Parallel',
                 tank_config='indirect',
                 file_path=None,
                 charge_margin=1.5,
                 zinc_pool_params=None):
        self.tes_params= tes_params
        self.component_params = component_params
        self.conexion_params = conexion_params
        self.HTF= HTF 
        self.system_mode = system_mode
        self.topology = topology
        self.tank_config = tank_config  # 'direct' or 'indirect'
        self.results = []
        self.current_mode = '4' 
        self.file_path = file_path
        self.mode_alert = False
        
        # --- Control parameters (visible for parametric analysis) ---
        A_ptc   = self.component_params.get('ptc_A', 10000)
        eta_opt = self.component_params.get('eta_opt', 0.75)
        Q_proc  = abs(self.component_params.get('PR_Q', 1e6))
        self.E_min_process = Q_proc / (A_ptc * eta_opt)  # W/m2
        self.E_min_charge  = self.E_min_process * charge_margin
        self.charge_margin = charge_margin
        # ---
        
        # --- Zinc pool (optional dynamic process model) ---
        self.zinc_pool = ZincPool(zinc_pool_params) if zinc_pool_params is not None else None
        # ---

        print(f'Control thresholds: E_min_process={self.E_min_process:.0f} W/m2, '
              f'E_min_charge={self.E_min_charge:.0f} W/m2 '
              f'(A_ptc={A_ptc} m2, eta_opt={eta_opt}, Q_proc={Q_proc/1e6:.1f} MW, '
              f'margin={charge_margin}x)')

    def load_data(self, csv, start_date, days_to_simulate):
        """
        Loads external data from a CSV file and fixes the year for all timestamps.
        :return: DataFrame, data loaded and adjusted.
        """
        fixed_year = 2022        

        # 2) Read TMY
        tmy_data = pd.read_csv('TMY.csv')#, parse_dates=['Fecha/Hora'])
        
        # Fix the year for all timestamps
        tmy_data['Fecha/Hora'] = pd.to_datetime(tmy_data['Fecha/Hora'])
        tmy_data['Fecha/Hora'] = tmy_data['Fecha/Hora'].apply(lambda x: x.replace(year=fixed_year))
        start_date = tmy_data['Fecha/Hora'].min()
        end_date   = start_date + pd.Timedelta(days=days_to_simulate)
        print(start_date, end_date)
       
        #filtered_data = filtered_data[filtered_data['Fecha/Hora'] >= start_date]
        filtered_data = tmy_data[(tmy_data['Fecha/Hora'] >= start_date) & (tmy_data['Fecha/Hora'] < end_date)]
        return filtered_data


    def get_mode(self, irr, TES_profile, prev_TES_lay):
        """
        Seleccion de modo basado en irradiancia, SOC, y viabilidad fisica.
        
        Thresholds (set in Solver.__init__):
          self.E_min_process : irradiancia minima para que el PTC entregue Q_proc
          self.E_min_charge  : irradiancia minima para cargar TES (process + margen)
          self.charge_margin : multiplicador para E_min_charge
        """
    
        # --- Top/Bottom coherentes con el layout previo ---
        lay = prev_TES_lay or getattr(self, 'TES_lay', 'Charge')
        if lay == 'Charge':
            TES_top = TES_profile[0];  TES_bot = TES_profile[-1]
        else:  # 'Discharge'
            TES_top = TES_profile[-1]; TES_bot = TES_profile[0]
            
        t_proc_set = self.solar_system.conexion_params['6_T']
        t_ph_out   = self.solar_system.conexion_params['5_T']
        
        # Discharge viability thresholds (adaptive to process temperatures)
        T_min_discharge = t_proc_set + 20  # 480+20=500 C (T04 = T15-20 >= T11 = 480)
        T_max_discharge = 580              # NaK safe limit - 20, expanded range
        
        # Calculate State of Charge (SOC) 
        current_soc = self.solar_system.tes.calculate_SoC(TES_profile)
        soc_empty = self.solar_system.tes.calculate_SoC(np.ones_like(TES_profile) * 400.0)
        soc_full = self.solar_system.tes.calculate_SoC(np.ones_like(TES_profile) * 560.0)
        soc_norm = (current_soc - soc_empty) / max(soc_full - soc_empty, 1e-3)
    
        # --- Lectura interna (opcional) de T_ptc_out desde la red actual ---
        def _read_T_ptc_out():
            for cname in ('conn_02', 'conn_04'):
                c = getattr(self.solar_system, cname, None)
                if c is not None and hasattr(c, 'T') and c.T is not None:
                    try:
                        if getattr(c.T, 'val', None) is not None:
                            return float(c.T.val)
                        if getattr(c.T, 'val_SI', None) is not None:
                            return float(c.T.val_SI - 273.15)
                    except AttributeError:
                        pass
            return None
    
        T_ptc_out = _read_T_ptc_out()
    
        # --- Dwell: mantener modo previo por 2 pasos para evitar oscilaciones ---
        if hasattr(self, '_mode_dwell') and self._mode_dwell < 2:
            self._mode_dwell += 1
            return self.prev_TESmode

        # --- Pegajosidad: permanecer en Mode 6 si TES aun necesita carga ---
        if self.prev_TESmode == '6' and soc_norm < 0.8 and irr > self.E_min_process:
            return '6'
    
        # --- TES muy frio y poca irradiancia -> standby ---
        if soc_norm < 0.05 and irr < self.E_min_process:
            return '4'
    
        # --- TES frio moderado: cargar TES si hay irradiancia suficiente ---
        if soc_norm < 0.4 and TES_top < 470:
            return '6' if irr > self.E_min_charge else '4'
    
        # --- Irradiancia suficiente para proceso + carga ---
        if irr > self.E_min_charge:
            # Mode 5: high-T charge when tank is warm and irradiance is sufficient
            if TES_top > t_ph_out and soc_norm < 0.85:
                return '5'
            charge_viable = True
            if T_ptc_out is not None:
                charge_viable = (T_ptc_out > TES_top)
            if charge_viable and soc_norm < 0.95:
                return '1'
            else:
                return '2'
    
        # --- Irradiancia suficiente solo para proceso (sin excedente para carga) ---
        if irr > self.E_min_process:
            # Check discharge first: if TES has energy, use it + top up with PTC
            if TES_top > T_min_discharge and TES_top <= T_max_discharge and soc_norm > 0.1:
                return '3'
            return '2'
    
        # --- Baja irradiancia: descargar TES si tiene energia ---
        if TES_top > T_min_discharge and TES_top <= T_max_discharge and soc_norm > 0.1:
            return '3'
        return '4'
    

    def get_system_mode(self, irr):
        if self.system_mode == 'Full':
            new_TESmode = self.get_mode(irr, self.solar_system.tes.profile, self.TES_lay)
            # Reset dwell counter when mode actually changes
            if new_TESmode != self.prev_TESmode:
                self._mode_dwell = 0
            self.prev_TESmode = new_TESmode
        elif self.system_mode == 'No TES':
            if irr > 300:
                new_TESmode = '2'
            else:
                new_TESmode = '4'
        elif self.system_mode == 'No solar':
            new_TESmode = '4'
        return new_TESmode
    def init_steady(self, irr, mode='design'):
        self.system_mode = 'Full'
        self.TES_lay = 'Charge'
        self.irr = irr
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF,
                                    topology=self.topology,
                                    tank_config=self.tank_config
                                    )
        print(f"Mode: {mode}")
        self.solve_network_steady(mode=mode)
        self.solar_system.network.print_results()
        
    def initialize_modes(self):
        import os, shutil, glob
        for f in glob.glob('base_design_*'):
            if os.path.isfile(f):
                os.remove(f)
            else:
                shutil.rmtree(f, ignore_errors=True)
        if os.path.exists('mode1_kA.txt'):
            os.remove('mode1_kA.txt')
        
        def _make_system(T_init):
            self.tes_params['Initial temperature'] = T_init
            return SolarThermalSystem(rows=1, tes_params=self.tes_params,
                        component_params=self.component_params,
                        conexion_params=self.conexion_params,
                        HTF=self.HTF, topology=self.topology, tank_config=self.tank_config)
        
        # ---- Mode 1 (charge + process, computes kA) ----
        self.system_mode = 'Full'; self.TES_lay = 'Charge'; self.irr = 1000
        sys1 = _make_system(400)
        self.solar_system = sys1
        self.solve_network_steady(TESmode='1')
        # Store kA for cross-mode use (Mode 5, 6 share same HX)
        self.charge_hx_kA = getattr(sys1, 'charge_hx_kA', None)
        if not self.charge_hx_kA:
            try:
                with open('mode1_kA.txt', 'r') as f:
                    self.charge_hx_kA = float(f.read())
            except: pass
        
        # ---- Mode 2 (process only) ----
        self.irr = 1000
        self.solar_system = _make_system(520)
        self.solve_network_steady(TESmode='2')
        
        # ---- Mode 3 (discharge, direct) ----
        self.irr = 0
        sys3 = _make_system(540)
        sys3.set_operation_mode(TESmode='3', current_irr=0,
            profile=sys3.tes.profile, prev_TES_lay='Discharge', mode='design')
        if hasattr(sys3, 'conn_15'): sys3.conn_15.set_attr(T=540)
        sys3.solve_network(mode='design', TESmode='3')
        self.solar_system = sys3
        
        # ---- Mode 4 (standby) ----
        self.irr = 0
        self.solar_system = _make_system(450)
        self.solve_network_steady(TESmode='4')
        
        # ---- Mode 5 (high-T charge, retry for convergence) ----
        self.irr = 1000
        sys5 = _make_system(400)
        if self.charge_hx_kA:
            sys5.charge_hx_kA = self.charge_hx_kA  # Use Mode 1's kA
        sys5.set_operation_mode(TESmode='5', current_irr=1000,
            profile=sys5.tes.profile, prev_TES_lay='Charge', mode='design')
        if hasattr(sys5, 'conn_13'): sys5.conn_13.set_attr(T=400)
        self.current_irr = 1000
        ok5, _, _ = self.attempt_to_solve(sys5, 'design', 'base_design', '5', tries=10)
        if ok5 and sys5.network.converged:
            sys5.network.save('base_design_5')
        self.solar_system = sys5
        
        # ---- Mode 6 (full charge, direct solve works) ----
        try:
            self.irr = 1000
            sys6 = _make_system(400)
            if self.charge_hx_kA:
                sys6.charge_hx_kA = self.charge_hx_kA
            sys6.set_operation_mode(TESmode='6', current_irr=1000,
                profile=sys6.tes.profile, prev_TES_lay='Charge', mode='design')
            if hasattr(sys6, 'conn_13'): sys6.conn_13.set_attr(T=400)
            sys6.network.solve('design', max_iter=100)
            sys6.network.save('base_design_6')
            self.solar_system = sys6
        except Exception as e:
            print(f'[WARNING] Mode 6 design initialization failed: {e}')
            print('          Mode 6 will fall back to Mode 4 at runtime.')
            self.solve_network_steady(TESmode='4')
            try:
                shutil.copytree('base_design_4', 'base_design_6', dirs_exist_ok=True)
            except Exception:
                pass
        
        # 
    # -------------------------------------------------------------------------
    # 1) Convergence Checking
    # -------------------------------------------------------------------------
    def _check_tes_convergence(self, T_out_history, conv_factors):
        """
        Checks for two criteria:
          1) Convergence if last 3 changes in T_out are < 5%.
          2) Divergence if the convergence factor has increased >10% 
             over the last 5 iterations.

        Returns
        -------
        str:
            'converged', 'diverged', or 'continue'
        """
        # (1) If we have at least 3 T_out values, check for <5% changes
        if len(T_out_history) >= 3:
            Tn   = T_out_history[-1]
            Tn_1 = T_out_history[-2]
            Tn_2 = T_out_history[-3]

            diff1 = abs(Tn   - Tn_1) / max(abs(Tn_1), 1e-6)
            diff2 = abs(Tn_1 - Tn_2) / max(abs(Tn_2), 1e-6)
            if diff1 < 0.05 and diff2 < 0.05:
                return 'converged'

        # (2) If we have at least 5 convergence factors, check for divergence
        if len(conv_factors) >= 5:
            earliest = conv_factors[-5]
            latest   = conv_factors[-1]
            if earliest > 0 and (latest - earliest)/earliest > 1:
                return 'diverged'

        return 'continue'
    
    def iteration_check(self, TESmode, system):
        if TESmode == '1':
            T_tes_out = system.conn_10.T.val
            if T_tes_out > self.conexion_params['5_T']:
                check = False
                mode = '2'
                #print('T TES out: ', T_tes_out)
            else:
                check = True
                mode = '1'
        elif TESmode == '3':   
            T_tes_out = system.conn_04.T.val
            if T_tes_out < self.conexion_params['6_T']:
                check = False
                mode = '4'
            else:
                check = True
                mode = '3'
        else:
            check = True
            mode = TESmode
        return check, mode
    # -------------------------------------------------------------------------
    # 2) Coupling Iteration Between TES and Main Loop (steady or single time-step)
    # -------------------------------------------------------------------------
    def attempt_to_solve(self, system, mode, design_path, TESmode, tries: int = 5):
        """
        Intenta resolver la red TESPy hasta `tries` veces.
        Implementa estrategias dinÃ¡micas de relajaciÃ³n (fallbacks) 
        para lograr convergencia antes de fallar por completo.
        Devuelve:
          ok: bool                -> True si alguna corrida converge
          attempts: list[dict]    -> bitÃ¡cora por intento
          last_err: str|None      -> mensaje del Ãºltimo error capturado (si hubo)
        """
        attempts = []
        last_err = None
        for k in range(1, tries + 1):
            if k > 1:
                # Recreate network to clear corrupted state from failed solves
                try:
                    saved_profile = (np.array(system.tes.profile).copy()
                        if hasattr(system, 'tes') and system.tes.profile is not None else None)
                    system.set_operation_mode(TESmode=TESmode, mode=mode,
                        current_irr=self.current_irr, profile=saved_profile)
                    # Re-apply TES boundary conditions!
                    tank_cfg = getattr(system, 'tank_config', 'indirect')
                    if TESmode in ['1','5','6']:
                        if tank_cfg == 'direct':
                            system.conn_10.set_attr(T=system.tes.profile[-1])
                        else:
                            system.conn_13.set_attr(T=system.tes.profile[-1])
                    elif TESmode in ['3']:
                        if tank_cfg == 'direct':
                            system.conn_04.set_attr(T=system.tes.profile[-1])
                        else:
                            system.conn_15.set_attr(T=system.tes.profile[-1])
                except Exception as e:
                    print(f"Warning: could not recreate network in attempt_to_solve: {e}")
                
                # Incrementally adjust parameters and randomize
                if k == 2:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(350.0, 550.0),
                                                 include=('T0'))
                elif k == 3:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(300.0, 600.0),
                                                 include=('T0', 'm0'))
                elif k == 4:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(250.0, 650.0),
                                                 include=('T0', 'm0', 'p0'))
                else:
                    self._randomize_conn_guesses(system, TESmode, seed=None,
                                                 T_bounds=(200.0, 700.0),
                                                 include=('T0', 'm0', 'p0'))
            try:
                # Desactiva trazas verbosas si corresponde
                try:
                    system.network.set_attr(iterinfo=False)
                except AttributeError:
                    pass
    
                warm_start = (mode == 'offdesign' and TESmode in ['1'])
                system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode,
                                     use_init_path=warm_start)
                conv = bool(getattr(system.network, 'converged', False))
                attempts.append({'mode': TESmode, 'try_idx': k, 'tespy_converged': conv})
                if conv:
                    return True, attempts, None
                else:
                    last_err = "TESPy did not converge."
                    print(f"[attempt_to_solve] Attempt {k} failed to converge. Retrying...")
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                attempts.append({'mode': TESmode, 'try_idx': k, 'tespy_converged': False, 'error': str(e)})
                print(f"[attempt_to_solve] Attempt {k} exception: {e}. Retrying...")
                
        # Si llegamos aquÃ­ sin retornar, fallaron todos los intentos
        if TESmode != '4':
            print(f"[attempt_to_solve] Solver failed after {tries} attempts for mode {TESmode}. Falling back to Mode 4.")
            self.current_mode = '4'
            try:
                system.set_operation_mode(TESmode='4', mode=mode, current_irr=self.current_irr, profile=system.tes.profile if hasattr(system, 'tes') else None)
                system.solve_network(mode=mode, design_path='base_design_4', TESmode='4')
                if bool(getattr(system.network, 'converged', False)):
                    attempts.append({'mode': '4', 'try_idx': 'fallback', 'tespy_converged': True})
                    return True, attempts, last_err
            except Exception as fallback_err:
                last_err = f"{last_err} | Fallback Mode 4 failed: {fallback_err}"

        raise RuntimeError(f"TESPy solver failed after {tries} attempts. Last error: {last_err}")
                
        # --- Helper: randomizar guesses de conexiones del modo activo -------------
    def _randomize_conn_guesses(self, system, TESmode, *, seed=None,
                                T_bounds=None, include=('T0')):
        """
        Randomiza los 'initial guesses' de las conexiones disponibles en el modo
        actual para ayudar a la convergencia.
        """
        rng = np.random.default_rng(seed)
        if T_bounds is None:
            T_bounds = (300.0, 600.0)

        randomized = []
        active_labels = set(system.network.conns.index) if hasattr(system.network, 'conns') else set()
        for name in dir(system):
            if not name.startswith('conn_'):
                continue
            conn = getattr(system, name, None)
            if conn is None or not hasattr(conn, 'set_attr'):
                continue
            # Skip stale connections not in current network
            if hasattr(conn, 'label') and conn.label is not None:
                if str(conn.label) not in active_labels:
                    continue
            try:
                if 'T0' in include:
                    T0 = float(rng.uniform(*T_bounds))
                    conn.set_attr(T0=T0)
                if 'm0' in include:
                    m0 = float(rng.uniform(20.0, 50.0))
                    conn.set_attr(m0=m0)
                if 'p0' in include:
                    p0 = float(rng.uniform(1.0, 10.0))
                    conn.set_attr(p0=p0)
                if 'h0' in include:
                    h0 = float(rng.uniform(500.0, 1000.0))
                    conn.set_attr(h0=h0)
                randomized.append(name)
            except ValueError:
                continue

        print(f"[attempt_to_solve] Randomized initial guesses ({include}) en modo {TESmode}:",
              f"{len(randomized)} conns")

        return randomized

    
    def _get_inlet_conn(self, comp, system):
        if comp is None:
            return None
        if hasattr(comp, 'inl') and len(comp.inl) > 0:
            return comp.inl[0]
        return None

    def _get_outlet_conn(self, comp, system):
        if comp is None:
            return None
        if hasattr(comp, 'outl') and len(comp.outl) > 0:
            return comp.outl[0]
        return None

    def _iterate_tes_coupling(self, system,
                              mode='design', TESmode='2', 
                              design_path='base_design',
                              Tamb=25):
        """
        Performs the inner iteration between the TES 1D model and
        the TESPy network for one 'steady' scenario (or one time-step).

        - Sets initial guess for TES-HX side from the top/bottom of the TES 
          depending on 'charge' or 'discharge'.
        - Iterates until we pass the convergence or divergence check, 
          or until hitting max_iter.
        """
        max_iter = 20
        T_out_history = []
        conv_factors  = []
        self.TES_profiles = []
        
        # --- logging de convergencia por paso (no altera la lógica ni las ecuaciones) ---
        iter_info = {
            'initial_mode': TESmode,
            'final_mode': None,
            'status': None,            # 'converged' | 'diverged' | 'max_iter'
            'attempts': [],            # lista de dicts: {mode, tespy_converged, iter_idx}
            'tespy_error': None,       # reservado: si capturas algún error de TESPy
            'dof_report': None,        # reservado: grados de libertad / diagnóstico si lo expones
        }
        self._last_iter_info = None    # se poblará al final del paso
        tank_cfg = getattr(system, 'tank_config', 'indirect')
        # 2) Initialize the TES_HX source temperature from top/bottom
        if TESmode in ['1','5','6']:
            if tank_cfg == 'direct':
                if hasattr(system, 'charge_tes_hx'):
                    T_in_bot = system.tes.profile[-1]
                    system.conn_10.set_attr(T=T_in_bot)
                else:
                    TESmode = '4'
                    self.current_mode = TESmode
            else:
                if hasattr(system, 'charge_tes_hx'):
                    T_in_bot = system.tes.profile[-1]
                    system.conn_13.set_attr(T=T_in_bot)
                else:
                    TESmode = '4'
                    self.current_mode = TESmode
        if TESmode in ['3']:
            if tank_cfg == 'direct':
                T_in_top = system.tes.profile[-1]
                system.conn_04.set_attr(T=T_in_top)
            else:
                T_in_top = system.tes.profile[-1]
                system.conn_15.set_attr(T=T_in_top)
            system.conn_04.set_attr(T=T_in_top)
        else:
            T_in_top = system.tes.profile[-1]
            system.conn_15.set_attr(T=T_in_top)

        mode_3_fail = False
        old_profile = np.array(system.tes.profile).copy()
        for iteration in range(max_iter):
            if mode == 'offdesign':
                system.network.set_attr(iterinfo=False)
            ok, att, err = self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
            TESmode = self.current_mode
            try:
                iter_info['attempts'].append({
                    'mode': TESmode,
                    'tespy_converged': bool(getattr(system.network, 'converged', False)),
                    'iter_idx': iteration + 1,
                })
            except AttributeError:
                pass
            # Revisar convergencia en HX de descarga
            if TESmode in ['3']:
                if tank_cfg == 'direct':
                    Q_hx = system.conn_04.T.val - system.conn_11.T.val  # proxy: positive if outlet hotter
                    if Q_hx <= 0:
                        mode_3_fail = True
                else:
                    dT_dhx = (system.conn_04.T.val - system.conn_11.T.val) if hasattr(system, 'conn_04') else 0
                    if dT_dhx <= 0:
                        mode_3_fail = True
                if mode_3_fail:
                    iter_info['attempts'].append({
                    'mode': TESmode,
                    'tespy_converged': bool(getattr(system.network, 'converged', False)),
                    'iter_idx': iteration + 1,
                    'ttd_min_if_mode3': dT_dhx,
                    })

            if not system.network.converged:
                if TESmode in ['1','5','6']:
                    print('System did not converge\n',TESmode, ' passing to 2')
                    TESmode = '2'
                    self.current_mode = TESmode
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=old_profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
                elif TESmode in ['3']:
                    print('System did not converge\n', TESmode, 'passing to 4')
                    TESmode = '4'
                    self.current_mode = TESmode
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=old_profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
                else:
                    self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
                    if not system.network.converged:
                        print(f"[WARNING] TESPy solver did not converge at iteration {iteration+1}.")
                        break
            if mode_3_fail:
                # DHX exhausted — accept partial discharge, don't fall back to Mode 4
                profile = system.tes.profile
                old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                system.tes.profile = old_profile
                iter_info['status'] = 'converged'
                iter_info['final_mode'] = TESmode
                self.TES_profiles.append(old_profile)
                break
            if TESmode in ['2', '4']:
                status = 'converged'
                profile = system.tes.profile
                old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                system.tes.profile = old_profile
                iter_info['status'] = 'converged'
                iter_info['final_mode'] = TESmode
                self.TES_profiles.append(old_profile)
                break
            # b) Read new TES inlet conditions from TES_HX outlet
            if TESmode in ['1','5','6']:
                    if TESmode == '1':
                        inlet_conn = system.conn_09
                    elif TESmode == '5':
                        inlet_conn = system.conn_14
                    else:  # mode 6
                        inlet_conn = system.conn_02
                    T_tes_in = inlet_conn.T.val
                    m_tes_in = inlet_conn.m.val_SI
                if tank_cfg == 'direct':
                    topo = getattr(system, 'topology', 'Parallel')
                    if TESmode == '1':
                        inlet_conn = system.conn_09 if topo == 'Parallel' else system.conn_06
                    elif TESmode == '5':
                        inlet_conn = system.conn_02
                    else:  # mode 6
                        inlet_conn = system.conn_02 if topo == 'Parallel' else system.conn_06
                    T_tes_in = inlet_conn.T.val
                    m_tes_in = inlet_conn.m.val_SI
                else:
                    T_tes_in = system.conn_14.T.val
                    m_tes_in = system.conn_14.m.val_SI
                    elif TESmode in ['3']:
                        if tank_cfg == 'direct':
                    T_tes_in = system.conn_11.T.val
                    m_tes_in = system.conn_11.m.val_SI
                else:
                    T_tes_in = system.conn_16.T.val
                    m_tes_in = system.conn_16.m.val_SI
            if m_tes_in < 0.01:
                self.mode_alert = True
                iter_info['status'] = 'diverged'
                iter_info['final_mode'] = TESmode
                print('TES mass flow alert')
                break

            system.tes.update_temperature_profile(
                T_in=T_tes_in,
                mass_flow=m_tes_in,
                initial_profile=old_profile
            )
            T_tes_out = system.tes.tout

            # d) Set the new outlet temperature to the HX inlet for next iteration
            if TESmode in ['1','5','6']:
                    system.conn_01.set_attr(T=T_tes_out)
                if tank_cfg == 'direct':
                    system.conn_10.set_attr(T=T_tes_out)
                else:
                    system.conn_13.set_attr(T=T_tes_out)
                self.TES_lay = 'Charge'
            elif TESmode in ['3']:
                if tank_cfg == 'direct':
                    system.conn_04.set_attr(T=T_tes_out)
                else:
                    system.conn_15.set_attr(T=T_tes_out)
                self.TES_lay = 'Discharge'

            # e) Track T_out for our multi-step convergence logic
            T_out_history.append(T_tes_out)
            if len(T_out_history) > 1:
                prev_T = T_out_history[-2]
                if abs(prev_T) > 1e-6:
                    cf = abs(T_tes_out - prev_T) / abs(prev_T)
                else:
                    cf = 0.0
                conv_factors.append(cf)

            # f) Evaluate our custom convergence criteria
            status = self._check_tes_convergence(T_out_history, conv_factors)
            #status = 'converged'
            if mode == 'design':
                print(f'outlet TES temperature: {T_tes_out}')   
            if status == 'converged':
                profile = system.tes.profile
                old_profile = system.tes.calc_heat_loss(profile, 3600, Tamb)
                system.tes.profile = old_profile
                self.TES_profiles.append(old_profile)
                break
            elif status == 'diverged':
                print(f"[WARNING] TES iteration diverging at iteration {iteration+1}!")
                break
        else:
            # If we never hit a 'break', we didn't converge within max_iter
            iter_info['status'] = 'max_iter'
            iter_info['final_mode'] = TESmode
            print("[WARNING] Reached max iteration count without TES convergence.")
        self.current_mode = TESmode

        # Exponer logging del paso (para usarlo en run_quasi_steady_simulation)
        self._last_iter_info = iter_info
        return iter_info
    # -------------------------------------------------------------------------
    # 3) Steady-State Solver
    # -------------------------------------------------------------------------
    def solve_network_steady(self, mode='design', TESmode=None):
        """
        Public method to solve the system in a stationary (steady) mode,
        including iteration with the TES if present.

        Args:
            operation_mode (str): 'charge' or 'discharge'.
            design_path (str): path to the saved design data (for offdesign mode).
        """
        # Simply call our coupling iteration for one single "steady" step
        system = self.solar_system
        #self.TES_lay = 'Charge'
        self.prev_TESmode = '4'
        self.current_irr = self.irr
        if TESmode is None:
            TESmode = self.get_mode(self.irr, system.tes.profile, self.TES_lay)
        print(f'TES mode {TESmode}')
        design_path = f'base_design_{TESmode}'
        system.set_operation_mode(TESmode=TESmode, 
                                             current_irr=self.irr, 
                                             profile=system.tes.profile,
                                             prev_TES_lay = self.TES_lay,
                                             mode=mode)

        self._iterate_tes_coupling(mode=mode, system = system,
                                   TESmode=TESmode, design_path=design_path,
                                   Tamb = 25)
    def _collect_step_signals(self, system, mode: str) -> dict:
        """
        SeÃ±ales del paso actual medidas directamente en los componentes:
          EnergÃ­as por paso (kJ): to_tes, tes_to_proc, solar_to_proc, aux_to_proc, ptc_total
          Temperaturas [Â°C]:      T_ptc_out, T_tes_top, T_tes_bottom
          Flujos mÃ¡sicos [kg/s]:  mdot_ptc, mdot_tes_charge, mdot_tes_discharge, mdot_process
    
        Correcciones:
        - Q de HX se toma como |Q| (signo en TESPy depende del lado).
        - Puertas lÃ³gicas por estado del TES para cargar/descargar (anula el opuesto).
        """
    

        # ---------- utilidades robustas ----------
        def _get_comp(sys, *names):
            for n in names:
                c = getattr(sys, n, None)
                if c is not None:
                    return c
            return None
    
        def _get_Q_kw(comp) -> float:
            """Intenta comp.Q.val (o comp.Q) y devuelve |Q| en kW; 0 si no disponible."""
            if comp is None:
                return 0.0
            
            # If it's a pipe, we can calculate Q from the streams
            if type(comp).__name__ == 'Pipe':
                try:
                    h_in = self._get_inlet_conn(comp, system).h.val_SI
                    h_out = comp.outl[0].h.val_SI
                    m = self._get_inlet_conn(comp, system).m.val_SI
                    if h_in is not None and h_out is not None and m is not None:
                        return abs(m * (h_in - h_out) / 1000.0)
                except Exception:
                    pass

            for a in ('Q'):
                qa = getattr(comp, a, None)
                if qa is None:
                    continue
                v = getattr(qa, 'val', None)
                if v is None:
                    try:
                        v = float(qa)
                    except (ValueError, TypeError):
                        v = None
                if v is not None and np.isfinite(v):
                    return abs(float(v))  # <<< valor absoluto: evita falsos 0 por signo
            return 0.0
    
        def _conn_T(comp):
            """Temperatura de salida si existe (Â°C)."""
            try:
                if comp is None:
                    return np.nan
                if self._get_outlet_conn(comp, system) and self._get_outlet_conn(comp, system) is not None:
                    v = getattr(getattr(self._get_outlet_conn(comp, system), 'T', None), 'val', None)
                    if v is None:
                        v = getattr(self._get_outlet_conn(comp, system), 'T', None)
                    return float(v) if v is not None else np.nan
            except (AttributeError, IndexError, TypeError):
                pass
            return np.nan
    
        def _mdot_kg_s(comp):
            """Flujo mÃ¡sico de salida si existe (kg/s)."""
            try:
                if comp is None:
                    return np.nan
                if self._get_outlet_conn(comp, system) and self._get_outlet_conn(comp, system) is not None:
                    v = getattr(getattr(self._get_outlet_conn(comp, system), 'm', None), 'val', None)
                    if v is None:
                        v = getattr(self._get_outlet_conn(comp, system), 'm', None)
                    return float(v) if v is not None else np.nan
            except (AttributeError, IndexError, TypeError):
                pass
            return np.nan
    
        # ---------- componentes ----------
        ptc     = _get_comp(system, 'ptc_field')
        hx_chg  = _get_comp(system, 'charge_tes_pipe', 'charge_tes_hx')
        hx_dch  = _get_comp(system, 'discharge_tes_pipe', 'discharge_tes_hx')
        hx_proc = _get_comp(system, 'process_hx')
        hx_aux  = _get_comp(system, 'preheater_hx')

        tes_state = ''
        try:
            tes_state = str(getattr(system.tes, 'state', '')).lower()
        except AttributeError:
            pass

        # ---------- time step (seconds) ----------
        dt_s = 3600.0  # 1-hour time step, consistent with simulation loop

        # ---------- read actual energy values from components ----------
        q_ptc_kw = _get_Q_kw(ptc)
        q_chg_kw = _get_Q_kw(hx_chg)
        q_dch_kw = _get_Q_kw(hx_dch)
        q_aux_kw = _get_Q_kw(hx_aux)
        q_proc_kw = _get_Q_kw(hx_proc)

        # ---------- mode-gating: zero out physically impossible contributions ----------
        if mode in ['1','5','6']:
            q_dch_kw = 0.0
        elif mode in ['3']:
            q_chg_kw = 0.0
            q_ptc_kw = 0.0
        else:
            # standby / Mode 2: no TES interaction
            q_chg_kw = 0.0
            q_dch_kw = 0.0
    
        # ---------- energÃ­as por paso (kJ) ----------
        to_tes_kJ        = q_chg_kw * dt_s
        tes_to_proc_kJ   = q_dch_kw * dt_s
        ptc_total_kJ     = q_ptc_kw * dt_s
    
        # Auxiliar â†’ proceso solo cuando no hay solar directo (misma regla de antes)
        aux_to_proc_kJ   = (0.0 if mode in ['1','2'] else q_aux_kw) * dt_s
    
        # Solar â†’ proceso directo (mediciÃ³n compuesta mÃ­nima), sin balances detallados:
        # PTC total menos lo que se desvÃ­a a cargar el TES.
        solar_to_proc_kJ = max(ptc_total_kJ - to_tes_kJ, 0.0)
    
        # ---------- temperaturas ----------
        T_ptc_out   = _conn_T(ptc)
        if mode not in ['1','2','6']:
            T_ptc_out = np.nan
        # perfil TES para top/bottom igual que en tus plots
        T_tes_top = np.nan
        T_tes_bot = np.nan
        try:
            prof_raw = None
            if hasattr(self, 'TES_profiles') and self.TES_profiles is not None:
                pr_val = self.TES_profiles
                arr = np.array(pr_val[-1] if isinstance(pr_val, (list, tuple)) and len(pr_val) > 0 else pr_val).ravel()
                prof_raw = arr if arr.size > 0 else None
            elif hasattr(system, 'tes') and hasattr(system.tes, 'profile'):
                arr = np.array(system.tes.profile).ravel()
                prof_raw = arr if arr.size > 0 else None
            if prof_raw is not None:
                prof = prof_raw[::-1] if mode in ['1','5','6'] else prof_raw
                T_tes_bot = float(prof[0])
                T_tes_top = float(prof[-1])
        except (IndexError, TypeError, ValueError, AttributeError):
            pass
    
        # ---------- flujos mÃ¡sicos ----------
        mdot_ptc          = _mdot_kg_s(ptc)
        mdot_tes_charge   = _mdot_kg_s(hx_chg)
        mdot_tes_discharge= _mdot_kg_s(hx_dch)
        mdot_process      = _mdot_kg_s(hx_proc)

        # puertas lÃ³gicas tambiÃ©n para á¹ (coherente con potencias)
        if mode in ['1','5','6']:
            mdot_tes_discharge = 0.0
        elif mode in ['3']:
            mdot_tes_charge = 0.0
            mdot_ptc = 0.0
        else:
            mdot_tes_charge    = 0.0
            mdot_tes_discharge = 0.0
            mdot_ptc           = 0.0 if mode == '4' else mdot_ptc  # Mode 2 has PTC

        # ---------- pump power fallback ----------
        pump_kw = None
        for p_name in ['pump', 'pump2', 'comp']:
            comp = _get_comp(system, p_name)
            if comp is not None and getattr(comp, 'P', None) is not None:
                val = getattr(comp.P, 'val', None)
                if val is not None and np.isfinite(val):
                    if pump_kw is None:
                        pump_kw = 0.0
                    pump_kw += abs(float(val)) / 1000.0
        
        if pump_kw is None:
            # Fallback calculation
            mdot_vals = [mdot_ptc, mdot_tes_charge, mdot_tes_discharge, mdot_process]
            mdot_max = max([0.0 if (m is None or np.isnan(m)) else float(m) for m in mdot_vals])
            density = 1850.0  # kg/m3 approx for molten salt
            delta_P = 500000.0  # Pa (5 bar)
            efficiency = 0.75
            if mdot_max > 0:
                pump_kw = (mdot_max * delta_P / (density * efficiency)) / 1000.0
            else:
                pump_kw = 0.0

        net_conv = bool(getattr(system.network, 'converged', False))
        return dict(
            # energÃ­as
            to_tes_kJ=to_tes_kJ,
            tes_to_proc_kJ=tes_to_proc_kJ,
            solar_to_proc_kJ=solar_to_proc_kJ,
            aux_to_proc_kJ=aux_to_proc_kJ,
            ptc_total_kJ=ptc_total_kJ,
            # temperaturas
            T_ptc_out=T_ptc_out,
            T_tes_top=T_tes_top,
            T_tes_bottom=T_tes_bot,
            # flujos mÃ¡sicos
            mdot_ptc_kg_s=mdot_ptc,
            mdot_tes_charge_kg_s=mdot_tes_charge,
            mdot_tes_discharge_kg_s=mdot_tes_discharge,
            mdot_process_kg_s=mdot_process,
            pump_power_kW=pump_kw,
            process_hx_Q_kW=q_proc_kw,
            network_converged=net_conv)
    


    def run_quasi_steady_simulation(self, days_to_simulate = 10,
                                    csv = 'TMY.csv', time_col='Fecha/Hora',
                                    E_col='dni', Tamb_col='temp'):
        """
        Existing method: only the snippet showing how to call _iterate_tes_coupling now.
        """
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF,
                                    topology=self.topology,
                                    tank_config=self.tank_config
                                    )
        self.solar_system.create_network(mode=4)
        self.results = []
        
        self.TES_lay = 'Charge'
        self.prev_TESmode = '4'
        self.current_irr = 0
        data_frame = self.load_data(csv, '2022-01-01', days_to_simulate=days_to_simulate)
        # Track total runtime
        print("\n=== Starting transient simulation ===")
        start_time = time.time()

        self.solar_system.tes.t_max = 600        
        self._mode_dwell = 0
        
        for idx, row in tqdm(data_frame.iterrows(), total=len(data_frame), desc="Simulating"):
            
            self.mode_alert = False
            current_irr = row[E_col]
            self.current_irr = current_irr
            current_Tamb = row[Tamb_col]
            
            # Decide TES mode
            new_TESmode = self.get_system_mode(current_irr)

            if self.zinc_pool is not None:
                self.solar_system._zinc_pool_T06 = (
                    self.zinc_pool.process_outlet_temp())

            self.solar_system.set_operation_mode(TESmode=new_TESmode, 
                                                 current_irr=current_irr,
                                                 profile=self.solar_system.tes.profile,
                                                 prev_TES_lay = self.TES_lay,
                                                 mode='offdesign')
            self.current_mode = new_TESmode

            if self.current_mode in ['1','2','5','6']:
                self.solar_system.ptc_field.set_attr(E=current_irr, Tamb=current_Tamb)

            # Zinc pool: override process outlet temperature
            if self.zinc_pool is not None:
                t06_zn = self.zinc_pool.process_outlet_temp()
                if hasattr(self.solar_system, 'conn_06') and self.solar_system.conn_06 is not None:
                    self.solar_system.conn_06.set_attr(T=t06_zn)

            design_path = f'base_design_{self.current_mode}'
            
            # For each time step, do the same iteration
            iter_info = self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                       TESmode=self.current_mode, design_path=design_path,
                                       Tamb=current_Tamb) 
            if self.mode_alert:
                self.current_mode = '4'
                self.solar_system.set_operation_mode(TESmode='4', 
                                                     current_irr=current_irr,
                                                     profile=self.solar_system.tes.profile,
                                                     prev_TES_lay = self.TES_lay)
                self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                               TESmode=self.current_mode, design_path=design_path,
                                               Tamb=current_Tamb) 
                        #print(new_TESmode)
            signals = self._collect_step_signals(self.solar_system, self.current_mode)

            if self.zinc_pool is not None:
                Q_to_proc_kW = signals.get('process_hx_Q_kW', 0.0) / 1000.0
                self.zinc_pool.update(
                    Q_in_kW=Q_to_proc_kW, dt_s=3600.0,
                    T_amb=current_Tamb, timestamp=row[time_col])

            # Clamp TES profile to valid CoolProp range
            if hasattr(self.solar_system, 'tes') and self.solar_system.tes.profile is not None:
                self.solar_system.tes.profile = np.clip(
                    self.solar_system.tes.profile, 300.1, 600.0)
            tes_soc_kWh = self.solar_system.tes.calculate_SoC(self.solar_system.tes.profile)
            # Standardize energy accounting to use _collect_step_signals which properly handles units (W -> kJ)
            Q_ptc_kJ = signals.get('ptc_total_kJ', 0.0)
            Q_ph_kJ = signals.get('aux_to_proc_kJ', 0.0)
            pump_power = signals.get('pump_power_kW', 0.0) * 1000.0
            self.results.append({
                'time': row[time_col],
                'E': current_irr,
                'Tamb': current_Tamb,
                'ptc_energy_kJ': Q_ptc_kJ,
                'ph_energy_kJ':  Q_ph_kJ,
                'pump_power_W':  pump_power,
                'TES_profiles': self.TES_profiles,
                'TES_layout': self.solar_system.tes.state,
                'TESmode': self.current_mode,
                # --- energÃ­as directas por paso ---
                'to_tes_kJ':          signals['to_tes_kJ'],
                'tes_to_proc_kJ':     signals['tes_to_proc_kJ'],
                'solar_to_proc_kJ':   signals['solar_to_proc_kJ'],
                'aux_to_proc_kJ':     signals['aux_to_proc_kJ'],
                'ptc_total_kJ':       signals['ptc_total_kJ'],
                
                # --- temperaturas relevantes ---
                'T_ptc_out':          signals['T_ptc_out'],
                'T_tes_top':          signals['T_tes_top'],
                'T_tes_bottom':       signals['T_tes_bottom'],
                
                # --- flujos mÃ¡sicos relevantes ---
                'mdot_ptc_kg_s':          signals['mdot_ptc_kg_s'],
                'mdot_tes_charge_kg_s':   signals['mdot_tes_charge_kg_s'],
                'mdot_tes_discharge_kg_s':signals['mdot_tes_discharge_kg_s'],
                'mdot_process_kg_s':      signals['mdot_process_kg_s'],
                
                # --- SoC (energÃ­a, NO acumulado) ---
                'tes_soc_kWh':        tes_soc_kWh,
                
                # --- logging de convergencia por paso ---
                'mode_initial':        iter_info.get('initial_mode'),
                'mode_final':          iter_info.get('final_mode'),
                'iter_status':         iter_info.get('status'),            # 'converged'|'diverged'|'max_iter'
                'attempt_count':       len(iter_info.get('attempts', [])),
                'attempted_modes':     [a.get('mode') for a in iter_info.get('attempts', [])],
                'attempts_json':       iter_info.get('attempts', []),      # serializable a CSV (json.dumps)
                'network_converged':   signals.get('network_converged', None),
                'tespy_error':         iter_info.get('tespy_error'),
                'dof_report':          iter_info.get('dof_report'),
                # --- zinc pool (dynamic process model, None if disabled) ---
                'zinc_pool_temp':  (self.zinc_pool.temperature
                                    if self.zinc_pool is not None else None),
                'process_hx_Q_kW': signals.get('process_hx_Q_kW', 0.0),
                            })
            
            self.prev_TESmode = self.current_mode

        # End of simulation: print total elapsed time
        end_time = time.time()
        total_runtime = end_time - start_time
        print(f"\nTransient simulation completed in {total_runtime:.2f} seconds.")

        return self.results

    def compute_performance_metrics(self):
        """
        Process self.results to compute plant factor, comp energy consumption, etc.

        Args:
            process_demand_kJ (float, optional): 
                Total heat demanded by the process (in kJ) 
                over the entire simulation horizon, if known.

        Returns:
            dict: A dictionary of computed metrics.
        """
        self.dt_hours = 1.0
        df = pd.DataFrame(self.results)
        total_ptc_energy_kJ = df['ptc_energy_kJ'].sum()
        total_ph_energy_kJ  = df['ph_energy_kJ'].sum()#.loc[df['ph_energy_kJ'] > 0].sum()
        # pump power (W) * 3600 s for each step (assuming dt=1h)
        total_pump_energy_kJ = (df['pump_power_W'] * 3600.0 * self.dt_hours).sum() / 1000
        
        # Convert kJ to MWh (1 MWh = 3.6e6 kJ)
        ptc_energy_GWh   = total_ptc_energy_kJ / 3.6e9
        ph_energy_GWh    = total_ph_energy_kJ  / 3.6e9
        pump_energy_MWh  = total_pump_energy_kJ / 3.6e6
        
        # Plant factor and Solar fraction
        total_thermal_energy = total_ptc_energy_kJ + total_ph_energy_kJ
        solar_fraction = total_ptc_energy_kJ / total_thermal_energy if total_thermal_energy > 0 else 0
        spf = total_ptc_energy_kJ / (total_thermal_energy + total_pump_energy_kJ) if (total_thermal_energy + total_pump_energy_kJ) > 0 else 0

        # Print performance summary line by line
        print("\n=== Performance Summary ===")
        print(f"Total PTC Energy:       {ptc_energy_GWh:6.2f} GWh")
        print(f"Total Preheater Energy:{ph_energy_GWh:6.2f} GWh")
        print(f"Total Pump Energy:      {pump_energy_MWh:6.2f} MWh")
        print(f"Solar Fraction:         {solar_fraction * 100:6.2f}%")
        print(f"Solar Plant Factor:     {spf * 100:6.2f}%")
        print("================================\n")

        return {'spf': spf, 'solar_fraction': solar_fraction}
class Reporting:
    """
    A class responsible for plotting and reporting simulation results.
    """
    
    def plot_results(self, df_results):
        """
        Plots the main simulation results over time.

        Parameters
        ----------
        df_results : pd.DataFrame
            A DataFrame that must have 'time', 'ptc_energy_kJ', and 'gb_energy_kJ' columns
            (or whichever columns you need for plotting).
        """
        df_results = self._ensure_df(df_results)
        df2 = df_results#.iloc[len(df_results)//2:]
        plt.figure(figsize=(8, 5))
        plt.plot(df2['time'], df2['ptc_energy_kJ'], label='PTC Energy [kJ]')
        plt.plot(df2['time'], df2['ph_energy_kJ'],  label='Preheater Energy [kJ]')
        plt.xlabel('Time')
        plt.ylabel('Energy [kJ]')
        plt.title('PTC and Preheater Energy vs. Time')
        plt.legend()
        plt.tight_layout()
        plt.show()
        
    def plot_results_mode(self, df_results):
        """
        Plots the main simulation results over time.

        Parameters
        ----------
        df_results : pd.DataFrame
            A DataFrame that must have 'time', 'ptc_energy_kJ', and 'gb_energy_kJ' columns
            (or whichever columns you need for plotting).
        """
        df_results = self._ensure_df(df_results)
        df2 = df_results#.iloc[len(df_results)//2:]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df2['time'], df2['ptc_energy_kJ'], label='PTC Energy [kJ]')
        ax.plot(df2['time'], df2['ph_energy_kJ'],  label='Preheater Energy [kJ]')
        ax2 = plt.twinx(ax)
        ax2.scatter(df2['time'], df2['TESmode'], c='k')
        ax.set_xlabel('Time')
        ax.set_ylabel('Energy [kJ]')
        plt.title('PTC and Preheater Energy vs. Time')
        plt.legend()
        plt.tight_layout()
        plt.show()
        
        
    def plot_TES_profile_colormap(self, df_results, vmin=None, vmax=None):
        df_results = self._ensure_df(df_results)
        df2 = df_results.copy()
        profiles_list = df2['TES_profiles'].values
        N = len(profiles_list)
    
        first_profile = np.array(profiles_list[0]).ravel()
        M = len(first_profile)
    
        Z = np.zeros((M, N))
        for i in range(N):
            list_element = profiles_list[i]
            list_element2 = list_element[0][::-1]
            layout_i = df2['TES_layout'].iloc[i]  # <-- posicional, evita KeyError
            if layout_i in ['discharge', 'standby_dc']:
                temp_profile = np.array(list_element).ravel()
            elif layout_i in ['charge', 'standby_ch']:
                temp_profile = np.array(list_element2).ravel()
            else:
                temp_profile = np.array(list_element).ravel()
    
            if len(temp_profile) != M:
                raise ValueError(f"Fila {i} en TES_profiles tiene largo {len(temp_profile)}, se esperaba {M}.")
            Z[:, i] = temp_profile
    
        y = np.linspace(0, 1, M)
    
        times_raw = df2['time'].values
        if isinstance(times_raw[0], pd.Timestamp):
            t0 = pd.to_datetime(df2['time'].iloc[0])
            x_vals = (pd.to_datetime(df2['time']) - t0).dt.total_seconds() / 3600.0
            x_label = 'Time [h]'
        else:
            x_vals = times_raw
            x_label = 'Time'
        # --- NEW: choose color limits (defaults: data min/max) ---
        if vmin is None:
            vmin = np.nanmin(Z)
        if vmax is None:
            vmax = np.nanmax(Z)
    
        X, Y = np.meshgrid(x_vals, y)
        fig, ax = plt.subplots(figsize=(8, 5))
        cs = ax.pcolormesh(X, Y, Z, cmap='coolwarm', shading='auto', vmin=vmin, vmax=vmax)
        cbar = plt.colorbar(cs, ax=ax)
        cbar.set_label('Temperature [Â°C]', rotation=90)
    
        ax.set_ylabel('Normalized TES Height [-]')
        ax.set_xlabel(x_label)
        ax.set_title('TES Temperature Distribution vs. Time')
        plt.tight_layout(); plt.show()

        
    def plot_annual_cumulative_energy(self, df_results, out_unit="MWh",
                                      title="EnergÃ­a acumulada anual (con SoC semanal)",
                                      savepath=None):
        df_results = self._ensure_df(df_results)
        req = ['solar_to_proc_kJ','tes_to_proc_kJ','to_tes_kJ','aux_to_proc_kJ','time']
        miss = [c for c in req if c not in df_results.columns]
        if miss:
            raise ValueError(f"Faltan columnas en df_results: {miss}")
    
        df = df_results.copy()
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time').set_index('time')
    
        # kJ -> unidad de salida para los ACUMULADOS
        kJ_to = {"Wh": 1/3.6, "kWh": 1/3600.0, "MWh": 1/3.6e6, "GWh": 1/3.6e9}
        if out_unit not in kJ_to:
            raise ValueError("out_unit debe ser Wh, kWh, MWh o GWh")
        convE = kJ_to[out_unit]
    
        # Acumulados de energÃ­a 
        cum = df[['solar_to_proc_kJ','tes_to_proc_kJ','to_tes_kJ','aux_to_proc_kJ']].cumsum() * convE
    
        # --- SoC: ya estÃ¡ en energÃ­a (kWh). NO acumulado. Alineado temporalmente.
        has_soc = 'tes_soc_kWh' in df.columns
        soc_week = None
        if has_soc:
            kWh_to = {"Wh": 1e3, "kWh": 1.0, "MWh": 1e-3, "GWh": 1e-6}
            soc = df['tes_soc_kWh'] * kWh_to[out_unit]               # ej: 18823 kWh -> 18.823 MWh
            # Promedio mÃ³vil de 7 dÃ­as CENTRADO, mismo Ã­ndice (evita desfase)
            soc_week = soc.rolling(window='7D', min_periods=1, center=True).mean()
    
        # --- Escalamiento por Ã³rdenes (misma lÃ³gica para todas las series, incluido SoC si existe)
        eps = 1e-12
        series = {
            'Solar â†’ Proceso':      cum['solar_to_proc_kJ'],
            'TES â†’ Proceso':        cum['tes_to_proc_kJ'],
            'â†’ TES (carga)':        cum['to_tes_kJ'],
            'Auxiliar â†’ Proceso':   cum['aux_to_proc_kJ'],
        }
        if has_soc and soc_week is not None and not soc_week.dropna().empty:
            series['SoC TES semanal'] = soc_week
    
        # mÃ¡ximo de referencia
        nonzero_max = []
        for s in series.values():
            try:
                mx = float(np.nanmax(s.values))
            except AttributeError:
                mx = float(np.nanmax(np.asarray(s)))
            if mx > eps:
                nonzero_max.append(mx)
        ref = max(nonzero_max) if nonzero_max else 1.0
    
        def scale_for(xmax):
            if xmax <= eps:
                return 1.0
            k = int(np.round(np.log10(ref / xmax)))     # cuÃ¡ntos Ã³rdenes hay que "subir"
            k = int(np.clip(k, -6, 6))                  # evita escalas extremas
            return 10.0**k
    
        scales = {}
        for name, s in series.items():
            try:
                xmax = float(np.nanmax(s.values))
            except AttributeError:
                xmax = float(np.nanmax(np.asarray(s)))
            scales[name] = scale_for(xmax)
    
        def label_scaled(name):
            s = scales[name]
            if abs(s - 1.0) < 1e-12:
                return name
            k = int(np.round(np.log10(s)))
            return f"{name} (Ã—10^{k})"
    
        # --- Plot
        fig, ax = plt.subplots(figsize=(10, 4.6))
        ax.plot(cum.index, cum['solar_to_proc_kJ'] * scales['Solar â†’ Proceso'],      label=label_scaled('Solar â†’ Proceso'))
        ax.plot(cum.index, cum['tes_to_proc_kJ']   * scales['TES â†’ Proceso'],        label=label_scaled('TES â†’ Proceso'))
        ax.plot(cum.index, cum['to_tes_kJ']       * scales['â†’ TES (carga)'],         label=label_scaled('â†’ TES (carga)'))
        ax.plot(cum.index, cum['aux_to_proc_kJ']  * scales['Auxiliar â†’ Proceso'],    label=label_scaled('Auxiliar â†’ Proceso'))
    
        if has_soc and soc_week is not None and not soc_week.dropna().empty:
            ax.plot(soc_week.index, soc_week.values * scales['SoC TES semanal'], '--', color='k',
                    label=label_scaled('SoC TES semanal'))
    
        ax.set_title(title)
        ax.set_ylabel(f"EnergÃ­a [{out_unit}] (con escalamiento por serie)")
        ax.set_xlabel("Fecha")
    
        # Formato de fechas robusto
        if len(cum.index) > 1:
            span_days = (cum.index[-1] - cum.index[0]).days
        else:
            span_days = 0
        if span_days <= 3:
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b %Hh'))
            ax.xaxis.set_minor_locator(mdates.HourLocator())
        elif span_days <= 60:
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b'))
            ax.xaxis.set_minor_locator(mdates.DayLocator())
        else:
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
            ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    
        ax.grid(True, which='both', alpha=0.3)
        ax.legend(loc='best')
        plt.tight_layout()
        if savepath:
            plt.savefig(savepath, dpi=200)
        plt.show()


        
    def plot_TES_profile_colormap_week(self, df_results, week: int):
        df_results = self._ensure_df(df_results)
        if not (1 <= week <= 53):
            raise ValueError("`week` debe estar entre 1 y 53")
    
        df = df_results.copy()
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time')
        iso = df['time'].dt.isocalendar()
        weeks_avail = sorted(iso.week.unique().tolist())
        dfw = df.loc[iso.week == week].reset_index(drop=True)  # <-- Ã­ndice nuevo 0..N-1
    
        if dfw.empty:
            raise ValueError(f"No hay datos para la semana ISO {week}. Semanas disponibles: {weeks_avail}")
    
        return self.plot_TES_profile_colormap(dfw)

    def plot_daily_powers_temps_massflows(self, df_results, day,
                                          power_unit="kW", soc_unit="MWh",
                                          title_prefix="Perfil diario",
                                          savepath=None):
        """
        Tres paneles para un dÃ­a:
          (1) Potencias instantÃ¡neas (desde energÃ­as por paso) + SoC
          (2) Temperaturas (PTC out, TES top, TES bottom)
          (3) Flujos mÃ¡sicos (PTC, TES carga/descarga, Proceso)
    
        Mejoras:
        - Potencias convertidas a la unidad pedida y escaladas por serie (Ã—10^k en leyenda).
        - mÌ‡ TES con "gating" por TES_layout (carga/descarga â†’ 0 cuando no corresponde).
        """
    
        df_results = self._ensure_df(df_results)
        if 'time' not in df_results.columns:
            raise ValueError("df_results debe contener la columna 'time'.")
    
        # -------- SelecciÃ³n del dÃ­a --------
        df = df_results.copy()
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time').set_index('time')
    
        if isinstance(day, int):
            year = df.index[0].year
            start = pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=day-1)
        else:
            start = pd.to_datetime(day).normalize()
        end = start + pd.Timedelta(days=1)
    
        day_df = df.loc[(df.index >= start) & (df.index < end)].copy()
        if day_df.empty:
            avail = pd.to_datetime(df.index.date).unique()
            raise ValueError(f"No hay datos para {start.date()}. Algunos dÃ­as disponibles: {avail[:8]}")
    
        # -------- Gating de mÌ‡ TES por layout (carga/descarga) --------
        if 'TES_layout' in day_df.columns:
            layout = day_df['TES_layout'].astype(str).str.lower()
            if 'mdot_tes_charge_kg_s' in day_df.columns:
                day_df.loc[layout != 'charge', 'mdot_tes_charge_kg_s'] = 0.0
            if 'mdot_tes_discharge_kg_s' in day_df.columns:
                day_df.loc[layout != 'discharge', 'mdot_tes_discharge_kg_s'] = 0.0
    
        # ===== (1) POTENCIAS + SoC =====
        # P_base[kW] = E[kJ] / Î”t[s]
        e_cols = ['solar_to_proc_kJ','tes_to_proc_kJ','to_tes_kJ','aux_to_proc_kJ']
        names_p = {
            'solar_to_proc_kJ': 'Solar â†’ Process',
            'tes_to_proc_kJ'  : 'TES â†’ Process',
            'to_tes_kJ'       : 'Solar â†’ TES',
            'aux_to_proc_kJ'  : 'Auxiliar â†’ Proces',
        }
        present_e = [c for c in e_cols if c in day_df.columns]
    
        dt_s = day_df.index.to_series().diff().dt.total_seconds()
        if len(dt_s) > 1:
            med = float(np.nanmedian(dt_s.values[1:])) if np.isfinite(np.nanmedian(dt_s.values[1:])) else 3600.0
        else:
            med = 3600.0
        dt_s.iloc[0] = med
        dt_s = dt_s.replace(0, np.nan).fillna(method='bfill').fillna(method='ffill')
    
        P_kw = {names_p[c]: (day_df[c] / dt_s) for c in present_e}  # base en kW
        

        # ConversiÃ³n a unidad solicitada
        pconv = {'W': 1e3, 'kW': 1.0, 'MW': 1e-3, 'GW': 1e-6}
        if power_unit not in pconv:
            raise ValueError("power_unit debe ser 'W', 'kW', 'MW' o 'GW'")
        P = {lbl: s * pconv[power_unit] for lbl, s in P_kw.items()}  
        
        # Escalamiento por Ã³rdenes de magnitud (por serie)
        eps = 1e-12
        maxima = [float(np.nanmax(s.values)) for s in P.values() if np.nanmax(s.values) > eps]
        ref = max(maxima) if maxima else 1.0
        def scale_of(xmax):
            if xmax <= eps:
                return 1.0
            k = int(np.round(np.log10(ref / xmax)))
            k = int(np.clip(k, -6, 6))
            return 10.0**k
    
        scales = {lbl: scale_of(float(np.nanmax(s.values))) for lbl, s in P.items()}
        
        def label_scaled(name):
            s = scales[name]
            if abs(s - 1.0) < 1e-12:
                return name
            k = int(np.round(np.log10(s)))
            return f"{name} (Ã—10^{k})"
    
        # SoC (no acumulado) en eje secundario
        soc = None
        if 'tes_soc_kWh' in day_df.columns:
            kwh_to = {"Wh": 1e3, "kWh": 1.0, "MWh": 1e-3, "GWh": 1e-6}
            if soc_unit not in kwh_to:
                raise ValueError("soc_unit debe ser Wh, kWh, MWh o GWh")
            soc = (day_df['tes_soc_kWh'] * kwh_to[soc_unit]).rename(f"SoC TES [{soc_unit}]")
    
        # ===== (2) TEMPERATURAS =====
        t_cols = ['T_ptc_out','T_tes_top','T_tes_bottom']
        names_t = {
            'T_ptc_out'   : 'Solar field oulet',
            'T_tes_top'   : 'TES top',
            'T_tes_bottom': 'TES bottom',
        }
        T = {names_t[c]: day_df[c] for c in t_cols if c in day_df.columns}

        mode_cols = ['TESmode']
        names_mode = {
            'TESmode'   : 'Operation mode',
        }
        modes = {names_mode[c]: day_df[c] for c in mode_cols if c in day_df.columns}
    
        # ===== (3) FLUJOS MÃSICOS =====
        m_cols = ['mdot_ptc_kg_s','mdot_tes_charge_kg_s','mdot_tes_discharge_kg_s']
        names_m = {
            'mdot_ptc_kg_s'          : 'Solar field',
            'mdot_tes_charge_kg_s'   : 'TES (charge)',
            'mdot_tes_discharge_kg_s': 'TES (discharge)',
        }
        M = {names_m[c]: day_df[c] for c in m_cols if c in day_df.columns}
    
        # ====== FIGURA: 3 paneles ======
        fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(11, 9), sharex=True)
    
        # (1) Potencias
        axP = axes[0]
        for lbl, s in P.items():
            axP.plot(s.index, (s.values * scales[lbl]), label=label_scaled(lbl))
        #axP.set_title(f"{title_prefix} â€” {start.date()} (Potencias + SoC)")
        axP.set_ylabel(f"Power [{power_unit}]")
        axP.grid(True, alpha=0.3)
    
        if soc is not None:
            axS = axP.twinx()
            axS.plot(soc.index, soc.values, '--', color='k', label=soc.name)
            axS.set_ylabel(soc.name)
            h1, l1 = axP.get_legend_handles_labels()
            h2, l2 = axS.get_legend_handles_labels()
            axS.legend(h1+h2, l1+l2, loc='best')
        else:
            axP.legend(loc='best')
    
        # (2) Temperaturas
        axT = axes[1]
        if T:
            axT2 = plt.twinx(axT)
            for lbl, s in T.items():
                axT.plot(s.index, s.values, label=lbl)
            for lbl, s in modes.items():
                axT2.scatter(s.index, s.values, label=lbl)
            #axT.set_title(f"{title_prefix} â€” {start.date()} (Temperaturas)")
            axT.set_ylabel("Temperature [Â°C]")
            axT2.set_ylabel("Operation mode")
            axT2.set_yticks([1,2,3,4,5,6])
            axT.grid(True, alpha=0.3)
            axT.legend(loc='best')

        else:
           #axT.set_title(f"{title_prefix} â€” {start.date()} (Temperaturas)")
            axT.text(0.5, 0.5, "No hay columnas de temperatura en df_results",
                     ha='center', va='center', transform=axT.transAxes)

        # (3) Flujos mÃ¡sicos
        axM = axes[2]
        if M:
            for lbl, s in M.items():
                axM.plot(s.index, s.values, label=lbl)
            #axM.set_title(f"{title_prefix} â€” {start.date()} (Flujos mÃ¡sicos)")
            axM.set_ylabel("Mass flow [kg/s]")
            axM.grid(True, alpha=0.3)
            axM.legend(loc='best')
        else:
            #axM.set_title(f"{title_prefix} â€” {start.date()} (Flujos mÃ¡sicos)")
            axM.text(0.5, 0.5, "No hay columnas de flujo mÃ¡sico en df_results",
                     ha='center', va='center', transform=axM.transAxes)
    
        # Eje X comÃºn a horas
        axes[-1].set_xlabel("Hour")
        for ax in axes:
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_minor_locator(mdates.HourLocator())
    
        plt.tight_layout()
        if savepath:
            plt.savefig(savepath, dpi=200)
        plt.show()


    # ====== Helpers de IO ======
    def _ensure_df(self, df_or_path):
        """
        Acepta un DataFrame o una ruta a CSV con nuestra cabecera __meta__.
        Devuelve (DataFrame). Si se entrega ruta, ignora el meta.
        """
        if isinstance(df_or_path, str):
            df, _ = self.load_simulation_from_csv(df_or_path)
            return df
        return df_or_path
    
    def _jsonable(self, obj):
        """
        Convierte obj a algo serializable en JSON (maneja numpy/pandas/tipos fecha/listas/dicts).
        """
        import json, numpy as np
        import pandas as pd
        import datetime as dt
        if obj is None:
            return None
        if isinstance(obj, (bool, int, float, str)):
            return obj
        if isinstance(obj, (np.integer)):
            return int(obj)
        if isinstance(obj, (np.floating)):
            return float(obj)
        if isinstance(obj, (np.ndarray)):
            return [self._jsonable(x) for x in obj.tolist()]
        if isinstance(obj, (list, tuple, set)):
            return [self._jsonable(x) for x in obj]
        if isinstance(obj, (pd.Timestamp, dt.datetime, dt.date, dt.time)):
            try:
                return obj.isoformat()
            except AttributeError:
                return str(obj)
        if isinstance(obj, dict):
            return {str(k): self._jsonable(v) for k, v in obj.items()}
        try:
            json.dumps(obj)
            return obj
        except TypeError:
            return str(obj)
    
    def save_simulation_to_csv(self, df_results, filepath,
                               solver=None,
                               params: dict = None,
                               sim_args: dict = None,
                               extra_meta: dict = None,
                               tes_params: dict = None,
                               component_params: dict = None,
                               conexion_params: dict = None):
        """
        Guarda un CSV con:
        - 1Âª lÃ­nea: __meta__,{JSON con parÃ¡metros y condiciones de la simulaciÃ³n}
        - Resto: df_results (una fila por paso temporal)
    
        Prioridad de metadatos (de menor a mayor):
          solver â†’ params â†’ (tes_params, component_params, conexion_params) â†’ sim_args â†’ extra_meta
    
        Cualquier dict que pases explÃ­citamente (tes_params/component_params/conexion_params)
        sobreescribe lo que se haya obtenido del solver o de `params`.
        """
    
        # --- ConstrucciÃ³n del META ---
        meta = {}
    
        # 1) Intento desde solver (si viene)
        if solver is not None:
            meta['system_mode']      = self._jsonable(getattr(solver, 'system_mode', None))
            meta['HTF']              = self._jsonable(getattr(solver, 'HTF', None))
            meta['tes_params']       = self._jsonable(deepcopy(getattr(solver, 'tes_params', {})))
            meta['component_params'] = self._jsonable(deepcopy(getattr(solver, 'component_params', {})))
            meta['conexion_params']  = self._jsonable(deepcopy(getattr(solver, 'conexion_params', {})))
    
        # 2) Mezcla con `params` (si viene) â€” Ãºtil para empaquetar varios en un solo dict
        if params is not None:
            for k, v in params.items():
                meta[k] = self._jsonable(v)
    
        # 3) Sobrescritura explÃ­cita (PRIORIDAD): los tres dicts pedidos
        if tes_params is not None:
            meta['tes_params'] = self._jsonable(deepcopy(tes_params))
        if component_params is not None:
            meta['component_params'] = self._jsonable(deepcopy(component_params))
        if conexion_params is not None:
            meta['conexion_params'] = self._jsonable(deepcopy(conexion_params))
    
        # 4) Argumentos de simulaciÃ³n y extras (quedan al mismo nivel)
        if sim_args is not None:
            meta['sim_args'] = self._jsonable(sim_args)
        if extra_meta is not None:
            meta['extra'] = self._jsonable(extra_meta)
    
        # --- Copia del DF y saneo de columnas no-escalares (listas/dicts)
        dfw = df_results.copy()
        if 'time' in dfw.columns:
            dfw['time'] = pd.to_datetime(dfw['time'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
    
        def _maybe_jsonify_cell(x):
            if isinstance(x, (list, tuple, dict)):
                return json.dumps(self._jsonable(x), ensure_ascii=False)
            return x
    
        for c in dfw.columns:
            if dfw[c].dtype == 'O':
                dfw[c] = dfw[c].apply(_maybe_jsonify_cell)
    
        # --- Escribir archivo (crear carpeta y sobrescribir si existe)
        dirpath = os.path.dirname(os.path.abspath(filepath))
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
    
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write('__meta__,' + json.dumps(meta, ensure_ascii=False) + '\n')
    
        dfw.to_csv(filepath, mode='a', index=False, encoding='utf-8')

    
    def load_simulation_from_csv(self, filepath):
        """
        Lee un CSV creado por save_simulation_to_csv y devuelve:
            (df_results: DataFrame, meta: dict)
    
        - Parsea la 1Âª lÃ­nea '__meta__,{...}' como JSON
        - Lee el resto con pandas
        - Convierte 'time' a datetime (si existe)
        - Intenta parsear columnas con JSON (p. ej., TES_profiles)
        """
    
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"No existe el archivo: {filepath}")
    
        # Leer primera lÃ­nea
        with open(filepath, 'r', encoding='utf-8') as f:
            first = f.readline().rstrip('\n')
        meta = {}
        prefix = '__meta__,'
        if first.startswith(prefix):
            try:
                meta = json.loads(first[len(prefix):])
            except json.JSONDecodeError:
                meta = {}
    
        # Leer el resto
        df = pd.read_csv(filepath, skiprows=1, encoding='utf-8')
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'], errors='coerce')
    
        # Reconvertir JSON en columnas objeto que lo aparenten
        def _looks_json(s):
            s = str(s).strip()
            return (s.startswith('[') and s.endswith(']')) or (s.startswith('{') and s.endswith('}'))
    
        for c in df.columns:
            if df[c].dtype == 'O':
                sample = df[c].dropna().astype(str).head(3).tolist()
                if any(_looks_json(s) for s in sample):
                    try:
                        df[c] = df[c].apply(lambda x: json.loads(x) if isinstance(x, str) and _looks_json(x) else x)
                    except ValueError:
                        pass
    
        return df, meta
