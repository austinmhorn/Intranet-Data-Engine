# scripts/config.py

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

DATA_DIR = PROJECT_DIR / "data"
JSON_DIR = PROJECT_DIR / "json"
LOG_DIR = PROJECT_DIR / "logs"

CONFIG_FILE = JSON_DIR / "intranet_config.json"

NOTION_DATA_FILE = DATA_DIR / "notion_data.csv"
NOTION_DATA_PROD_FILE = DATA_DIR / "notion_data_prod.csv"
NOTION_DATA_SOFT_FILE = DATA_DIR / "notion_data_soft.csv"
NOTION_DATA_TEST_FILE = DATA_DIR / "notion_data_test.csv"

SCIM_SCRIPT = SCRIPT_DIR / "CSV-2-SCIM_Intranet_v2.py"
PROD_CONFIG_SCRIPT = SCRIPT_DIR / "filter_for_prod.py"
SOFT_CONFIG_SCRIPT = SCRIPT_DIR / "filter_for_soft.py"
TEST_CONFIG_SCRIPT = SCRIPT_DIR / "filter_for_test.py"


def load_intranet_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


_CONFIG = load_intranet_config()

BASE_URL     = _CONFIG["base_url"]
BEARER_TOKEN = _CONFIG["bearer_token"]