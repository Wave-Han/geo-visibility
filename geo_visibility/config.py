# Load YAML config / data files from the project data/ directory.
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"


def load_yaml(path: pathlib.Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict:
    return {
        "engines": load_yaml(DATA_DIR / "engines.yaml"),
        "brands": load_yaml(DATA_DIR / "brands.yaml"),
        "questions": load_yaml(DATA_DIR / "questions.yaml"),
    }
