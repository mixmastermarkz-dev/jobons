"""Configuration pytest — ajoute la racine du projet au sys.path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
