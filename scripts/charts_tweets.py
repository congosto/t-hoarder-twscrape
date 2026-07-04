"""
Funciones de graficas para tweets.
Equivalente Python de utils/charts.R (solo las funciones usadas por
twscrapeR_charts.ipynb / twscrapeR_charts.Rmd).

Dependencias: pandas, numpy, matplotlib, wordcloud, nltk
(opcional: adjustText, para separar mejor las etiquetas de texto).
"""
import re

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import EngFormatter
from wordcloud import WordCloud

from utils_charts import apply_date_axis, expand_time, my_theme, style_twin_axis

try:
    from adjustText import adjust_text
except ImportError:  # pragma: no cover - opcional
    adjust_text = None

# Colores por defecto (equivalente al chunk "color" de los .Rmd)
color_tweets = "#4682b4"
color_reach = "#6e322d"
color_RT = "#6e322d"
color_comments = "#ff7733"
COLOR_TEXTO = "#5a5856"

ENG_FMT = EngFormatter(sep="")


def _repel(ax, xs, ys, labels, color=COLOR_TEXTO, size=9, max_texts=20, min_sep_px=22.0, **kwargs):
    """Coloca etiquetas de texto intentando que no se solapen.

    Equivalente aproximado a geom_text_repel()/geom_label_repel(). Si la
    libreria adjustText esta disponible se usa para separar las etiquetas;
    si no, se colocan con un pequeno desplazamiento vertical.

    Si hay mas de max_texts etiquetas solo se colocan las de mayor valor y
    (las mas prominentes): adjust_text es O(n^2) en memoria y tiempo, y con
    miles de etiquetas (p.ej. muchos influencers sobre el umbral en un
    dataset grande) el calculo de solapes agota la RAM. Ademas, emulando el
    max.overlaps de ggrepel, se descartan las etiquetas cuyo punto caiga a
    menos de min_sep_px de otra ya aceptada (si no, un pico viral con
    decenas de influencers a la vez sale como un monton ilegible);
    min_sep_px=None desactiva ese descarte (para etiquetas que deben salir
    siempre, como las anotaciones de maximos).
    """
    points = sorted(zip(xs, ys, labels), key=lambda p: p[1], reverse=True)
    if min_sep_px is not None and len(points) > 1:
        try:
            # los limites del eje se autoescalan de forma perezosa (al dibujar); sin esto
            # la transformacion a pixeles usa los limites por defecto 0-1 y no descarta nada
            ax.autoscale_view()
            display = ax.transData.transform([(mdates.date2num(x) if hasattr(x, "toordinal") else x, y)
                                              for x, y, _ in points])
        except Exception:
            display = None
        if display is not None:
            kept, kept_xy = [], []
            for point, xy in zip(points, display):
                if all((xy[0] - kx) ** 2 + (xy[1] - ky) ** 2 >= min_sep_px ** 2 for kx, ky in kept_xy):
                    kept.append(point)
                    kept_xy.append(xy)
                if len(kept) >= max_texts:
                    break
            points = kept
    points = points[:max_texts]
    texts = []
    for x, y, label in points:
        texts.append(ax.annotate(
            label, (x, y), color=color, fontsize=size,
            ha=kwargs.get("ha", "center"), va=kwargs.get("va", "bottom"),
        ))
    if adjust_text is not None and texts:
        adjust_text(
            texts, ax=ax,
            arrowprops=dict(arrowstyle="-", color=COLOR_TEXTO, lw=0.5),
        )
    return texts


def _slot_seconds(date_slot):
    diffs = date_slot.sort_values().diff().dropna()
    if diffs.empty:
        return pd.Timedelta(hours=1)
    return diffs.mode().iloc[0]


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_tweets_vs_reach_influencers
#
# Chart de doble escala: total tweets vs alcance, marcando influencers
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_tweets_vs_reach_influencers(df, ini_date, end_date, min_reach, base_title, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]

    tweets_vs_reach = (
        df.groupby("date_slot")
        .agg(num_tweets=("date", "size"), reach=("views_count", "sum"))
        .reindex(pd.date_range(ini_date, end_date, freq=slot_time), fill_value=0)
        .rename_axis("date_slot")
        .reset_index()
    )

    influencers = (
        df.groupby(["date", "username"])["views_count"]
        .sum()
        .reset_index(name="reach")
    )
    influencers = influencers[influencers["reach"] >= min_reach]

    max_tweets = tweets_vs_reach["num_tweets"].max()
    max_reach = tweets_vs_reach["reach"].max()
    ajuste = max_reach / max_tweets if max_tweets else 1
    limit_y = max_tweets

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.step(tweets_vs_reach["date_slot"], tweets_vs_reach["num_tweets"],
            color=color_tweets, alpha=0.8, where="post")
    ax.scatter(influencers["date"], influencers["reach"] / ajuste,
               s=influencers["reach"] / ajuste / max(max_reach / ajuste, 1) * 200 + 10,
               color=color_reach, alpha=0.8)
    _repel(ax, influencers["date"], influencers["reach"] / ajuste, influencers["username"])

    ax.set_ylim(0, limit_y * 1.3)
    ax.set_ylabel(f"Num. Original tweets per {slot_time}")
    ax2 = ax.twinx()
    ax2.set_ylim(0, limit_y * 1.3 * ajuste)
    ax2.set_ylabel("Reach influencers")
    ax2.yaxis.set_major_formatter(ENG_FMT)
    ax.yaxis.set_major_formatter(ENG_FMT)
    apply_date_axis(ax, ini_date, end_date)

    title = f"{base_title}: Tweets per {slot_time} vs Reach influencers"
    subtitle = f"Reach influencers >= {ENG_FMT(min_reach)}"
    my_theme(ax, title=title, subtitle=subtitle)
    style_twin_axis(ax2)
    ax.yaxis.label.set_color(color_tweets)
    ax2.yaxis.label.set_color(color_reach)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_tweets_vs_reach
#
# Chart de doble escala: total tweets vs alcance
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_tweets_vs_reach(df, ini_date, end_date, base_title, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]

    tweets_vs_reach = (
        df.groupby("date_slot")
        .agg(num_tweets=("date", "size"), reach=("views_count", "sum"))
        .reindex(pd.date_range(ini_date, end_date, freq=slot_time), fill_value=0)
        .rename_axis("date_slot")
        .reset_index()
    )

    mean_reach = tweets_vs_reach["reach"].mean()
    mean_tweets = tweets_vs_reach["num_tweets"].mean()
    max_tweets = tweets_vs_reach["num_tweets"].max()
    max_reach = tweets_vs_reach["reach"].max()
    ajuste = max_reach / max_tweets if max_tweets else 1
    limit_y = max_tweets

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.step(tweets_vs_reach["date_slot"], tweets_vs_reach["num_tweets"],
            color=color_tweets, where="post")
    ax.scatter(tweets_vs_reach["date_slot"], tweets_vs_reach["reach"] / ajuste,
               color=color_reach, alpha=0.8)

    # una sola llamada para que adjust_text separe ambas anotaciones si los
    # maximos coinciden (en llamadas separadas no se ven entre si y se solapan)
    row_max_tweets = tweets_vs_reach.loc[tweets_vs_reach["num_tweets"].idxmax()]
    row_max_reach = tweets_vs_reach.loc[tweets_vs_reach["reach"].idxmax()]
    _repel(ax, [row_max_tweets["date_slot"], row_max_reach["date_slot"]],
           [row_max_tweets["num_tweets"], row_max_reach["reach"] / ajuste],
           [f"{row_max_tweets['date_slot']}\nMax. tweets = {row_max_tweets['num_tweets']:,.0f}",
            f"{row_max_reach['date_slot']}\nMax. reach = {row_max_reach['reach']:,.0f}"],
           min_sep_px=None)

    # recuadro de medias siempre a la misma altura (95% del tope del eje) y
    # anclado por su borde superior para que no se salga de la grafica
    ax.text(ini_date + (end_date - ini_date) * 0.06, limit_y * 1.8 * 0.95,
            f"mean tweets = {mean_tweets:,.1f}\nmean reach = {mean_reach:,.1f}",
            color=COLOR_TEXTO, fontsize=9, va="top",
            bbox=dict(boxstyle="round", fc="white", ec=COLOR_TEXTO))

    ax.set_ylim(0, limit_y * 1.8)
    ax.set_ylabel(f"Num. Original tweets per {slot_time}")
    ax2 = ax.twinx()
    ax2.set_ylim(0, limit_y * 1.8 * ajuste)
    ax2.set_ylabel(f"Reach per {slot_time}")
    ax2.yaxis.set_major_formatter(ENG_FMT)
    ax.yaxis.set_major_formatter(ENG_FMT)
    apply_date_axis(ax, ini_date, end_date)

    title = f"{base_title}: Tweets per {slot_time} vs Reach"
    my_theme(ax, title=title)
    style_twin_axis(ax2)
    ax.yaxis.label.set_color(color_tweets)
    ax2.yaxis.label.set_color(color_reach)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_tweets_vs_reach_by_username
#
# Chart de doble escala por usuario (facetas)
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_tweets_vs_reach_by_username(df, ini_date, end_date, base_title, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    usernames = df["username"].dropna().unique()
    n = len(usernames)
    ncols = 2
    nrows = int(np.ceil(n / ncols)) if n else 1

    fig, axes = plt.subplots(nrows, ncols, figsize=(10, 3.5 * nrows), squeeze=False)
    fig.suptitle(f"{base_title}: Tweets per {slot_time} vs Reach", color=COLOR_TEXTO,
                 fontsize=17, fontweight="bold", x=0.02, ha="left")

    for i, username in enumerate(usernames):
        ax = axes[i // ncols][i % ncols]
        sub = df[df["username"] == username]
        grouped = (
            sub.groupby("date_slot")
            .agg(num_tweets=("date", "size"), reach=("views_count", "sum"))
            .reindex(pd.date_range(ini_date, end_date, freq=slot_time), fill_value=0)
            .rename_axis("date_slot")
            .reset_index()
        )
        max_tweets = grouped["num_tweets"].max() or 1
        max_reach = grouped["reach"].max() or 1
        ajuste = max_reach / max_tweets

        ax.bar(grouped["date_slot"], grouped["num_tweets"], color=color_tweets,
               edgecolor="white", width=0.03)
        ax2 = ax.twinx()
        ax2.scatter(grouped["date_slot"], grouped["reach"], color=color_reach, alpha=0.8)
        ax.set_title(username, color=COLOR_TEXTO, fontsize=11)
        apply_date_axis(ax, ini_date, end_date)
        ax.yaxis.set_major_formatter(ENG_FMT)
        ax2.yaxis.set_major_formatter(ENG_FMT)
        my_theme(ax)
        style_twin_axis(ax2)

    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_tweets_vs_RTs_influencers
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_tweets_vs_RTs_influencers(df, ini_date, end_date, min_RTs, base_title, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]

    tweets_vs_rt = (
        df.groupby("date_slot")
        .agg(num_tweets=("date", "size"), num_RTs=("retweet_count", "sum"))
        .reindex(pd.date_range(ini_date, end_date, freq=slot_time), fill_value=0)
        .rename_axis("date_slot")
        .reset_index()
    )

    influencers = (
        df.groupby(["date_slot", "username"])["retweet_count"]
        .sum()
        .reset_index(name="num_RTs")
    )
    influencers = influencers[influencers["num_RTs"] >= min_RTs]

    max_tweets = tweets_vs_rt["num_tweets"].max()
    max_RT = tweets_vs_rt["num_RTs"].max()
    ajuste = max_RT / max_tweets if max_tweets else 1
    limit_y = max_tweets

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.step(tweets_vs_rt["date_slot"], tweets_vs_rt["num_tweets"], color=color_tweets, where="post")
    ax.scatter(influencers["date_slot"], influencers["num_RTs"] / ajuste, color=color_RT, alpha=0.8)
    _repel(ax, influencers["date_slot"], influencers["num_RTs"] / ajuste, influencers["username"])

    ax.set_ylim(0, limit_y * 1.1)
    ax.set_ylabel(f"Num. Original tweets per {slot_time}")
    ax2 = ax.twinx()
    ax2.set_ylim(0, limit_y * 1.1 * ajuste)
    ax2.set_ylabel(f"RTs per {slot_time}")
    ax2.yaxis.set_major_formatter(ENG_FMT)
    ax.yaxis.set_major_formatter(ENG_FMT)
    apply_date_axis(ax, ini_date, end_date)

    title = f"{base_title}: Tweets per {slot_time} vs RTs influencers"
    subtitle = f"RTs influencers >= {ENG_FMT(min_RTs)}"
    my_theme(ax, title=title, subtitle=subtitle)
    style_twin_axis(ax2)
    ax.yaxis.label.set_color(color_tweets)
    ax2.yaxis.label.set_color(color_RT)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_tweets_vs_RTs
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_tweets_vs_RTs(df, ini_date, end_date, base_title, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]

    tweets_vs_rt = (
        df.groupby("date_slot")
        .agg(num_tweets=("date", "size"), num_RTs=("retweet_count", "sum"))
        .reset_index()
    )

    mean_RTs = tweets_vs_rt["num_RTs"].mean()
    mean_tweets = tweets_vs_rt["num_tweets"].mean()
    max_tweets = tweets_vs_rt["num_tweets"].max()
    max_RT = tweets_vs_rt["num_RTs"].max()
    ajuste = max_RT / max_tweets if max_tweets else 1
    limit_y = max_tweets

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.step(tweets_vs_rt["date_slot"], tweets_vs_rt["num_tweets"], color=color_tweets, where="post")
    ax.scatter(tweets_vs_rt["date_slot"], tweets_vs_rt["num_RTs"] / ajuste, color=color_RT, alpha=0.8)

    # una sola llamada para que adjust_text separe ambas anotaciones si los
    # maximos coinciden (en llamadas separadas no se ven entre si y se solapan)
    row_max_tweets = tweets_vs_rt.loc[tweets_vs_rt["num_tweets"].idxmax()]
    row_max_RT = tweets_vs_rt.loc[tweets_vs_rt["num_RTs"].idxmax()]
    _repel(ax, [row_max_tweets["date_slot"], row_max_RT["date_slot"]],
           [row_max_tweets["num_tweets"], row_max_RT["num_RTs"] / ajuste],
           [f"{row_max_tweets['date_slot']}\nMax. tweets = {row_max_tweets['num_tweets']:,.0f}",
            f"{row_max_RT['date_slot']}\nMax. RTs = {row_max_RT['num_RTs']:,.0f}"],
           min_sep_px=None)

    # recuadro de medias siempre a la misma altura (95% del tope del eje) y
    # anclado por su borde superior para que no se salga de la grafica
    ax.text(ini_date + (end_date - ini_date) * 0.06, limit_y * 1.5 * 0.95,
            f"mean tweets = {mean_tweets:,.1f}\nmean RTs = {mean_RTs:,.1f}",
            color=COLOR_TEXTO, fontsize=9, va="top",
            bbox=dict(boxstyle="round", fc="white", ec=COLOR_TEXTO))

    ax.set_ylim(0, limit_y * 1.5)
    ax.set_ylabel(f"Num. Original tweets per {slot_time}")
    ax2 = ax.twinx()
    ax2.set_ylim(0, limit_y * 1.5 * ajuste)
    ax2.set_ylabel(f"RTs per {slot_time}")
    ax2.yaxis.set_major_formatter(ENG_FMT)
    ax.yaxis.set_major_formatter(ENG_FMT)
    apply_date_axis(ax, ini_date, end_date)

    title = f"{base_title}: Tweets per {slot_time} vs RTs"
    my_theme(ax, title=title)
    style_twin_axis(ax2)
    ax.yaxis.label.set_color(color_tweets)
    ax2.yaxis.label.set_color(color_RT)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_comments_vs_RTs
#
# scatterplot comments vs RTs
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_comments_vs_RTs(df, ini_date, end_date, min_comments, base_title):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    sub = df.copy()
    sub["num_comments"] = sub["reply_count"]
    sub["num_RTs"] = sub["retweet_count"]
    sub["possible_controversy"] = (sub["num_comments"] > sub["num_RTs"]).astype(int)
    sub = sub[sub["num_comments"] >= min_comments]

    title = f"{base_title}: Comments vs. RTs"
    subtitle = f"Comments >= {ENG_FMT(min_comments)}"

    # sin tweets sobre el umbral, los limites de los ejes serian NaN: se
    # devuelve la grafica vacia con un aviso en vez de reventar
    if sub.empty:
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.text(0.5, 0.5, f"No tweets with comments >= {ENG_FMT(min_comments)}",
                ha="center", va="center", color=COLOR_TEXTO, fontsize=12,
                transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        my_theme(ax, title=title, subtitle=subtitle)
        fig.tight_layout()
        return fig

    max_comments = sub["num_comments"].max()
    max_RTs = sub["num_RTs"].max()
    size_x = max(max_comments, max_RTs)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.fill_between([0, max_comments * 1.4], [0, max_comments * 1.4],
                     color=color_comments, alpha=0.25)
    ax.scatter(sub["num_RTs"], sub["num_comments"], color=color_RT)
    _repel(ax, sub["num_RTs"], sub["num_comments"], sub["username"])

    pct_controversy = round(sub["possible_controversy"].sum() * 100 / len(sub), 1) if len(sub) else 0
    ax.text(max_RTs * 0.25, max_comments * 1.3, f"{pct_controversy}% controversy",
            color=COLOR_TEXTO, fontsize=11)

    ax.set_xlim(0, size_x * 1.3)
    ax.set_ylim(0, max_comments * 1.4)
    ax.set_xlabel("Num. RTs")
    ax.set_ylabel("Num. comments")

    my_theme(ax, title=title, subtitle=subtitle)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_word_frequency
#
# tagcloud
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
_URL_RE = re.compile(r"http\S+\s*")
_RT_RE = re.compile(r"RT @\w+:")
_MENTION_RE = re.compile(r"@\w+")
_WORD_RE = re.compile(r"[a-zA-ZáéíóúñÁÉÍÓÚÑàèìòùçÀÈÌÒÙÇ]{2,}")


def _stopwords():
    """Stopwords en, es, ca, equivalente a stop_words + tm::stopwords()."""
    import nltk
    try:
        from nltk.corpus import stopwords
        words = set(stopwords.words("english")) | set(stopwords.words("spanish"))
    except LookupError:
        nltk.download("stopwords", quiet=True)
        from nltk.corpus import stopwords
        words = set(stopwords.words("english")) | set(stopwords.words("spanish"))
    # nltk no incluye catalan: lista minima de uso frecuente
    catalan = {
        "el", "la", "els", "les", "de", "del", "dels", "un", "una", "uns",
        "unes", "i", "o", "que", "no", "en", "amb", "per", "es", "se", "al",
        "als", "com", "ja", "molt", "pero", "si", "aquest", "aquesta", "te",
    }
    return words | catalan


def _tokenize(text):
    text = _URL_RE.sub("", text)
    text = _RT_RE.sub("", text)
    text = text.replace("&amp;", "&")
    text = _MENTION_RE.sub("", text)
    return [w.lower() for w in _WORD_RE.findall(text)]


def word_frequency_table(df, ini_date, end_date, RTs):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    stop_words = _stopwords()
    counts = {}
    for _, row in df.iterrows():
        rt = row.get("retweet_count", 0) or 0
        for word in _tokenize(str(row.get("text", "")) or ""):
            if word in stop_words:
                continue
            counts[word] = counts.get(word, 0) + (1 + rt if RTs else 1)
    freq = (
        pd.DataFrame(sorted(counts.items(), key=lambda kv: -kv[1]), columns=["word", "freq"])
        .head(1000)
    )
    return freq


def draw_word_frequency(df, ini_date, end_date, RTs, base_title, data_path=None, prefix=None):
    freq = word_frequency_table(df, ini_date, end_date, RTs)

    if not RTs and data_path and prefix:
        freq.to_csv(f"{data_path}/{prefix}_frequency_word.csv", index=False)

    wc = WordCloud(
        width=1200, height=800, background_color="white",
        colormap="Dark2", max_words=100,
    ).generate_from_frequencies(dict(zip(freq["word"], freq["freq"])))

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    subtitle = "(Adding retweet amplification)" if RTs else None
    # my_theme para que el titulo tenga el mismo tamano que el resto de graficas
    my_theme(ax, title=f"{base_title}: most frequent words", subtitle=subtitle)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_media_acumulate
#
# chart line acumulado por medio
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_media_acumulate(df, ini_date, end_date, media, RTs, base_title, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    sub = df[df["username"].isin(media)][["date", "username", "retweet_count"]].copy()

    rows = []
    for username, grp in sub.groupby("username"):
        if not (grp["date"] == end_date).any():
            rows.append({"date": end_date, "username": username, "retweet_count": 0})
    sub = pd.concat([sub, pd.DataFrame(rows)], ignore_index=True)

    sub = sub.sort_values("date")
    grp = sub.groupby(["username", "date"])
    sizes = grp.size()
    rts = grp["retweet_count"].sum()
    tweets_count = (sizes + rts) if RTs else sizes
    counts = tweets_count.reset_index(name="tweets_count")
    counts["cumulative_sum"] = counts.groupby("username")["tweets_count"].cumsum()

    top_media = (
        counts.groupby("username")["tweets_count"].sum().sort_values(ascending=False).head(15).index
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    limit_y = counts["cumulative_sum"].max() if not counts.empty else 1
    for username in top_media:
        g = counts[counts["username"] == username]
        ax.plot(g["date"], g["cumulative_sum"], marker="o", markersize=3, label=username)
        last = g.iloc[-1]
        ax.annotate(f"{username} ({last['cumulative_sum']:,.0f} ref.)",
                     (last["date"], last["cumulative_sum"]), fontsize=8,
                     xytext=(5, 0), textcoords="offset points", va="center")

    apply_date_axis(ax, ini_date, end_date + expand_time(ini_date, end_date, 40))
    ax.set_ylim(0, limit_y * 1.3)
    ax.yaxis.set_major_formatter(ENG_FMT)
    ax.set_ylabel(f"Accumulated Media per {slot_time}")
    subtitle = "(Adding retweet amplification)" if RTs else ""
    my_theme(ax, title=f"{base_title}: Accumulated Media", subtitle=subtitle)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_topics_acumulate
#
# chart line acumulado por topic
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def draw_topics_acumulate(df, topics, ini_date, end_date, RTs, base_title, events=None, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)][["date_slot", "text", "retweet_count"]].copy()

    frames = []
    for _, t in topics.iterrows():
        topic = t["topics"]
        pattern = re.compile(rf"\b{re.escape(topic.lower())}\b")
        mask = df["text"].str.lower().apply(lambda s: bool(pattern.search(s)) if isinstance(s, str) else False)
        aux = df[mask].copy()
        aux["topics"] = topic
        aux["retweet_count"] = aux["retweet_count"].fillna(0)
        frames.append(aux)
    topics_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["date_slot", "text", "retweet_count", "topics"])

    rows = []
    for topic, grp in topics_df.groupby("topics"):
        if not (grp["date_slot"] == end_date).any():
            rows.append({"date_slot": end_date, "topics": topic, "retweet_count": 0})
    topics_df = pd.concat([topics_df, pd.DataFrame(rows)], ignore_index=True)

    grp = topics_df.groupby(["topics", "date_slot"])
    sizes = grp.size()
    rts = grp["retweet_count"].sum()
    num_topics = (sizes + rts) if RTs else sizes
    grouped = num_topics.reset_index(name="num_topics").sort_values(["topics", "date_slot"])
    grouped["cumulative_sum"] = grouped.groupby("topics")["num_topics"].cumsum()

    color_map = dict(zip(topics["topics"], topics["color"].astype(str).str.replace(",", "")))
    limit_y = grouped["cumulative_sum"].max() if not grouped.empty else 1

    fig, ax = plt.subplots(figsize=(10, 6))
    for topic, g in grouped.groupby("topics"):
        ax.plot(g["date_slot"], g["cumulative_sum"], linewidth=2, alpha=0.7,
                color=color_map.get(topic), label=topic)
        last = g[g["date_slot"] == g["date_slot"].max()].iloc[-1]
        ax.annotate(f"{topic} ({last['cumulative_sum']:,.0f} ref.)",
                     (last["date_slot"], last["cumulative_sum"]), fontsize=8,
                     color=color_map.get(topic), xytext=(5, 0), textcoords="offset points")

    if events is not None and not events.empty:
        ev = events[(events["date"] >= ini_date) & (events["date"] <= end_date)]
        for _, e in ev.iterrows():
            ax.axvline(e["date"], linestyle="--", color=COLOR_TEXTO)
            ax.text(e["date"], limit_y * 1.4, e["event"], color=COLOR_TEXTO, fontsize=9, va="top")

    apply_date_axis(ax, ini_date, end_date + expand_time(ini_date, end_date, 40))
    ax.set_ylim(0, limit_y * 1.6)
    ax.yaxis.set_major_formatter(ENG_FMT)
    ax.set_ylabel(f"Accumulated topics per {slot_time}")
    subtitle = "(Adding retweet amplification)" if RTs else ""
    my_theme(ax, title=f"{base_title}: Accumulated topics", subtitle=subtitle)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# words_frequency_by_community
#
# Word cloud de cada comunidad en una rejilla
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def words_frequency_by_community(df, communities, base_title):
    stop_words = _stopwords()
    merged = df.merge(communities, on="community", how="left")
    merged = merged[merged["community"].isin(communities["community"])]

    ncols = 2
    n = len(communities)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(10, 4 * nrows), squeeze=False)
    fig.suptitle(f"{base_title}: Most frequent words by group", color=COLOR_TEXTO,
                 fontsize=17, fontweight="bold", x=0.02, ha="left")

    for i, (_, comm) in enumerate(communities.iterrows()):
        ax = axes[i // ncols][i % ncols]
        sub = merged[merged["community"] == comm["community"]]
        counts = {}
        for text in sub["text"].dropna():
            for word in _tokenize(text):
                if word in stop_words:
                    continue
                counts[word] = counts.get(word, 0) + 1
        top = dict(sorted(counts.items(), key=lambda kv: -kv[1])[:15])
        if top:
            wc = WordCloud(width=800, height=500, background_color="white",
                            colormap="Dark2").generate_from_frequencies(top)
            ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        ax.set_title(comm["name_community"], color="white", fontsize=11,
                     backgroundcolor=comm["color"])

    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# tweets_by_community
#
# Bar chart desglosado por comunidades
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def tweets_by_community(df, ini_date, end_date, communities, base_title, events=None, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    top_community = list(communities["community"])
    sub = df[df["community"].isin(top_community)].copy()

    grp = sub.groupby(["date_slot", "community"])
    num_tweets = grp.size() + grp["retweet_count"].sum()
    grouped = num_tweets.reset_index(name="num_tweets")
    pivot = grouped.pivot(index="date_slot", columns="community", values="num_tweets").fillna(0)
    pivot = pivot.reindex(columns=top_community, fill_value=0)
    pivot = pivot.reindex(pd.date_range(ini_date, end_date, freq=slot_time), fill_value=0)

    color_map = dict(zip(communities["community"], communities["color"]))
    name_map = dict(zip(communities["community"], communities["name_community"]))
    tweet_peak = pivot.sum(axis=1).max() if not pivot.empty else 1

    fig, ax = plt.subplots(figsize=(10, 6))
    bottom = np.zeros(len(pivot))
    width = (pivot.index[1] - pivot.index[0]).total_seconds() / 86400 * 0.8 if len(pivot) > 1 else 0.03
    for community in top_community:
        values = pivot[community].values
        ax.bar(pivot.index, values, bottom=bottom, width=width,
               color=color_map.get(community), alpha=0.7, label=name_map.get(community))
        bottom += values

    if events is not None and not events.empty:
        ev = events[(events["date"] >= ini_date) & (events["date"] <= end_date)]
        for _, e in ev.iterrows():
            ax.axvline(e["date"], linestyle="--", color=COLOR_TEXTO)

    ax.set_ylim(0, tweet_peak * 1.3)
    ax.yaxis.set_major_formatter(ENG_FMT)
    ax.set_ylabel(f"Num tweets per {slot_time}")
    apply_date_axis(ax, ini_date, end_date)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    my_theme(ax, title=f"{base_title}: Tweets by group")
    fig.tight_layout()
    return fig
