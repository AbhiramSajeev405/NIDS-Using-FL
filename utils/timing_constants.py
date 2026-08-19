"""
LSCUDAPORT - Timing Constants
Configurable timing values to avoid magic numbers (Fixes BUG #005).
"""

import os

# Connection startup delays
SERVER_STARTUP_DELAY = 3.0  # Time to wait for server to start
CLIENT_STARTUP_DELAY = 2.0  # Time between starting each client
DASHBOARD_UPDATE_DELAY = 0.5  # Dashboard refresh interval

# Network operation timeouts
CONNECTION_TIMEOUT = 10  # seconds
API_TIMEOUT = 3  # seconds for API calls

# Training delays
ROUND_COMPLETION_CHECK = 1.0  # Time between checking if round completed

def get_delay(delay_name):
    """Get a delay value by name, allowing runtime configuration.

    Environment variables can override:
    FL_NIDS_SERVER_STARTUP_DELAY=5.0
    """
    delays = {
        'server_startup': SERVER_STARTUP_DELAY,
        'client_startup': CLIENT_STARTUP_DELAY,
        'dashboard_update': DASHBOARD_UPDATE_DELAY,
        'round_completion': ROUND_COMPLETION_CHECK,
    }

    # Check environment variable override
    env_var = f"FL_NIDS_{delay_name.upper()}_DELAY"
    env_val = os.environ.get(env_var)

    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass

    return delays.get(delay_name, 1.0)
