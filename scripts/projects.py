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


def _last_activity(path: Path) -> float:
    """Fecha de actividad de un proyecto: el mtime más reciente entre el
    directorio y sus ficheros de primer nivel (así descargar datos cuenta
    como actividad, no solo crear el proyecto)."""
    times = [path.stat().st_mtime]
    try:
        times.extend(f.stat().st_mtime for f in path.iterdir())
    except OSError:
        pass
    return max(times)


def list_active_projects() -> list[str]:
    """Proyectos activos, del de actividad más reciente al más antiguo."""
    if not DATA_DIR.exists():
        return []
    dirs = [p for p in DATA_DIR.iterdir() if p.is_dir() and p.name != "desactivated"]
    return [p.name for p in sorted(dirs, key=_last_activity, reverse=True)]


def list_inactive_projects() -> list[str]:
    """Proyectos desactivados, del de actividad más reciente al más antiguo."""
    if not INACTIVE_DIR.exists():
        return []
    dirs = [p for p in INACTIVE_DIR.iterdir() if p.is_dir()]
    return [p.name for p in sorted(dirs, key=_last_activity, reverse=True)]


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
