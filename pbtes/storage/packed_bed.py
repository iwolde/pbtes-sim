import numpy as np
import CoolProp.CoolProp as cp
from scipy.optimize import brentq
from scipy.interpolate import interp1d
from copy import deepcopy


class ThermalEnergyStorage:
    """
    Manages the thermal energy storage with capability to store, release, or maintain energy,
    simulating temperature profiles and managing energy state.
    """

    def __init__(self, tes_params, name, dt):
        """
        Initializes the thermal energy storage unit.

        Parameters
        ----------
        dt : Int
            Time step.
        tes_params : Dict
            TES parameters.
        name : Str
            TES name.
        """
        self.dt = dt  # seconds
        self.name = name
        self.state = 'charge'  # default state
        self.inlet = 'top'
        self.outlet = 'bottom'
        self.valve_state = 'off'  # Valve controlling the TES flow

        self.initial_temperature = tes_params['Initial temperature']
        self.HT = tes_params['Tank length']
        self.Dint = tes_params['Tank diameter']
        self.dp = tes_params['Particle diameter']
        self.e = tes_params['Void fraction']
        self.rho_s = tes_params['Solid density']
        self.cp_s = tes_params['Solid specific heat']
        self.k_s = tes_params['Solid conductivity']
        self.wst = tes_params['Wall thickness']
        self.kst = tes_params['Tank conductivity']
        self.wins = tes_params['Insulation thickness']
        self.kins = tes_params['Insulation conductivity']
        self.HTF = tes_params['HTF']
        self.AT = 0.25 * self.Dint**2 * np.pi  # m2 - cross-sectional area
        self.Aphi = 0.25 * (25.4e-3*2)**2* np.pi  # m2 - discharge tube area

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
        # Fluid properties at average temperature
        self.rho_f = cp.PropsSI('D', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.cp_f = cp.PropsSI('C', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.k_f = cp.PropsSI('L', 'T', Tav, 'P', self.HTF_P, self.HTF)
        self.mu_f = cp.PropsSI('V', 'T', Tav, 'P', self.HTF_P, self.HTF)

        self.rho_out = cp.PropsSI('D', 'T', self.tout+273.15, 'P', self.HTF_P, self.HTF)

    def eq_params(self, T_in, mass_flow):
        """
        Calculate equation parameters for the temperature profile.

        Parameters
        ----------
        T_in : Float
            Inlet Temperature.
        mass_flow : Float
            Inlet mass flow [kg/s].
        """
        self.t_in = T_in
        self.mflow = mass_flow  # kg/s

        self.air_params()

        # Mass flow per unit area
        G = self.mflow / self.AT 
        # Calculate alpha and k_eff
        Re = G*self.dp/self.mu_f  # Reynolds
        Pr = self.mu_f * self.cp_f / self.k_f  # Prandtl
        ff = 6*(1-self.e)/self.dp  # m - solid-fluid shape factor
        rho_cp_line = (self.e * self.rho_f * self.cp_f + (1-self.e) * self.rho_s * self.cp_s)  # equivalent capacitance
        self.kappa = self.e * (self.rho_f * self.cp_f) / rho_cp_line  # kappa factor
        u_in = G / (self.rho_f)  # m/s - interstitial velocity
        hv = ff * (self.k_f/self.dp) * 1.32 * Re**0.59 * Pr**(1/3)  # W/m3 K - volumetric heat transfer coeff
        k_line = (self.e *self.k_f + (1-self.e)*self.k_s)  # average conductivity
        k_eff = k_line + ((1-self.e) * (self.rho_s*self.cp_s) * (G*self.cp_f/rho_cp_line))**2/hv  # effective conductivity
        alpha = k_eff / rho_cp_line  # alpha
        self.Pe = u_in * self.HT / alpha  # Péclet number
        self.a = self.kappa * self.Pe / 2
        if self.a > 15.0:
            self.a = 15.0
            self.Pe = self.a * 2 / self.kappa
        elif self.a < -15.0:
            self.a = -15.0
            self.Pe = self.a * 2 / self.kappa

        # Internal resistance
        hint = (self.k_f/self.dp) * (0.203 * Re**(1/3) * Pr**(1/3) + 0.22 * Re**0.8 * Pr**0.4)
        Rint = 1/hint
        # Heat transfer coefficient
        hw = 1/Rint
        # Stanton
        self.beta = 4/self.Dint
        self.St = 0.75*hw*self.beta*self.HT/(rho_cp_line*u_in)
        self.b = -(self.St + self.a**2/self.Pe)

        self.tau = u_in*self.dt/self.HT

    def _eq(self, ev, a):
        """Transcendental equation for eigenvalue search."""
        eq1 = ev / a
        eq2 = np.tan(ev)
        eq = eq1 + eq2
        return eq

    def solve_eq(self, Nroots, a):
        """
        Root-finding algorithm.

        Parameters
        ----------
        Nroots : Roots number.
        a : Parameter a.

        Returns
        -------
        rts : Roots array.
        """
        rts = np.zeros(Nroots)
        margin = 1e-5
        left = 0
        right = np.pi / (2)
        _ = brentq(self._eq, left, right - margin, args=(a))
        for i in range(1, Nroots+1):
            left = (2*i - 1)*np.pi/(2)
            right = (2*i + 1)*np.pi/(2)
            rts[i-1] = brentq(self._eq, left + margin, right - margin, args=(a))
        return rts

    def calc_solution(self):
        """Evaluate the solution given current timestep conditions."""
        theta = (self.t_in-self.t_min)/(self.t_max-self.t_min)
        init = (self.init-self.t_min)/(self.t_max-self.t_min)
        # Stationary solution
        k1 = np.longdouble(0.5 * (self.kappa * self.Pe - np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        k2 = np.longdouble(0.5 * (self.kappa * self.Pe + np.sqrt(self.kappa**2 * self.Pe**2 + 4 * self.Pe * self.St)))
        C2 = theta * k1 * np.exp(k1) / (k1*np.exp(k1) - k2*np.exp(k2))
        C1 = theta - C2
        Mx = lambda x : C1*np.exp(k1*x) + C2*np.exp(k2*x)

        # Transient solution
        lbd = self.solve_eq(200, self.a)
        fn = np.sqrt(2) * np.sqrt((lbd**2 + self.a**2)/(lbd**2 + self.a**2 + self.a))
        Knx = lambda x : fn[:, None] * np.sin(lbd[:, None]*x)
        xint = np.linspace(0, 1, 200)
        t0_int = interp1d(self.xev, init, bounds_error=False, fill_value='extrapolate')(xint)
        phi0 = (t0_int - Mx(xint)) / np.exp(self.a*xint)
        phi0n = np.trapz(Knx(xint)*phi0, x=xint, axis=1)
        phin = phi0n[:, None] * np.exp(-lbd[:, None]**2 * self.tau / self.Pe)
        Nxt = np.exp(self.a*self.xev[:, None] + self.b*self.tau) * (np.sum(phin * Knx(self.xev), axis=0)[:, None])

        sol = Mx(self.xev)[:, None] + Nxt

        return sol

    def update_temperature_profile(self, T_in, mass_flow, initial_profile):
        """
        Updates the temperature profile of the TES for the given time step.

        Parameters
        ----------
        T_in : Float
            Inlet Temperature [C].
        mass_flow : Float
            Inlet mass flow [kg/s].
        initial_profile : array
            Previous temperature profile.

        Returns
        -------
        profile : array
            Updated temperature profile.
        """
        initial_profile = np.clip(np.array(initial_profile), 300.1, 600.0)
        T_in = max(T_in, 300.1)

        self.init = initial_profile
        self.t_max = max(self.profile.max(), T_in)
        self.t_min = min(self.profile.min(), T_in)
        self.eq_params(T_in, mass_flow)
        self.profile = self.calc_solution().reshape((len(self.xev)))*(self.t_max-self.t_min) + self.t_min
        self.init = self.profile
        self.tout = self.profile[-1]
        return self.profile

    def calc_heat_loss(self, profile, dt, T_amb):
        """
        Update the temperature profile of a stratified TES packed bed over a time step dt,
        accounting for heat losses to ambient.

        Parameters
        ----------
        profile : array
            Current temperature profile [C].
        dt : float
            Time step [s].
        T_amb : float
            Ambient temperature [C].

        Returns
        -------
        new_T_profile : array
            Updated temperature profile after heat losses [C].
        """
        profile = np.clip(np.array(profile), 300.1, 600.0)
        n_layers = len(profile)
        dz = self.HT / n_layers
        A_cross = np.pi * (self.Dint / 2)**2
        volume_layer = A_cross * dz

        new_T_profile = np.zeros_like(profile)

        for i, T in enumerate(profile):
            T = max(T, 300.1)
            T_K = T + 273.15
            fluid_density = cp.PropsSI('D', 'T', T_K, 'P', self.HTF_P, self.HTF)
            fluid_cp = cp.PropsSI('C', 'T', T_K, 'P', self.HTF_P, self.HTF)

            effective_capacity = volume_layer * (self.e * fluid_density * fluid_cp +
                                                  (1 - self.e) * self.rho_s * self.cp_s)

            if i == 0:
                area = A_cross + (np.pi * self.Dint * dz)
            elif i == n_layers - 1:
                area = np.pi * self.Dint * dz
            else:
                area = np.pi * self.Dint * dz

            R_wall = np.log((self.Dint+self.wst)/(self.Dint)) / (np.pi*self.HT*self.kst)
            R_ins  = np.log((self.Dint+self.wst+self.wins)/(self.Dint+self.wst)) / (np.pi*self.HT*self.kins)
            h_conv = 4  # W/m2 K
            R_conv = 1/(h_conv * area)

            R_total = R_wall + R_ins + R_conv

            Q_loss = (T - T_amb) / R_total

            dT = (Q_loss * dt) / effective_capacity

            new_T_profile[i] = T - dT

        return new_T_profile

    def set_state(self, new_state):
        """
        Sets the operational state of the TES and switches the inlet and outlet
        if changing from charge to discharge and vice versa.

        Parameters
        ----------
        new_state : str
            The new state ('charge', 'discharge', 'standby').
        """
        if new_state != self.state: 
            if new_state in ['charge', 'discharge']:
                self.inlet, self.outlet = self.outlet, self.inlet
                self.profile = np.flip(self.profile)
        self.state = new_state

    def calculate_SoC(self, profile):
        """
        Calculate the energy stored in the TES unit by integrating the temperature profile.

        Parameters
        ----------
        profile : array
            Temperature profile [C].

        Returns
        -------
        SoC : float
            State of charge in kWh.
        """
        T_avg_C = np.mean(profile)
        T_avg_K = T_avg_C + 273.15
        T_ref = 300.0  # Base discharge temperature

        try:
            rho_f = cp.PropsSI('D', 'T', T_avg_K, 'P', self.HTF_P, self.HTF)
            cp_f  = cp.PropsSI('C', 'T', T_avg_K, 'P', self.HTF_P, self.HTF)
        except Exception:
            self.air_params()
            rho_f = self.rho_out
            cp_f = self.cp_f

        C_vol = self.rho_s * self.cp_s * (1 - self.e) + rho_f * cp_f * self.e
        volume = np.pi * (self.Dint / 2)**2 * self.HT
        dT = np.array(profile) - T_ref
        SoC = volume * C_vol * np.mean(dT)
        return max(SoC / 3.6e6, 0.0)  # kWh
