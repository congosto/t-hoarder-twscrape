"""
Generacion de graficas de tweets para la app real (Charts > Tweets).
Envoltorio sobre charts_tweets.py y charts_profile.py.
"""
from pathlib import Path

import pandas as pd

import charts_tweets as _charts
import charts_profile as _charts_profile
from utils_charts import savefig


def _load_tweets(project_dir: Path, prefix: str):
    classified_file = project_dir / f"{prefix}_classified.csv"
    plain_file = project_dir / f"{prefix}.csv"
    communities_name_file = project_dir / f"{prefix}_communities.csv"

    if classified_file.exists():
        tweets_file = classified_file
        ars = True
    elif plain_file.exists():
        tweets_file = plain_file
        ars = False
    else:
        raise FileNotFoundError(f"No existe {plain_file} ni {classified_file}")

    tweets = pd.read_csv(tweets_file)
    if "date" not in tweets.columns:
        raise FileNotFoundError(f"{tweets_file} no tiene columna 'date'; no es un fichero de tweets valido")
    tweets["date"] = pd.to_datetime(tweets["date"], utc=True, errors="coerce")
    tweets = (
        tweets.sort_values("date")
        .drop_duplicates(subset=["username", "url"], keep="first")
        .sort_values("date")
        .reset_index(drop=True)
    )

    communities = pd.read_csv(communities_name_file) if ars and communities_name_file.exists() else None
    return tweets, ars, communities


def generate_tweet_charts(
    project_dir: Path,
    prefix: str,
    base_title: str,
    time_zone: str = "Europe/Berlin",
    min_reach: int = 0,
    min_RTs: int = 0,
    show_topics: bool = False,
    topics_file: str = "",
    show_events: bool = False,
    events_file: str = "",
    min_date_zoom: str | None = None,
    max_date_zoom: str | None = None,
    log=print,
):
    """Genera las graficas de tweets de un proyecto.

    Si se indican min_date_zoom/max_date_zoom, las graficas se limitan a ese
    rango de fechas en vez de usar todo el periodo disponible.

    Devuelve (figs, image_path): figs es un dict {nombre: matplotlib.Figure},
    image_path es la carpeta donde se han guardado los PNG.
    """
    project_dir = Path(project_dir)
    slot_time = "1h"

    tweets, ars, communities = _load_tweets(project_dir, prefix)

    image_path = project_dir / f"{prefix}_graficas"
    image_path.mkdir(exist_ok=True)

    tweets["date"] = tweets["date"].dt.tz_convert(time_zone).dt.tz_localize(None).dt.floor("s")
    tweets = tweets[tweets["date"].notna()]
    tweets["date_slot"] = tweets["date"].dt.floor("h")

    if tweets.empty:
        raise FileNotFoundError(f"{prefix}: no hay tweets con fecha valida")

    if min_date_zoom and max_date_zoom:
        try:
            min_date = pd.Timestamp(min_date_zoom)
            max_date = pd.Timestamp(max_date_zoom)
        except (ValueError, TypeError):
            raise ValueError("min_date_zoom/max_date_zoom deben tener formato yyyy-mm-dd HH:MM:SS")
        if min_date >= max_date:
            raise ValueError("min_date_zoom debe ser anterior a max_date_zoom")
    else:
        min_date = tweets["date_slot"].min()
        max_date = tweets["date_slot"].max()

    events = None
    if show_events and events_file:
        events_path = project_dir / events_file
        events = pd.read_csv(events_path, usecols=["date", "event"], dtype={"date": str, "event": str})
        events["event"] = events["event"].str.replace(r"\\n", "\n", regex=True)
        events["date"] = pd.to_datetime(events["date"], utc=True, errors="coerce")
        events["date"] = events["date"].dt.tz_convert(time_zone).dt.tz_localize(None)

    topics = None
    if show_topics and topics_file:
        topics = pd.read_csv(project_dir / topics_file)

    figs = {}

    def add(name, fig, filename=None):
        figs[name] = fig
        if filename:
            savefig(fig, image_path / filename)
        log(f"Grafica generada: {name}")

    add(
        "Tweets vs. alcance con influencers",
        _charts.draw_tweets_vs_reach_influencers(tweets, min_date, max_date, min_reach, base_title, slot_time),
        f"{prefix}_tweets_vs_reach_influencers.png",
    )
    add(
        "Tweets vs. alcance",
        _charts.draw_tweets_vs_reach(tweets, min_date, max_date, base_title, slot_time),
        f"{prefix}_tweets_vs_reach.png",
    )

    add(
        "Tweets vs. RTs con influencers",
        _charts.draw_tweets_vs_RTs_influencers(tweets, min_date, max_date, min_RTs, base_title, slot_time),
        f"{prefix}_tweets_vs_RTs_influencers.png",
    )
    add(
        "Tweets vs. RTs",
        _charts.draw_tweets_vs_RTs(tweets, min_date, max_date, base_title, slot_time),
        f"{prefix}_tweets_vs_RTs.png",
    )
    add(
        "Comentarios vs. RTs",
        _charts.draw_comments_vs_RTs(tweets, min_date, max_date, base_title),
        f"{prefix}_comments_vs_RTs.png",
    )
    add(
        "Palabras mas frecuentes",
        _charts.draw_word_frequency(tweets, min_date, max_date, False, base_title, str(project_dir), prefix),
        f"{prefix}_word_cloud.png",
    )
    add(
        "Palabras mas frecuentes (con amplificacion)",
        _charts.draw_word_frequency(tweets, min_date, max_date, True, base_title),
        f"{prefix}_word_cloud_RTs.png",
    )

    media = [
        "UHN_Plus", "El_Plural", "eldiarioes", "el_pais", "La_SER",
        "TheObjective_es", "eldebate_com", "publico_es", "elmundoes",
        "europapress", "ElHuffPost", "elespanolcom", "elconfidencial",
        "laSextaTV", "abc_es", "rtvenoticias", "OndaCero_es", "HoyPorHoy",
        "okdiario", "voz_populi", "libertaddigital",
    ]
    add(
        "Menciones a medios",
        _charts.draw_media_acumulate(tweets, min_date, max_date, media, True, base_title, slot_time),
        f"{prefix}_medios.png",
    )

    if topics is not None:
        add(
            "Topics - evolucion acumulada",
            _charts.draw_topics_acumulate(tweets, topics, min_date, max_date, False, base_title, events, slot_time),
            f"{prefix}_topics.png",
        )
        add(
            "Topics - evolucion acumulada (con amplificacion)",
            _charts.draw_topics_acumulate(tweets, topics, min_date, max_date, True, base_title, events, slot_time),
            f"{prefix}_topics_RTs.png",
        )

    if ars and communities is not None:
        add(
            "Palabras mas frecuentes por comunidad",
            _charts.words_frequency_by_community(tweets, communities, base_title),
        )
        add(
            "Tweets por comunidad",
            _charts.tweets_by_community(tweets, min_date, max_date, communities, base_title, events, slot_time),
            f"{prefix}_tweets_by_communities.png",
        )

    return figs, image_path


def _load_user_tweets(project_dir: Path, prefix: str, username: str):
    plain_file = project_dir / f"{prefix}.csv"
    if not plain_file.exists():
        raise FileNotFoundError(f"No existe {plain_file}")

    tweets = pd.read_csv(plain_file)
    if "date" not in tweets.columns:
        raise FileNotFoundError(f"{plain_file} no tiene columna 'date'; no es un fichero de tweets valido")
    tweets["date"] = pd.to_datetime(tweets["date"], utc=True, errors="coerce")
    tweets = tweets[tweets["username"].str.lower() == username.lower()]
    tweets = tweets.drop_duplicates(subset=["url"], keep="first").sort_values("date").reset_index(drop=True)
    return tweets


def generate_user_charts(
    project_dir: Path,
    prefix: str,
    username: str,
    base_title: str,
    time_zone: str = "Europe/Berlin",
    show_topics: bool = False,
    topics_file: str = "",
    show_events: bool = False,
    events_file: str = "",
    log=print,
):
    """Genera las graficas del perfil de un usuario.

    Equivalente a twscrapeR_charts_profile.Rmd. Devuelve (figs, image_path).
    """
    project_dir = Path(project_dir)

    tweets = _load_user_tweets(project_dir, prefix, username)
    if tweets.empty:
        raise FileNotFoundError(f"No hay tweets de '{username}' en {prefix}.csv")

    image_path = project_dir / f"{prefix}_graficas"
    image_path.mkdir(exist_ok=True)

    tweets["date"] = tweets["date"].dt.tz_convert(time_zone).dt.tz_localize(None).dt.floor("s")
    tweets = tweets[tweets["date"].notna()]
    num_days = (tweets["date"].max() - tweets["date"].min()).total_seconds() / 86400
    slot_time = "1h" if num_days <= 15 else "1D"
    tweets["date_slot"] = tweets["date"].dt.floor("h" if slot_time == "1h" else "D")

    min_date = tweets["date_slot"].min()
    max_date = tweets["date_slot"].max()

    events = None
    if show_events and events_file:
        events_path = project_dir / events_file
        events = pd.read_csv(events_path)
        events["event_plain"] = events["event"]
        events["date"] = pd.to_datetime(events["date"], utc=True, errors="coerce")
        events["date"] = events["date"].dt.tz_convert(time_zone).dt.tz_localize(None)

    topics = None
    if show_topics and topics_file:
        topics = pd.read_csv(project_dir / topics_file)

    figs = {}

    def add(name, fig, filename=None):
        figs[name] = fig
        if filename:
            savefig(fig, image_path / filename)
        log(f"Grafica generada: {name}")

    add(
        "Rutina diaria",
        _charts_profile.daily_routine(tweets, min_date, max_date, time_zone, base_title, events),
        f"{prefix}_daily_routine_total.png",
    )
    add(
        "Ritmo semanal",
        _charts_profile.rhythm_week(tweets, min_date, max_date, time_zone, base_title),
        f"{prefix}_rhythm_week_total.png",
    )
    add(
        "Ritmo mensual",
        _charts_profile.rhythm_month(tweets, min_date, max_date, time_zone, base_title),
        f"{prefix}_rhythm_month_total.png",
    )
    add(
        "Tweets vs. Favoritos",
        _charts_profile.impact_tweets(tweets, min_date, max_date, "Fav", "#50af4a", base_title),
        f"{prefix}_tweets_vs_fav_total.png",
    )
    add(
        "Tweets vs. RTs",
        _charts_profile.impact_tweets(tweets, min_date, max_date, "RTs", "#6e322d", base_title),
        f"{prefix}_tweets_vs_RTs_total.png",
    )
    add(
        "Tweets vs. Citas",
        _charts_profile.impact_tweets(tweets, min_date, max_date, "Quotes", "#9C1A37", base_title),
        f"{prefix}_tweets_vs_quotes_total.png",
    )
    add(
        "Tweets vs. Comentarios",
        _charts_profile.impact_tweets(tweets, min_date, max_date, "Replies", "#ff7733", base_title),
        f"{prefix}_tweets_vs_replies_total.png",
    )
    add(
        "Tweets vs. Impresiones",
        _charts_profile.impact_tweets(tweets, min_date, max_date, "Impresions", "#bf609f", base_title),
        f"{prefix}_tweets_vs_impresions_total.png",
    )
    add(
        "Engagement",
        _charts_profile.engagement_tweets(tweets, min_date, max_date, "#778dcf", base_title, events, slot_time),
        f"{prefix}_engagement_total.png",
    )
    add(
        "Comentarios vs. RTs",
        _charts.draw_comments_vs_RTs(tweets, min_date, max_date, base_title),
        f"{prefix}_comments_vs_RTs.png",
    )
    add(
        "Palabras mas frecuentes",
        _charts.draw_word_frequency(tweets, min_date, max_date, False, base_title, str(project_dir), prefix),
        f"{prefix}_word_cloud.png",
    )

    if topics is not None:
        add(
            "Topics - evolucion acumulada",
            _charts.draw_topics_acumulate(tweets, topics, min_date, max_date, False, base_title, events, slot_time),
            f"{prefix}_topics.png",
        )

    return figs, image_path
