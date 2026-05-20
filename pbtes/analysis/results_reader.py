import os
import json
import pandas as pd

def _looks_json_like(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    return (s.startswith('[') and s.endswith(']')) or (s.startswith('{') and s.endswith('}'))

def load_results(filepath: str) -> tuple[pd.DataFrame, dict]:
    """
    Reads a simulation results CSV file with a leading __meta__ metadata line.
    
    Parameters
    ----------
    filepath : str
        Path to the saved results CSV.
        
    Returns
    -------
    df : pd.DataFrame
        The simulation timeseries data.
    meta : dict
        The simulation parameters and metadata dictionary.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"No existe el archivo: {filepath}")

    # Read the first line to extract metadata
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

    # Read DataFrame starting after the metadata line
    df = pd.read_csv(filepath, skiprows=skiprows, encoding='utf-8')

    # Convert time column to datetime if it exists
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], errors='coerce')

    # Parse JSON-formatted cells (like TES_profiles or list strings)
    for c in df.columns:
        if df[c].dtype == 'O':
            sample = df[c].dropna().astype(str).head(3).tolist()
            if any(_looks_json_like(s) for s in sample):
                try:
                    df[c] = df[c].apply(lambda x: json.loads(x) if isinstance(x, str) and _looks_json_like(x) else x)
                except Exception:
                    pass

    return df, meta
