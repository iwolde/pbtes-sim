import pandas as pd
from datetime import datetime

class WinterLogic:
    """
    Manages the seasonal control logic for the PBTES storage tanks,
    determining target temperature setpoints for the heater blankets
    and ensuring proper thresholds for operational modes and solver convergence.
    """

    def __init__(self, T_set_production=450.0, T_set_winter=300.1, winter_months=(6, 7, 8)):
        """
        Initialize WinterLogic.

        Parameters
        ----------
        T_set_production : float
            Tank target temperature setpoint during production months [°C].
        T_set_winter : float
            Tank target temperature setpoint during winter months [°C].
        winter_months : tuple of int
            Months considered as winter (default: 6, 7, 8 corresponding to June-August).
        """
        self.T_set_production = T_set_production
        self.T_set_winter = T_set_winter
        self.winter_months = list(winter_months)

    def is_winter(self, timestamp) -> bool:
        """
        Check if the given timestamp falls within the winter months.
        """
        if timestamp is None:
            return False
        
        # Handle datetime or pandas Timestamp objects
        if hasattr(timestamp, 'month'):
            month = timestamp.month
        elif isinstance(timestamp, str):
            try:
                dt = pd.to_datetime(timestamp)
                month = dt.month
            except Exception:
                return False
        else:
            return False

        return month in self.winter_months

    def get_tank_setpoint(self, timestamp) -> float:
        """
        Get the target setpoint temperature for the storage tank heaters
        based on the season of the current timestamp.
        """
        if self.is_winter(timestamp):
            return self.T_set_winter
        return self.T_set_production
