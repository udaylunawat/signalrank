import json
from pathlib import Path

SESSION_FILE = Path(".streamlit_session.json")


def load_session():
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except Exception:
            pass
    return {}


def save_session(data: dict):
    SESSION_FILE.write_text(json.dumps(data))
