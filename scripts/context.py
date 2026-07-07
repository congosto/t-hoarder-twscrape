from datetime import datetime
from pathlib import Path

import pandas as pd


def put_context_merge(dataset: Path, prefix: str, sources: list, total: int) -> None:
    """Contexto de procedencia de un dataset combinado (Tools > Merge datasets):
    de qué datasets viene, cuántos tweets tiene y cuándo se creó. Su existencia
    también hace que el dataset combinado aparezca en las listas de datasets."""
    dataset.mkdir(parents=True, exist_ok=True)
    context_file = dataset / f"{prefix}_merge_context.csv"
    pd.DataFrame({
        "created": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "merged_from": [", ".join(sources)],
        "n_datasets": [len(sources)],
        "total_tweets": [total],
    }).to_csv(context_file, index=False, encoding="utf-8")


def put_context_search(
    dataset: Path, prefix: str, date, since, until, query: str = "", product: str = "", frequency: str = ""
) -> None:
    dataset.mkdir(parents=True, exist_ok=True)
    context_file = dataset / f"{prefix}_search_context.csv"
    pd.DataFrame({
        "last_date": [str(date)], "since": [str(since)], "until": [str(until)],
        "query": [query], "product": [product], "frequency": [frequency],
    }).to_csv(context_file, index=False, encoding="utf-8")


def get_context_search(dataset: Path, prefix: str) -> str | None:
    context_file = dataset / f"{prefix}_search_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, encoding="utf-8")
    return context["last_date"].iloc[-1]


def get_context_search_range(dataset: Path, prefix: str) -> tuple[str, str] | None:
    """Devuelve (since, until) originales guardados, para autorrellenar el formulario al reanudar."""
    context_file = dataset / f"{prefix}_search_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, encoding="utf-8")
    if "since" not in context.columns or "until" not in context.columns:
        return None
    return context["since"].iloc[-1], context["until"].iloc[-1]


def get_context_search_full(dataset: Path, prefix: str) -> dict | None:
    """Devuelve todos los campos guardados (query, product, since, until, frequency)
    para autorrellenar el formulario de Search al reutilizar un Prefix existente."""
    context_file = dataset / f"{prefix}_search_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, encoding="utf-8")
    last = context.iloc[-1]
    return {
        "query": last.get("query", "") or "",
        "product": last.get("product", "") or "",
        "since": last.get("since", "") or "",
        "until": last.get("until", "") or "",
        "frequency": last.get("frequency", "") or "",
    }


def put_context_user(
    dataset: Path, prefix: str, date, order: int, username: str, since, until,
    product: str = "", frequency: str = "",
) -> None:
    dataset.mkdir(parents=True, exist_ok=True)
    context_file = dataset / f"{prefix}_users_context.csv"
    row = pd.DataFrame({
        "last_date": [str(date)], "order": [order], "username": [username],
        "since": [str(since)], "until": [str(until)],
        "product": [product], "frequency": [frequency],
    })
    row.to_csv(context_file, mode="a", header=not context_file.exists(), index=False, encoding="utf-8")


def get_context_user(dataset: Path, prefix: str) -> pd.DataFrame | None:
    context_file = dataset / f"{prefix}_users_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, encoding="utf-8")
    context = context.groupby("username", as_index=False).tail(1).sort_values("order")
    return context


def get_context_user_range(dataset: Path, prefix: str) -> tuple[str, str] | None:
    """Devuelve (since, until) originales guardados, para autorrellenar el formulario al reanudar."""
    context_file = dataset / f"{prefix}_users_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, encoding="utf-8")
    if "since" not in context.columns or "until" not in context.columns:
        return None
    return context["since"].iloc[-1], context["until"].iloc[-1]


def get_context_user_full(dataset: Path, prefix: str) -> dict | None:
    """Devuelve todos los campos guardados (list_users, product, since, until, frequency)
    para autorrellenar el formulario de User TL al reutilizar un Prefix existente."""
    context_file = dataset / f"{prefix}_users_context.csv"
    if not context_file.exists():
        return None
    context = pd.read_csv(context_file, encoding="utf-8")
    last_per_user = context.groupby("username", as_index=False).tail(1).sort_values("order")
    last = context.iloc[-1]
    return {
        "list_users": ", ".join(last_per_user["username"].astype(str)),
        "product": last.get("product", "") or "",
        "since": last.get("since", "") or "",
        "until": last.get("until", "") or "",
        "frequency": last.get("frequency", "") or "",
    }


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
