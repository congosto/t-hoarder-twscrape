import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
INACTIVE_DIR = DATA_DIR / "desactivated"


def _validate_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("El nombre del proyecto no puede estar vacío")
    if any(c in name for c in r'\/:*?"<>|'):
        raise ValueError("El nombre del proyecto contiene caracteres no válidos")
    return name


def new_project(name: str) -> Path:
    name = _validate_name(name)
    project_dir = DATA_DIR / name

    if project_dir.exists():
        raise FileExistsError(f"El proyecto '{name}' ya existe")
    if (INACTIVE_DIR / name).exists():
        raise FileExistsError(f"El proyecto '{name}' existe pero está desactivado")

    project_dir.mkdir(parents=True)
    return project_dir


def list_active_projects() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(
        p.name for p in DATA_DIR.iterdir()
        if p.is_dir() and p.name != "desactivated"
    )


def list_inactive_projects() -> list[str]:
    if not INACTIVE_DIR.exists():
        return []
    return sorted(p.name for p in INACTIVE_DIR.iterdir() if p.is_dir())


def select_project(name: str) -> Path:
    project_dir = DATA_DIR / name
    if not project_dir.is_dir():
        raise FileNotFoundError(f"El proyecto '{name}' no existe o no está activo")
    return project_dir


def deactivate_project(name: str) -> None:
    project_dir = DATA_DIR / name
    if not project_dir.is_dir():
        raise FileNotFoundError(f"El proyecto '{name}' no existe o no está activo")

    INACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(project_dir), str(INACTIVE_DIR / name))
