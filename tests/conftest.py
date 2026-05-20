"""
conftest.py — Shared pytest fixtures for the PBTES test suite.

All fixtures use baseline_config() from pbtes/config.py as the single
source of truth. Import fixtures by name in any test file — pytest
discovers conftest.py automatically.
"""

import os
import shutil
import pytest
from pbtes.config import baseline_config, zinc_pool_config
from pbtes.network.system import SolarThermalSystem
from pbtes.storage.zinc_pool import ZincPool


# ── Session setup ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def clear_tespy_cache():
    """
    Wipe .tespy_cache/ before the test session starts.

    TESPy saves design states to .tespy_cache/. If a previous offdesign run
    diverged (mass-flow sentinel = -1e12 kg/s), those corrupted files get
    loaded as warm-start init for the next design solve and break the result.
    Clearing the cache ensures every test session starts from scratch.

    Uses a Windows-safe removal that handles read-only and locked files.
    """
    import stat

    def _force_remove(func, path, exc_info):
        """onerror handler: chmod +w then retry."""
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass  # best-effort; do not fail the test session

    cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.tespy_cache')
    if os.path.isdir(cache_dir):
        # Remove each base_design_* subdirectory individually — safer on Windows
        for entry in os.listdir(cache_dir):
            entry_path = os.path.join(cache_dir, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, onerror=_force_remove)
            else:
                try:
                    os.remove(entry_path)
                except Exception:
                    pass
    os.makedirs(cache_dir, exist_ok=True)
    yield
    # (leave cache in place after tests — useful for debugging)

@pytest.fixture(scope="session")
def base_config():
    """Return the baseline (tes_params, component_params, conexion_params) tuple."""
    return baseline_config()


@pytest.fixture(scope="session")
def tes_params(base_config):
    """Return baseline TES parameter dict."""
    return base_config[0]


@pytest.fixture(scope="session")
def component_params(base_config):
    """Return baseline component parameter dict."""
    return base_config[1]


@pytest.fixture(scope="session")
def conexion_params(base_config):
    """Return baseline connection parameter dict."""
    return base_config[2]


@pytest.fixture(scope="session")
def zinc_params():
    """Return baseline zinc pool parameter dict."""
    return zinc_pool_config()


# ── System fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def parallel_indirect_system(tes_params, component_params, conexion_params):
    """Build a Parallel/indirect SolarThermalSystem (no solve)."""
    return SolarThermalSystem(
        rows=1,
        tes_params=tes_params,
        component_params=component_params,
        conexion_params=conexion_params,
        HTF='INCOMP::NaK',
        topology='Parallel',
        tank_config='indirect',
    )


@pytest.fixture
def series_indirect_system(tes_params, component_params, conexion_params):
    """Build a Series/indirect SolarThermalSystem (no solve)."""
    return SolarThermalSystem(
        rows=1,
        tes_params=tes_params,
        component_params=component_params,
        conexion_params=conexion_params,
        HTF='INCOMP::NaK',
        topology='Series',
        tank_config='indirect',
    )


# ── ZincPool fixture ───────────────────────────────────────────────────────────

@pytest.fixture
def zinc_pool(zinc_params):
    """Return a ZincPool instance initialised from baseline config."""
    return ZincPool(zinc_params)
