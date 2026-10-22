import os
from pathlib import Path
from dotenv import load_dotenv

# Base workspace directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")

# OpenRouter API Key (supporting both OPENROUTER_API_KEY and OPEN_ROUTER_API_KEY)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY")

# Hugging Face Configuration (optional backup)
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")

# OpenRouter endpoint
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default Model: Qwen2.5-VL 7B Instruct on OpenRouter
DEFAULT_MODEL = os.getenv("MODEL", "qwen/qwen3-vl-8b-instruct")
 
# Fallback models on OpenRouter
FALLBACK_MODELS = [
    "qwen/qwen-2.5-vl-72b-instruct",
    "qwen/qwen-2.5-vl-72b-instruct:free",
]

# Output directory for extracted JSON dumps
DEFAULT_OUTPUT_DIR = BASE_DIR / "output_enriched"
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Output directory for PurchaseBillMain form outputs
PURCHASE_BILL_FORM_DIR = BASE_DIR / "output_purchasebillmainform"
PURCHASE_BILL_FORM_DIR.mkdir(parents=True, exist_ok=True)

# Image processing limits (preserves legibility while optimizing payload size)
MAX_IMAGE_DIMENSION = 2048
IMAGE_JPEG_QUALITY = 90

# SQL Server (SSMS) Database Configuration for ItemMaster enrichment
def parse_db_connection_string() -> str:
    raw_val = (
        os.getenv("SQL_SERVER_DATABASE_URL")
        or os.getenv("SQL_SERVER_CONNECTION_STRING")
        or os.getenv("SQL_SERVER_DATABSE")
        or os.getenv("SQL_SERVER_DATABASE")
        or ""
    ).strip()

    if not raw_val:
        return ""

    # If already standard ODBC connection string
    if "driver=" in raw_val.lower() and "://" not in raw_val:
        return raw_val

    # If SQLAlchemy format: mssql+pyodbc://user:pass@host/db?driver=...
    if "://" in raw_val:
        import urllib.parse
        parsed = urllib.parse.urlparse(raw_val)
        query_params = urllib.parse.parse_qs(parsed.query)

        driver = query_params.get("driver", ["ODBC Driver 18 for SQL Server"])[0]
        if not driver.startswith("{") and not driver.endswith("}"):
            driver = f"{{{driver}}}"

        server = parsed.hostname or "localhost"
        if parsed.port:
            server = f"{server},{parsed.port}"

        database = parsed.path.lstrip("/")
        parts = [
            f"Driver={driver}",
            f"Server={server}",
            f"Database={database}",
        ]
        if parsed.username:
            parts.append(f"UID={parsed.username}")
        if parsed.password:
            parts.append(f"PWD={parsed.password}")

        for k, vals in query_params.items():
            if k.lower() != "driver":
                parts.append(f"{k}={vals[0]}")

        return ";".join(parts) + ";"

    return raw_val

SQL_SERVER_CONNECTION_STRING = parse_db_connection_string()
ENABLE_DB_ENRICHMENT = os.getenv("ENABLE_DB_ENRICHMENT", "true").lower() in ("true", "1", "yes")
