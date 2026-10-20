"""Rutas locales de la app.

`accounts.db` (la BD de cuentas de twscrape) se guarda POR DEFECTO donde siempre
(`accounts.db` en la raíz del proyecto), para que el usuario normal no tenga que
hacer nada. Ruta única compartida por accounts.py y scraping.py.

Comportamiento:
  - Si existe la variable de entorno THOARDER_ACCOUNTS_DB, se toma como el
    DIRECTORIO donde vivirá `accounts.db` (se crea si no existe).
  - Si no existe, se usa `accounts.db` en la raíz del proyecto. La ruta es
    absoluta: antes era relativa y dependía de la carpeta desde la que se
    arrancaba la app (desde `app/` acababa en `app/accounts.db`).
    Migración de esa BD antigua: si en la raíz no hay `accounts.db` y en
    `app/` sí, se mueve a la raíz; si hay en los dos sitios, se usa la de la
    raíz y ACCOUNTS_DB_WARNING lleva un aviso para mostrarlo en la app.

Motivo del override: quien tenga la carpeta del proyecto en un sincronizador
(Dropbox/OneDrive) puede sufrir `sqlite3.OperationalError: disk I/O error` en
descargas con muchas escrituras a la BD (p. ej. Retweets, que bloquea/desbloquea
cuentas una vez por tweet): el sincronizador retiene el fichero y su journal y el
`commit` de SQLite falla. Apuntar THOARDER_ACCOUNTS_DB a una carpeta fuera del
sincronizador lo resuelve. Es opcional; sin ella todo sigue igual que antes.
"""
import os
from pathlib import Path

DB_FILENAME = "accounts.db"
REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_DB = REPO_ROOT / "app" / DB_FILENAME
ACCOUNTS_DB_WARNING = None


def _migrate_legacy_db(target: Path) -> Path:
    """Mueve app/accounts.db a la raíz si es la única BD; devuelve la que se usará."""
    global ACCOUNTS_DB_WARNING
    if not LEGACY_DB.exists():
        return target
    if target.exists():
        ACCOUNTS_DB_WARNING = (
            f"There is another accounts database at {LEGACY_DB} (left by older versions "
            f"when the app was started from the app folder). The app uses {target}. "
            "If accounts are missing, add them again in Settings > New Account and "
            "then delete the old file."
        )
        return target
    try:
        os.replace(LEGACY_DB, target)
    except OSError as e:
        # Probablemente abierta por otra instancia de la app: se usa donde está
        ACCOUNTS_DB_WARNING = (
            f"Could not move {LEGACY_DB} to {target} ({e}). Using it from its old "
            "location for now; close other running instances of the app and restart."
        )
        return LEGACY_DB
    return target


def _accounts_db_path() -> str:
    directory = os.environ.get("THOARDER_ACCOUNTS_DB")
    if directory:
        d = Path(directory).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return str(d / DB_FILENAME)
    return str(_migrate_legacy_db(REPO_ROOT / DB_FILENAME))


ACCOUNTS_DB = _accounts_db_path()
