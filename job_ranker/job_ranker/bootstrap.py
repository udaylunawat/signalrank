# bootstrap.py
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# HuggingFace + transformers silence
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

for noisy in [
    "httpx",
    "urllib3",
    "huggingface_hub",
    "sentence_transformers",
    "transformers",
    "tokenizers",
]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")
