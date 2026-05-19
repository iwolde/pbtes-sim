# -*- coding: utf-8 -*-
"""
Analítica de convergencia anual para planta solar + PBTES

Uso rápido:
    python analizar_convergencia.py --in results_annual.csv --out ./analysis_out

Produce:
    - CSVs con tablas de frecuencia/tasa de error (por hora, TESmode, TES_layout, bines de E)
    - Correlaciones (Pearson y Spearman) entre error y variables operativas
    - Gráficos PNG (barras y heatmaps) con las tasas de error
    - Un CSV con los eventos de error detallados (error_events.csv)

Notas:
- No asume rangos de E: usa deciles y bines uniformes.
- "Estado del TES" se usa en dos sentidos: TES_layout (charge/discharge/standby)
  y SoC (tes_soc_kWh).
- "Error" se define como: (iter_status != 'converged') OR (network_converged == False).
- "Casi-falla" se marca si en attempts_json algún intento tiene tespy_converged == False
  pero luego el paso termina convergiendo.

Requisitos: Python 3.9+, pandas, numpy, matplotlib, scipy (opcional pero recomendado).
"""

import os
import json
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    from scipy.stats import pearsonr, spearmanr
    _SCIPY_OK = True
except Exception:
    _SCIPY_OK = False

# ----------------------------
# 0) Utilidades de I/O robustas
# ----------------------------
def _looks_json_like(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    return (s.startswith('[') and s.endswith(']')) or (s.startswith('{') and s.endswith('}'))

def load_results_with_meta(filepath: str) -> tuple[pd.DataFrame, dict]:
    """Lee results_annual.csv con posible cabecera __meta__ y reinterpreta columnas JSON."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"No existe el archivo: {filepath}")

    # Lee primera línea para meta (si existe)
    meta = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        first = f.readline().rstrip('\n')
    prefix = '__meta__,'
    skiprows = 1 if first.startswith(prefix) else 0
    if skiprows == 1:
        try:
            meta = json.loads(first[len(prefix):])
        except Exception:
            meta = {}

    # DataFrame
    df = pd.read_csv(filepath, skiprows=skiprows, encoding='utf-8')

    # time -> datetime (si existe)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], errors='coerce')

    # Parseo blando de columnas tipo JSON guardadas como texto
    for c in df.columns:
        if df[c].dtype == 'O':
            sample = df[c].dropna().astype(str).head(3).tolist()
            if any(_looks_json_like(s) for s in sample):
                try:
                    df[c] = df[c].apply(lambda x: json.loads(x) if isinstance(x, str) and _looks_json_like(x) else x)
                except Exception:
                    # deja tal cual si falla
                    pass

    return df, meta


# -------------------------------------------
# 1) Ingeniería de variables para el análisis
# -------------------------------------------
def build_flags_and_features(df: pd.DataFrame) -> pd.DataFrame:
    """Crea banderas de error y features auxiliares (hora, bines de E, etc.)."""
    out = df.copy()

    # Normalización de columnas esperadas
    if 'iter_status' in out.columns:
        out['iter_status'] = out['iter_status'].astype(str).str.lower()
    else:
        out['iter_status'] = None

    if 'network_converged' not in out.columns:
        out['network_converged'] = np.nan

    # Banderas básicas
    out['err_iter'] = out['iter_status'].apply(lambda s: (s is not None) and (s != 'converged'))
    out['err_net']  = out['network_converged'].apply(lambda x: (x is not True))  # False o NaN se considera problema
    out['is_error'] = out[['err_iter', 'err_net']].any(axis=1)

    # "Casi-falla": hubo intentos no convergentes pero el paso terminó convergiendo
    def _near_miss(row):
        it_ok = (row.get('iter_status', '') == 'converged')
        atts = row.get('attempts_json', None)
        if (atts is None) or (not isinstance(atts, list)):
            return False
        any_fail = any([ (not a.get('tespy_converged', True)) for a in atts ])
        return bool(it_ok and any_fail)

    out['near_miss'] = out.apply(_near_miss, axis=1)

    # Hora del día, mes, semana ISO
    if 'time' in out.columns and pd.api.types.is_datetime64_any_dtype(out['time']):
        out['hour'] = out['time'].dt.hour
        out['month'] = out['time'].dt.month
        try:
            out['iso_week'] = out['time'].dt.isocalendar().week.astype(int)
        except Exception:
            out['iso_week'] = np.nan
        out['date'] = out['time'].dt.date
    else:
        out['hour'] = np.nan
        out['month'] = np.nan
        out['iso_week'] = np.nan
        out['date'] = np.nan

    # Estado TES (layout) a minúsculas
    if 'TES_layout' in out.columns:
        out['TES_layout'] = out['TES_layout'].astype(str).str.lower()
    else:
        out['TES_layout'] = 'unknown'

    # TESmode como str
    if 'TESmode' in out.columns:
        out['TESmode'] = out['TESmode'].astype(str)
    else:
        out['TESmode'] = 'unknown'

    # Bines de irradiancia E (si existe)
    if 'E' in out.columns:
        e = out['E'].astype(float)
        # bines uniformes (10)
        try:
            bins_uniform = np.linspace(np.nanmin(e), np.nanmax(e), 11) if np.isfinite(e).any() else None
        except Exception:
            bins_uniform = None
        if bins_uniform is not None and np.all(np.isfinite(bins_uniform)) and len(np.unique(bins_uniform)) > 1:
            out['E_bin_uniform'] = pd.cut(e, bins=bins_uniform, include_lowest=True)
        else:
            out['E_bin_uniform'] = pd.Series([np.nan]*len(out), index=out.index)
        # bines por deciles (10)
        try:
            out['E_bin_decile'] = pd.qcut(e, q=10, duplicates='drop')
        except Exception:
            out['E_bin_decile'] = pd.Series([np.nan]*len(out), index=out.index)
    else:
        out['E_bin_uniform'] = np.nan
        out['E_bin_decile'] = np.nan

    return out


# -------------------------------------
# 2) Tablas descriptivas y visualización
# -------------------------------------
def _ensure_outdir(path: str):
    os.makedirs(path, exist_ok=True)

def rate_table(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Devuelve conteos y tasa de error por agrupación."""
    g = df.groupby(key, dropna=False)
    tab = g['is_error'].agg(['count', 'sum']).rename(columns={'sum':'errors'})
    tab['error_rate'] = tab['errors'] / tab['count']
    return tab.reset_index()

def save_barplot_rate(df: pd.DataFrame, key: str, outdir: str, title: str):
    """Bar chart de tasa de error por clave."""
    tab = rate_table(df, key).sort_values('error_rate', ascending=False)
    plt.figure(figsize=(10, 4.5))
    x = tab[key].astype(str).values
    y = tab['error_rate'].values
    plt.bar(x, y)
    plt.xticks(rotation=45, ha='right')
    plt.ylabel('Tasa de error')
    plt.title(title)
    plt.tight_layout()
    fname = os.path.join(outdir, f"rate_by_{key}.png")
    plt.savefig(fname, dpi=180)
    plt.close()
    # Guarda CSV
    tab.to_csv(os.path.join(outdir, f"rate_by_{key}.csv"), index=False)

def save_heatmap_hour_by(df: pd.DataFrame, col: str, outdir: str, title: str):
    """
    Heatmap de tasa de error por hora (filas 0..23) vs 'col' (columnas).
    Sólo para columnas discretas/binned.
    """
    tmp = df.copy()
    tmp = tmp.dropna(subset=['hour'])
    # tabla de tasas
    g = tmp.groupby(['hour', col], dropna=False)['is_error'].agg(['count', 'sum'])
    g['rate'] = g['sum'] / g['count']
    p = g['rate'].unstack(col)  # filas: hour, cols: col
    plt.figure(figsize=(11, 5))
    plt.imshow(p.values, aspect='auto', origin='lower')
    plt.colorbar(label='Tasa de error')
    plt.yticks(ticks=np.arange(0, p.shape[0]), labels=p.index.tolist())
    plt.xticks(ticks=np.arange(0, p.shape[1]), labels=[str(c) for c in p.columns], rotation=45, ha='right')
    plt.xlabel(col)
    plt.ylabel('Hora del día')
    plt.title(title)
    plt.tight_layout()
    fname = os.path.join(outdir, f"heatmap_hour_vs_{col}.png")
    plt.savefig(fname, dpi=180)
    plt.close()
    # Guarda CSV de la matriz
    p.to_csv(os.path.join(outdir, f"heatmap_hour_vs_{col}.csv"))

def save_top_error_windows(df: pd.DataFrame, outdir: str, window_h=6, topk=10):
    """
    Detecta ventanas de 'window_h' horas con mayor densidad de errores (rolling sum por día).
    Entrega tabla con ranking de días/ventanas problemáticas.
    """
    if 'time' not in df.columns or not pd.api.types.is_datetime64_any_dtype(df['time']):
        return
    tmp = df[['time', 'is_error']].dropna().copy()
    tmp = tmp.sort_values('time').set_index('time')
    # rolling por horas
    roll = tmp['is_error'].astype(int).rolling(f'{window_h}H').sum()
    # top-k momentos
    top = roll.sort_values(ascending=False).head(topk)
    out = top.reset_index().rename(columns={'is_error': f'errors_in_{window_h}h'})
    out.to_csv(os.path.join(outdir, f"top_windows_{window_h}h.csv"), index=False)

# -------------------------------------
# 3) Correlaciones con variables operativas
# -------------------------------------
def _safe_series(df, name):
    return df[name].astype(float) if name in df.columns else pd.Series(dtype=float)

def correlations_block(df: pd.DataFrame, outdir: str):
    """
    Calcula correlaciones (Pearson/Spearman) entre is_error (0/1) y varias variables:
    E, Tamb, tes_soc_kWh, T_ptc_out, T_tes_top, T_tes_bottom, mdot_*.
    Guarda un CSV con los coeficientes y p-valores (si SciPy está disponible).
    """
    vars_candidates = [
        'E', 'Tamb', 'tes_soc_kWh',
        'T_ptc_out', 'T_tes_top', 'T_tes_bottom',
        'mdot_ptc_kg_s', 'mdot_tes_charge_kg_s', 'mdot_tes_discharge_kg_s', 'mdot_process_kg_s'
    ]
    res = []
    y = df['is_error'].astype(int)

    for v in vars_candidates:
        if v not in df.columns:
            continue
        x = pd.to_numeric(df[v], errors='coerce')
        mask = x.notna() & y.notna()
        if mask.sum() < 5:
            continue
        xv = x[mask].values
        yv = y[mask].values
        row = {'variable': v, 'n': int(mask.sum())}
        # Pearson (equivalente a point-biserial con y binaria)
        if _SCIPY_OK:
            try:
                r_p, p_p = pearsonr(xv, yv)
                row['pearson_r'] = r_p
                row['pearson_p'] = p_p
            except Exception:
                row['pearson_r'] = np.nan
                row['pearson_p'] = np.nan
            # Spearman
            try:
                r_s, p_s = spearmanr(xv, yv)
                row['spearman_r'] = r_s
                row['spearman_p'] = p_s
            except Exception:
                row['spearman_r'] = np.nan
                row['spearman_p'] = np.nan
        else:
            # fallback: solo r de Pearson con numpy
            try:
                r = np.corrcoef(xv, yv)[0,1]
            except Exception:
                r = np.nan
            row['pearson_r'] = r
            row['pearson_p'] = np.nan
            row['spearman_r'] = np.nan
            row['spearman_p'] = np.nan

        res.append(row)

    if res:
        out = pd.DataFrame(res).sort_values('pearson_r', ascending=False)
        out.to_csv(os.path.join(outdir, "correlations_error_vs_features.csv"), index=False)

# -------------------------------------
# X) Detección de errores físicos
# -------------------------------------

def _get_time_step_seconds(df: pd.DataFrame) -> pd.Series | None:
    """Devuelve dt (s) por fila usando:
       1) Columna 'dt_s' si existe.
       2) Diferencia de 'time' si existe.
       Si nada existe, retorna None.
    """
    if 'dt_s' in df.columns:
        dt = pd.to_numeric(df['dt_s'], errors='coerce')
        return dt

    if 'time' in df.columns and pd.api.types.is_datetime64_any_dtype(df['time']):
        t = df['time'].sort_values()
        # reconstruct order-based dt: asigna dt a cada fila según dif con anterior
        df_sorted = df.sort_values('time').copy()
        dt_sorted = df_sorted['time'].diff().dt.total_seconds()
        # vuelve al orden original
        dt = pd.Series(index=df_sorted.index, data=dt_sorted.values).reindex(df.index)
        return dt

    return None


def _iqr_outliers_mask(x: pd.Series, k: float = 1.5) -> pd.Series:
    """Máscara booleana True donde hay outliers por regla IQR (1.5*IQR por defecto)."""
    x = pd.to_numeric(x, errors='coerce')
    q1 = x.quantile(0.25)
    q3 = x.quantile(0.75)
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr == 0:
        return pd.Series(False, index=x.index)
    low = q1 - k * iqr
    high = q3 + k * iqr
    return (x < low) | (x > high)


def _first_existing(cols, df):
    return [c for c in cols if c in df.columns]


def detect_physical_anomalies(df: pd.DataFrame,
                              flow_hi_thr: float = 15.0,
                              iqr_k: float = 1.5,
                              outdir: str = "analysis_out"):
    """
    Detecta:
      (A) Flujos másicos negativos o > flow_hi_thr (kg/s).
      (B) Outliers en energías *_kJ por IQR.
      (C) Potencias derivadas (kW) si hay dt: outliers por IQR.
      (D) Spikes: outliers por IQR en |ΔE| y |ΔP|.

    Genera:
      - 'phys_flags.csv' con banderas por fila y contadores
      - 'phys_anomalies_events.csv' con filas anómalas y detalles
      - Figuras PNG y CSVs de tasas por hora/TES_layout/TESmode
      - Histogramas de flujos másicos con líneas en 0 y flow_hi_thr
    """
    _ensure_outdir(outdir)

    out = df.copy()

    # -------------------------
    # (A) Flujos másicos
    # -------------------------
    mf_cols = [c for c in out.columns if c.startswith('mdot')]
    mf_neg_cols, mf_hi_cols = [], []

    for c in mf_cols:
        x = pd.to_numeric(out[c], errors='coerce')
        neg = x < 0
        hi  = x > flow_hi_thr
        out[f'{c}__neg'] = neg.fillna(False)
        out[f'{c}__hi']  = hi.fillna(False)
        mf_neg_cols.append(f'{c}__neg')
        mf_hi_cols.append(f'{c}__hi')

    out['mf_any_neg'] = out[mf_neg_cols].any(axis=1) if mf_neg_cols else False
    out['mf_any_hi']  = out[mf_hi_cols].any(axis=1) if mf_hi_cols else False

    # -------------------------
    # (B) Energías (kJ): outliers
    # -------------------------
    e_cols = [c for c in out.columns
              if ('kJ' in c) and (out[c].dtype != 'O')]
    e_oi_cols = []
    for c in e_cols:
        mask = _iqr_outliers_mask(out[c], k=iqr_k)
        colname = f'{c}__oi'
        out[colname] = mask.fillna(False)
        e_oi_cols.append(colname)

    out['E_any_oi'] = out[e_oi_cols].any(axis=1) if e_oi_cols else False

    # -------------------------
    # (C) Potencias (kW) si hay dt
    # -------------------------
    dt = _get_time_step_seconds(out)
    p_cols = []
    p_oi_cols = []
    if dt is not None and dt.notna().any():
        # 1 kJ/s = 1 kW
        for c in e_cols:
            p_name = c.replace('_kJ', '_kW') if c.endswith('_kJ') else f'P_{c}'
            with np.errstate(invalid='ignore', divide='ignore'):
                p = pd.to_numeric(out[c], errors='coerce') / dt
            out[p_name] = p
            p_cols.append(p_name)
            # outliers por IQR
            mask = _iqr_outliers_mask(out[p_name], k=iqr_k)
            colname = f'{p_name}__oi'
            out[colname] = mask.fillna(False)
            p_oi_cols.append(colname)

        out['P_any_oi'] = out[p_oi_cols].any(axis=1) if p_oi_cols else False
    else:
        out['P_any_oi'] = False

    # -------------------------
    # (D) Spikes: ΔE, ΔP (absolutos)
    # -------------------------
    dE_oi_cols, dP_oi_cols = [], []

    for c in e_cols:
        dE = pd.to_numeric(out[c], errors='coerce').diff().abs()
        out[f'd{c}'] = dE
        m = _iqr_outliers_mask(dE, k=iqr_k)
        name = f'd{c}__oi'
        out[name] = m.fillna(False)
        dE_oi_cols.append(name)

    if p_cols:
        for c in p_cols:
            dP = pd.to_numeric(out[c], errors='coerce').diff().abs()
            out[f'd{c}'] = dP
            m = _iqr_outliers_mask(dP, k=iqr_k)
            name = f'd{c}__oi'
            out[name] = m.fillna(False)
            dP_oi_cols.append(name)

    out['dE_any_oi'] = out[dE_oi_cols].any(axis=1) if dE_oi_cols else False
    out['dP_any_oi'] = out[dP_oi_cols].any(axis=1) if dP_oi_cols else False

    # -------------------------
    # Agregado global de anomalías
    # -------------------------
    phys_cols = ['mf_any_neg', 'mf_any_hi', 'E_any_oi', 'P_any_oi', 'dE_any_oi', 'dP_any_oi']
    out['phys_anomaly'] = out[phys_cols].any(axis=1)

    # Contadores por fila
    detail_cols = mf_neg_cols + mf_hi_cols + e_oi_cols + p_oi_cols + dE_oi_cols + dP_oi_cols
    if detail_cols:
        out['phys_anomaly_count'] = out[detail_cols].sum(axis=1)
    else:
        out['phys_anomaly_count'] = 0

    # Guarda CSV con todas las banderas
    out.to_csv(os.path.join(outdir, "phys_flags.csv"), index=False)

    # Tabla corta de eventos anómalos
    base_cols = _first_existing(
        ['time','hour','TES_layout','TESmode','E','Tamb','tes_soc_kWh'], out
    ) + phys_cols + ['phys_anomaly_count']
    extras = _first_existing(
        ['mdot_ptc_kg_s','mdot_tes_charge_kg_s','mdot_tes_discharge_kg_s','mdot_process_kg_s'], out
    ) + e_cols + p_cols
    events = out.loc[out['phys_anomaly'], base_cols + extras]
    events.to_csv(os.path.join(outdir, "phys_anomalies_events.csv"), index=False)

    # -------------------------
    # Figuras y tasas
    # -------------------------
    def _rate_bar(df_, key, title, fname_prefix):
        tab = df_.groupby(key, dropna=False, observed=False)['phys_anomaly'] \
                 .agg(['count','sum']).rename(columns={'sum':'events'})
        tab['rate'] = tab['events'] / tab['count']
        tab = tab.reset_index().sort_values('rate', ascending=False)
        plt.figure(figsize=(10,4.5))
        plt.bar(tab[key].astype(str), tab['rate'])
        plt.xticks(rotation=45, ha='right')
        plt.ylabel('Tasa de anomalía física')
        plt.title(title)
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, f"{fname_prefix}.png"), dpi=180)
        plt.close()
        tab.to_csv(os.path.join(outdir, f"{fname_prefix}.csv"), index=False)

    if 'hour' in out.columns:
        _rate_bar(out, 'hour', "Tasa de anomalía física por hora", "phys_rate_by_hour")
    if 'TES_layout' in out.columns:
        _rate_bar(out, 'TES_layout', "Tasa de anomalía física por TES_layout", "phys_rate_by_TES_layout")
    if 'TESmode' in out.columns:
        _rate_bar(out, 'TESmode', "Tasa de anomalía física por TESmode", "phys_rate_by_TESmode")
    if 'E_bin_uniform' in out.columns:
        _rate_bar(out, 'E_bin_uniform', "Tasa de anomalía física por radiación (bines uniformes)", "phys_rate_by_E_bin_uniform")
    if 'E_bin_decile' in out.columns:
        _rate_bar(out, 'E_bin_decile', "Tasa de anomalía física por radiación (deciles)", "phys_rate_by_E_bin_decile")

    # Heatmaps: hora vs radiación / layout / TESmode
    def _heatmap(df_, col, title, fname_prefix):
        tmp = df_.dropna(subset=['hour']).copy()
        g = tmp.groupby(['hour', col], dropna=False, observed=False)['phys_anomaly'] \
               .agg(['count','sum'])
        g['rate'] = g['sum'] / g['count']
        pvt = g['rate'].unstack(col)
        plt.figure(figsize=(11,5))
        plt.imshow(pvt.values, aspect='auto', origin='lower')
        plt.colorbar(label='Tasa de anomalía física')
        plt.yticks(range(pvt.shape[0]), pvt.index.tolist())
        plt.xticks(range(pvt.shape[1]), [str(c) for c in pvt.columns], rotation=45, ha='right')
        plt.xlabel(col)
        plt.ylabel('Hora del día')
        plt.title(title)
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, f"{fname_prefix}.png"), dpi=180)
        plt.close()
        pvt.to_csv(os.path.join(outdir, f"{fname_prefix}.csv"))

    if 'E_bin_uniform' in out.columns:
        _heatmap(out, 'E_bin_uniform',
                 "Anomalía física — hora vs radiación (bines uniformes)",
                 "phys_heatmap_hour_vs_E_bin_uniform")
    if 'TES_layout' in out.columns:
        _heatmap(out, 'TES_layout',
                 "Anomalía física — hora vs TES_layout",
                 "phys_heatmap_hour_vs_TES_layout")
    if 'TESmode' in out.columns:
        _heatmap(out, 'TESmode',
                 "Anomalía física — hora vs TESmode",
                 "phys_heatmap_hour_vs_TESmode")

    # Histogramas de flujos másicos con líneas en 0 y umbral alto
    for c in mf_cols:
        x = pd.to_numeric(out[c], errors='coerce')
        plt.figure(figsize=(7,4))
        plt.hist(x.dropna(), bins=50)
        plt.axvline(0.0, linestyle='--')
        plt.axvline(flow_hi_thr, linestyle='--')
        plt.title(f"Histograma {c} (líneas en 0 y {flow_hi_thr} kg/s)")
        plt.xlabel('kg/s'); plt.ylabel('frecuencia')
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, f"hist_{c}.png"), dpi=160)
        plt.close()

    # Resumen general
    summary = {
        'rows_total': len(out),
        'phys_events': int(out['phys_anomaly'].sum()),
        'phys_rate': float(out['phys_anomaly'].mean()),
        'mf_any_neg': int(out['mf_any_neg'].sum()),
        'mf_any_hi': int(out['mf_any_hi'].sum()),
        'E_any_oi': int(out['E_any_oi'].sum()),
        'P_any_oi': int(out['P_any_oi'].sum()),
        'dE_any_oi': int(out['dE_any_oi'].sum()),
        'dP_any_oi': int(out['dP_any_oi'].sum())
    }
    pd.DataFrame([summary]).to_csv(os.path.join(outdir, "phys_summary.csv"), index=False)

    return out  # dataframe con flags añadidas

# -------------------------------------
# 4) Pipeline principal
# -------------------------------------
def run_all_analyses(in_csv: str, outdir: str = "analysis_out"):
    _ensure_outdir(outdir)

    # 4.1) Carga
    df_raw, meta = load_results_with_meta(in_csv)
    # Guarda meta si existe
    if meta:
        with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # 4.2) Features + banderas
    df = build_flags_and_features(df_raw)
    df.to_csv(os.path.join(outdir, "results_with_flags.csv"), index=False)

    # 4.3) Resúmenes básicos
    total = len(df)
    n_err = int(df['is_error'].sum())
    n_nm  = int(df['near_miss'].sum())
    summary = pd.DataFrame({
        'total_steps':[total],
        'error_steps':[n_err],
        'near_miss_steps':[n_nm],
        'error_rate':[n_err/total if total else np.nan]
    })
    summary.to_csv(os.path.join(outdir, "summary_overall.csv"), index=False)

    # 4.4) Tablas de tasa de error
    if 'hour' in df.columns:
        save_barplot_rate(df, 'hour', outdir, "Tasa de error por hora del día")
    if 'TESmode' in df.columns:
        save_barplot_rate(df, 'TESmode', outdir, "Tasa de error por TESmode")
    if 'TES_layout' in df.columns:
        save_barplot_rate(df, 'TES_layout', outdir, "Tasa de error por TES_layout")

    # por bines de E (uniforme y deciles)
    if 'E_bin_uniform' in df.columns:
        save_barplot_rate(df, 'E_bin_uniform', outdir, "Tasa de error por radiación (bines uniformes)")
    if 'E_bin_decile' in df.columns:
        save_barplot_rate(df, 'E_bin_decile', outdir, "Tasa de error por radiación (deciles)")

    # 4.5) Heatmaps útiles
    if 'E_bin_uniform' in df.columns:
        save_heatmap_hour_by(df, 'E_bin_uniform', outdir, "Tasa de error — hora vs radiación (bines uniformes)")
    if 'TESmode' in df.columns:
        save_heatmap_hour_by(df, 'TESmode', outdir, "Tasa de error — hora vs TESmode")
    if 'TES_layout' in df.columns:
        save_heatmap_hour_by(df, 'TES_layout', outdir, "Tasa de error — hora vs TES_layout")

    # 4.6) Top ventanas problemáticas (densidad de errores)
    save_top_error_windows(df, outdir, window_h=6, topk=15)

    # 4.7) Eventos de error detallados
    err_cols = [
        'time','E','Tamb','TESmode','TES_layout','iter_status','network_converged',
        'attempt_count','attempted_modes','attempts_json',
        'T_ptc_out','T_tes_top','T_tes_bottom',
        'mdot_ptc_kg_s','mdot_tes_charge_kg_s','mdot_tes_discharge_kg_s','mdot_process_kg_s',
        'tes_soc_kWh','to_tes_kJ','tes_to_proc_kJ','solar_to_proc_kJ','aux_to_proc_kJ','ptc_total_kJ'
    ]
    err_cols = [c for c in err_cols if c in df.columns]
    df_errors = df.loc[df['is_error'], err_cols].copy()
    df_errors.to_csv(os.path.join(outdir, "error_events.csv"), index=False)

    # 4.8) Correlaciones
    correlations_block(df, outdir)
    
    # 4.10) Errores físicos (flujos, energías/potencias y spikes)
    df_phys = detect_physical_anomalies(df, flow_hi_thr=25.0, iqr_k=1.5, outdir=outdir)
    
    _print_console_error_summary(df, df_phys)
    
    # 4.9) Pequeño “log” final
    with open(os.path.join(outdir, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            "Archivos generados:\n"
            "- summary_overall.csv: resumen global de errores\n"
            "- rate_by_hour/TESmode/TES_layout/E_bin_*.csv y .png: tasas de error por categoría\n"
            "- heatmap_hour_vs_*.csv y .png: mapas de calor de tasa de error\n"
            "- top_windows_6h.csv: ventanas de 6 h con mayor densidad de errores\n"
            "- error_events.csv: tabla detallada de pasos con error\n"
            "- correlations_error_vs_features.csv: correlaciones con variables operativas\n"
            "- results_with_flags.csv: resultados con banderas y features añadidas\n"
            "- meta.json (si existía): metadatos de la simulación\n"
        )

def _print_console_error_summary(df: pd.DataFrame, df_phys: pd.DataFrame | None = None):
    """
    Imprime un resumen breve de errores en consola:
      - Pasos totales, con error y near-miss
      - Top TESmode / TES_layout / horas con más errores
      - Indicadores por "componente" (a través de mdot_*), si df_phys viene con flags
    """
    total = len(df)
    n_err = int(df.get('is_error', pd.Series(False, index=df.index)).sum())
    n_nm  = int(df.get('near_miss', pd.Series(False, index=df.index)).sum())
    rate  = (n_err / total) if total else float('nan')

    print("\n=== Resumen breve de errores ===")
    print(f"Pasos totales: {total} | Con error: {n_err} ({rate:.1%}) | Near-miss: {n_nm}")

    # Utilidad local segura
    def _top(table_key, topn=5, title=None):
        if table_key in df.columns:
            tab = df.groupby(table_key, dropna=False)['is_error'].agg(['count', 'sum'])
            tab = tab.rename(columns={'sum':'errors'}).sort_values('errors', ascending=False).head(topn)
            if title:
                print(f"\n- Top por {title}:")
            for idx, row in tab.iterrows():
                cnt, err = int(row['count']), int(row['errors'])
                r = (err/cnt) if cnt else float('nan')
                r_txt = f"{r:.1%}" if not (r != r) else "n/a"  # evita imprimir nan
                print(f"  {idx}: errores={err} / n={cnt} (tasa={r_txt})")

    _top('TESmode',  5, 'TESmode')
    _top('TES_layout', 5, 'TES_layout')
    _top('hour', 5, 'hora del día')

    # Frecuencias de modos intentados (si existe columna y fue parseada como lista)
    if 'attempted_modes' in df.columns:
        try:
            err_rows = df.loc[df['is_error'], 'attempted_modes'].dropna()
            # a veces viene como lista; a veces como str ya parseado arriba
            expl = err_rows.apply(lambda x: x if isinstance(x, list) else ([] if pd.isna(x) else [x])).explode()
            freq = expl.value_counts().head(8)
            if not freq.empty:
                print("\n- Modos intentados en pasos con error (top 8):")
                for k, v in freq.items():
                    print(f"  {k}: {int(v)}")
        except Exception:
            pass

    # "Componentes": usa flags por flujo másico si df_phys está disponible
    if df_phys is not None and 'is_error' in df_phys.columns:
        comps = [c for c in ['mdot_ptc_kg_s','mdot_tes_charge_kg_s','mdot_tes_discharge_kg_s','mdot_process_kg_s']
                 if c in df_phys.columns]
        if comps:
            print("\n- Señales por componente (solo en filas con error):")
            err_mask = df_phys['is_error'].fillna(False)
            for c in comps:
                neg_col = f'{c}__neg'
                hi_col  = f'{c}__hi'
                neg = int((err_mask & df_phys.get(neg_col, False)).sum()) if neg_col in df_phys.columns else 0
                hi  = int((err_mask & df_phys.get(hi_col,  False)).sum()) if hi_col  in df_phys.columns else 0
                print(f"  {c}: neg={neg}, >umbral={hi}")

        # Resumen global de anomalías físicas en filas con error
        phys_cols = [col for col in ['mf_any_neg','mf_any_hi','E_any_oi','P_any_oi','dE_any_oi','dP_any_oi']
                     if col in df_phys.columns]
        if phys_cols:
            any_phys_err = int((df_phys['is_error'] & df_phys[phys_cols].any(axis=1)).sum())
            print(f"\n- Filas con error que además tienen anomalía física: {any_phys_err}")
    print("================================\n")
# -------------------------------------
# 5) CLI
# -------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analítica de convergencia para resultados anuales.")
    parser.add_argument("--in", dest="in_csv", type=str, default="test3.csv",
                        help="Ruta al CSV de resultados anuales.")
    parser.add_argument("--out", dest="outdir", type=str, default="analysis_out",
                        help="Carpeta de salida para tablas y gráficos.")
    args = parser.parse_args()

    run_all_analyses(args.in_csv, args.outdir)
