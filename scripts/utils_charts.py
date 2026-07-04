"""
Funciones compartidas por los notebooks de visualizacion.
Equivalente Python de utils/utils_charts.R
"""
from datetime import timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

BASE_COLOR = "#5a5856"


def my_theme(ax, title=None, subtitle=None, base_color=BASE_COLOR, base_size=13):
    """Aplica una plantilla de estilo parecida a la usada en R (theme_bw + ajustes).

    Equivalente a my_theme() en utils_charts.R. Se aplica directamente sobre
    un Axes en lugar de devolver un objeto theme, ya que es el equivalente
    natural en matplotlib. Sin grid y sin efectos globales (antes usaba
    sns.set_style, que activaba el grid en todos los ejes creados despues,
    incluidos los twinx). Para el eje gemelo de la derecha usar
    style_twin_axis().
    """
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_edgecolor(base_color)
    ax.tick_params(colors=base_color, labelsize=base_size - 2)
    ax.xaxis.label.set_color(base_color)
    ax.yaxis.label.set_color(base_color)
    ax.xaxis.label.set_size(base_size + 1)
    ax.yaxis.label.set_size(base_size + 1)
    if title:
        # con subtitulo el titulo necesita mas pad para no solaparse con el
        ax.set_title(title, color=base_color, fontsize=base_size + 4,
                     fontweight="bold", loc="left", pad=30 if subtitle else 12)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=base_color,
                 fontsize=base_size + 1, ha="left", va="bottom")
    return ax


def style_twin_axis(ax2, base_color=BASE_COLOR, base_size=13):
    """Aplica a un eje gemelo (twinx) el mismo estilo que my_theme: sin grid
    y con el label del mismo tamano que el del eje izquierdo."""
    ax2.grid(False)
    for spine in ax2.spines.values():
        spine.set_edgecolor(base_color)
    ax2.tick_params(colors=base_color, labelsize=base_size - 2)
    ax2.yaxis.label.set_color(base_color)
    ax2.yaxis.label.set_size(base_size + 1)
    return ax2


def time_scale(ini_date, end_date):
    """Devuelve un mdates.Locator adecuado al rango de fechas.

    Equivalente a time_scale() en utils_charts.R (que devolvia un
    date_breaks de ggplot). Aqui devolvemos directamente el locator de
    matplotlib que produce un efecto equivalente.
    """
    num_days = (end_date - ini_date).total_seconds() / 86400
    num_years = num_days / 365
    num_months = num_days / 30
    num_weeks = num_days / 7
    num_hours = num_days * 24

    if num_years >= 10:
        return mdates.YearLocator()
    if num_months >= 12:
        interval = int((num_months + 12) / 12)
        return mdates.MonthLocator(interval=interval)
    if num_weeks >= 25:
        interval = int((num_weeks + 7) / 7)
        return mdates.WeekdayLocator(interval=interval)
    if num_days >= 4:
        interval = int((num_days + 10) / 10)
        return mdates.DayLocator(interval=interval)
    if num_days >= 2:
        interval = int((num_hours + 10) / 10)
        return mdates.HourLocator(interval=interval)
    interval = int((num_hours + 14) / 14)
    return mdates.HourLocator(interval=max(interval, 1))


def format_time(ini_date, end_date):
    """Devuelve el strftime equivalente a format_time() en utils_charts.R."""
    num_days = (end_date - ini_date).total_seconds() / 86400
    num_years = num_days / 365
    num_months = num_days / 30
    num_weeks = num_days / 7

    if num_years >= 10:
        return "%Y"
    if num_months >= 12:
        return "%b\n%Y"
    if num_weeks >= 25:
        return "%d-%b\n%Y"
    if num_days >= 4:
        return "%d-%b\n%Y"
    return "%H:00\n%d-%b"


def format_time_plain(ini_date, end_date):
    """Equivalente a format_time_plain() en utils_charts.R."""
    num_days = (end_date - ini_date).total_seconds() / 86400
    num_years = num_days / 365
    num_months = num_days / 30
    num_weeks = num_days / 7

    if num_years >= 10:
        return "%Y"
    if num_months >= 12:
        return "%b-%Y"
    if num_weeks >= 25:
        return "%d-%b-%Y"
    if num_days >= 4:
        return "%d-%b-%Y"
    return "%H:00-%d-%b"


def expand_time(ini_date, end_date, percentage):
    """Equivalente a expand_time() en utils_charts.R: devuelve un timedelta."""
    num_days = (end_date - ini_date).total_seconds() / 86400
    num_seconds = num_days * 24 * 60 * 60
    return timedelta(seconds=(num_seconds * percentage) / 100)


def apply_date_axis(ax, ini_date, end_date):
    """Aplica locator + formatter de fechas equivalentes a scale_x_datetime()."""
    ax.xaxis.set_major_locator(time_scale(ini_date, end_date))
    ax.xaxis.set_major_formatter(mdates.DateFormatter(format_time(ini_date, end_date)))
    ax.set_xlim(ini_date, end_date)
    return ax


def savefig(fig, path):
    """Equivalente a ggsave(): guarda la figura y la cierra."""
    fig.savefig(path, bbox_inches="tight", dpi=150)
