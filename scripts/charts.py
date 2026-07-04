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
        "Rutina diaria por fuente",
        _charts_profile.daily_routine_by_source(tweets, min_date, max_date, time_zone, base_title, events),
        f"{prefix}_daily_routine_by_source.png",
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
    add(
        "Palabras mas frecuentes (con amplificacion)",
        _charts.draw_word_frequency(tweets, min_date, max_date, True, base_title),
        f"{prefix}_word_cloud_RTs.png",
    )

    if topics is not None:
        add(
            "Topics - evolucion acumulada",
            _charts.draw_topics_acumulate(tweets, topics, min_date, max_date, False, base_title, events, slot_time),
            f"{prefix}_topics.png",
        )

    return figs, image_path


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# Informes HTML (autocontenidos: las graficas van embebidas en base64)
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

_REPORT_CSS = """
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f5f4f2; color: #333; margin: 0; }
  .container { max-width: 1000px; margin: 0 auto; padding: 16px 16px 40px; }
  header { border-bottom: 3px solid #4682b4; margin-bottom: 8px; padding: 20px 0 12px; }
  h1 { color: #2c2c2c; margin: 0 0 4px; font-size: 26px; }
  .meta { color: #777; font-size: 14px; }
  nav { background: white; border: 1px solid #e3e0dc; border-radius: 8px; padding: 10px 16px; margin: 16px 0; }
  nav a { color: #4682b4; text-decoration: none; margin-right: 14px; font-size: 14px; display: inline-block; }
  nav a:hover { text-decoration: underline; }
  section { background: white; border: 1px solid #e3e0dc; border-radius: 8px; padding: 16px; margin: 16px 0; }
  h2 { color: #4682b4; font-size: 17px; margin: 0 0 10px; }
  img { max-width: 100%; height: auto; display: block; margin: 0 auto; }
  footer { color: #999; font-size: 12px; text-align: center; margin-top: 20px; }
"""


def build_html_report(figs: dict, title: str, subtitle: str = "") -> str:
    """Compone un informe HTML autocontenido con las graficas de figs.

    Cada figura se embebe como PNG en base64 (el informe es un unico fichero,
    facil de compartir), con un indice de enlaces al principio.
    """
    import base64
    import io
    from datetime import datetime
    from html import escape

    nav, sections = [], []
    for i, (name, fig) in enumerate(figs.items()):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        nav.append(f'<a href="#g{i}">{escape(name)}</a>')
        sections.append(
            f'<section id="g{i}"><h2>{escape(name)}</h2>'
            f'<img src="data:image/png;base64,{b64}" alt="{escape(name)}"></section>'
        )

    fecha = datetime.now().strftime("%d-%m-%Y %H:%M")
    meta = f"{escape(subtitle)} &middot; " if subtitle else ""
    return (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title><style>{_REPORT_CSS}</style></head><body>"
        "<div class='container'>"
        f"<header><h1>{escape(title)}</h1>"
        f"<div class='meta'>{meta}Generado el {fecha}</div></header>"
        f"<nav>{''.join(nav)}</nav>"
        f"{''.join(sections)}"
        "<footer>Generado con t-hoarder_twscrape</footer>"
        "</div></body></html>"
    )


def generate_tweet_report(project_dir: Path, prefix: str, base_title: str, *args, log=print, **kwargs):
    """Genera las graficas de tweets y las empaqueta en un informe HTML.

    Mismos parametros que generate_tweet_charts. Devuelve (html, out_path);
    el informe se guarda en {prefix}_informe_tweets.html dentro del proyecto.
    """
    import matplotlib.pyplot as plt

    figs, _ = generate_tweet_charts(project_dir, prefix, base_title, *args, log=log, **kwargs)
    html = build_html_report(figs, title=f"{base_title}: informe de tweets", subtitle=f"Dataset {prefix}")
    out_path = Path(project_dir) / f"{prefix}_informe_tweets.html"
    out_path.write_text(html, encoding="utf-8")
    for fig in figs.values():
        plt.close(fig)
    log(f"Informe HTML guardado en {out_path}")
    return html, out_path


def generate_user_report(project_dir: Path, prefix: str, username: str, base_title: str, *args, log=print, **kwargs):
    """Genera las graficas de un usuario y las empaqueta en un informe HTML.

    Mismos parametros que generate_user_charts. Devuelve (html, out_path);
    el informe se guarda en {prefix}_{username}_informe_usuario.html.
    """
    import matplotlib.pyplot as plt

    figs, _ = generate_user_charts(project_dir, prefix, username, base_title, *args, log=log, **kwargs)
    html = build_html_report(figs, title=f"{base_title}: informe de usuario", subtitle=f"Dataset {prefix} — @{username}")
    out_path = Path(project_dir) / f"{prefix}_{username}_informe_usuario.html"
    out_path.write_text(html, encoding="utf-8")
    for fig in figs.values():
        plt.close(fig)
    log(f"Informe HTML guardado en {out_path}")
    return html, out_path
