import re
import shutil
import unicodedata
from pathlib import Path

import pandas as pd

# backups de tweets creados por merge/clean/restore: {name}_prev_<YYYYMMDD-HHMMSS>.csv
_BACKUP_RE = re.compile(r"^(?P<name>.+)_prev_(?P<stamp>\d{8}-\d{6})\.csv$")


def datasets_with_backups(project_dir: Path) -> list[str]:
    """Nombres de datasets que tienen alguna versión anterior (_prev_) restaurable."""
    names = {m.group("name") for f in project_dir.glob("*_prev_*.csv")
             if (m := _BACKUP_RE.match(f.name))}
    return sorted(names)


def dataset_backups(project_dir: Path, name: str) -> list[Path]:
    """Backups _prev_ de un dataset, del más reciente al más antiguo."""
    files = [f for f in project_dir.glob(f"{name}_prev_*.csv")
             if (m := _BACKUP_RE.match(f.name)) and m.group("name") == name]
    return sorted(files, key=lambda f: f.name, reverse=True)


def restore_dataset(project_dir: Path, name: str, backup_filename: str, log=print) -> tuple:
    """Restaura {name}.csv desde uno de sus backups _prev_. Antes respalda el actual
    (restore reversible) y anota la operación restore_dataset en el log de contexto.
    Devuelve (path, total_tweets)."""
    import context

    backup = project_dir / backup_filename
    if not backup.exists():
        raise FileNotFoundError(f"Backup {backup_filename} does not exist")

    _backup_dataset(project_dir, name, log=log)  # respalda el actual si existe
    current = project_dir / f"{name}.csv"
    shutil.copy(backup, current)
    total = len(pd.read_csv(current, encoding="utf-8"))

    log_type = context.dataset_log_type(project_dir, name) or "search"
    context.log_restore_dataset(project_dir, name, log_type, backup_filename, total)
    log(f"Dataset '{name}' restored from {backup_filename} ({total} tweets)")
    return current, total

_NEWLINES = re.compile(r"[\n\r]+")


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def clean_text(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["text"] = df["text"].astype(str).str.replace(_NEWLINES, " ", regex=True)
    df["user_displayname"] = df["user_displayname"].astype(str).str.replace(_NEWLINES, " ", regex=True)
    df["location"] = df["location"].astype(str).str.replace(_NEWLINES, " ", regex=True)
    return df


def clean_tweets(df: pd.DataFrame, since, until) -> pd.DataFrame:
    df = clean_text(df)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["id"] = df["url"].str.extract(r".*status/(\d+)")
    df["user_id"] = df["user_id"].astype(str)

    df = df.drop_duplicates(subset="url", keep="first")
    df = df.sort_values("date")

    since = pd.Timestamp(since, tz="UTC") if pd.Timestamp(since).tz is None else pd.Timestamp(since)
    until = pd.Timestamp(until, tz="UTC") if pd.Timestamp(until).tz is None else pd.Timestamp(until)
    df = df[(df["date"] >= since) & (df["date"] <= until)]

    return df


def merge_datasets(project_dir: Path, datasets: list[str], dest: str, log=print) -> Path:
    """Une los tweets de varios datasets del proyecto en uno nuevo, quitando
    duplicados por 'id' (o 'url'). Los datasets son nombres (sin extensión); se
    lee {dataset}.csv de cada uno, y deben tener las mismas columnas.

    Si el dataset destino ya existe (p.ej. es uno de los que se unen), su versión
    anterior se guarda con sufijo _prev_<fecha> antes de sobrescribirla. Además se
    crea un fichero de contexto {dest}_merge_context.csv con la procedencia.
    """
    import context

    if len(datasets) < 2:
        raise ValueError("At least 2 datasets are needed to merge")

    paths = {ds: project_dir / f"{ds}.csv" for ds in datasets}
    missing = [ds for ds, p in paths.items() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Not found in the project: {', '.join(ds + '.csv' for ds in missing)}")

    # el dataset combinado hereda el tipo (search/users) de sus orígenes: deben
    # ser del mismo tipo, si no las operaciones de Charts no encajan
    types = {context.dataset_log_type(project_dir, ds) for ds in datasets}
    present = {t for t in types if t}
    if len(present) > 1:
        raise ValueError("Cannot merge datasets of different types (search and users); merge datasets of the same type")
    log_type = present.pop() if present else "search"

    dfs = {ds: pd.read_csv(p, encoding="utf-8") for ds, p in paths.items()}
    ref_ds, ref_df = next(iter(dfs.items()))
    # las columnas about_* (Tools > About accounts) son opcionales: un dataset
    # enriquecido se puede unir con otro que no lo esté (quedan vacías)
    def _base_cols(df):
        return {c for c in df.columns if not c.startswith(ABOUT_PREFIX)}

    ref_cols = _base_cols(ref_df)
    mismatched = [ds for ds, df in dfs.items() if _base_cols(df) != ref_cols]
    if mismatched:
        raise ValueError(f"Columns do not match {ref_ds}.csv in: {', '.join(mismatched)}")

    log(f"Merging {len(datasets)} datasets...")
    merged = pd.concat(dfs.values(), ignore_index=True)
    total_raw = len(merged)
    key = "id" if "id" in merged.columns else ("url" if "url" in merged.columns else None)
    if key:
        merged = merged.drop_duplicates(subset=key, keep="first")
    log(f"Tweets: {total_raw} -> {len(merged)} after removing duplicates")

    # si el destino ya existe (típicamente porque es uno de los datasets unidos),
    # se guarda la versión anterior antes de sobrescribir para no perderla
    _backup_dataset(project_dir, dest, log=log)
    dest_path = project_dir / f"{dest}.csv"
    merged.to_csv(dest_path, index=False, encoding="utf-8")
    context.log_merge_datasets(project_dir, dest, log_type, datasets, len(merged))
    log(f"Merged dataset '{dest}' in {dest_path.name} ({len(merged)} tweets, from: {', '.join(datasets)})")
    return dest_path


def _backup_dataset(project_dir: Path, name: str, log=print) -> None:
    """Si {name}.csv existe, guarda su versión anterior como {name}_prev_<fecha>.csv
    antes de sobrescribirla (para no perder los tweets anteriores). El contexto no se
    respalda: es un log append-only y conserva la historia por sí mismo."""
    from datetime import datetime

    dest_path = project_dir / f"{name}.csv"
    if not dest_path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest_path.rename(project_dir / f"{name}_prev_{stamp}.csv")
    log(f"Destination dataset already existed; previous version saved as {name}_prev_{stamp}.csv")


# Esquema canónico de un dataset de tweets t-hoarder-twscrape (orden estable) y el
# valor por defecto de cada columna al importar de otra herramienta. Debe coincidir
# con scripts/scraping.py:_tweet_to_dict y especificaciones/metadatos.txt.
_IMPORT_DEFAULTS = {
    "id": "", "date": "", "username": "", "text": "", "source": "",
    "lang": "und", "reply_count": 0, "retweet_count": 0, "like_count": 0,
    "quote_count": 0, "views_count": 0, "in_reply_to_user_id_str": "",
    "in_reply_to_user_username": "", "in_reply_to_tweet_id_str": "",
    "conversation_id_str": "", "is_quote_status": False,
    "quoted_tweet_username": "", "quoted_tweet_url": "", "user_id": "",
    "user_displayname": "", "followers_count": 0, "friends_count": 0,
    "statuses_count": 0, "favourites_count": 0, "listed_count": 0,
    "location": "", "created_at": "", "user_verified": False,
    "is_blue_verified": False, "verified_type": "", "expanded_url": "",
    "media": "", "url": "",
}
_CANON_COLS = list(_IMPORT_DEFAULTS)
# columnas mínimas que el dataset de origen DEBE traer (el resto se rellena)
_IMPORT_REQUIRED = [
    "id", "date", "username", "text", "reply_count", "retweet_count",
    "like_count", "quote_count", "views_count", "user_id", "url",
]


def import_dataset(project_dir: Path, source, dest: str, kind: str | None = None,
                   log=print) -> tuple:
    """Importa un dataset externo (extraído con otra herramienta, p.ej. el de Barri)
    al formato t-hoarder-twscrape, dentro del proyecto activo.

    source: ruta al CSV / CSV.gz a importar.
    dest:   nombre del dataset destino (prefijo). Se guarda como {dest}.csv.
    kind:   'search' (tweets) | 'users' (TL de usuario) | None (autodetecta:
            1 usuario distinto -> users, varios -> search).

    - Exige al menos las columnas mínimas (_IMPORT_REQUIRED); el resto del esquema
      canónico se rellena con su valor por defecto.
    - Lee los ids como TEXTO y comprueba que id/user_id son solo dígitos (rechaza la
      corrupción float/científica del tipo '1.2e18' o '123.0'); descarta filas con
      'id' no numérico.
    - Normaliza 'date' a 'YYYY-MM-DD HH:MM:SS+00:00' (UTC); descarta fechas no
      parseables.
    - Genera el fichero de contexto (search/users) que marca el tipo del dataset.

    Devuelve (dest_path, total_importados, kind).
    """
    import context

    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Source dataset not found: {source}")
    if kind not in (None, "search", "users"):
        raise ValueError("kind must be 'search', 'users' or None (autodetect)")

    # leer TODO como texto: evita que pandas convierta los ids a float (y los
    # corrompa). keep_default_na=False para no convertir vacíos en NaN.
    df = pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8")
    log(f"Read {len(df)} rows from {source.name}")

    missing_req = [c for c in _IMPORT_REQUIRED if c not in df.columns]
    if missing_req:
        raise ValueError("Source dataset is missing required columns: "
                         + ", ".join(missing_req))

    # construir el df en el esquema canónico, rellenando las columnas ausentes
    out = pd.DataFrame(index=df.index)
    filled = []
    for col, default in _IMPORT_DEFAULTS.items():
        if col in df.columns:
            out[col] = df[col].astype(str)
        else:
            out[col] = default
            filled.append(col)
    if filled:
        log(f"Columns absent in source, filled with defaults: {', '.join(filled)}")

    # 'id' de mensaje: obligatorio y numérico-como-texto (no float/científica)
    id_ok = out["id"].str.strip().str.fullmatch(r"\d+")
    if int((~id_ok).sum()):
        corrupt = out.loc[~id_ok, "id"].str.strip()
        ej = corrupt[corrupt != ""].unique()[:5].tolist()
        log(f"WARNING: dropping {int((~id_ok).sum())} rows with non-numeric 'id'"
            + (f" (e.g. {ej})" if ej else " (empty)"))
        out = out[id_ok].copy()

    # 'user_id': solo aviso si hay corrupción (no se descartan filas)
    uid = out["user_id"].str.strip()
    uid_bad = (uid != "") & ~uid.str.fullmatch(r"\d+")
    if int(uid_bad.sum()):
        ej = uid[uid_bad].unique()[:5].tolist()
        log(f"WARNING: 'user_id' has {int(uid_bad.sum())} non-numeric values "
            f"(possible float/scientific corruption), e.g. {ej}")

    # normalizar fechas a UTC 'YYYY-MM-DD HH:MM:SS+00:00'. format="mixed" infiere el
    # formato por elemento (admite ISO con 'Z', con espacio, solo-día, etc.).
    dt = pd.to_datetime(out["date"], utc=True, errors="coerce", format="mixed")
    if int(dt.isna().sum()):
        log(f"Dropping {int(dt.isna().sum())} rows with unparseable date")
    out = out[dt.notna()].copy()
    out["date"] = dt[dt.notna()].dt.strftime("%Y-%m-%d %H:%M:%S+00:00")

    if out.empty:
        raise ValueError("No valid rows to import after validation")

    # tipo: en un TL los tweets van en BLOQUES por usuario (todo un usuario, luego
    # otro, y así); en una búsqueda los usuarios van salpicados. Medimos la fracción
    # de filas consecutivas del MISMO usuario: alta -> bloques (users); baja ->
    # search. (Se usa el orden del fichero de origen, que conserva esa estructura.)
    if kind is None:
        u = out["username"].to_numpy()
        if len(u) >= 2:
            same_frac = float((u[1:] == u[:-1]).mean())
            kind = "users" if same_frac >= 0.5 else "search"
            log(f"Detected type: {kind} (same-user adjacency {same_frac:.2f}, "
                f"{out['username'].nunique()} distinct users)")
        else:
            kind = "users"
            log("Detected type: users (single row)")

    # guardar en el proyecto activo (respaldando el destino si ya existe)
    _backup_dataset(project_dir, dest, log=log)
    dest_path = project_dir / f"{dest}.csv"
    out.reindex(columns=_CANON_COLS).to_csv(dest_path, index=False, encoding="utf-8")

    context.log_import_dataset(project_dir, dest, kind, str(source), len(out))
    log(f"Imported dataset '{dest}' ({len(out)} tweets, type {kind}) "
        f"from {source.name} -> {dest_path.name}")
    return dest_path, len(out), kind


def clean_dataset(project_dir: Path, source: str, dest: str,
                  langs: list[str] | None = None, positives: list[str] | None = None,
                  false_positives: list[str] | None = None, log=print) -> tuple:
    """Filtra el dataset {source}.csv por idioma y/o palabras clave y lo guarda como
    {dest}.csv.

    langs: lista de códigos de idioma a conservar (ej. ['es', 'ca']). Vacío/None = no filtra.
    positives/false_positives: comparación insensible a mayúsculas y a acentos
    (ej. 'sanchez' coincide con 'Sánchez').

    Si el dataset destino ya existe (típicamente porque es el mismo que el origen,
    limpieza in situ), su versión anterior se guarda antes de sobrescribir; al log
    de contexto se le añade la operación clean_dataset (de qué dataset viene y con
    qué criterios), que hace que el dataset limpio aparezca en las listas.

    Devuelve (output_path, total_before, total_after, discarded_df): los tweets
    descartados (los del origen que no pasan el filtro), ordenados por RTs.
    """
    import context

    input_file = project_dir / f"{source}.csv"
    if not input_file.exists():
        raise FileNotFoundError(f"{input_file.name} does not exist in the project")

    df_source = pd.read_csv(input_file, encoding="utf-8")
    total_before = len(df_source)
    df = df_source

    if langs:
        df = df[df["lang"].isin(langs)]
        log(f"After filtering by language {langs}: {len(df)} tweets")

    if positives or false_positives:
        text_normalized = df["text"].astype(str).map(_strip_accents)

    if positives:
        pattern = "|".join(re.escape(_strip_accents(w.strip())) for w in positives if w.strip())
        if pattern:
            df = df[text_normalized.str.contains(pattern, case=False, na=False, regex=True)]
            text_normalized = text_normalized[df.index]
            log(f"After filtering by positives {positives}: {len(df)} tweets")

    if false_positives:
        pattern = "|".join(re.escape(_strip_accents(w.strip())) for w in false_positives if w.strip())
        if pattern:
            df = df[~text_normalized.str.contains(pattern, case=False, na=False, regex=True)]
            log(f"After excluding false positives {false_positives}: {len(df)} tweets")

    # el dataset limpio hereda el tipo (search/users) de su origen
    log_type = context.dataset_log_type(project_dir, source) or "search"

    # el df ya está en memoria, así que se puede respaldar/sobrescribir el destino
    # aunque sea el mismo fichero de origen (limpieza in situ); el contexto no se
    # respalda, se le añade la operación clean_dataset y conserva la historia
    _backup_dataset(project_dir, dest, log=log)

    output_path = project_dir / f"{dest}.csv"
    df.to_csv(output_path, index=False, encoding="utf-8")
    context.log_clean_dataset(project_dir, dest, log_type, source, langs, positives,
                              false_positives, total_before, len(df))
    log(f"Cleaned dataset '{dest}' in {output_path.name} ({total_before} -> {len(df)} tweets, from: {source})")

    # tweets descartados: los del origen que no han pasado el filtro (los índices
    # de un filtrado booleano se conservan, así que basta con la diferencia)
    discarded = df_source.loc[df_source.index.difference(df.index)]
    if "retweet_count" in discarded.columns:
        discarded = discarded.sort_values("retweet_count", ascending=False)
    return output_path, total_before, len(df), discarded
    return output_path


def _normalize_key(text: str) -> str:
    return _strip_accents(text).lower().strip()


_ASCII_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .\-]+$")
_LOCATION_SPLIT_RE = re.compile(r"[,/|()]+")
_PART_CLEAN_RE = re.compile(r"[^a-z' .\-]+")

_geo_lookup_cache = None

# geonamescache solo da los nombres de país en inglés; se añaden los nombres en
# español más habituales en biografías de Twitter para no perderlos.
_COUNTRY_ALIASES_ES = {
    "españa": "Spain", "estados unidos": "United States", "eeuu": "United States",
    "ee.uu.": "United States", "usa": "United States", "us": "United States",
    "mexico": "Mexico", "méxico": "Mexico",
    "argentina": "Argentina", "colombia": "Colombia", "chile": "Chile",
    "peru": "Peru", "perú": "Peru", "venezuela": "Venezuela", "ecuador": "Ecuador",
    "bolivia": "Bolivia", "paraguay": "Paraguay", "uruguay": "Uruguay", "cuba": "Cuba",
    "republica dominicana": "Dominican Republic", "guatemala": "Guatemala",
    "honduras": "Honduras", "el salvador": "El Salvador", "nicaragua": "Nicaragua",
    "costa rica": "Costa Rica", "panama": "Panama", "panamá": "Panama",
    "puerto rico": "Puerto Rico", "francia": "France", "alemania": "Germany",
    "italia": "Italy", "reino unido": "United Kingdom", "inglaterra": "United Kingdom",
    "portugal": "Portugal", "brasil": "Brazil", "marruecos": "Morocco",
    "paises bajos": "Netherlands", "holanda": "Netherlands", "suiza": "Switzerland",
    "belgica": "Belgium", "bélgica": "Belgium", "suecia": "Sweden", "noruega": "Norway",
    "dinamarca": "Denmark", "irlanda": "Ireland", "grecia": "Greece", "rusia": "Russia",
    "turquia": "Turkey", "turquía": "Turkey", "china": "China", "japon": "Japan",
    "japón": "Japan", "india": "India", "canada": "Canada", "canadá": "Canada",
    "australia": "Australia", "egipto": "Egypt", "polonia": "Poland", "austria": "Austria",
}

# Nombres de estados de EEUU, para que "Ciudad, Estado" (ej. "Toledo, Ohio")
# se reconozca como Estados Unidos aunque el país no se mencione literalmente.
_US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
]
for _state in _US_STATES:
    _COUNTRY_ALIASES_ES[_state] = "United States"

# Comunidades autónomas de España (con variantes en catalán/euskera/gallego y sin
# acentos), ya que geonamescache no da regiones/admin1 por nombre. Si el texto
# menciona una, se asume país España aunque no se mencione explícitamente.
_SPAIN_REGIONS = {
    "andalucia": "Andalucía",
    "aragon": "Aragón",
    "asturias": "Asturias", "principado de asturias": "Asturias",
    "baleares": "Islas Baleares", "islas baleares": "Islas Baleares", "illes balears": "Islas Baleares",
    "canarias": "Canarias", "islas canarias": "Canarias",
    "cantabria": "Cantabria",
    "castilla y leon": "Castilla y León",
    "castilla-la mancha": "Castilla-La Mancha", "castilla la mancha": "Castilla-La Mancha",
    "catalunya": "Cataluña", "cataluna": "Cataluña", "catalonia": "Cataluña",
    "comunidad valenciana": "Comunidad Valenciana", "pais valenciano": "Comunidad Valenciana",
    "comunitat valenciana": "Comunidad Valenciana",
    "extremadura": "Extremadura",
    "galicia": "Galicia", "galiza": "Galicia",
    "comunidad de madrid": "Comunidad de Madrid",
    "murcia": "Región de Murcia", "region de murcia": "Región de Murcia",
    "navarra": "Navarra", "nafarroa": "Navarra", "comunidad foral de navarra": "Navarra",
    "pais vasco": "País Vasco", "euskadi": "País Vasco", "euskal herria": "País Vasco",
    "la rioja": "La Rioja",
    "ceuta": "Ceuta",
    "melilla": "Melilla",
}


def _build_geo_lookup() -> tuple[dict, dict]:
    """Construye los diccionarios de búsqueda offline (sin red) a partir de geonamescache:
    nombre normalizado -> país, y nombre normalizado -> (poblacion, ciudad, pais).
    Solo se construye una vez por proceso."""
    global _geo_lookup_cache
    if _geo_lookup_cache is not None:
        return _geo_lookup_cache

    import geonamescache
    gc = geonamescache.GeonamesCache()

    countries = gc.get_countries()
    countrycode_to_name = {code: c["name"] for code, c in countries.items()}
    country_lookup = {_normalize_key(c["name"]): c["name"] for c in countries.values()}
    for alias, name in _COUNTRY_ALIASES_ES.items():
        country_lookup.setdefault(_normalize_key(alias), name)

    # Cada clave puede mapear a varias ciudades homónimas en distintos países
    # (ej. "Valencia" en España y en Venezuela); se guardan todas para poder
    # desambiguar por país cuando el texto lo menciona explícitamente.
    city_lookup: dict[str, list[tuple[int, str, str | None]]] = {}
    for city in gc.get_cities().values():
        country_name = countrycode_to_name.get(city["countrycode"])
        names = {city["name"]}
        for variant in city.get("alternatenames", []):
            if variant and _ASCII_NAME_RE.match(variant) and len(variant) >= 4:
                names.add(variant)
        population = city.get("population", 0) or 0
        for name in names:
            key = _normalize_key(name)
            if not key:
                continue
            entries = city_lookup.setdefault(key, [])
            if not any(country_name == c for _, _, c in entries):
                entries.append((population, city["name"], country_name))

    _geo_lookup_cache = (country_lookup, city_lookup)
    return _geo_lookup_cache


def geocode_location_offline(location: str) -> tuple[str | None, str | None, str | None]:
    """Resuelve país/región/ciudad a partir de texto libre, sin consultas a servicios externos,
    usando la lista de países y ciudades por población de geonamescache. La región no siempre
    se puede determinar (geonames no la da de forma fiable salvo para algunos países) y se deja
    en None en ese caso."""
    if not location or not str(location).strip():
        return None, None, None

    country_lookup, city_lookup = _build_geo_lookup()

    normalized = _normalize_key(str(location))
    parts = [p.strip() for p in _LOCATION_SPLIT_RE.split(normalized) if p.strip()]
    candidates = parts + [normalized]
    # quita signos sueltos (puntos, emoji, etc.) que dejarían una clave sin match
    candidates += [_PART_CLEAN_RE.sub("", p).strip() for p in candidates]
    candidates = [c for c in dict.fromkeys(candidates) if c]

    matched_country = None
    matched_region = None
    city_matches = []  # [(population, city_name, country_name), ...]
    for part in candidates:
        if matched_country is None and part in country_lookup:
            matched_country = country_lookup[part]
        if matched_region is None and part in _SPAIN_REGIONS:
            matched_region = _SPAIN_REGIONS[part]
            if matched_country is None:
                matched_country = "Spain"
        if part in city_lookup:
            city_matches.extend(city_lookup[part])

    if city_matches:
        # Si el texto menciona un país explícito, se prioriza la ciudad de ese país
        # (ej. "Valencia, España" debe resolver a España y no a Valencia, Venezuela).
        # Si esa ciudad no existe en geonamescache para el país mencionado, se respeta
        # el país del texto y no se cuela una ciudad homónima de otro país
        # (ej. "Andalucía, España" no debe acabar resolviendo a Colombia).
        if matched_country:
            same_country = [c for c in city_matches if c[2] == matched_country]
            if same_country:
                _, city_name, country_name = max(same_country, key=lambda c: c[0])
                return country_name, matched_region, city_name
            return matched_country, matched_region, None
        # Sin país explícito en el texto, una ciudad homónima de España se prioriza
        # sobre otras de mayor población (ej. "Toledo" no debe asumir Estados Unidos),
        # ya que el corpus de este proyecto es mayoritariamente de Twitter en español.
        spain_matches = [c for c in city_matches if c[2] == "Spain"]
        _, city_name, country_name = max(spain_matches or city_matches, key=lambda c: c[0])
        return country_name, matched_region, city_name
    if matched_country is not None:
        return matched_country, matched_region, None
    return None, None, None


def extract_locations(project_dir: Path, prefix: str, log=print) -> Path:
    """Extrae los perfiles con localización en su biografía de {prefix}.csv (y, si existen,
    {prefix}_RTs.csv y {prefix}_replies_advanced.csv para cubrir también a los usuarios
    retuiteados/replicados) y resuelve país/región/ciudad de forma offline (sin red).

    Genera {prefix}_loc.csv con username, location, location_country, location_region,
    location_city, solo para los perfiles que tienen localización en su biografía y cuyo
    país se ha podido resolver.
    """
    tweets_file = project_dir / f"{prefix}.csv"
    if not tweets_file.exists():
        raise FileNotFoundError(f"{tweets_file.name} does not exist")

    frames = [pd.read_csv(tweets_file, encoding="utf-8")]

    rts_file = project_dir / f"{prefix}_RTs.csv"
    if rts_file.exists():
        rts_df = pd.read_csv(rts_file, encoding="utf-8")
        if "location" in rts_df.columns:
            frames.append(rts_df[["username", "location"]])

    replies_file = project_dir / f"{prefix}_replies_advanced.csv"
    if replies_file.exists():
        replies_df = pd.read_csv(replies_file, encoding="utf-8")
        if "location" in replies_df.columns:
            frames.append(replies_df[["username", "location"]])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["username"]).drop_duplicates(subset="username", keep="first")
    combined = combined[combined["location"].notna() & (combined["location"].astype(str).str.strip() != "")]
    log(f"Profiles with location in their bio: {len(combined)}")

    countries, regions, cities = [], [], []
    cache: dict[str, tuple] = {}
    for loc in combined["location"]:
        if loc not in cache:
            cache[loc] = geocode_location_offline(loc)
        c = cache[loc]
        countries.append(c[0])
        regions.append(c[1])
        cities.append(c[2])

    result = combined[["username", "location"]].copy()
    result["location_country"] = countries
    result["location_region"] = regions
    result["location_city"] = cities

    n_total = len(result)
    # Se descartan las localizaciones que no resolvieron a un país real
    # (texto sin sentido geográfico, ej. "Everywhere", "Mundo", etc.)
    result = result[result["location_country"].notna()]
    log(f"Locations resolved to a real country: {len(result)}/{n_total}")

    output_path = project_dir / f"{prefix}_loc.csv"
    result.to_csv(output_path, index=False, encoding="utf-8")
    return output_path


# Columnas de la página x.com/{user}/about (descargadas en Download > About como
# {prefix}_about.csv) que Tools > About accounts añade al final de {dataset}.csv (al
# final para que las descargas incrementales, que añaden filas sin cabecera, sigan
# encajando por posición).
ABOUT_PREFIX = "about_"


def add_about_to_dataset(project_dir: Path, prefix: str, log=print) -> Path:
    """Añade a {prefix}.csv las columnas about_* de {prefix}_about.csv, unidas por
    user_id (los autores sin fila en _about quedan vacíos). Si el dataset ya las
    tenía se sustituyen. Respalda el dataset (_prev_) y anota la operación
    add_about en su log de contexto; si no cambia nada no reescribe ni anota."""
    import context

    tweets_file = project_dir / f"{prefix}.csv"
    about_file = project_dir / f"{prefix}_about.csv"
    for f in (tweets_file, about_file):
        if not f.exists():
            raise FileNotFoundError(f"{f.name} does not exist")
    df = pd.read_csv(tweets_file, encoding="utf-8", dtype=str)  # texto: se reescribe tal cual
    about = (pd.read_csv(about_file, encoding="utf-8", dtype=str)
               .drop(columns="username").drop_duplicates(subset="user_id", keep="last"))
    about_cols = [c for c in about.columns if c.startswith(ABOUT_PREFIX)]

    base = df.drop(columns=[c for c in df.columns if c.startswith(ABOUT_PREFIX)])
    out = base.merge(about, on="user_id", how="left")[list(base.columns) + about_cols]

    def _norm(d):
        return d.astype(object).where(d.notna(), None).astype(str)

    if list(df.columns) == list(out.columns) and _norm(df).equals(_norm(out)):
        log(f"{tweets_file.name} already has the about columns of {about_file.name}")
        return tweets_file

    users = base["user_id"].dropna().unique()
    status = (about.loc[about["user_id"].isin(users), "about_status"]
                   .value_counts().to_dict())
    n_missing = len(users) - int(about["user_id"].isin(users).sum())
    log(f"Authors with about data: {len(users) - n_missing}/{len(users)} "
        f"({', '.join(f'{k}={v}' for k, v in status.items())})")

    _backup_dataset(project_dir, prefix, log=log)
    out.to_csv(tweets_file, index=False, encoding="utf-8")
    context.log_add_about(project_dir, prefix, context.dataset_log_type(project_dir, prefix) or "search",
                          about_file.name, len(users), len(users) - n_missing, status, len(out))
    log(f"Added {len(about_cols)} about_* columns to {tweets_file.name}")
    return tweets_file
