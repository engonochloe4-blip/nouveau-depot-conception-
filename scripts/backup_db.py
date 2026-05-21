from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path


def find_database() -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    env_path = os.getenv("VMWARE_DB_PATH")
    candidates = [
        Path(env_path) if env_path else None,
        base_dir / "backend" / "instance" / "vmware_history.db",
        base_dir / "instance" / "vmware_history.db",
    ]

    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate

    raise FileNotFoundError("Aucune base SQLite vmware_history.db trouvee.")


def backup_database() -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    source = find_database()
    backups_dir = base_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backups_dir / f"{source.stem}_{timestamp}{source.suffix}"
    shutil.copy2(source, destination)
    return destination


if __name__ == "__main__":
    backup_path = backup_database()
    print(f"Sauvegarde creee: {backup_path}")
