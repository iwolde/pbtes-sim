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
        total_m_in = self.inl[0].m.val_SI
        
        # 2) Scale both mass flow and area for a single-row
        if self.rows > 1:
            # Inlet flow
            self.inl[0].m.val_SI = total_m_in / self.rows


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
        self.outl[0].m.val_SI = total_m_in
      
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

        self.dt = dt #min

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
        self.AT = 0.25 * self.Dint**2 * np.pi  # m2 - Área transversal del estanque
        self.Aphi = 0.25 * (25.4e-3*2)**2* np.pi  # m2 - Área transversal del tubo de descarga
        
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
        # Temperatura media
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
        
        self.mflow = mass_flow #kg/min
        #print(self.mflow)
        
        self.air_params()
        
        # Flujo másico por unidad de área al interior del TES
        G = self.mflow / self.AT 
        # Cálculo de alpha y k_eff
        Re = G*self.dp/self.mu_f  # Reynolds
        Pr = self.mu_f * self.cp_f / self.k_f  # Prandtl
        ff = 6*(1-self.e)/self.dp  # m - Factor de forma roca - fluido
        rho_cp_line = (self.e * self.rho_f * self.cp_f + (1-self.e) * self.rho_s * self.cp_s) # Capacitancia equivalente
        self.kappa = self.e * (self.rho_f * self.cp_f) / rho_cp_line  # Factor kappa (adimensional de interés para el modelo)
        u_in = G / (self.rho_f)  # m/s - Velocidad intersticial
        hv = ff * (self.k_f/self.dp) * 1.32 * Re**0.59 * Pr**(1/3)  # W/m3 K - Coef. de transferencia de calor volumétrica (Tesis Daniel Orellana)
        k_line = (self.e *self.k_f + (1-self.e)*self.k_s) # Conductividad promedio
        k_eff = k_line + ((1-self.e) * (self.rho_s*self.cp_s) * (G*self.cp_f/rho_cp_line))**2/hv  # Conductividad efectiva (Ver ec. 7 de Paper 1)
        alpha = k_eff / rho_cp_line  # Cálculo de alpha
        self.Pe = u_in * self.HT / alpha  # Cálculo de Péclet que cambia con el tiempo (adimensional de interés para el modelo)
        self.a = self.kappa * self.Pe / 2
       
        # Resistencia interna
        hint = (self.k_f/self.dp) * (0.203 * Re**(1/3) * Pr**(1/3) + 0.22 * Re**0.8 * Pr**0.4)
        Rint = 1/hint
        # Coeficiente de transferencia de calor
        hw = 1/Rint
        # Stanton
        self.beta = 4/self.Dint
        #self.St = 0.75*hw*self.beta*self.HT/(rho_cp_line*u_in)
        self.St = 0#1e-3
        self.b = -(self.St + self.a**2/self.Pe)
        
        self.tau = u_in*self.dt/self.HT
        

    def _eq(self, ev, a):
        """
        Ecuación trascendental para obtener autovalores

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
        Algoritmo de búsqueda de raíces

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
        Función que evalúa la solución dadas las condiciones de un paso de tiempo

        Returns
        -------
        sol : List
            DESCRIPTION.

        """
        theta = (self.t_in-self.t_min)/(self.t_max-self.t_min)
        init = (self.init-self.t_min)/(self.t_max-self.t_min)
        ############# Sol. Estacionaria
        # Definir constantes de la solución estacionaria
        k1 = np.longdouble(0.5 * (self.kappa * self.Pe - np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        k2 = np.longdouble(0.5 * (self.kappa * self.Pe + np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        C2 = theta * k1 * np.exp(k1) / (k1*np.exp(k1) - k2*np.exp(k2))
        C1 = theta - C2
        # Solución estacionaria
        Mx = lambda x : C1*np.exp(k1*x) + C2*np.exp(k2*x)
    
        ############# Sol. Transiente        
        # Calcular autovalores
        lbd = self.solve_eq(200, self.a)
        # Definir la functión Kernel
        fn = np.sqrt(2) * np.sqrt((lbd**2 + self.a**2)/(lbd**2 + self.a**2 + self.a))
        Knx = lambda x : fn[:, None] * np.sin(lbd[:, None]*x)
        # Transformada integral de la solución inicial
        # 1, Interpolar datos de la condición inicial
        xint = np.linspace(0, 1, 200)
        t0_int = interp1d(self.xev, init, bounds_error=False, fill_value='extrapolate')(xint)
        phi0 = (t0_int - Mx(xint)) / np.exp(self.a*xint)
        phi0n = np.trapz(Knx(xint)*phi0, x=xint, axis=1)
        # 2, Solución del problema de autovalores
        phin = phi0n[:, None] * np.exp(-lbd[:, None]**2 * self.tau / self.Pe)
        # 3, Solución del problema transiente
        Nxt = np.exp(self.a*self.xev[:, None] + self.b*self.tau) * (np.sum(phin * Knx(self.xev), axis=0)[:, None])
    
        ############# Sol.
        sol = Mx(self.xev)[:, None] + Nxt
    
        return sol
    
    def update_temperature_profile(self, T_in, mass_flow, initial_profile):
        """
        Updates the temperature profile of the TES for the given time.

        Parameters
        ----------
        dt : TYPE
            Time step.
        mass_flow : Float
            Inlet mass flow [kg/s].
        T_in : Float
            Inlet Temperature [°C].

        Returns
        -------
        None.

        """
        
        self.init = initial_profile
        self.t_max = max(self.profile.max(), T_in)
        self.t_min = min(self.profile.min(), T_in)
        self.eq_params(T_in, mass_flow)
        self.profile = self.calc_solution().reshape((len(self.xev), ))*(self.t_max-self.t_min) + self.t_min
        self.init = self.profile
        self.tout = self.profile[-1]
        return self.profile
    
    def calc_heat_loss(self, profile, dt, T_amb):
        """
        Update the temperature profile of a stratified TES packed bed over a time step dt.
        
        The packed bed consists of a solid matrix and a fluid. Fluid properties (density and cp)
        are calculated using CoolProp at the current layer temperature. The effective thermal capacity 
        (mass*cp) for each layer is computed from the contributions of both the fluid and the solid.

        Returns:
            np.array: Updated temperature profile (in °C) after dt seconds.
            
        Notes:
            - Each layer has a volume V_layer = A_cross * dz, with dz = height / n_layers and 
              A_cross = π*(diameter/2)².
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
            # Convert layer temperature from °C to Kelvin for CoolProp calculations
            T_K = T + 273.15
            fluid_density = cp.PropsSI('D', 'T', T_K, 'P', self.HTF_P, self.HTF)  # kg/m³
            fluid_cp = cp.PropsSI('C', 'T', T_K, 'P', self.HTF_P, self.HTF)         # J/kg·K
            
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
            
            # Compute temperature change dT (°C) for the time step dt
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

        self.air_params()
        
        radius = self.Dint / 2
        volume = np.pi * (radius ** 2) * self.HT

        Cp_pb = self.cp_s * self.e + self.cp_f * (1-self.e)# (kJ/kg°C)
        rho_pb = self.rho_s * self.e + self.rho_out * (1-self.e)  #  (kg/m³)
        
        SoC = 0
        for temp in profile:
            energy = volume * rho_pb * Cp_pb  * temp / len(profile)
            SoC += energy #J
        return SoC/3.6e6 #kWh
         
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
                 HTF=None):
        """
        Constructor initializes placeholders for the network, components, 
        and connections. Actual creation of these will occur in other methods.
        """
        self.HTF = HTF
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
        
        
    def create_network1(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600],
                              #m_range=[0, 50]
                              )

        # 3) Create and add components
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')

        # TES layout
        self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
        
        self.splitter1 = tpc.nodes.splitter.Splitter(label='Splitter1')
        self.merge2 = tpc.nodes.merge.Merge(label='Merge2')
        
        #TES
        self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
        self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        
        # Main Loop
        self.conn_01 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='01_CC_PTC'
            )
        
        self.conn_02 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.splitter1, 'in1',
            label='02_PTC_SP1'
            )
        
        self.conn_04 = tpcn.Connection(
            self.splitter1, 'out1',
            self.preheater_hx, 'in1',
            label='04_SP1_PH'
            )
        
        self.conn_05 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='05_PH_PR'
            )
        
        self.conn_06 = tpcn.Connection(
            self.process_hx, 'out1',
            self.merge2, 'in1',
            label='06_PR_MG2'
            )
        
        self.conn_08 = tpcn.Connection(
            self.merge2, 'out1',
            self.cycle_closer, 'in1',
            label='08_MG2_CC'
            )
        
        # Branch 1 (Charge path)
        self.conn_09 = tpcn.Connection(
            self.splitter1, 'out2',
            self.charge_tes_hx, 'in1',
            label='09_SP1_CHX'
            )
        
        self.conn_10 = tpcn.Connection(
            self.charge_tes_hx, 'out1',
            self.merge2, 'in2',
            label='10_CHX_MG2'
            )
        
        #TES
        self.conn_13 = tpcn.Connection(
            self.tes_ch_source, 'out1',
            self.charge_tes_hx, 'in2',
            label='13_CHSC_CHX'
            )

        
        self.conn_14   = tpcn.Connection(
            self.charge_tes_hx, 'out2',
            self.tes_ch_sink, 'in1',       
            label='14_CHX_CHSK'
            )
        
        self.network.add_conns(
            self.conn_01,
            self.conn_02,
            self.conn_04,
            self.conn_05,
            self.conn_06,
            self.conn_08,
            self.conn_09,
            self.conn_10,
            self.conn_13,
            self.conn_14,
           )
        
        self.conn_01.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_02.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_04.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_05.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_06.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_08.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_09.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_10.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_13.set_attr(T0=500, h0=700, m0=5, p0=5)
        self.conn_14.set_attr(T0=500, h0=700, m0=5, p0=5)

           # Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'],
                                #design=['pr'], offdesign=['zeta']
                                )
        
        # self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
        #                         Q=850000
        #                         )

        
        self.conn_05.set_attr(T=self.conexion_params['5_T'],
                              )
        # Outflow of process HX
        self.conn_06.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'],
                             )
        
        self.process_hx.set_attr(pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'],
                                 #design=['pr'], offdesign=['zeta']
                                 )
        
        # Preheater HX
        self.preheater_hx.set_attr(#pr=self.component_params['PH_pr'],
                                   #design=['pr'], offdesign=['zeta']
                                   )
        
        # TES HTF
        self.conn_13.set_attr(p=self.conexion_params['13_p'], 
                              fluid=self.conexion_params['13_f']
                              )

        #
        self.charge_tes_hx.set_attr(pr2=1,
                                   offdesign=['eff_cold','eff_hot'],
                                   )


    def create_network2(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        #self.network.set_attr(T_range=[300, 600])

        # 3) Create and add components
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')
        
        # Main Loop
        self.conn_01 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='01_CC_PTC'
            )
        
        self.conn_02 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.preheater_hx, 'in1',
            label='02_PTC_PH'
            )

        self.conn_05 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='05_PH_PR'
            )
        
        self.conn_06 = tpcn.Connection(
            self.process_hx, 'out1',
            self.cycle_closer, 'in1',
            label='06_PR_CC'
            )
        


        self.network.add_conns(
            self.conn_01,
            self.conn_02,
            self.conn_05,
            self.conn_06,
           )
        
        self.conn_01.set_attr(T0=500, h0=700)
        self.conn_02.set_attr(T0=500, h0=700)
        self.conn_05.set_attr(T0=500, h0=700)
        self.conn_06.set_attr(T0=500, h0=700)
        
        #    Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'])


        # Outflow of process HX
        self.conn_06.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        
        self.process_hx.set_attr(#pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_05.set_attr(T=self.conexion_params['5_T'])

    def create_network3(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """
        
        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600],
                              #m_range=[0, 50]
                              )

        # 3) Create and add components
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
    
        # TES layout
        self.discharge_tes_hx = tpc.HeatExchanger(label='Discharge_TES_HX')
        
        #TES
        self.tes_dch_source = tpc.Source('TES_discharge_inlet_source')
        self.tes_dch_sink   = tpc.Sink('TES_discharge_outlet_sink')
        
        # Main Loop
        self.conn_04 = tpcn.Connection(
            self.discharge_tes_hx, 'out2',
            self.preheater_hx, 'in1',
            label='04_DHX_PH'
            )
        
        self.conn_05 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='05_PH_PR'
            )
        
        self.conn_06 = tpcn.Connection(
            self.process_hx, 'out1',
            self.cycle_closer, 'in1',
            label='06_PR_CC'
            )


        self.conn_11 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.discharge_tes_hx, 'in2',
            label='11_CC_DHX'
            )
        
        #TES
        self.conn_15= tpcn.Connection(
            self.tes_dch_source, 'out1',       
            self.discharge_tes_hx, 'in1',       
            label='15_DCHSC_DHX'
            )
        
        self.conn_16  = tpcn.Connection(
            self.discharge_tes_hx, 'out1',
            self.tes_dch_sink, 'in1',
            label='16_DHX_DCHSK'
            )
        
        

        self.network.add_conns(
            self.conn_04,    
            self.conn_05,
            self.conn_06,
            self.conn_11,
            self.conn_15,
            self.conn_16,
           )
        
        self.conn_04.set_attr(T0=500, m0=1, p0=5)
        self.conn_05.set_attr(T0=500, m0=1, p0=5)
        self.conn_06.set_attr(T0=500, m0=1, p0=5)
        self.conn_11.set_attr(T0=500, m0=1, p0=5)
        self.conn_15.set_attr(T0=500, m0=1, p0=5)
        self.conn_16.set_attr(T0=500, m0=1, p0=5)

        # Outflow of process HX
        self.conn_06.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        
        self.process_hx.set_attr(#pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # TES HTF
        self.conn_15.set_attr(p=self.conexion_params['15_p'], 
                              fluid=self.conexion_params['15_f'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_05.set_attr(T=self.conexion_params['5_T'])
        
        self.discharge_tes_hx.set_attr(pr1=1, pr2=1, 
                                       #ttd_min=5,
                                       #design=['ttd_min'],
                                       offdesign=['eff_cold','eff_hot',
                                                  #'ttd_min'
                                                  ],
                                   )

    def create_network4(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')
        self.network.set_attr(T_range=[300, 600],
                              #m_range=[0, 50]
                              )

        # 3) Create and add components
        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
    

        # Main Loop
        self.conn_04 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.preheater_hx, 'in1',
            label='04_CC_PH'
            )
        
        self.conn_05 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='05_PH_PR'
            )
        
        self.conn_06 = tpcn.Connection(
            self.process_hx, 'out1',
            self.cycle_closer, 'in1',
            label='06_PR_CC'
            )


        self.network.add_conns(
            self.conn_04,    
            self.conn_05,
            self.conn_06,
           )
        
        self.conn_04.set_attr(T0=500, m0=1, p0=5)
        self.conn_05.set_attr(T0=500, m0=1, p0=5)
        self.conn_06.set_attr(T0=500, m0=1, p0=5)


        # Outflow of process HX
        self.conn_06.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        
        self.process_hx.set_attr(#pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_05.set_attr(T=self.conexion_params['5_T'])

    def create_network5(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')

        # 3) Create and add components

        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')

        # TES layout
        self.tes_hx_ch = tpc.SimpleHeatExchanger(label='TES_charger_HX')
        
        #TES
        self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
        self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        
        
        # Process Loop
        self.conn_04 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.preheater_hx, 'in1',
            label='04_CC_PH'
            )
        
        self.conn_05 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='05_PH_PR'
            )

        self.conn_06 = tpcn.Connection(
            self.process_hx, 'out1',
            self.cycle_closer, 'in1',
            label='06_PR_CC'
            )
        
        #TES
        
        self.conn_13   = tpcn.Connection(
            self.tes_ch_source, 'out1',
            self.tes_hx_ch, 'in1',       
            label='13_CHSC_CHTES'
            )
        
        self.conn_14   = tpcn.Connection(
            self.tes_hx_ch, 'out1',
            self.tes_ch_sink, 'in1',       
            label='14_CHTES_CHSK'
            )
        self.network.add_conns(

            self.conn_04,
            self.conn_05,
            self.conn_06,
            self.conn_13,
            self.conn_14,
           )

        self.conn_04.set_attr(T0=500, h0=700, m0=2)
        self.conn_05.set_attr(T0=500, h0=700, m0=2)
        self.conn_06.set_attr(T0=500, h0=700, m0=2)
        self.conn_13.set_attr(T0=500, h0=700, m0=2)
        self.conn_14.set_attr(T0=500, h0=700, m0=2)

        # Outflow of process HX
        self.conn_06.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f'])
        
        self.process_hx.set_attr(#pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        self.conn_05.set_attr(T=self.conexion_params['5_T'])
        
        # TES HTF
        self.conn_13.set_attr(p=self.conexion_params['13_p'], 
                              fluid=self.conexion_params['13_f']
                              )
        
        self.tes_hx_ch.set_attr(pr=self.component_params['PR_pr'], 
                                Q=-self.component_params['PR_Q'])
        
    def create_network6(self):
        """
        Build or rebuild the entire TESPy network from scratch for the given mode.
        This resets self.network to a new instance and adds the relevant components
        and connections for that mode.
        """

        # 2) Create a new TESPy Network
        self.network = tpn.Network(fluids=[self.HTF], T_unit='C', p_unit='bar', h_unit='kJ / kg')

        # 3) Create and add components

        self.process_hx = tpc.SimpleHeatExchanger(label='Process_HX')
        self.preheater_hx = tpc.SimpleHeatExchanger(label='Preheater_HX')
        self.cycle_closer = tpc.CycleCloser(label='CycleCloser')
        self.cycle_closer2 = tpc.CycleCloser(label='CycleCloser2')
        self.ptc_field = tpc.ParabolicTrough(label='PTCField')

        # TES layout
        self.charge_tes_hx = tpc.HeatExchanger(label='Charge_TES_HX')
        
        #TES
        self.tes_ch_source = tpc.Source('TES_charge_inlet_source')
        self.tes_ch_sink   = tpc.Sink('TES_charge_outlet_sink')
        
        # Main Loop
        self.conn_01 = tpcn.Connection(
            self.cycle_closer, 'out1',
            self.ptc_field, 'in1',
            label='01_CC_PTC'
            )
        
        self.conn_02 = tpcn.Connection(
            self.ptc_field, 'out1',
            self.charge_tes_hx, 'in1',
            label='02_PTC_CHX'
            )
        
        self.conn_10 = tpcn.Connection(
            self.charge_tes_hx, 'out1',
            self.cycle_closer, 'in1',
            label='10_CHX_CC'
            )
        
        # Process Loop
        self.conn_04 = tpcn.Connection(
            self.cycle_closer2, 'out1',
            self.preheater_hx, 'in1',
            label='04_CC2_PH'
            )
        
        self.conn_05 = tpcn.Connection(
            self.preheater_hx, 'out1',
            self.process_hx, 'in1',
            label='05_PH_PR'
            )

        self.conn_06 = tpcn.Connection(
            self.process_hx, 'out1',
            self.cycle_closer2, 'in1',
            label='06_PR_CC2'
            )
        
        #TES
        self.conn_13 = tpcn.Connection(
            self.tes_ch_source, 'out1',
            self.charge_tes_hx, 'in2',
            label='13_CHSC_CHX'
            )
        
        self.conn_14   = tpcn.Connection(
            self.charge_tes_hx, 'out2',
            self.tes_ch_sink, 'in1',       
            label='14_CHX_CHSK'
            )
        
        self.network.add_conns(
            self.conn_01,
            self.conn_02,
            self.conn_10,
            self.conn_04,
            self.conn_05,
            self.conn_06,
            self.conn_13,
            self.conn_14,
           )
    

        self.conn_01.set_attr(T0=500, h0=700, m0=2)
        self.conn_02.set_attr(T0=500, h0=700, m0=2)
        self.conn_10.set_attr(T0=500, h0=700, m0=2)
        self.conn_04.set_attr(T0=500, h0=700, m0=2)
        self.conn_05.set_attr(T0=500, h0=700, m0=2)
        self.conn_06.set_attr(T0=500, h0=700, m0=2)
        self.conn_13.set_attr(T0=500, h0=700, m0=2)
        self.conn_14.set_attr(T0=500, h0=700, m0=2)
        


        #    Set collector parameters pero row (area, pr, DNI, design, etc.)
        self.ptc_field.set_attr(pr=self.component_params['ptc_pr'], 
                                aoi=self.component_params['ptc_aoi'], 
                                doc=self.component_params['ptc_doc'],
                                Tamb=self.component_params['ptc_tamb'], 
                                A=self.component_params['ptc_A'], 
                                eta_opt=self.component_params['eta_opt'], 
                                c_1=self.component_params['ptc_c_1'], 
                                c_2=self.component_params['ptc_c_2'], 
                                E=self.component_params['ptc_E'],
                                iam_1=self.component_params['ptc_iam_1'], 
                                iam_2=self.component_params['ptc_iam_2'])


        # Outflow of process HX
        
        self.conn_05.set_attr(T=self.conexion_params['5_T'],
                             )
        self.conn_06.set_attr(T=self.conexion_params['6_T'],
                             p=self.conexion_params['6_p'],
                             fluid=self.conexion_params['6_f']
                             )
        
        self.conn_02.set_attr(p=self.conexion_params['6_p'], 
                             fluid=self.conexion_params['6_f']
                             )

        self.process_hx.set_attr(#pr=self.component_params['PR_pr'], 
                                 Q=self.component_params['PR_Q'])

        # TES HTF
        self.conn_14.set_attr(p=self.conexion_params['13_p'], 
                              fluid=self.conexion_params['13_f']
                              )

        # Preheater HX
        self.preheater_hx.set_attr(pr=self.component_params['PH_pr'])
        
        self.charge_tes_hx.set_attr(pr2=1,
                                   offdesign=['eff_cold','eff_hot'],
                                   )
        
    def set_operation_mode(self, TESmode='4', 
                           current_irr=0,
                           profile=None,
                           prev_TES_lay = 'Charge',
                           mode = 'design'):
        """
        mode 1: High irradiation, PTC to process and to TES
        mode 2: Mid irradiation, PTC to process, TES in standby
        mode 3: Low irradiation, TES to process
        mode 4: Low irradiation, TES in standby
        mode 5: Low irradiation, TES re-stratification
        mode 6: Mid to high irradiation, PTC full to TES
        """
        if prev_TES_lay == 'Charge':
            TES_top = profile[0]
            TES_bot = profile[-1]
        elif prev_TES_lay == 'Discharge':
            TES_top = profile[-1]
            TES_bot = profile[0]

        if TESmode == '1':
            self.create_network1()
            self.tes.set_state('charge')

            self.preheater_hx.set_attr(Q=0)
            
            TES_target = self.conexion_params['6_T']

            self.conn_10.set_attr(T=TES_target)
            self.conn_14.set_attr(T=TES_bot+40)

            if mode == 'offdesign':
                self.conn_14.set_attr(T=None)
                self.conn_10.set_attr(T=None)
            
        elif TESmode == '2':
            # All flow from PTC to process
            self.create_network2()
            #self.tes.set_state('standby_ch')
            if current_irr > 500:
                self.ptc_field.set_attr(A='var')
                self.preheater_hx.set_attr(Q=0)
                
        elif TESmode == '3':
            # All flow from TES, none in PTC and charge loop
            self.create_network3()
            self.tes.set_state('discharge')
            #if TES_top > self.conexion_params['7_T']: 
            TES_target = TES_top - 20 
            TES_toutlet = TES_top - 25 

            self.conn_16.set_attr(T=TES_toutlet)
            self.conn_04.set_attr(T=TES_target)
            if mode == 'offdesign':
                #pass
                self.conn_04.set_attr(T=None)
                self.conn_16.set_attr(T=None)

        elif TESmode == '4':
            self.create_network4()
            #self.tes.set_state('standby_dc')
            #self.tes.set_state('discharge')
            
        elif TESmode == '5':
            self.create_network5()
            self.tes.set_state('charge')
            self.conn_14.set_attr(T=TES_bot+40)
            
        elif TESmode == '6':
            self.create_network6()
            self.tes.set_state('charge')
            TES_target = self.conexion_params['6_T']

            self.conn_10.set_attr(T=TES_target)
            self.conn_14.set_attr(T=TES_bot+40)
            self.conn_02.set_attr(m=tpcn.Ref(self.conn_04,1,0))

            if mode == 'offdesign':
                self.conn_14.set_attr(T=None)
                #self.conn_10.set_attr(T=None)
                self.conn_02.set_attr(m=None)

        else:   
            raise ValueError(f"Unknown mode {TESmode}")

            
    def solve_network(self, mode='design', design_path="base_design", TESmode='1'):
        """
        Attempts to solve the network in the specified mode (default: 'design').
        Raises an exception if the solver fails.
        
        Args:
            mode (str): 'design' or 'offdesign' (TESPy modes).
        """

        name = f'base_design_{TESmode}'        
        if mode == 'design':

            self.network.solve(mode=mode, max_iter=100)
            self.network.save(name)
        else:
            self.network.solve(mode=mode, max_iter=100,
                               design_path = f'base_design_{TESmode}')
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
                 file_path=None):
        self.tes_params= tes_params
        self.component_params = component_params
        self.conexion_params = conexion_params
        self.HTF= HTF 
        self.system_mode = system_mode
        self.results = []
        self.current_mode = '4' 
        self.file_path = file_path
        self.mode_alert = False

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
        Selección de modo (ordenada y con verificación interna de viabilidad de carga).
        - No cambia tu filosofía ni umbrales.
        - Si se puede leer T_ptc_out de la red actual, evita elegir Modo 1 cuando
          T_ptc_out ≤ TES_top (cargar sin ΔT).
        """
    
        # --- Top/Bottom coherentes con el layout previo ---
        lay = prev_TES_lay or getattr(self, 'TES_lay', 'Charge')
        if lay == 'Charge':
            TES_top = TES_profile[0];  TES_bot = TES_profile[-1]
        else:  # 'Discharge'
            TES_top = TES_profile[-1]; TES_bot = TES_profile[0]
            
        TES_max = float(np.max(TES_profile))
        TES_min = float(np.min(TES_profile))
    
        t_proc_set = self.solar_system.conexion_params['6_T']  # referencia de proceso
        t_ph_out   = self.solar_system.conexion_params['5_T']   # (PH out) ~ 520°C
    
        # --- Lectura interna (opcional) de T_ptc_out desde la red actual ---
        def _read_T_ptc_out():
            # conn_02: PTC -> splitter ; conn_04: splitter -> preheater (fallback)
            for cname in ('conn_02', 'conn_04'):
                c = getattr(self.solar_system, cname, None)
                if c is not None and hasattr(c, 'T') and c.T is not None:
                    # TESPy: T.val (en unidades de la red) o T.val_SI
                    try:
                        if getattr(c.T, 'val', None) is not None:
                            return float(c.T.val)  # red está en °C
                        if getattr(c.T, 'val_SI', None) is not None:
                            return float(c.T.val_SI - 273.15)
                    except Exception:
                        pass
            return None
    
        T_ptc_out = _read_T_ptc_out()
    
        # --- Preferencias por modo previo (pegajosidad) ---
        if self.prev_TESmode == '5' and (TES_bot < 400) and (irr < 600):
            return '5'
        if self.prev_TESmode == '6' and (TES_bot < 460) and (irr > 600):
            return '6'
    
        # --- Casos extremos primero ---
        # Opcion 1
        #if (TES_max < 400.0 or TES_min < 360.0) and irr < 600:
        # # Opcion 2
        if TES_max < 440.0 and irr < 600:
            return '5'  # muy frío y poca irradiancia → auxiliar
        # # Opcion 3
        if TES_min < 400.0 and irr < 600:
            return '5'  # muy frío y poca irradiancia → auxiliar
    
        # --- TES frío moderado: decide entre 6 y 4 por irradiancia ---
        if TES_bot < 430 and TES_top < 470:
        # if TES_top < 470:
        # if TES_bot < 430:
            return '6' if irr > 600 else '4'
    
        # --- Irradiancia alta (700+): decidir 1 vs 2 con viabilidad de carga ---
        if irr > 700:
            charge_viable = True
            if T_ptc_out is not None:
                charge_viable = (T_ptc_out > TES_top)  # sin margen adicional
            if charge_viable and (TES_bot < t_proc_set + 30.0):
                return '1'
            else:
                return '2'
    

        # --- Poca irradiancia: descarga si el top supera la consigna, si no standby ---
        dhx_viable   = (TES_top > (t_proc_set + 25.0))
        ph_ok       = ((TES_top - 20.0) <= t_ph_out)
        if dhx_viable and ph_ok:
            return '3'
        else:
            return '4'

        # --- Irradiancia media (600–700): tu criterio original ---
        if irr > 600:
            return '2'
    

    def get_system_mode(self, irr):
        if self.system_mode == 'Full':
            new_TESmode = self.get_mode(irr, self.solar_system.tes.profile, self.TES_lay)
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
        self.system_mode == 'Full'
        self.TES_lay = 'Charge'
        self.irr = irr
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        print(f"Mode: {mode}")
        self.solve_network_steady(mode=mode)
        self.solar_system.network.print_results()
        
    def initialize_modes(self):
        # Mode 1
        self.system_mode == 'Full'
        self.TES_lay = 'Charge'
        self.irr = 1000
        self.tes_params['Initial temperature'] = 470
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        # Mode 2
        self.irr = 1000
        self.tes_params['Initial temperature'] = 520
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        # Mode 3
        self.irr = 0
        self.tes_params['Initial temperature'] = 510
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        # Mode 4
        self.irr = 0
        self.tes_params['Initial temperature'] = 450
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        
        # # Mode 5
        self.irr = 100
        self.tes_params['Initial temperature'] = 399
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()

        # Mode 6
        self.irr = 1000
        self.tes_params['Initial temperature'] = 410
        self.solar_system = SolarThermalSystem(rows=1, 
                                    tes_params=self.tes_params,
                                    component_params = self.component_params,
                                    conexion_params = self.conexion_params,
                                    HTF=self.HTF 
                                    )
        self.solve_network_steady()
        
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
            T_tes_out = system.conn_13.T.val
            if T_tes_out > self.conexion_params['5_T']:
                check = False
                mode = '2'
                #print('T TES out: ', T_tes_out)
            else:
                check = True
                mode = '1'
        elif TESmode == '3':   
            T_tes_out = system.conn_15.T.val
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
        Devuelve:
          ok: bool                -> True si alguna corrida converge
          attempts: list[dict]    -> bitácora por intento
          last_err: str|None      -> mensaje del último error capturado (si hubo)
        """
        attempts = []
        last_err = None
        for k in range(1, tries + 1):
            if k == 2:
                # Sólo T0 por defecto, coherente con T_range usado al crear la red.
                # Si quieres abrir m0/p0/h0, pásame rangos y lo habilitamos aquí.
                self._randomize_conn_guesses(system, TESmode, seed=None,
                                             T_bounds=(400.0, 500.0),  # ya usado en tu network
                                             include=('T0',))
            try:
                # Desactiva trazas verbosas si corresponde
                try:
                    system.network.set_attr(iterinfo=False)
                except Exception:
                    pass
    
                system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode)
                conv = bool(getattr(system.network, 'converged', False))
                attempts.append({'mode': TESmode, 'try_idx': k, 'tespy_converged': conv})
                if conv:
                    return True, attempts, None
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                attempts.append({'mode': TESmode, 'try_idx': k, 'tespy_converged': False, 'error': str(e)})
                
        # --- Helper: randomizar guesses de conexiones del modo activo -------------
    def _randomize_conn_guesses(self, system, TESmode, *, seed=None,
                                T_bounds=None, include=('T0',)):
        """
        Randomiza los 'initial guesses' de las conexiones disponibles en el modo
        actual. Por defecto sólo T0, usando un rango que ya existe en tu red.
        - No toca las condiciones de borde (T/p/m/h 'fijadas' como valores).
        - Devuelve la lista de conexiones en las que se aplicó randomización.

        Params
        ------
        system    : instancia con la red y las conns del modo actual
        TESmode   : str, modo (para logging)
        seed      : int|None, semilla reproducible si se desea
        T_bounds  : (float, float)|None, rango para T0 (°C). Si None, se usa
                    (300, 600) consistente con tu `network.set_attr(T_range=...)`.
        include   : tuple, campos a randomizar ('T0','m0','p0','h0'). Por ahora
                    dejamos sólo ('T0',) para no introducir supuestos nuevos.

        Nota: si luego quieres abrir m0/p0/h0, pásame rangos y lo habilitamos.
        """
        rng = np.random.default_rng(seed)
        if T_bounds is None:
            # coherente con tu construcción de la red (T_range=[300, 600])
            T_bounds = (300.0, 600.0)

        randomized = []
        # Iteramos atributos tipo conn_* del objeto 'system' (modo actual)
        for name in dir(system):
            if not name.startswith('conn_'):
                continue
            conn = getattr(system, name, None)
            # Debe tener set_attr para aceptar T0/m0/p0/h0
            if conn is None or not hasattr(conn, 'set_attr'):
                continue
            try:
                # Temperatura inicial
                if 'T0' in include:
                    T0 = float(rng.uniform(*T_bounds))
                    conn.set_attr(T0=T0)
                # Si en el futuro activamos m0/p0/h0, irían acá con sus bounds
                # (sin tocar valores 'fijados' como condiciones de borde).
                randomized.append(name)
            except Exception:
                # Silencioso: si alguna conexión no acepta, seguimos con el resto
                continue

        # Logging simple (opcional)
        print(f"[attempt_to_solve] Randomized initial guesses ({include}) en modo {TESmode}:",
              f"{len(randomized)} conns")

        return randomized

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
        # 2) Initialize the TES_HX source temperature from top/bottom
        if TESmode in ['1','5','6']:
            T_in_bot = system.tes.profile[-1]  # top node for charging
            system.conn_13.set_attr(T=T_in_bot)
        elif TESmode in ['3']: # discharging: use bottom node to extract heat from the hottest (bottom) region
            T_in_top = system.tes.profile[-1]
            system.conn_15.set_attr(T=T_in_top)
            
        mode_3_fail = False
        
        old_profile = np.array(system.tes.profile).copy()
        # 3) Iteration loop
        for iteration in range(max_iter):
            # a) Solve the main TESPy network
            if mode == 'offdesign':
                system.network.set_attr(iterinfo=False)
            self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
            # --- logging del intento de solve ---
            try:
                iter_info['attempts'].append({
                    'mode': TESmode,
                    'tespy_converged': bool(getattr(system.network, 'converged', False)),
                    'iter_idx': iteration + 1,
                })
            except Exception:
                pass
            # Revisar convergencia en HX de descarga
            if TESmode in ['3']:
                Q_hx = system.discharge_tes_hx.Q.val
                #print('mode 3 ttd_min ', ttd_min)
                if 0 < Q_hx:
                    mode_3_fail = True
                    iter_info['attempts'].append({
                    'mode': TESmode,
                    'tespy_converged': bool(getattr(system.network, 'converged', False)),
                    'iter_idx': iteration + 1,
                    'ttd_min_if_mode3': Q_hx,
                    })

            if not system.network.converged:
                if TESmode in ['1','6']:
                    print('System did not converge\n',TESmode, ' passing to 2')
                    TESmode = '2'
                    self.current_mode = TESmode
                    system.set_operation_mode(TESmode=TESmode, 
                                              current_irr=self.current_irr,
                                              profile=old_profile,
                                              prev_TES_lay = self.TES_lay)
                    system.network.set_attr(iterinfo=False)
                    self.attempt_to_solve(system, mode, design_path, TESmode, tries=5)
                elif TESmode in ['3','5']:
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
                print('Mode 3 fail in second law')
                TESmode = '4'
                self.current_mode = TESmode
            
                system.set_operation_mode(TESmode=TESmode, 
                                          current_irr=self.current_irr,
                                          profile=old_profile,
                                          prev_TES_lay = self.TES_lay)
                system.network.set_attr(iterinfo=False)
                system.solve_network(mode=mode, design_path=design_path, TESmode=TESmode)
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
                T_tes_in = system.conn_14.T.val
                m_tes_in = system.conn_14.m.val_SI
            elif TESmode in ['3']:  # discharging: use bottom node to extract heat from the hottest (bottom) region
                T_tes_in = system.conn_16.T.val
                m_tes_in = system.conn_16.m.val_SI
                
            if m_tes_in < 0.01:
                self.mode_alert == True
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
                system.conn_13.set_attr(T=T_tes_out)
                self.TES_lay = 'Charge'
            elif TESmode in ['3']:
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
    def solve_network_steady(self, mode='design', TESmode='2'):
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
        Señales del paso actual medidas directamente en los componentes:
          Energías por paso (kJ): to_tes, tes_to_proc, solar_to_proc, aux_to_proc, ptc_total
          Temperaturas [°C]:      T_ptc_out, T_tes_top, T_tes_bottom
          Flujos másicos [kg/s]:  mdot_ptc, mdot_tes_charge, mdot_tes_discharge, mdot_process
    
        Correcciones:
        - Q de HX se toma como |Q| (signo en TESPy depende del lado).
        - Puertas lógicas por estado del TES para cargar/descargar (anula el opuesto).
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
            for a in ('Q',):
                qa = getattr(comp, a, None)
                if qa is None:
                    continue
                v = getattr(qa, 'val', None)
                if v is None:
                    try:
                        v = float(qa)
                    except Exception:
                        v = None
                if v is not None and np.isfinite(v):
                    return abs(float(v))  # <<< valor absoluto: evita falsos 0 por signo
            return 0.0
    
        def _conn_T(comp):
            """Temperatura de salida si existe (°C)."""
            try:
                if comp is None:
                    return np.nan
                if getattr(comp, 'outl', None) and len(comp.outl) > 0:
                    v = getattr(getattr(comp.outl[0], 'T', None), 'val', None)
                    if v is None:
                        v = getattr(comp.outl[0], 'T', None)
                    return float(v) if v is not None else np.nan
            except Exception:
                pass
            return np.nan
    
        def _mdot_kg_s(comp):
            """Flujo másico de salida si existe (kg/s)."""
            try:
                if comp is None:
                    return np.nan
                if getattr(comp, 'outl', None) and len(comp.outl) > 0:
                    v = getattr(getattr(comp.outl[0], 'm', None), 'val', None)
                    if v is None:
                        v = getattr(comp.outl[0], 'm', None)
                    return float(v) if v is not None else np.nan
            except Exception:
                pass
            return np.nan
    
        # ---------- componentes ----------
        ptc     = _get_comp(system, 'ptc_field')
        hx_chg  = _get_comp(system, 'charge_tes_hx', 'charge_hx')
        hx_dch  = _get_comp(system, 'discharge_tes_hx', 'discharge_hx')
        hx_proc = _get_comp(system, 'process_hx')
        hx_aux  = _get_comp(system, 'preheater_hx')
    
        # ---------- tiempo de paso ----------
        dt_s = float(getattr(system, 'TES_dt', 3600.0))
    
        # ---------- potencias en kW (valor absoluto) ----------
        q_ptc_kw = _get_Q_kw(ptc)
        q_chg_kw = _get_Q_kw(hx_chg)
        q_dch_kw = _get_Q_kw(hx_dch)
        q_aux_kw = _get_Q_kw(hx_aux)
    
        hx_chg  = _get_comp(system, 'charge_tes_hx', 'charge_hx', 'tes_hx_ch')  # <<< añadido 'tes_hx_ch'
        hx_dch  = _get_comp(system, 'discharge_tes_hx', 'discharge_hx')
        
            
        # anula el opuesto (evita potencias falsas por signo/ruido)
        if mode in ['1','5','6']:
            q_dch_kw = 0.0
        elif mode in ['3']:
            q_chg_kw = 0.0
            q_ptc_kw = 0.0
        else:
            # standby / otros estados
            q_chg_kw = 0.0
            q_dch_kw = 0.0
            q_ptc_kw = 0.0

    
        # ---------- energías por paso (kJ) ----------
        to_tes_kJ        = q_chg_kw * dt_s
        tes_to_proc_kJ   = q_dch_kw * dt_s
        ptc_total_kJ     = q_ptc_kw * dt_s
    
        # Auxiliar → proceso solo cuando no hay solar directo (misma regla de antes)
        aux_to_proc_kJ   = (0.0 if mode in ['1','2'] else q_aux_kw) * dt_s
    
        # Solar → proceso directo (medición compuesta mínima), sin balances detallados:
        # PTC total menos lo que se desvía a cargar el TES.
        solar_to_proc_kJ = max(ptc_total_kJ - to_tes_kJ, 0.0)
    
        # ---------- temperaturas ----------
        T_ptc_out   = _conn_T(ptc)
        if mode not in ['1','6']:
            T_ptc_out = np.nan
        # perfil TES para top/bottom igual que en tus plots
        T_tes_top = np.nan
        T_tes_bot = np.nan
        try:
            prof_raw = None
            if hasattr(self, 'TES_profiles') and self.TES_profiles is not None:
                pr = self.TES_profiles
                arr = np.array(pr[0] if isinstance(pr, (list, tuple)) and len(pr) > 0 else pr).ravel()
                prof_raw = arr if arr.size > 0 else None
            elif hasattr(system, 'tes') and hasattr(system.tes, 'profile'):
                arr = np.array(system.tes.profile).ravel()
                prof_raw = arr if arr.size > 0 else None
            if prof_raw is not None:
                prof = prof_raw[::-1] if mode in ['1','5','6'] else prof_raw
                T_tes_bot = float(prof[0])
                T_tes_top = float(prof[-1])
        except Exception:
            pass
    
        # ---------- flujos másicos ----------
        mdot_ptc          = _mdot_kg_s(ptc)
        mdot_tes_charge   = _mdot_kg_s(hx_chg)
        mdot_tes_discharge= _mdot_kg_s(hx_dch)
        mdot_process      = _mdot_kg_s(hx_proc)

        # puertas lógicas también para ṁ (coherente con potencias)
        if mode in ['1','5','6']:
            mdot_tes_discharge = 0.0
        elif mode in ['3']:
            mdot_tes_charge = 0.0
            mdot_ptc = 0.0
        else:
            mdot_tes_charge    = 0.0
            mdot_tes_discharge = 0.0
            mdot_ptc           = 0.0

        net_conv = bool(getattr(system.network, 'converged', False))
        return dict(
            # energías
            to_tes_kJ=to_tes_kJ,
            tes_to_proc_kJ=tes_to_proc_kJ,
            solar_to_proc_kJ=solar_to_proc_kJ,
            aux_to_proc_kJ=aux_to_proc_kJ,
            ptc_total_kJ=ptc_total_kJ,
            # temperaturas
            T_ptc_out=T_ptc_out,
            T_tes_top=T_tes_top,
            T_tes_bottom=T_tes_bot,
            # flujos másicos
            mdot_ptc_kg_s=mdot_ptc,
            mdot_tes_charge_kg_s=mdot_tes_charge,
            mdot_tes_discharge_kg_s=mdot_tes_discharge,
            mdot_process_kg_s=mdot_process,
            network_converged=net_conv,
        )
    


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
                                    HTF=self.HTF 
                                    )
        self.solar_system.create_network4()
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

            self.solar_system.set_operation_mode(TESmode=new_TESmode, 
                                                 current_irr=current_irr,
                                                 profile=self.solar_system.tes.profile,
                                                 prev_TES_lay = self.TES_lay,
                                                 mode='offdesign')
            self.current_mode = new_TESmode

            if self.current_mode in ['1','2','6']:
                self.solar_system.ptc_field.set_attr(E=current_irr, Tamb=current_Tamb)

            design_path = f'base_design_{self.current_mode}'
            
            # For each time step, do the same iteration
            iter_info = self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                       TESmode=self.current_mode, design_path=design_path,
                                       Tamb=current_Tamb) 
            if self.mode_alert:
                self.current_mode == '4'
                self.solar_system.set_operation_mode(TESmode=new_TESmode, 
                                                     current_irr=current_irr,
                                                     profile=self.solar_system.tes.profile,
                                                     prev_TES_lay = self.TES_lay)
                self._iterate_tes_coupling(mode='offdesign', system =self.solar_system,
                                               TESmode=self.current_mode, design_path=design_path,
                                               Tamb=current_Tamb) 
                        #print(new_TESmode)
            signals = self._collect_step_signals(self.solar_system, self.current_mode)
            tes_soc_kWh = self.solar_system.tes.calculate_SoC(self.solar_system.tes.profile)
            Q_ph_kJ = 0
            # After final iteration for this time-step:
            if self.current_mode in ['1','6']:
                Q_ptc_kJ   = self.solar_system.ptc_field.Q.val * 3600.0
                #pump_power = self.solar_system.pump.P.val + self.solar_system.pump2.P.val + self.solar_system.comp.P.val
            elif self.current_mode in ['2']:
                Q_ptc_kJ   = self.solar_system.ptc_field.Q.val * 3600.0
                #pump_power = self.solar_system.pump.P.val 
            elif self.current_mode in ['3']:
                Q_ptc_kJ   = 0
                #pump_power = self.solar_system.pump.P.val + self.solar_system.comp.P.val
            elif self.current_mode in ['4']:
                Q_ptc_kJ   = 0
                #pump_power = self.solar_system.pump.P.val 
            elif self.current_mode in ['5']:
                Q_ptc_kJ = 0
                Q_ph_kJ = self.solar_system.tes_hx_ch.Q.val * 3600.0
            else:
                Q_ptc_kJ   = self.solar_system.ptc_field.Q.val * 3600.0
                #pump_power = self.solar_system.pump.P.val + self.solar_system.pump2.P.val
            Q_ph_kJ += self.solar_system.preheater_hx.Q.val * 3600.0
            #if Q_ph_kJ > 0:
            #    Q_ph_kJ = self.solar_system.preheater_hx.Q.val * 3600.0
            #else:
            #    Q_ph_kJ = 0
            pump_power = 0
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
                # --- energías directas por paso ---
                'to_tes_kJ':          signals['to_tes_kJ'],
                'tes_to_proc_kJ':     signals['tes_to_proc_kJ'],
                'solar_to_proc_kJ':   signals['solar_to_proc_kJ'],
                'aux_to_proc_kJ':     signals['aux_to_proc_kJ'],
                'ptc_total_kJ':       signals['ptc_total_kJ'],
                
                # --- temperaturas relevantes ---
                'T_ptc_out':          signals['T_ptc_out'],
                'T_tes_top':          signals['T_tes_top'],
                'T_tes_bottom':       signals['T_tes_bottom'],
                
                # --- flujos másicos relevantes ---
                'mdot_ptc_kg_s':          signals['mdot_ptc_kg_s'],
                'mdot_tes_charge_kg_s':   signals['mdot_tes_charge_kg_s'],
                'mdot_tes_discharge_kg_s':signals['mdot_tes_discharge_kg_s'],
                'mdot_process_kg_s':      signals['mdot_process_kg_s'],
                
                # --- SoC (energía, NO acumulado) ---
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
        
        # Optional "solar plant factor" if user provided a process demand
        spf = total_ptc_energy_kJ / (total_ptc_energy_kJ + total_ph_energy_kJ + total_pump_energy_kJ*1000) # fraction

        # Print performance summary line by line
        print("\n=== Performance Summary ===")
        print(f"Total PTC Energy:       {ptc_energy_GWh:6.2f} GWh")
        print(f"Total Preheater Energy:{ph_energy_GWh:6.2f} GWh")
        print(f"Total Pump Energy:      {pump_energy_MWh:6.2f} MWh")
        if spf is not None:
            print(f"Solar Plant Factor:     {spf * 100:6.2f}%")
        print("================================\n")

        return spf
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
        
        
    def plot_TES_profile_colormap(self, df_results):
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
    
        X, Y = np.meshgrid(x_vals, y)
        fig, ax = plt.subplots(figsize=(8, 5))
        cs = ax.pcolormesh(X, Y, Z, cmap='coolwarm', shading='auto')
        cbar = plt.colorbar(cs, ax=ax); cbar.set_label('Temperature [°C]', rotation=90)
        ax.set_ylabel('Normalized TES Height [-]')
        ax.set_xlabel(x_label)
        ax.set_title('TES Temperature Distribution vs. Time')
        plt.tight_layout(); plt.show()

        
    def plot_annual_cumulative_energy(self, df_results, out_unit="MWh",
                                      title="Energía acumulada anual (con SoC semanal)",
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
    
        # Acumulados de energía 
        cum = df[['solar_to_proc_kJ','tes_to_proc_kJ','to_tes_kJ','aux_to_proc_kJ']].cumsum() * convE
    
        # --- SoC: ya está en energía (kWh). NO acumulado. Alineado temporalmente.
        has_soc = 'tes_soc_kWh' in df.columns
        soc_week = None
        if has_soc:
            kWh_to = {"Wh": 1e3, "kWh": 1.0, "MWh": 1e-3, "GWh": 1e-6}
            soc = df['tes_soc_kWh'] * kWh_to[out_unit]               # ej: 18823 kWh -> 18.823 MWh
            # Promedio móvil de 7 días CENTRADO, mismo índice (evita desfase)
            soc_week = soc.rolling(window='7D', min_periods=1, center=True).mean()
    
        # --- Escalamiento por órdenes (misma lógica para todas las series, incluido SoC si existe)
        eps = 1e-12
        series = {
            'Solar → Proceso':      cum['solar_to_proc_kJ'],
            'TES → Proceso':        cum['tes_to_proc_kJ'],
            '→ TES (carga)':        cum['to_tes_kJ'],
            'Auxiliar → Proceso':   cum['aux_to_proc_kJ'],
        }
        if has_soc and soc_week is not None and not soc_week.dropna().empty:
            series['SoC TES semanal'] = soc_week
    
        # máximo de referencia
        nonzero_max = []
        for s in series.values():
            try:
                mx = float(np.nanmax(s.values))
            except Exception:
                mx = float(np.nanmax(np.asarray(s)))
            if mx > eps:
                nonzero_max.append(mx)
        ref = max(nonzero_max) if nonzero_max else 1.0
    
        def scale_for(xmax):
            if xmax <= eps:
                return 1.0
            k = int(np.round(np.log10(ref / xmax)))     # cuántos órdenes hay que "subir"
            k = int(np.clip(k, -6, 6))                  # evita escalas extremas
            return 10.0**k
    
        scales = {}
        for name, s in series.items():
            try:
                xmax = float(np.nanmax(s.values))
            except Exception:
                xmax = float(np.nanmax(np.asarray(s)))
            scales[name] = scale_for(xmax)
    
        def label_scaled(name):
            s = scales[name]
            if abs(s - 1.0) < 1e-12:
                return name
            k = int(np.round(np.log10(s)))
            return f"{name} (×10^{k})"
    
        # --- Plot
        fig, ax = plt.subplots(figsize=(10, 4.6))
        ax.plot(cum.index, cum['solar_to_proc_kJ'] * scales['Solar → Proceso'],      label=label_scaled('Solar → Proceso'))
        ax.plot(cum.index, cum['tes_to_proc_kJ']   * scales['TES → Proceso'],        label=label_scaled('TES → Proceso'))
        ax.plot(cum.index, cum['to_tes_kJ']       * scales['→ TES (carga)'],         label=label_scaled('→ TES (carga)'))
        ax.plot(cum.index, cum['aux_to_proc_kJ']  * scales['Auxiliar → Proceso'],    label=label_scaled('Auxiliar → Proceso'))
    
        if has_soc and soc_week is not None and not soc_week.dropna().empty:
            ax.plot(soc_week.index, soc_week.values * scales['SoC TES semanal'], '--', color='k',
                    label=label_scaled('SoC TES semanal'))
    
        ax.set_title(title)
        ax.set_ylabel(f"Energía [{out_unit}] (con escalamiento por serie)")
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
        dfw = df.loc[iso.week == week].reset_index(drop=True)  # <-- índice nuevo 0..N-1
    
        if dfw.empty:
            raise ValueError(f"No hay datos para la semana ISO {week}. Semanas disponibles: {weeks_avail}")
    
        return self.plot_TES_profile_colormap(dfw)

    def plot_daily_powers_temps_massflows(self, df_results, day,
                                          power_unit="kW", soc_unit="MWh",
                                          title_prefix="Perfil diario",
                                          savepath=None):
        """
        Tres paneles para un día:
          (1) Potencias instantáneas (desde energías por paso) + SoC
          (2) Temperaturas (PTC out, TES top, TES bottom)
          (3) Flujos másicos (PTC, TES carga/descarga, Proceso)
    
        Mejoras:
        - Potencias convertidas a la unidad pedida y escaladas por serie (×10^k en leyenda).
        - ṁ TES con "gating" por TES_layout (carga/descarga → 0 cuando no corresponde).
        """
    
        df_results = self._ensure_df(df_results)
        if 'time' not in df_results.columns:
            raise ValueError("df_results debe contener la columna 'time'.")
    
        # -------- Selección del día --------
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
            raise ValueError(f"No hay datos para {start.date()}. Algunos días disponibles: {avail[:8]}")
    
        # -------- Gating de ṁ TES por layout (carga/descarga) --------
        if 'TES_layout' in day_df.columns:
            layout = day_df['TES_layout'].astype(str).str.lower()
            if 'mdot_tes_charge_kg_s' in day_df.columns:
                day_df.loc[layout != 'charge', 'mdot_tes_charge_kg_s'] = 0.0
            if 'mdot_tes_discharge_kg_s' in day_df.columns:
                day_df.loc[layout != 'discharge', 'mdot_tes_discharge_kg_s'] = 0.0
    
        # ===== (1) POTENCIAS + SoC =====
        # P_base[kW] = E[kJ] / Δt[s]
        e_cols = ['solar_to_proc_kJ','tes_to_proc_kJ','to_tes_kJ','aux_to_proc_kJ']
        names_p = {
            'solar_to_proc_kJ': 'Solar → Proceso',
            'tes_to_proc_kJ'  : 'TES → Proceso',
            'to_tes_kJ'       : 'Solar → TES',
            'aux_to_proc_kJ'  : 'Auxiliar → Proceso',
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
        

        # Conversión a unidad solicitada
        pconv = {'W': 1e3, 'kW': 1.0, 'MW': 1e-3, 'GW': 1e-6}
        if power_unit not in pconv:
            raise ValueError("power_unit debe ser 'W', 'kW', 'MW' o 'GW'")
        P = {lbl: s * pconv[power_unit] for lbl, s in P_kw.items()}  
        
        # Escalamiento por órdenes de magnitud (por serie)
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
            return f"{name} (×10^{k})"
    
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
            'T_ptc_out'   : 'Salida campo solar',
            'T_tes_top'   : 'TES – parte superior',
            'T_tes_bottom': 'TES – parte inferior',
        }
        T = {names_t[c]: day_df[c] for c in t_cols if c in day_df.columns}

        mode_cols = ['TESmode']
        names_mode = {
            'TESmode'   : 'Operation mode',
        }
        modes = {names_mode[c]: day_df[c] for c in mode_cols if c in day_df.columns}
    
        # ===== (3) FLUJOS MÁSICOS =====
        m_cols = ['mdot_ptc_kg_s','mdot_tes_charge_kg_s','mdot_tes_discharge_kg_s']
        names_m = {
            'mdot_ptc_kg_s'          : 'campo solar',
            'mdot_tes_charge_kg_s'   : 'TES (carga)',
            'mdot_tes_discharge_kg_s': 'TES (descarga)',
        }
        M = {names_m[c]: day_df[c] for c in m_cols if c in day_df.columns}
    
        # ====== FIGURA: 3 paneles ======
        fig, axes = plt.subplots(nrows=3, ncols=1, figsize=(11, 9), sharex=True)
    
        # (1) Potencias
        axP = axes[0]
        for lbl, s in P.items():
            axP.plot(s.index, (s.values * scales[lbl]), label=label_scaled(lbl))
        axP.set_title(f"{title_prefix} — {start.date()} (Potencias + SoC)")
        axP.set_ylabel(f"Potencia [{power_unit}]")
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
            axT.set_title(f"{title_prefix} — {start.date()} (Temperaturas)")
            axT.set_ylabel("Temperatura [°C]")
            axT2.set_ylabel("Operation mode")
            axT2.set_yticks([1,2,3,4,5,6])
            axT.grid(True, alpha=0.3)
            axT.legend(loc='best')

        else:
            axT.set_title(f"{title_prefix} — {start.date()} (Temperaturas)")
            axT.text(0.5, 0.5, "No hay columnas de temperatura en df_results",
                     ha='center', va='center', transform=axT.transAxes)

        # (3) Flujos másicos
        axM = axes[2]
        if M:
            for lbl, s in M.items():
                axM.plot(s.index, s.values, label=lbl)
            axM.set_title(f"{title_prefix} — {start.date()} (Flujos másicos)")
            axM.set_ylabel("Flujo másico [kg/s]")
            axM.grid(True, alpha=0.3)
            axM.legend(loc='best')
        else:
            axM.set_title(f"{title_prefix} — {start.date()} (Flujos másicos)")
            axM.text(0.5, 0.5, "No hay columnas de flujo másico en df_results",
                     ha='center', va='center', transform=axM.transAxes)
    
        # Eje X común a horas
        axes[-1].set_xlabel("Hora")
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
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return [self._jsonable(x) for x in obj.tolist()]
        if isinstance(obj, (list, tuple, set)):
            return [self._jsonable(x) for x in obj]
        if isinstance(obj, (pd.Timestamp, dt.datetime, dt.date, dt.time)):
            try:
                return obj.isoformat()
            except Exception:
                return str(obj)
        if isinstance(obj, dict):
            return {str(k): self._jsonable(v) for k, v in obj.items()}
        try:
            json.dumps(obj)
            return obj
        except Exception:
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
        - 1ª línea: __meta__,{JSON con parámetros y condiciones de la simulación}
        - Resto: df_results (una fila por paso temporal)
    
        Prioridad de metadatos (de menor a mayor):
          solver → params → (tes_params, component_params, conexion_params) → sim_args → extra_meta
    
        Cualquier dict que pases explícitamente (tes_params/component_params/conexion_params)
        sobreescribe lo que se haya obtenido del solver o de `params`.
        """
    
        # --- Construcción del META ---
        meta = {}
    
        # 1) Intento desde solver (si viene)
        if solver is not None:
            meta['system_mode']      = self._jsonable(getattr(solver, 'system_mode', None))
            meta['HTF']              = self._jsonable(getattr(solver, 'HTF', None))
            meta['tes_params']       = self._jsonable(deepcopy(getattr(solver, 'tes_params', {})))
            meta['component_params'] = self._jsonable(deepcopy(getattr(solver, 'component_params', {})))
            meta['conexion_params']  = self._jsonable(deepcopy(getattr(solver, 'conexion_params', {})))
    
        # 2) Mezcla con `params` (si viene) — útil para empaquetar varios en un solo dict
        if params is not None:
            for k, v in params.items():
                meta[k] = self._jsonable(v)
    
        # 3) Sobrescritura explícita (PRIORIDAD): los tres dicts pedidos
        if tes_params is not None:
            meta['tes_params'] = self._jsonable(deepcopy(tes_params))
        if component_params is not None:
            meta['component_params'] = self._jsonable(deepcopy(component_params))
        if conexion_params is not None:
            meta['conexion_params'] = self._jsonable(deepcopy(conexion_params))
    
        # 4) Argumentos de simulación y extras (quedan al mismo nivel)
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
    
        - Parsea la 1ª línea '__meta__,{...}' como JSON
        - Lee el resto con pandas
        - Convierte 'time' a datetime (si existe)
        - Intenta parsear columnas con JSON (p. ej., TES_profiles)
        """
    
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"No existe el archivo: {filepath}")
    
        # Leer primera línea
        with open(filepath, 'r', encoding='utf-8') as f:
            first = f.readline().rstrip('\n')
        meta = {}
        prefix = '__meta__,'
        if first.startswith(prefix):
            try:
                meta = json.loads(first[len(prefix):])
            except Exception:
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
                    except Exception:
                        pass
    
        return df, meta
