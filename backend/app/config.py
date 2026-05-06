"""
Settings loaded from environment variables.

Single source of truth for runtime config. All other modules import from
here instead of calling os.getenv directly, so defaults stay consistent.
"""

import os

from dotenv import load_dotenv

load_dotenv()


# Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "tortilla_db")
DB_USER = os.getenv("DB_USER", "tortilla_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "tortilla_pass")

# Display / locale (from design-doc §5)
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "€")
CHAIN_TZ = os.getenv("CHAIN_TZ", "Europe/Madrid")

# POS export root. Inside the container the Dockerfile sets this to
# /app/data/pos_exports, mounted from ./data/pos_exports on the host.
# On bare metal it defaults to "pos_exports" relative to CWD, matching
# the pre-restructure behaviour.
POS_EXPORTS_DIR = os.getenv("POS_EXPORTS_DIR", "pos_exports")
