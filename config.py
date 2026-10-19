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
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Image processing limits (preserves legibility while optimizing payload size)
MAX_IMAGE_DIMENSION = 2048
IMAGE_JPEG_QUALITY = 90
