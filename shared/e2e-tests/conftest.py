"""Fixtures pytest partagées entre les tests e2e."""

import sys
from pathlib import Path


# Permet d'importer cam.py depuis les tests
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
