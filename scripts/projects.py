import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
INACTIVE_DIR = DATA_DIR / "desactivated"


def _validate_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Project name cannot be empty")
    if any(c in name for c in r'\/:*?"<>|'):
        raise ValueError("Project name contains invalid characters")
    return name


def new_project(name: str) -> Path:
    name = _validate_name(name)
    project_dir = DATA_DIR / name

    if project_dir.exists():
        raise FileExistsError(f"Project '{name}' already exists")
    if (INACTIVE_DIR / name).exists():
        raise FileExistsError(f"Project '{name}' exists but is deactivated")

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
        raise FileNotFoundError(f"Project '{name}' does not exist or is not active")
    return project_dir


def deactivate_project(name: str) -> None:
    """No borra el proyecto: lo mueve de data/{name} a data/desactivated/{name}."""
    project_dir = DATA_DIR / name
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project '{name}' does not exist or is not active")

    INACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(project_dir), str(INACTIVE_DIR / name))


def reactivate_project(name: str) -> Path:
    """Vuelve a activar un proyecto desactivado: lo mueve de data/desactivated/{name}
    de vuelta a data/{name}."""
    inactive_dir = INACTIVE_DIR / name
    if not inactive_dir.is_dir():
        raise FileNotFoundError(f"Project '{name}' is not deactivated")
    project_dir = DATA_DIR / name
    if project_dir.exists():
        raise FileExistsError(f"An active project named '{name}' already exists")

    shutil.move(str(inactive_dir), str(project_dir))
    return project_dir
