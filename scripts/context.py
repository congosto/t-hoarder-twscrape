"""Contexto de los datasets como log append-only.

Hay dos logs por dataset, según su origen (la distinción importa para Charts):
  {prefix}_search_context.csv  — datasets de historical_search
  {prefix}_users_context.csv   — datasets de historical_timeline

Dentro de cada log se anotan las operaciones según se producen, una fila por
operación, con una columna 'operation' y la unión de los campos:
  download_tweets: last_date, since, until, query, product, frequency
  download_users:  last_date, order, username, since, until, product, frequency
  end_download:    date, total_tweets
  merge_datasets:  date, merged_from, n_datasets, total_tweets
  clean_dataset:   date, cleaned_from, langs, positives, false_positives,
                   total_before, total_after

Un dataset combinado (merge) o limpio (clean) hereda el log de su origen, así
que sigue siendo de tipo 'search' o 'users'. Los cursores de reanudación de
RTs/replies (last_tweet_id) son otra cosa y viven en ficheros aparte.
"""
from datetime import datetime
from pathlib import Path

import pandas as pd

# columnas del log (unión de los campos de todas las operaciones), orden estable
_LOG_COLUMNS = [
    "operation", "last_date", "since", "until", "query", "product", "frequency",
    "order", "username", "date", "total_tweets", "merged_from", "n_datasets",
    "cleaned_from", "langs", "positives", "false_positives", "total_before", "total_after",
]


def _ctx_path(dataset: Path, prefix: str, log_type: str) -> Path:
    return dataset / f"{prefix}_{log_type}_context.csv"


def _ensure_log_format(path: Path, log_type: str) -> None:
    """Convierte un contexto en formato antiguo (una/varias filas sin columna
    'operation') al formato log. Idempotente."""
    if not path.exists():
        return
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    if "operation" in df.columns:
        return
    df.insert(0, "operation", "download_tweets" if log_type == "search" else "download_users")
    df.reindex(columns=_LOG_COLUMNS, fill_value="").to_csv(path, index=False, encoding="utf-8")


def _read_log(dataset: Path, prefix: str, log_type: str) -> pd.DataFrame | None:
    path = _ctx_path(dataset, prefix, log_type)
    if not path.exists():
        return None
    _ensure_log_format(path, log_type)
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    return df.reindex(columns=_LOG_COLUMNS, fill_value="")


def _write_log(path: Path, df: pd.DataFrame) -> None:
    df.reindex(columns=_LOG_COLUMNS, fill_value="").to_csv(path, index=False, encoding="utf-8")


def _record(dataset: Path, prefix: str, log_type: str, row: dict,
            update_if_last_is: str | None = None, upsert_key: str | None = None) -> None:
    """Anota una operación en el log. Con update_if_last_is actualiza la última fila
    si es de esa operación (para que una descarga en curso avance en una sola fila);
    con upsert_key actualiza la fila de esa operación con el mismo valor de clave
    (una fila por usuario). Si no, añade una fila nueva."""
    dataset.mkdir(parents=True, exist_ok=True)
    path = _ctx_path(dataset, prefix, log_type)
    row_full = {c: row.get(c, "") for c in _LOG_COLUMNS}
    df = _read_log(dataset, prefix, log_type)

    if df is not None and len(df):
        if upsert_key is not None:
            mask = (df["operation"] == row["operation"]) & (df[upsert_key] == str(row.get(upsert_key, "")))
            if mask.any():
                df.loc[df.index[mask][-1]] = row_full
                _write_log(path, df)
                return
        elif update_if_last_is is not None and df.iloc[-1]["operation"] == update_if_last_is:
            df.loc[df.index[-1]] = row_full
            _write_log(path, df)
            return

    new = pd.DataFrame([row_full], columns=_LOG_COLUMNS)
    _write_log(path, pd.concat([df, new], ignore_index=True) if df is not None else new)


# ── Anotar operaciones ───────────────────────────────────────────────────────

def log_download_tweets(dataset, prefix, last_date, since, until,
                        query="", product="", frequency="") -> None:
    _record(dataset, prefix, "search", {
        "operation": "download_tweets", "last_date": str(last_date),
        "since": str(since), "until": str(until),
        "query": query, "product": product, "frequency": frequency,
    }, update_if_last_is="download_tweets")


def log_download_users(dataset, prefix, last_date, order, username, since, until,
                       product="", frequency="") -> None:
    _record(dataset, prefix, "users", {
        "operation": "download_users", "last_date": str(last_date), "order": str(order),
        "username": username, "since": str(since), "until": str(until),
        "product": product, "frequency": frequency,
    }, upsert_key="username")


def log_end_download(dataset, prefix, log_type, total_tweets) -> None:
    _record(dataset, prefix, log_type, {
        "operation": "end_download",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_tweets": str(total_tweets),
    })


def log_merge_datasets(dataset, prefix, log_type, sources, total) -> None:
    _record(dataset, prefix, log_type, {
        "operation": "merge_datasets",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "merged_from": ", ".join(sources), "n_datasets": str(len(sources)),
        "total_tweets": str(total),
    })


def log_clean_dataset(dataset, prefix, log_type, source, langs, positives,
                      false_positives, total_before, total_after) -> None:
    _record(dataset, prefix, log_type, {
        "operation": "clean_dataset",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cleaned_from": source,
        "langs": "|".join(langs or []), "positives": "|".join(positives or []),
        "false_positives": "|".join(false_positives or []),
        "total_before": str(total_before), "total_after": str(total_after),
    })


# ── Tipo de log de un dataset (search / users) ───────────────────────────────

def dataset_log_type(dataset: Path, prefix: str) -> str | None:
    if _ctx_path(dataset, prefix, "search").exists():
        return "search"
    if _ctx_path(dataset, prefix, "users").exists():
        return "users"
    return None


# ── Lectura (reanudar descargas y "Cargar contexto") ─────────────────────────

def _last(df: pd.DataFrame, operation: str) -> pd.Series | None:
    sub = df[df["operation"] == operation]
    return None if sub.empty else sub.iloc[-1]


def get_context_search(dataset: Path, prefix: str) -> str | None:
    df = _read_log(dataset, prefix, "search")
    row = _last(df, "download_tweets") if df is not None else None
    return (row["last_date"] or None) if row is not None else None


def get_context_search_range(dataset: Path, prefix: str) -> tuple[str, str] | None:
    df = _read_log(dataset, prefix, "search")
    row = _last(df, "download_tweets") if df is not None else None
    if row is None or not row["since"] or not row["until"]:
        return None
    return row["since"], row["until"]


def get_context_search_full(dataset: Path, prefix: str) -> dict | None:
    df = _read_log(dataset, prefix, "search")
    row = _last(df, "download_tweets") if df is not None else None
    if row is None:
        return None
    return {k: row[k] for k in ("query", "product", "since", "until", "frequency")}


def get_context_user(dataset: Path, prefix: str) -> pd.DataFrame | None:
    df = _read_log(dataset, prefix, "users")
    if df is None:
        return None
    du = df[df["operation"] == "download_users"].copy()
    if du.empty:
        return None
    du["order"] = pd.to_numeric(du["order"], errors="coerce").fillna(0).astype(int)
    return du.groupby("username", as_index=False).tail(1).sort_values("order")


def get_context_user_range(dataset: Path, prefix: str) -> tuple[str, str] | None:
    df = _read_log(dataset, prefix, "users")
    row = _last(df, "download_users") if df is not None else None
    if row is None or not row["since"] or not row["until"]:
        return None
    return row["since"], row["until"]


def get_log(dataset: Path, prefix: str) -> pd.DataFrame | None:
    """Log completo de operaciones del dataset (para mostrar en el panel de
    Contexto), sin las columnas totalmente vacías. None si no tiene log."""
    log_type = dataset_log_type(dataset, prefix)
    if log_type is None:
        return None
    df = _read_log(dataset, prefix, log_type)
    if df is None or df.empty:
        return None
    keep = [c for c in df.columns
            if c == "operation" or (df[c].astype(str).str.strip() != "").any()]
    return df[keep]


def get_context_user_full(dataset: Path, prefix: str) -> dict | None:
    du = get_context_user(dataset, prefix)
    if du is None or du.empty:
        return None
    last = du.iloc[-1]
    return {
        "list_users": ", ".join(du["username"].astype(str)),
        "product": last["product"], "since": last["since"],
        "until": last["until"], "frequency": last["frequency"],
    }


# ── Migración de proyectos con contexto en formato antiguo ───────────────────

def _fold_legacy(dataset: Path, name: str, path: Path, kind: str) -> None:
    """Pliega un fichero suelto {name}_merge_context.csv / _clean_context.csv en el
    log del dataset (heredando su tipo; search por defecto) y lo borra."""
    old = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    if old.empty:
        path.unlink()
        return
    row = old.iloc[-1]
    log_type = dataset_log_type(dataset, name) or "search"
    if kind == "merge":
        sources = [s.strip() for s in str(row.get("merged_from", "")).split(",") if s.strip()]
        log_merge_datasets(dataset, name, log_type, sources, row.get("total_tweets", ""))
    else:
        log_clean_dataset(
            dataset, name, log_type, row.get("cleaned_from", ""),
            [row.get("langs", "")] if row.get("langs") else [],
            [row.get("positives", "")] if row.get("positives") else [],
            [row.get("false_positives", "")] if row.get("false_positives") else [],
            row.get("total_before", ""), row.get("total_after", ""),
        )
    path.unlink()


def migrate_project(dataset: Path) -> None:
    """Convierte los contextos de un proyecto al formato log: añade la columna
    'operation' a los logs antiguos y pliega los contextos merge/clean sueltos.
    Idempotente (no hace nada si ya está migrado)."""
    dataset = Path(dataset)
    if not dataset.exists():
        return
    for path in list(dataset.glob("*_search_context.csv")):
        _ensure_log_format(path, "search")
    for path in list(dataset.glob("*_users_context.csv")):
        _ensure_log_format(path, "users")
    for path in list(dataset.glob("*_merge_context.csv")):
        _fold_legacy(dataset, path.name[: -len("_merge_context.csv")], path, "merge")
    for path in list(dataset.glob("*_clean_context.csv")):
        _fold_legacy(dataset, path.name[: -len("_clean_context.csv")], path, "clean")


# ── Cursores de reanudación de RTs / replies (ficheros aparte) ───────────────

def put_context_replies(dataset: Path, prefix: str, last_tweet_id, kind: str = "replies") -> None:
    dataset.mkdir(parents=True, exist_ok=True)
    context_file = dataset / f"{prefix}_{kind}_context.csv"
    pd.DataFrame({"last_tweet_id": [str(last_tweet_id)]}).to_csv(context_file, index=False, encoding="utf-8")


def get_context_replies(dataset: Path, prefix: str, kind: str = "replies") -> str | None:
    context_file = dataset / f"{prefix}_{kind}_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, dtype={"last_tweet_id": str}, encoding="utf-8")
    return context["last_tweet_id"].iloc[-1]


def put_context_RTs(dataset: Path, prefix: str, last_tweet_id) -> None:
    dataset.mkdir(parents=True, exist_ok=True)
    context_file = dataset / f"{prefix}_RTs_context.csv"
    pd.DataFrame({"last_tweet_id": [str(last_tweet_id)]}).to_csv(context_file, index=False, encoding="utf-8")


def get_context_RTs(dataset: Path, prefix: str) -> str | None:
    context_file = dataset / f"{prefix}_RTs_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, dtype={"last_tweet_id": str}, encoding="utf-8")
    return context["last_tweet_id"].iloc[-1]
