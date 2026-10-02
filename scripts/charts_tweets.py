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
from matplotlib.lines import Line2D
from matplotlib.ticker import EngFormatter, FuncFormatter
from wordcloud import WordCloud

from utils_charts import (apply_date_axis, draw_events, expand_time, legend_top, my_theme,
                          my_theme_colored_title, style_twin_axis)

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

    my_theme_colored_title(ax, [
        (f"{base_title}: ", None),
        ("Tweets", color_tweets),
        (f" per {slot_time} vs ", None),
        ("Reach influencers", color_reach),
    ], subtitle=f"Reach influencers >= {ENG_FMT(min_reach)}")
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

    my_theme_colored_title(ax, [
        (f"{base_title}: ", None),
        ("Tweets", color_tweets),
        (f" per {slot_time} vs ", None),
        ("Reach", color_reach),
    ])
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

    my_theme_colored_title(ax, [
        (f"{base_title}: ", None),
        ("Tweets", color_tweets),
        (f" per {slot_time} vs ", None),
        ("RTs influencers", color_RT),
    ], subtitle=f"RTs influencers >= {ENG_FMT(min_RTs)}")
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

    my_theme_colored_title(ax, [
        (f"{base_title}: ", None),
        ("Tweets", color_tweets),
        (f" per {slot_time} vs ", None),
        ("RTs", color_RT),
    ])
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
def draw_comments_vs_RTs(df, ini_date, end_date, base_title):
    # umbral fijo, no parametrizado (como en el cuaderno R): por debajo de 30
    # comentarios la grafica se inunda de puntos y etiquetas sin interes
    min_comments = 30

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
        fig, ax = plt.subplots(figsize=(10, 6))
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

    fig, ax = plt.subplots(figsize=(10, 6))
    # triangulo de la zona polemica (comments > RTs), como el geom_polygon del
    # cuaderno R: vertices (0,0), (0,max*1.4), (max*1.4,max*1.4). fill_between
    # rellenaba por debajo de la diagonal (la zona equivocada).
    ax.fill([0, 0, max_comments * 1.4], [0, max_comments * 1.4, max_comments * 1.4],
            color=color_comments, alpha=0.25, linewidth=0)
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
# Dos escrituras: latina (en, es, ca, fr; el rango cubre todos los acentos y
# ligaduras de Latin-1 y deja fuera los signos × ÷) y arabe. Los datasets
# mezclan idiomas, asi que la palabra se reconoce por como esta escrita, no
# por el campo lang del tweet
_WORD_RE = re.compile(r"[a-zA-ZÀ-ÖØ-öø-ÿŒœ]{2,}|[\u0621-\u0655\u0670\u066E-\u06D3]{2,}")

# Signos que no son letra: harakat (vocales cortas), tanwin, shadda, sukun,
# hamza suelta sobre/bajo la linea, alef superscript y tatweel (el guion de
# alargamiento tipografico). Estorban para agrupar y para casar con stopwords
_AR_DIACRITICS_RE = re.compile(r"[\u064B-\u0655\u0640\u0670]")
_AR_RE = re.compile(r"[\u0600-\u06FF]")
# Variantes de una misma letra: alef con hamza/madda/wasla, alef maqsura, ta
# marbuta, hamza sobre waw/ya y las formas persas de kaf y ya. Sin unificarlas
# la misma palabra se cuenta dos veces
_AR_NORMALIZE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي",
    "ک": "ك", "ی": "ي",
})
# Romanizacion letra a letra al estilo ALA-LC simplificado (sin puntos ni
# subrayados, que en una nube de palabras solo ensucian). El arabe se escribe
# sin vocales cortas, asi que salen palabras consonanticas tipo "almghrb": no
# es una transcripcion fonetica, es una etiqueta legible y buscable
_AR_TO_LATIN = {
    "ا": "a", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h", "خ": "kh",
    "د": "d", "ذ": "dh", "ر": "r", "ز": "z", "س": "s", "ش": "sh", "ص": "s",
    "ض": "d", "ط": "t", "ظ": "z", "ع": "'", "غ": "gh", "ف": "f", "ق": "q",
    "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h", "و": "w", "ي": "y",
    "ء": "",
    # persa/urdu: aparecen en textos escritos en alfabeto arabe
    "پ": "p", "چ": "ch", "ژ": "zh", "گ": "g",
}
# Articulo definido y procliticos de una letra (wa-, bi-, ka-, fa-, li-, y la
# contraccion li+al). "almghrb", "walmghrb" y "balmghrb" son la misma palabra y
# sin quitarles el articulo se reparten por la nube. La conjuncion "wa" suelta
# NO se quita (en muchisimas palabras es letra raiz: wzyr ministro, wald padre),
# pero delante del articulo solo puede ser proclitico, asi que ahi se va con el
_AR_ARTICLE = "ال"
_AR_PROCLITICS = "وبكفل"
_AR_LI_AL = "لل"
_AR_LETTERS = "\u0621-\u064A"
# Sufijos pegados de uso corriente: nisba (-y, -yh: "marroqui" de "Marruecos"),
# plurales y pronombres posesivos. Un topic geografico sin ellos pierde la
# mitad de las menciones, y una lista cerrada no abre la puerta a los falsos
# positivos que traeria buscar el termino como simple subcadena
_AR_SUFFIXES = ("ية", "ي", "ات", "ون", "ين", "ها", "هما", "هم", "ه", "ا")


def _clean_ar(word):
    """Quita solo lo que no es letra (harakat, tatweel). La palabra sigue
    escrita en arabe correcto, que es lo que necesita un traductor: unificar
    ademas las variantes de letra la estropea (الجزائري -> الجزايري deja de ser
    "argelino" y pasa a transcribirse como "Jazairy")."""
    return _AR_DIACRITICS_RE.sub("", word)


def _normalize_ar(word):
    """_clean_ar + unificacion de variantes de letra. Es la forma con la que se
    cuenta, se agrupa y se casan las stopwords, no la que se traduce."""
    return _clean_ar(word).translate(_AR_NORMALIZE)


def _strip_ar_article(word):
    if word.startswith(_AR_ARTICLE):
        stem = word[2:]
    elif len(word) > 3 and word[0] in _AR_PROCLITICS and word[1:3] == _AR_ARTICLE:
        stem = word[3:]
    elif word.startswith(_AR_LI_AL):
        stem = word[2:]
    else:
        return word
    # si lo que queda no llega a 3 letras no es una palabra: esas dos letras son
    # parte de la raiz, no un articulo (allh -> lh, alf -> f, balwn -> wn)
    return stem if len(stem) >= 3 else word


def _romanize_ar(word):
    """Palabra arabe (ya normalizada) -> grafia latina. WordCloud dibuja las
    letras arabes sueltas y de izquierda a derecha (no hace el shaping ni el
    bidi), y la fuente por defecto ni siquiera las tiene: en la nube saldrian
    cuadraditos. Romanizar es lo que hace legible el resultado."""
    return "".join(_AR_TO_LATIN.get(ch, ch) for ch in word)


_STOPWORDS_CACHE = None
_AR_STOPWORDS_CACHE = None


def _nltk_stopwords():
    import nltk
    from nltk.corpus import stopwords
    try:
        stopwords.words("english")
    except LookupError:
        nltk.download("stopwords", quiet=True)
    return stopwords


def _stopwords():
    """Stopwords en escritura latina (en, es, fr, ca), equivalente a
    stop_words + tm::stopwords(). Cacheadas a nivel de módulo: cargar el
    corpus de nltk en cada gráfica encarecía visiblemente los wordclouds."""
    global _STOPWORDS_CACHE
    if _STOPWORDS_CACHE is not None:
        return _STOPWORDS_CACHE
    sw = _nltk_stopwords()
    words = set()
    for lang in ("english", "spanish", "french"):
        words |= {w.lower() for w in sw.words(lang)}
    # la lista francesa de nltk (snowball) es solo pronombres y conjugaciones
    # de avoir/etre: se completa con las funcionales mas frecuentes, con y sin
    # acento (en Twitter se escriben de las dos formas)
    french = {
        "où", "ou", "ça", "ca", "cet", "cette", "celui", "celle", "ceux", "celles",
        "cela", "dont", "donc", "alors", "aussi", "autre", "autres", "avant",
        "après", "apres", "bien", "chez", "comme", "comment", "contre", "depuis",
        "déjà", "deja", "dès", "encore", "être", "etre", "faire", "fait", "ici",
        "jamais", "juste", "là", "leurs", "moins", "non", "oui", "peu", "plus",
        "plusieurs", "pendant", "pourquoi", "quand", "quel", "quelle", "quels",
        "quelles", "quelque", "quelques", "rien", "sans", "sauf", "selon", "sinon",
        "sous", "souvent", "tant", "tel", "telle", "toujours", "tous", "tout",
        "toute", "toutes", "très", "tres", "trop", "vers", "voici", "voilà",
        "voila", "vraiment",
    }
    # nltk no incluye catalan: lista minima de uso frecuente
    catalan = {
        "el", "la", "els", "les", "de", "del", "dels", "un", "una", "uns",
        "unes", "i", "o", "que", "no", "en", "amb", "per", "es", "se", "al",
        "als", "com", "ja", "molt", "pero", "si", "aquest", "aquesta", "te",
    }
    _STOPWORDS_CACHE = words | french | catalan
    return _STOPWORDS_CACHE


def _ar_stopwords():
    """Stopwords arabes normalizadas igual que los tokens. Se filtran en arabe,
    antes de romanizar, a proposito: sus transcripciones ("ala", "ana", "ant",
    "bat"...) colisionan con palabras latinas corrientes y las borrarian de las
    nubes de datasets que no tienen nada de arabe."""
    global _AR_STOPWORDS_CACHE
    if _AR_STOPWORDS_CACHE is not None:
        return _AR_STOPWORDS_CACHE
    sw = _nltk_stopwords()
    _AR_STOPWORDS_CACHE = {_normalize_ar(w) for w in sw.words("arabic")}
    return _AR_STOPWORDS_CACHE


def _tokenize_src(text):
    """[(token, forma original)]. El token es lo que se cuenta y se dibuja; la
    forma original es la palabra tal como aparecia en el tweet (normalizada) y
    es la unica que un traductor puede entender: a "almghrb" no hay quien le
    saque nada. En escritura latina las dos coinciden."""
    text = _URL_RE.sub("", text)
    text = _RT_RE.sub("", text)
    text = text.replace("&amp;", "&")
    text = _MENTION_RE.sub("", text)
    words = []
    for word in _WORD_RE.findall(text):
        if not _AR_RE.search(word):
            words.append((word.lower(), word.lower()))
            continue
        ar_stop = _ar_stopwords()
        source = _clean_ar(word)
        norm = source.translate(_AR_NORMALIZE)
        if norm in ar_stop:
            continue
        # el articulo se quita despues de filtrar: las stopwords arabes de
        # nltk lo llevan puesto (alty, aldhy, allaty...) y sin el no casan
        word = _strip_ar_article(norm)
        if word in ar_stop:
            continue
        word = _romanize_ar(word)
        if len(word) < 2:
            continue
        # la forma original conserva el articulo: "almghrb" es Marruecos y
        # "mghrb" a secas es el poniente, y el traductor lo nota
        words.append((word.lower(), source))
    return words


def _tokenize(text):
    return [word for word, _ in _tokenize_src(text)]


def word_frequency_table(df, ini_date, end_date, RTs):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    stop_words = _stopwords()
    counts = {}
    # zip sobre las dos columnas en vez de df.iterrows(): iterrows materializa
    # una Series por fila (30+ columnas) y dominaba el tiempo de los wordclouds
    texts = df["text"].fillna("") if "text" in df.columns else []
    rts = (pd.to_numeric(df["retweet_count"], errors="coerce").fillna(0)
           if "retweet_count" in df.columns else pd.Series(0, index=df.index))
    # forma original de cada token, para poder traducirlo despues: de las
    # variantes que se funden en un mismo token se guarda la mas usada
    sources = {}
    for text, rt in zip(texts, rts):
        weight = 1 + int(rt) if RTs else 1
        for word, source in _tokenize_src(str(text)):
            if word in stop_words:
                continue
            counts[word] = counts.get(word, 0) + weight
            seen = sources.setdefault(word, {})
            seen[source] = seen.get(source, 0) + 1
    freq = (
        pd.DataFrame(sorted(counts.items(), key=lambda kv: -kv[1]), columns=["word", "freq"])
        .head(1000)
    )
    freq["word_src"] = [max(sources[w].items(), key=lambda kv: kv[1])[0] for w in freq["word"]]
    return freq


def draw_word_frequency(df, ini_date, end_date, RTs, base_title, data_path=None, prefix=None,
                       translate=None):
    freq = word_frequency_table(df, ini_date, end_date, RTs)
    if translate is not None:
        freq = translate(freq)

    # el CSV se guarda ya traducido y con la columna word_src: la nube dice
    # "fuerzas" y el fichero dice de que palabra arabe ha salido
    if not RTs and data_path and prefix:
        freq.to_csv(f"{data_path}/{prefix}_frequency_word.csv", index=False)

    wc = WordCloud(
        width=1200, height=800, background_color="white",
        colormap="Dark2", max_words=100,
    ).generate_from_frequencies(dict(zip(freq["word"], freq["freq"])))

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    notes = ["Adding retweet amplification"] if RTs else []
    if freq.attrs.get("translated"):
        notes.append("words machine-translated {0} -> {1}".format(*freq.attrs["translated"]))
    subtitle = f"({'; '.join(notes)})" if notes else None
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
    finals, colors = {}, {}
    for username in top_media:
        g = counts[counts["username"] == username]
        line = ax.plot(g["date"], g["cumulative_sum"], marker="o", markersize=3, label=username)[0]
        colors[username] = line.get_color()
        finals[username] = (g["date"].iloc[-1], g["cumulative_sum"].iloc[-1])

    # etiquetas al final de cada línea separadas verticalmente un mínimo para que
    # no se solapen (con muchos medios de valores parecidos se pisaban); van del
    # color de su línea, así se distinguen aunque se muevan
    min_sep = limit_y * 0.03
    label_y, prev = {}, None
    for username in sorted(top_media, key=lambda u: finals[u][1]):
        y = finals[username][1]
        if prev is not None and y - prev < min_sep:
            y = prev + min_sep
        label_y[username] = y
        prev = y
    for username in top_media:
        x_last, y_real = finals[username]
        ax.annotate(f"{username} ({y_real:,.0f} ref.)", (x_last, label_y[username]),
                    fontsize=8, xytext=(5, 0), textcoords="offset points",
                    va="center", color=colors[username])

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
def _topic_terms(row):
    """Terminos que cuentan como un topic: el nombre con el que se etiqueta la
    grafica mas los sinonimos de la columna opcional "aliases", separados por
    "|". Asi se busca en los idiomas del corpus y se etiqueta en el propio:
    topics,color,aliases -> Argelia,#F50202,الجزائر|algérie|algeria"""
    aliases = row.get("aliases", "")
    aliases = "" if aliases is None or pd.isna(aliases) else str(aliases)
    return [str(row["topics"])] + [a.strip() for a in aliases.split("|") if a.strip()]


def _topic_pattern(term):
    """En arabe el articulo y los procliticos van pegados a la palabra (sbth,
    wsbth, baljzayr): exigir frontera de palabra por delante, como en las
    lenguas latinas, dejaria fuera todas esas formas. Se admiten delante hasta
    dos procliticos y el articulo, y por detras los sufijos de _AR_SUFFIXES,
    que es lo que hace que "Marruecos" cuente tambien "marroqui"."""
    if _AR_RE.search(term):
        suffixes = "|".join(_normalize_ar(x) for x in _AR_SUFFIXES)
        return re.compile(
            f"(?<![{_AR_LETTERS}])[{_AR_PROCLITICS}]{{0,2}}(?:{_AR_ARTICLE})?"
            f"{re.escape(_normalize_ar(term))}(?:{suffixes})?(?![{_AR_LETTERS}])"
        )
    return re.compile(rf"\b{re.escape(term.lower())}\b")


def draw_topics_acumulate(df, topics, ini_date, end_date, RTs, base_title, events=None, slot_time="1h"):
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)][["date_slot", "text", "retweet_count"]].copy()

    # el texto se prepara una vez, no una por topic (eran diez pasadas sobre
    # cientos de miles de filas); la version normalizada solo si hay arabe
    terms = {str(t["topics"]): _topic_terms(t) for _, t in topics.iterrows()}
    text = df["text"].fillna("").astype(str).str.lower()
    text_ar = (text.map(_normalize_ar)
               if any(_AR_RE.search(w) for ws in terms.values() for w in ws) else text)

    frames = []
    for topic, words in terms.items():
        mask = pd.Series(False, index=df.index)
        for word in words:
            source = text_ar if _AR_RE.search(word) else text
            mask |= source.str.contains(_topic_pattern(word), regex=True)
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
    finals = {}
    for topic, g in grouped.groupby("topics"):
        ax.plot(g["date_slot"], g["cumulative_sum"], linewidth=2, alpha=0.7,
                color=color_map.get(topic), label=topic)
        last = g[g["date_slot"] == g["date_slot"].max()].iloc[-1]
        finals[topic] = (last["date_slot"], last["cumulative_sum"])

    # etiquetas al final separadas verticalmente un mínimo para que no se solapen
    # (con muchos topics de valores parecidos se pisaban), del color de su línea
    topic_order = list(finals.keys())
    min_sep = limit_y * 0.035
    label_y, prev = {}, None
    for topic in sorted(topic_order, key=lambda t: finals[t][1]):
        y = finals[topic][1]
        # la primera etiqueta no se pega al eje: ahi se corta por la mitad
        y = max(y, limit_y * 0.02) if prev is None else y
        if prev is not None and y - prev < min_sep:
            y = prev + min_sep
        label_y[topic] = y
        prev = y

    # linea guia del final de cada curva hasta su etiqueta. Con un topic
    # dominante el resto se apelotona abajo y las etiquetas, ya separadas para
    # no pisarse, acaban muy lejos de su curva: sin la guia parece que ese
    # topic no tiene linea
    dx = expand_time(ini_date, end_date, 3)
    for topic in topic_order:
        x_last, y_real = finals[topic]
        if abs(label_y[topic] - y_real) > min_sep / 2:
            ax.plot([x_last, x_last + dx], [y_real, label_y[topic]],
                    linewidth=0.6, alpha=0.5, color=color_map.get(topic))
        ax.annotate(f"{topic} ({y_real:,.0f} ref.)", (x_last + dx, label_y[topic]),
                    fontsize=8, color=color_map.get(topic),
                    xytext=(3, 0), textcoords="offset points", va="center")

    head_room = max(1.6, draw_events(ax, events, ini_date, end_date, limit_y))

    apply_date_axis(ax, ini_date, end_date + expand_time(ini_date, end_date, 40))
    ax.set_ylim(0, limit_y * head_room)
    ax.yaxis.set_major_formatter(ENG_FMT)
    ax.set_ylabel(f"Accumulated topics per {slot_time}")
    subtitle = "(Adding retweet amplification)" if RTs else ""
    my_theme(ax, title=f"{base_title}: Accumulated topics", subtitle=subtitle)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_about_acumulate
#
# chart line acumulado por país de la cuenta (about_account_based_in, de
# Download > About), los top_n más frecuentes
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

# paleta categórica validada (8 tonos, orden fijo) + dos grises neutros para los
# puestos 9 y 10: el color sigue al país por su puesto en el total del periodo
ABOUT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
                "#008300", "#4a3aa7", "#e34948", "#5f5e5a", "#a3a29b"]


def draw_about_acumulate(df, ini_date, end_date, RTs, base_title, events=None, slot_time="1h",
                         top_n=10):
    """Tweets acumulados por país de la cuenta del autor (about_account_based_in).
    Con RTs, cada tweet cuenta además los RTs que recibió (amplificación), como
    en draw_topics_acumulate. Los top_n países se eligen SIEMPRE por número de
    tweets, también con RTs: así las dos versiones muestran los mismos países con
    los mismos colores y se comparan una al lado de la otra."""
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    df = df.dropna(subset=["about_account_based_in"])[["date_slot", "about_account_based_in",
                                                        "retweet_count"]].copy()
    df["retweet_count"] = pd.to_numeric(df["retweet_count"], errors="coerce").fillna(0)
    df["weight"] = 1 + df["retweet_count"] if RTs else 1

    countries = list(df["about_account_based_in"].value_counts().head(top_n).index)
    color_map = dict(zip(countries, ABOUT_COLORS))

    slots = pd.date_range(ini_date.floor("h"), end_date.floor("h"), freq="h")
    grouped = (df[df["about_account_based_in"].isin(countries)]
               .groupby(["date_slot", "about_account_based_in"])["weight"].sum()
               .unstack(fill_value=0).reindex(slots, fill_value=0)
               .reindex(columns=countries, fill_value=0).cumsum())
    limit_y = grouped.values.max() if grouped.size else 1

    fig, ax = plt.subplots(figsize=(10, 6))
    finals = {}
    for country in countries:
        ax.plot(grouped.index, grouped[country], linewidth=2, alpha=0.85,
                color=color_map[country], label=country)
        finals[country] = (grouped.index[-1], grouped[country].iloc[-1])

    # etiquetas al final (país y valor acumulado) separadas verticalmente un
    # mínimo para que no se pisen, con línea guía hasta su curva (como en topics)
    min_sep = limit_y * 0.035
    label_y, prev = {}, None
    for country in sorted(countries, key=lambda c: finals[c][1]):
        y = finals[country][1]
        y = max(y, limit_y * 0.02) if prev is None else y
        if prev is not None and y - prev < min_sep:
            y = prev + min_sep
        label_y[country] = y
        prev = y
    dx = expand_time(ini_date, end_date, 3)
    for country in countries:
        x_last, y_real = finals[country]
        if abs(label_y[country] - y_real) > min_sep / 2:
            ax.plot([x_last, x_last + dx], [y_real, label_y[country]],
                    linewidth=0.6, alpha=0.5, color=color_map[country])
        ax.annotate(f"{country} ({y_real:,.0f})", (x_last + dx, label_y[country]),
                    fontsize=8, color=color_map[country],
                    xytext=(3, 0), textcoords="offset points", va="center")

    head_room = max(1.15, draw_events(ax, events, ini_date, end_date, limit_y))

    apply_date_axis(ax, ini_date, end_date + expand_time(ini_date, end_date, 40))
    ax.set_ylim(0, limit_y * head_room)
    ax.yaxis.set_major_formatter(ENG_FMT)
    ax.set_ylabel(f"Accumulated {'tweets + RTs' if RTs else 'tweets'} per {slot_time}")
    subtitle = ("Country the account is based in (X about), top "
                f"{len(countries)}" + (" (Adding retweet amplification)" if RTs else ""))
    my_theme(ax, title=f"{base_title}: Accumulated tweets by account country", subtitle=subtitle)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_about_scatter
#
# dispersión escritura vs. amplificación por país de la cuenta (about),
# coloreada por continente
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

# regiones que X da en lugar de un país -> código de continente de geonames
ABOUT_REGIONS = {
    "Europe": "EU", "Eastern Europe (Non-EU)": "EU", "North America": "NA",
    "Caribbean": "NA", "Central America": "NA", "South America": "SA", "Africa": "AF",
    "North Africa": "AF", "Asia": "AS", "West Asia": "AS", "East Asia": "AS",
    "South Asia": "AS", "Southeast Asia": "AS", "Central Asia": "AS",
    "Australasia": "OC", "Oceania": "OC",
}
# nombres que da X (oficiales, tipo ONU) que geonamescache escribe de otra forma
ABOUT_COUNTRY_ALIASES = {
    "Netherlands": "The Netherlands", "Czech Republic": "Czechia", "Viet Nam": "Vietnam",
    "Russian Federation": "Russia", "Korea": "South Korea", "Macedonia": "North Macedonia",
    "Congo": "Republic of the Congo", "Syrian Arab Republic": "Syria",
    "Côte d'Ivoire": "Ivory Coast", "Curaçao": "Curacao",
    "Lao People's Democratic Republic": "Laos",
}
# continentes en orden fijo con los 6 primeros tonos de la paleta categórica
ABOUT_CONTINENTS = [("EU", "Europe", "#2a78d6"), ("NA", "North America", "#eb6834"),
                    ("AS", "Asia", "#1baf7a"), ("SA", "South America", "#eda100"),
                    ("AF", "Africa", "#e87ba4"), ("OC", "Oceania", "#008300")]
_continent_table = None


def _about_continent(name):
    """Código de continente (EU, NA, AS, SA, AF, OC) de un país o región de X."""
    global _continent_table
    if name in ABOUT_REGIONS:
        return ABOUT_REGIONS[name]
    if _continent_table is None:
        import geonamescache
        _continent_table = {c["name"]: c["continentcode"]
                            for c in geonamescache.GeonamesCache().get_countries().values()}
    return _continent_table.get(ABOUT_COUNTRY_ALIASES.get(name, name))


def draw_about_scatter(df, ini_date, end_date, base_title, min_tweets=10):
    """Escritura vs. amplificación por país de la cuenta del autor: tweets (X) frente
    a RTs recibidos por tweet (Y), ambos en escala log, con las medianas como
    cuadrantes. Color = continente; círculo hueco = región (X no da el país). Solo
    países con >= min_tweets tweets, para que uno con 2 tweets virales no domine."""
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    df = df.dropna(subset=["about_account_based_in"]).copy()
    df["retweet_count"] = pd.to_numeric(df["retweet_count"], errors="coerce").fillna(0)
    agg = (df.groupby("about_account_based_in")
           .agg(tweets=("about_account_based_in", "size"), rts=("retweet_count", "sum")))
    agg = agg[agg["tweets"] >= min_tweets].copy()

    fig, ax = plt.subplots(figsize=(10, 7))
    if agg.empty:
        ax.text(0.5, 0.5, f"No country with >= {min_tweets} tweets", ha="center",
                transform=ax.transAxes, color=COLOR_TEXTO)
        my_theme(ax, title=f"{base_title}: Writing vs. amplification by account country")
        return fig

    agg["rts_per_tweet"] = agg["rts"] / agg["tweets"]
    agg["is_region"] = agg.index.isin(list(ABOUT_REGIONS))
    agg["continent"] = [_about_continent(n) for n in agg.index]
    cont_color = {code: color for code, _, color in ABOUT_CONTINENTS}
    colors = agg["continent"].map(cont_color).fillna("#a3a29b")
    y = agg["rts_per_tweet"].clip(lower=0.1)  # en log los de 0 RTs quedan pegados abajo

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.axvline(agg["tweets"].median(), color=COLOR_TEXTO, linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(agg["rts_per_tweet"].median(), color=COLOR_TEXTO, linestyle="--",
               linewidth=0.8, alpha=0.6)

    countries, regions = agg[~agg["is_region"]], agg[agg["is_region"]]
    ax.scatter(countries["tweets"], y[countries.index], s=60, color=colors[countries.index],
               alpha=0.9, edgecolor="white", linewidth=1, zorder=3)
    ax.scatter(regions["tweets"], y[regions.index], s=60, facecolor="white",
               edgecolor=colors[regions.index], linewidth=1.8, zorder=3)
    _repel(ax, list(agg["tweets"]), list(y), list(agg.index), size=8, max_texts=len(agg),
           min_sep_px=None, ha="left", va="center")

    xmin, xmax = agg["tweets"].min() * 0.8, agg["tweets"].max() * 1.6
    ymin, ymax = y.min() * 0.6, y.max() * 1.8
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    kw = dict(color=COLOR_TEXTO, fontsize=9, alpha=0.8, style="italic")
    ax.text(xmax / 1.05, ymax / 1.1, "writes a lot, highly amplified", ha="right", va="top", **kw)
    ax.text(xmin * 1.05, ymax / 1.1, "writes little, highly amplified", ha="left", va="top", **kw)
    ax.text(xmax / 1.05, ymin * 1.1, "writes a lot, little amplified", ha="right", va="bottom", **kw)
    ax.text(xmin * 1.05, ymin * 1.1, "writes little, little amplified", ha="left", va="bottom", **kw)

    fmt = FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(fmt)
        axis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_xlabel("Tweets (log)")
    ax.set_ylabel("RTs received per tweet (log)")

    present = [(name, color) for code, name, color in ABOUT_CONTINENTS
               if code in set(agg["continent"])]
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7, color=color)
               for _, color in present]
    handles.append(Line2D([], [], marker="o", linestyle="", markersize=7, markerfacecolor="white",
                          markeredgecolor=COLOR_TEXTO, markeredgewidth=1.5))
    legend_top(ax, handles, [n for n, _ in present] + ["Region (no country)"], fontsize=8)
    my_theme(ax, title=f"{base_title}: Writing vs. amplification by account country",
             subtitle=f"Countries with >= {min_tweets} tweets · dashed lines = medians",
             subtitle_y=1.055, title_pad=48)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# draw_about_suspicious
#
# perfiles sospechosos por cambios de nombre: antigüedad vs. seguidores
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def _kmg(v, _):
    """Etiquetas de eje log: 1, 10, 100, 1K, 10K, 100K, 1M, 10M."""
    for div, suf in ((1e6, "M"), (1e3, "K")):
        if v >= div:
            return f"{v / div:g}{suf}"
    return f"{v:g}"


def draw_about_suspicious(df, ini_date, end_date, base_title, min_changes=5,
                          young_years=3, many_followers=5000):
    """Autores con >= min_changes cambios de nombre (about_username_changes):
    antigüedad de la cuenta (X) frente a seguidores (Y, log), tamaño = cambios
    de nombre, color = país de la cuenta. De fondo, en gris, todos los autores.
    Se sombrea la zona "joven y con muchos seguidores" (< young_years años y
    >= many_followers) y se rotulan sus cuentas, las más seguidas y las que más
    han cambiado de nombre. Colores de país como draw_about_acumulate (los
    países con más tweets, en ese orden), para reconocerlos igual en todas."""
    df = df[(df["date"] >= ini_date) & (df["date"] <= end_date)]
    users = df.sort_values("date").drop_duplicates("user_id", keep="last").copy()
    users["changes"] = pd.to_numeric(users["about_username_changes"], errors="coerce")
    users["followers"] = pd.to_numeric(users["followers_count"], errors="coerce").clip(lower=1)
    created = pd.to_datetime(users["created_at"], utc=True, errors="coerce").dt.tz_localize(None)
    users["age"] = (end_date - created).dt.days / 365.25
    users = users.dropna(subset=["age", "followers"])
    sus = users[users["changes"] >= min_changes].copy()

    palette = ABOUT_COLORS[:8]
    ranking = list(df["about_account_based_in"].value_counts().head(len(palette)).index)
    color_map = dict(zip(ranking, palette))
    other = "#a3a29b"
    sus["color"] = sus["about_account_based_in"].map(color_map).fillna(other)
    sus = sus.sort_values("changes", ascending=False)  # las burbujas grandes, debajo

    def size(changes):  # área proporcional a los cambios, con un mínimo visible
        return 18 + np.sqrt(changes) * 40

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_yscale("log")
    ax.scatter(users["age"], users["followers"], s=6, color="#d3d1c7", alpha=0.6,
               linewidth=0, zorder=1)
    ymax = max(users["followers"].max(), many_followers) * 2.5
    ax.fill_between([0, young_years], many_followers, ymax, color="#e34948", alpha=0.07, zorder=0)
    ax.text(0.15, ymax / 1.3, f"young (< {young_years} y) & many followers (≥ {many_followers:,})",
            color="#e34948", fontsize=9, style="italic", va="top")

    if not sus.empty:
        ax.scatter(sus["age"], sus["followers"], s=size(sus["changes"]), color=sus["color"],
                   alpha=0.8, edgecolor="white", linewidth=0.8, zorder=3)
        zone = sus[(sus["age"] < young_years) & (sus["followers"] >= many_followers)]
        labelled = pd.concat([zone, sus.nlargest(6, "followers"),
                              sus.nlargest(5, "changes")]).drop_duplicates("user_id")
        _repel(ax, list(labelled["age"]), list(labelled["followers"]),
               [f"@{n} ({int(c)})" for n, c in zip(labelled["username"], labelled["changes"])],
               size=8, max_texts=len(labelled), min_sep_px=None, ha="left", va="center")

    ax.set_xlim(0, users["age"].max() * 1.03)
    ax.set_ylim(1, ymax)
    ax.yaxis.set_major_formatter(FuncFormatter(_kmg))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_xlabel("Account age (years)")
    ax.set_ylabel("Followers (log)")

    present = set(sus["about_account_based_in"])
    shown = [c for c in ranking if c in present]
    handles = [Line2D([], [], marker="o", linestyle="", markersize=7, color=color_map[c])
               for c in shown]
    labels = list(shown)
    if (sus["color"] == other).any():
        handles.append(Line2D([], [], marker="o", linestyle="", markersize=7, color=other))
        labels.append("Other")
    country_leg = legend_top(ax, handles, labels, fontsize=8) if handles else None

    for c in (5, 20, 100):  # leyenda de tamaños, abajo a la derecha
        ax.scatter([], [], s=size(c), color="white", edgecolor=COLOR_TEXTO, label=f"{c} changes")
    size_leg = ax.legend(loc="lower right", frameon=False, fontsize=8, labelspacing=1.4,
                         borderpad=1, title="Username changes", title_fontsize=8)
    for t in size_leg.get_texts() + [size_leg.get_title()]:
        t.set_color(COLOR_TEXTO)
    if country_leg is not None:
        ax.add_artist(country_leg)  # matplotlib solo conserva la última leyenda si no

    my_theme(ax, title=f"{base_title}: Suspicious profiles (≥ {min_changes} username changes)",
             subtitle=f"{len(sus)} of {len(users):,} authors · grey = all authors · "
                      "size = username changes",
             subtitle_y=1.055, title_pad=48)
    fig.tight_layout()
    return fig


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# words_frequency_by_community
#
# Word cloud de cada comunidad en una rejilla
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def words_frequency_by_community(df, communities, base_title, translate=None):
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
        counts, sources = {}, {}
        for text in sub["text"].dropna():
            for word, source in _tokenize_src(text):
                if word in stop_words:
                    continue
                counts[word] = counts.get(word, 0) + 1
                seen = sources.setdefault(word, {})
                seen[source] = seen.get(source, 0) + 1
        top = dict(sorted(counts.items(), key=lambda kv: -kv[1])[:15])
        if translate is not None and top:
            table = pd.DataFrame({"word": list(top), "freq": list(top.values())})
            table["word_src"] = [max(sources[w].items(), key=lambda kv: kv[1])[0] for w in table["word"]]
            table = translate(table)
            top = dict(zip(table["word"], table["freq"]))
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
    cum = (
        grouped.pivot(index="date_slot", columns="community", values="num_tweets").fillna(0)
        .reindex(columns=top_community, fill_value=0)
        .reindex(pd.date_range(ini_date, end_date, freq=slot_time), fill_value=0)
        .cumsum()
    )

    color_map = dict(zip(communities["community"], communities["color"]))
    name_map = dict(zip(communities["community"], communities["name_community"]))
    limit_y = max(cum.to_numpy().max(), 1) if len(cum) else 1

    # acumulado por comunidad: nunca baja, y con muchas comunidades se lee mucho
    # mejor que las barras (el mismo criterio que Tweets by language / medios)
    fig, ax = plt.subplots(figsize=(10, 6))
    finals = {}
    for community in top_community:
        ax.plot(cum.index, cum[community].values, color=color_map.get(community),
                linewidth=2, alpha=0.85)
        finals[community] = cum[community].iloc[-1]

    head_room = max(1.15, draw_events(ax, events, ini_date, end_date, limit_y))

    # etiqueta "comunidad (total)" al final de cada línea, separadas verticalmente
    # un mínimo para que no se pisen, del color de su línea
    min_sep = limit_y * 0.035
    label_y, prev = {}, None
    for community in sorted(top_community, key=lambda c: finals[c]):
        y = finals[community]
        if prev is not None and y - prev < min_sep:
            y = prev + min_sep
        label_y[community] = y
        prev = y
    for community in top_community:
        ax.annotate(f"{name_map.get(community)} ({finals[community]:,.0f})",
                    (cum.index[-1], label_y[community]), fontsize=8,
                    xytext=(5, 0), textcoords="offset points", va="center",
                    color=color_map.get(community))

    ax.set_ylim(0, limit_y * head_room)
    ax.yaxis.set_major_formatter(ENG_FMT)
    ax.set_ylabel("Accumulated tweets")
    apply_date_axis(ax, ini_date, end_date + expand_time(ini_date, end_date, 18))
    my_theme(ax, title=f"{base_title}: Tweets by community",
             subtitle="(Adding retweet amplification)")
    fig.tight_layout()
    return fig
