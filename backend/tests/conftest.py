import os
os.environ["FINBRIDGE_OFFLINE"] = "1"      # tests never touch the network
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))
os.environ.setdefault("FINBRIDGE_DB", ":memory:")      # tests use a throw-away in-memory database
