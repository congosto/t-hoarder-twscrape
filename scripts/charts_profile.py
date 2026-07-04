"""
Funciones de graficas para el perfil de un usuario.
Equivalente Python de utils/charts_profile.R (usadas por
twscrapeR_charts_profile.Rmd / Charts > Users).
"""
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from charts_tweets import COLOR_TEXTO, ENG_FMT, _repel, color_tweets
from utils_charts import apply_date_axis, legend_top, my_theme, my_theme_colored_title, style_twin_axis

_WEEKDAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# daily_routine
#
# Scatterplot de la rutina de publicacion (hora del dia x fecha)
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def daily_routine(df, ini_date, end_date, time_zone, base_title, events=None):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)].copy()
    df["day"] = df["date_slot"].dt.floor("D")
    df["hour_tweet"] = df["date"].dt.hour

    grouped = (
        df.groupby(["day", "hour_tweet"])
        .size()
        .reset_index(name="num_tweets")
    )

    fig, ax = plt.subplots(figsize=(9, 7))
    scatter = ax.scatter(grouped["hour_tweet"], grouped["day"], s=grouped["num_tweets"] * 8 + 10,
                         color=color_tweets, alpha=0.5)
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24))
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%d-%b-%Y"))

    # leyenda de tamanos: los tamanos de punto se convierten de vuelta a
    # num. de tweets con la inversa de s = n * 8 + 10
    handles, labels = scatter.legend_elements(
        prop="sizes", num=4, func=lambda s: (s - 10) / 8, color=color_tweets, alpha=0.5,
    )
    legend_top(ax, handles, labels, title="N. tweets")

    if events is not None and not events.empty:
        ev = events[(events["date"] >= ini_date) & (events["date"] <= end_date)]
        for _, e in ev.iterrows():
            ax.axhline(e["date"], linestyle="--", color="grey")
            ax.text(-1, e["date"], e.get("event_plain", e.get("event", "")), fontsize=8,
                     color="grey", va="center", ha="right")

    my_theme(ax, title=f"{base_title}: daily routine", subtitle=f"Time zone: {time_zone}")
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# daily_routine_by_source
#
# Como daily_routine, pero coloreada por la fuente de publicacion
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def daily_routine_by_source(df, ini_date, end_date, time_zone, base_title, events=None):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)].copy()
    df["day"] = df["date_slot"].dt.floor("D")
    df["hour_tweet"] = df["date"].dt.hour
    df["source"] = df["source"].fillna("unknown") if "source" in df.columns else "unknown"

    grouped = (
        df.groupby(["day", "hour_tweet", "source"])
        .size()
        .reset_index(name="num_tweets")
    )

    # fuentes ordenadas por volumen para que la leyenda liste primero las importantes
    sources = grouped.groupby("source")["num_tweets"].sum().sort_values(ascending=False).index
    palette = plt.get_cmap("tab10")

    fig, ax = plt.subplots(figsize=(9, 7))
    for i, source in enumerate(sources):
        g = grouped[grouped["source"] == source]
        ax.scatter(g["hour_tweet"], g["day"], s=g["num_tweets"] * 8 + 10,
                   color=palette(i % palette.N), alpha=0.5, label=source)
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24))
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%d-%b-%Y"))

    # en la leyenda solo aparecen las fuentes (sin rotulo), con marcadores de tamano uniforme
    legend = legend_top(ax)
    for handle in getattr(legend, "legend_handles", None) or legend.legendHandles:
        handle.set_sizes([40])
        handle.set_alpha(1)

    if events is not None and not events.empty:
        ev = events[(events["date"] >= ini_date) & (events["date"] <= end_date)]
        for _, e in ev.iterrows():
            ax.axhline(e["date"], linestyle="--", color="grey")
            ax.text(-1, e["date"], e.get("event_plain", e.get("event", "")), fontsize=8,
                     color="grey", va="center", ha="right")

    my_theme(ax, title=f"{base_title}: daily routine by source",
             subtitle=f"Time zone: {time_zone}")
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# rhythm_week
#
# Heatmap dia de la semana x hora
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def rhythm_week(df, ini_date, end_date, time_zone, base_title):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)].copy()
    df["weekday"] = df["date"].dt.strftime("%a")
    df["hour"] = df["date"].dt.hour

    pivot = (
        df.groupby(["weekday", "hour"]).size().reset_index(name="num_tweets")
        .pivot(index="weekday", columns="hour", values="num_tweets")
        .reindex(index=_WEEKDAY_ORDER, columns=range(24))
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    im = ax.imshow(pivot.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(24))
    ax.set_xticklabels(range(24))
    ax.set_yticks(range(len(_WEEKDAY_ORDER)))
    ax.set_yticklabels(_WEEKDAY_ORDER)
    ax.set_xlabel("Hour")
    fig.colorbar(im, ax=ax, label="N. tweets")

    my_theme(ax, title=f"{base_title}: weekly rhythm", subtitle=f"Time zone: {time_zone}")
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# rhythm_month
#
# Heatmap mes x ano
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def rhythm_month(df, ini_date, end_date, time_zone, base_title):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)].copy()
    df["month"] = df["date"].dt.strftime("%b")
    df["year"] = df["date"].dt.strftime("%y")

    years = sorted(df["year"].unique())
    pivot = (
        df.groupby(["month", "year"]).size().reset_index(name="num_tweets")
        .pivot(index="month", columns="year", values="num_tweets")
        .reindex(index=_MONTH_ORDER, columns=years)
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(max(6, len(years) * 1.2), 6))
    im = ax.imshow(pivot.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years)
    ax.set_yticks(range(len(_MONTH_ORDER)))
    ax.set_yticklabels(_MONTH_ORDER)
    ax.set_xlabel("Year")
    fig.colorbar(im, ax=ax, label="N. tweets")

    my_theme(ax, title=f"{base_title}: monthly rhythm", subtitle=f"Time zone: {time_zone}")
    fig.tight_layout()
    return fig


_IMPACT_COLUMNS = {
    "Fav": "like_count",
    "RTs": "retweet_count",
    "Quotes": "quote_count",
    "Replies": "reply_count",
    "Impresions": "views_count",
}


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# impact_tweets
#
# Chart de doble escala: tweets originales vs un indicador de impacto
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def impact_tweets(df, ini_date, end_date, indicator, impact_color, base_title, events=None):
    column = _IMPACT_COLUMNS[indicator]
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)].copy()
    df["day"] = df["date"].dt.floor("D")

    grouped = (
        df.groupby("day")
        .agg(num_tweets=("date", "size"), impact=(column, "sum"))
        .reindex(pd.date_range(ini_date.floor("D"), end_date.floor("D"), freq="D"), fill_value=0)
        .rename_axis("day")
        .reset_index()
    )

    mean_impact = grouped["impact"].mean()
    mean_tweets = grouped["num_tweets"].mean()
    max_tweets = grouped["num_tweets"].max() or 1
    max_impact = grouped["impact"].max() or 1
    ajuste = max_impact / max_tweets
    limit_y = max_tweets

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.step(grouped["day"], grouped["num_tweets"], color=color_tweets, where="post")
    ax.scatter(grouped["day"], grouped["impact"] / ajuste, color=impact_color, alpha=0.8)

    # una sola llamada para que adjust_text separe ambas anotaciones si los
    # maximos coinciden (en llamadas separadas no se ven entre si y se solapan)
    row_max_tweets = grouped.loc[grouped["num_tweets"].idxmax()]
    row_max_impact = grouped.loc[grouped["impact"].idxmax()]
    _repel(ax, [row_max_tweets["day"], row_max_impact["day"]],
           [row_max_tweets["num_tweets"], row_max_impact["impact"] / ajuste],
           [f"{row_max_tweets['day'].date()}\nMax. tweets = {row_max_tweets['num_tweets']:,.0f}",
            f"{row_max_impact['day'].date()}\nMax. {indicator} = {row_max_impact['impact']:,.0f}"],
           min_sep_px=None)

    # recuadro de medias siempre a la misma altura (95% del tope del eje) y
    # anclado por su borde superior para que no se salga de la grafica
    ax.text(ini_date + (end_date - ini_date) * 0.06, max_tweets * 1.5 * 0.95,
            f"mean tweets = {mean_tweets:,.1f}\nmean {indicator} = {mean_impact:,.1f}",
            color=COLOR_TEXTO, fontsize=9, va="top",
            bbox=dict(boxstyle="round", fc="white", ec=COLOR_TEXTO))

    ax.set_ylim(0, max_tweets * 1.5)
    ax.set_ylabel("Num. Original tweets per day")
    ax2 = ax.twinx()
    ax2.set_ylim(0, max_tweets * 1.5 * ajuste)
    ax2.set_ylabel(f"{indicator} per day")
    ax.yaxis.set_major_formatter(ENG_FMT)
    ax2.yaxis.set_major_formatter(ENG_FMT)
    apply_date_axis(ax, ini_date, end_date)

    if events is not None and not events.empty:
        ev = events[(events["date"] >= ini_date) & (events["date"] <= end_date)]
        for _, e in ev.iterrows():
            ax.axvline(e["date"], linestyle="--", color=COLOR_TEXTO)
            ax.text(e["date"], max_tweets, e["event"], color=COLOR_TEXTO, fontsize=9, va="bottom")

    my_theme_colored_title(ax, [
        (f"{base_title}: ", None),
        ("Tweets", color_tweets),
        (" per day vs ", None),
        (indicator, impact_color),
    ])
    style_twin_axis(ax2)
    ax.yaxis.label.set_color(color_tweets)
    ax2.yaxis.label.set_color(impact_color)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# engagement_tweets
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def engagement_tweets(df, ini_date, end_date, my_color, base_title, events=None, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]

    grouped = (
        df.groupby("date_slot")
        .apply(
            lambda g: (g["retweet_count"].sum() * 100 / g["views_count"].sum())
            if g["views_count"].sum() > 0 else 0,
            include_groups=False,
        )
        .reset_index(name="engagement")
    )

    max_engagement = grouped["engagement"].max() or 1

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(grouped["date_slot"], grouped["engagement"], color=my_color, alpha=0.8)

    row_max = grouped.loc[grouped["engagement"].idxmax()]
    ax.annotate(
        f"{row_max['date_slot']}\n{row_max['engagement']:.2f} engagement",
        (row_max["date_slot"], row_max["engagement"]), color=COLOR_TEXTO, fontsize=8,
        xytext=(10, 10), textcoords="offset points",
    )

    ax.set_ylim(0, max_engagement * 1.5)
    ax.set_ylabel(f"engagement per {slot_time}")
    apply_date_axis(ax, ini_date, end_date)

    if events is not None and not events.empty:
        ev = events[(events["date"] >= ini_date) & (events["date"] <= end_date)]
        for _, e in ev.iterrows():
            ax.axvline(e["date"], linestyle="--", color=COLOR_TEXTO)
            ax.text(e["date"], max_engagement * 1.25, e["event"], color=COLOR_TEXTO, fontsize=9, va="center")

    my_theme(ax, title=f"{base_title}: engagement per {slot_time}",
             subtitle="engagement = (Sum(RTs) * 100) / impresions")
    fig.tight_layout()
    return fig
