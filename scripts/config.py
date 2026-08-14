"""Rutas locales de la app.

`accounts.db` (la BD de cuentas de twscrape) se guarda POR DEFECTO donde siempre
(`accounts.db` junto a la app), para que el usuario normal no tenga que hacer
nada. Ruta única compartida por accounts.py y scraping.py.

Comportamiento:
  - Si existe la variable de entorno THOARDER_ACCOUNTS_DB, se toma como el
    DIRECTORIO donde vivirá `accounts.db` (se crea si no existe).
  - Si no existe, se usa la ubicación actual (`accounts.db`, junto a la app).

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


def _accounts_db_path() -> str:
    directory = os.environ.get("THOARDER_ACCOUNTS_DB")
    if directory:
        d = Path(directory).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return str(d / DB_FILENAME)
    return DB_FILENAME


ACCOUNTS_DB = _accounts_db_path()
