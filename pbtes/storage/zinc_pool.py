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
        Terminal temperature difference for process HX. Default 20 K.
    op_start_hour : int
        Hour of day when production starts (0-23). Default 8.
    op_end_hour : int
        Hour of day when production ends (0-23). Default 20.
    op_days_per_week : int
        Number of operating days per week (1=Mon only, 5=Mon-Fri). Default 5.
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
