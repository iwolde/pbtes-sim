import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
import json, os
from copy import deepcopy


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
