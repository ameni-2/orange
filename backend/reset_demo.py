"""Réinitialise uniquement les données fictives de démonstration."""
from pathlib import Path
from .database import DATABASE_URL
if not DATABASE_URL.startswith("sqlite:///./data/"):
    raise SystemExit("Réinitialisation autorisée uniquement sur la base SQLite de démonstration.")
p=Path(DATABASE_URL.replace("sqlite:///./", ""))
if p.exists(): p.unlink()
from .seed_demo import seed_demo
seed_demo()
print("Base de démonstration recréée avec les sites tunisiens fictifs.")
