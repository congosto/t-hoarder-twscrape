import re
import unicodedata
from pathlib import Path

import pandas as pd

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


def merge_files(project_dir: Path, filenames: list[str], output_filename: str, log=print) -> Path:
    """Une varios CSV del mismo proyecto, quitando duplicados por 'id'.

    Todos los ficheros deben existir en project_dir y tener exactamente las
    mismas columnas (mismo formato), si no se rechaza antes de leer nada.
    """
    if len(filenames) < 2:
        raise ValueError("Se necesitan al menos 2 ficheros para unir")

    missing = [f for f in filenames if not (project_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"No existen en el proyecto: {', '.join(missing)}")

    dfs = {}
    for f in filenames:
        dfs[f] = pd.read_csv(project_dir / f, encoding="utf-8")

    reference_file, reference_df = next(iter(dfs.items()))
    reference_columns = set(reference_df.columns)
    mismatched = [f for f, df in dfs.items() if set(df.columns) != reference_columns]
    if mismatched:
        raise ValueError(
            f"Las columnas no coinciden con {reference_file} en: {', '.join(mismatched)}"
        )

    log(f"Uniendo {len(filenames)} ficheros...")
    merged = pd.concat(dfs.values(), ignore_index=True)
    if "id" in merged.columns:
        merged = merged.drop_duplicates(subset="id", keep="first")

    output_path = project_dir / output_filename
    merged.to_csv(output_path, index=False, encoding="utf-8")
    log(f"Tweets totales: {len(merged)}")
    return output_path


def clean_data(project_dir: Path, prefix: str, output_filename: str,
                langs: list[str] | None = None, positives: list[str] | None = None,
                false_positives: list[str] | None = None, log=print) -> Path:
    """Filtra el fichero {prefix}.csv del proyecto por idioma y/o palabras clave.

    langs: lista de códigos de idioma a conservar (ej. ['es', 'ca']). Vacío/None = no filtra.
    positives/false_positives: comparación insensible a mayúsculas y a acentos
    (ej. 'sanchez' coincide con 'Sánchez').
    """
    input_file = project_dir / f"{prefix}.csv"
    if not input_file.exists():
        raise FileNotFoundError(f"No existe {input_file.name} en el proyecto")

    df = pd.read_csv(input_file, encoding="utf-8")

    if langs:
        df = df[df["lang"].isin(langs)]
        log(f"Tras filtrar por idioma {langs}: {len(df)} tweets")

    if positives or false_positives:
        text_normalized = df["text"].astype(str).map(_strip_accents)

    if positives:
        pattern = "|".join(re.escape(_strip_accents(w.strip())) for w in positives if w.strip())
        if pattern:
            df = df[text_normalized.str.contains(pattern, case=False, na=False, regex=True)]
            text_normalized = text_normalized[df.index]
            log(f"Tras filtrar por positivas {positives}: {len(df)} tweets")

    if false_positives:
        pattern = "|".join(re.escape(_strip_accents(w.strip())) for w in false_positives if w.strip())
        if pattern:
            df = df[~text_normalized.str.contains(pattern, case=False, na=False, regex=True)]
            log(f"Tras excluir falsas positivas {false_positives}: {len(df)} tweets")

    output_path = project_dir / output_filename
    df.to_csv(output_path, index=False, encoding="utf-8")
    log(f"Tweets totales: {len(df)}")
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
        raise FileNotFoundError(f"No existe {tweets_file.name}")

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
    log(f"Perfiles con localización en su biografía: {len(combined)}")

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
    log(f"Localizaciones resueltas a un país real: {len(result)}/{n_total}")

    output_path = project_dir / f"{prefix}_loc.csv"
    result.to_csv(output_path, index=False, encoding="utf-8")
    return output_path
