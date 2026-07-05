"""Interfaz de t-hoarder-twscraper. Settings>New Account y Download>Search ya están conectados a scripts reales."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import accounts, context, download, projects, scraping, utils  # noqa: E402
from async_utils import run_async  # noqa: E402

DATA_PATH = str(REPO_ROOT / "data")

FREQ_UNITS = ["min", "hour", "day", "week", "month", "year"]


def frequency_input(key_prefix: str) -> str:
    col_n, col_unit = st.columns(2)
    with col_n:
        n = st.number_input("Frequency (cantidad)", min_value=1, value=1, key=f"{key_prefix}_freq_n")
    with col_unit:
        unit = st.selectbox("Frequency (unidad)", FREQ_UNITS, key=f"{key_prefix}_freq_unit")
    return f"{int(n)} {unit}"


def validate_date_range(since: str, until: str) -> str | None:
    """Devuelve un mensaje de error si las fechas están vacías o mal formadas; None si son válidas."""
    if not since.strip() or not until.strip():
        return "Error: rellena los campos 'From' y 'To' con fecha YYYY-mm-dd HH:MM:SS"
    try:
        pd.Timestamp(since)
        pd.Timestamp(until)
    except (ValueError, TypeError):
        return "Error: 'From'/'To' deben tener formato YYYY-mm-dd HH:MM:SS"
    return None


def parse_users_list(text: str) -> tuple[list[str], str | None]:
    """Parsea una lista de usuarios separada por comas. Devuelve (lista, error).
    Si algún usuario lleva '@', se devuelve error en vez de quitarlo silenciosamente."""
    users = [u.strip() for u in text.split(",") if u.strip()]
    if not users:
        return [], "Error: escribe al menos un username en 'Users list'"
    with_at = [u for u in users if u.startswith("@")]
    if with_at:
        return [], f"Error: no incluyas '@' en los usuarios ({', '.join(with_at)})"
    return users, None

st.set_page_config(page_title="t-hoarder-twscraper", layout="wide")

LOGO_PATH = "../especificaciones/logo_t-hoarder.png"

# Settings al final: es la sección que menos se usa una vez configuradas las cuentas
SECTIONS = ["Project", "Download", "Tools", "Graphs", "Charts", "Settings"]

if "section" not in st.session_state:
    st.session_state.section = "Project"
if "console" not in st.session_state:
    st.session_state.console = ["> consola lista..."]
if "active_project" not in st.session_state:
    st.session_state.active_project = None
if "active_accounts" not in st.session_state:
    st.session_state.active_accounts = run_async(accounts.list_accounts())

# ---------- Cabecera ----------
header_col1, header_col2 = st.columns([1, 6])
with header_col1:
    try:
        st.image(LOGO_PATH, width=70)
    except Exception:
        st.write("🐦")
with header_col2:
    st.markdown("## t-hoarder-twscraper")

# ---------- Barra de navegación horizontal ----------
nav_cols = st.columns(len(SECTIONS))
for col, name in zip(nav_cols, SECTIONS):
    with col:
        is_active = st.session_state.section == name
        if st.button(name, key=f"nav_{name}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state.section = name
            # sin este rerun, en la pasada del clic los botones ya se pintaron
            # con la sección anterior y el resaltado rojo se queda en la vieja
            st.rerun()

st.divider()

# ---------- Cuerpo: formulario izquierda (30%) / resultados centro (60%) / contexto derecha (10%) ----------
VSEP_STYLE = "border-left:1px solid rgba(128,128,128,0.4);height:100%;min-height:600px;"
left, sep1, right, sep2, context_col = st.columns([29, 1, 59, 1, 10])
with sep1:
    st.markdown(f"<div style='{VSEP_STYLE}'></div>", unsafe_allow_html=True)
with sep2:
    st.markdown(f"<div style='{VSEP_STYLE}'></div>", unsafe_allow_html=True)

st.divider()
st.markdown("### Consola")
console_placeholder = st.empty()


def _render_console():
    lines = st.session_state.console[-15:]
    rendered = []
    for line in lines:
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        color = "color:#ff4b4b;" if line.startswith("> Error") else ""
        rendered.append(f'<div style="{color}white-space:pre-wrap">{safe}</div>')
    console_placeholder.markdown(
        "<div style='background-color:#0e1117;color:#fafafa;padding:0.75rem;"
        "border-radius:0.25rem;font-family:monospace;font-size:0.85rem;"
        "overflow-x:auto'>" + "".join(rendered) + "</div>",
        unsafe_allow_html=True,
    )


_render_console()


def log(msg: str):
    st.session_state.console.append(f"> {msg}")
    _render_console()


def log_error(msg: str):
    st.session_state.last_error = str(msg)
    log(f"Error: {msg}")


def set_result(file, file2=None):
    st.session_state.last_result_file = file
    st.session_state.last_result_file2 = file2
    st.session_state.last_result_df = None
    st.session_state.last_error = None
    st.session_state.graph_html = None
    st.session_state.chart_figures = None
    st.session_state.report_html = None


def set_result_df(df, title):
    st.session_state.last_result_df = df
    st.session_state.last_result_df_title = title
    st.session_state.last_result_file = None
    st.session_state.last_result_file2 = None
    st.session_state.last_error = None
    st.session_state.graph_html = None
    st.session_state.chart_figures = None
    st.session_state.report_html = None


def clear_results():
    st.session_state.last_result_file = None
    st.session_state.last_result_file2 = None
    st.session_state.last_result_df = None
    st.session_state.last_error = None
    st.session_state.graph_html = None
    st.session_state.chart_figures = None
    st.session_state.report_html = None


def set_result_graph_html(html):
    st.session_state.graph_html = html
    st.session_state.last_result_file = None
    st.session_state.last_result_file2 = None
    st.session_state.last_result_df = None
    st.session_state.last_error = None
    st.session_state.chart_figures = None
    st.session_state.report_html = None


def set_result_charts(figs, image_path):
    st.session_state.chart_figures = figs
    st.session_state.chart_figures_path = image_path
    st.session_state.chart_carousel_idx = 0
    st.session_state.last_result_file = None
    st.session_state.last_result_file2 = None
    st.session_state.last_result_df = None
    st.session_state.last_error = None
    st.session_state.graph_html = None
    st.session_state.report_html = None


# tipo de contexto -> sufijo del fichero que lo guarda
_PREFIX_KIND_SUFFIXES = {
    "search": "_search_context.csv",
    "users": "_users_context.csv",
}


def project_prefixes(project_dir, kinds=("search", "users")):
    """Prefixes del proyecto, del más reciente al más antiguo (fecha del contexto).

    kinds filtra por origen: 'search' (historical_search) y/o 'users'
    (historical_timeline)."""
    suffixes = [_PREFIX_KIND_SUFFIXES[k] for k in kinds]
    files = sorted(
        (f for suffix in suffixes for f in project_dir.glob(f"*{suffix}")),
        key=lambda f: f.stat().st_mtime, reverse=True,
    )
    prefixes = []
    for f in files:
        for suffix in suffixes:
            if f.name.endswith(suffix):
                prefix = f.name[: -len(suffix)]
                if prefix not in prefixes:
                    prefixes.append(prefix)
    return prefixes


_NEW_PREFIX_OPTION = "➕ nuevo prefix..."


def prefix_input(label, key, allow_new=False, kinds=("search", "users")):
    """Entrada de Prefix como desplegable con los prefixes del proyecto activo,
    el más reciente preseleccionado (así se trabaja por defecto con lo último).

    Con allow_new (Search y User TL) el desplegable incluye la opción de crear
    un prefix nuevo, que despliega un campo de texto. En el resto de casos el
    prefix tiene que existir. Sin proyecto activo, campo de texto plano.
    kinds limita el origen de los prefixes listados (ver project_prefixes).
    """
    if not st.session_state.active_project:
        return st.text_input(label, key=f"{key}_txt").strip()
    options = project_prefixes(projects.select_project(st.session_state.active_project), kinds=kinds)
    if allow_new:
        options = options + [_NEW_PREFIX_OPTION]
    if not options:
        st.caption("No hay ningún prefix en este proyecto todavía.")
        return ""
    choice = st.selectbox(label, options, key=f"{key}_sel")
    if choice == _NEW_PREFIX_OPTION:
        return st.text_input("Nuevo prefix", key=f"{key}_new").strip()
    return choice or ""


def set_result_report(html, path):
    st.session_state.report_html = html
    st.session_state.report_path = str(path)
    st.session_state.last_result_file = None
    st.session_state.last_result_file2 = None
    st.session_state.last_result_df = None
    st.session_state.last_error = None
    st.session_state.graph_html = None
    st.session_state.chart_figures = None


with left:
    section = st.session_state.section

    if section == "Settings":
        tab1, tab2, tab3 = st.tabs(["New Account", "Active Accounts", "Delete Account"])
        with tab1:
            new_username = st.text_input("Username", key="new_username")
            new_password = st.text_input("Password", type="password", key="new_password")
            new_email = st.text_input("Email", key="new_email")
            new_email_password = st.text_input("Email Password", type="password", key="new_email_password")
            new_auth_token = st.text_input("Auth Token", key="new_auth_token")
            new_ct0 = st.text_input("ct0", key="new_ct0")
            if st.button("Crear cuenta"):
                cookies = f"auth_token={new_auth_token}; ct0={new_ct0}"
                log(f"Agregando cuenta @{new_username}...")
                result = run_async(accounts.add_account(
                    new_username, new_password, new_email, new_email_password, cookies
                ))
                if result.get("success") and result.get("active"):
                    log(f"Cuenta @{new_username} agregada y activa")
                elif result.get("success"):
                    log(f"Cuenta @{new_username} agregada pero no activa (revisa cookies)")
                else:
                    log_error(f"{result.get('message')}")
        with tab2:
            if st.button("Refrescar lista"):
                st.session_state.active_accounts = run_async(accounts.list_accounts())
            data = st.session_state.get("active_accounts", [])
            if data:
                set_result_df(pd.DataFrame(data)[["username", "email", "active"]], "Cuentas activas")
            else:
                st.write("Sin datos. Pulsa 'Refrescar lista'.")
        with tab3:
            del_username = st.text_input("Username a eliminar", key="del_username")
            if st.button("Eliminar cuenta"):
                result = run_async(accounts.delete_account(del_username))
                if result.get("success"):
                    log(f"Cuenta @{del_username} eliminada")
                else:
                    log_error(f"{result.get('message')}")

    elif section == "Project":
        tab1, tab2, tab3, tab4 = st.tabs(["Select project", "New project", "Active projects", "Desactive project"])
        with tab1:
            active_list = projects.list_active_projects()
            if active_list:
                chosen = st.selectbox("Project name", active_list)
                if st.button("Seleccionar proyecto"):
                    st.session_state.active_project = chosen
                    log(f"Proyecto activo: {chosen}")
            else:
                st.write("No hay proyectos. Crea uno en 'New project'.")
        with tab2:
            new_project_name = st.text_input("Project name (nuevo)", key="new_project_name")
            if st.button("Crear proyecto"):
                try:
                    projects.new_project(new_project_name)
                    st.session_state.active_project = new_project_name
                    log(f"Proyecto '{new_project_name}' creado y activado")
                except (ValueError, FileExistsError) as e:
                    log_error(str(e))
        with tab3:
            active_list = projects.list_active_projects()
            if active_list:
                set_result_df(pd.DataFrame({"project": active_list}), "Proyectos activos")
            else:
                st.write("No hay proyectos activos.")
        with tab4:
            active_list = projects.list_active_projects()
            if active_list:
                to_deactivate = st.selectbox("Project name a desactivar", active_list, key="deact_select")
                if st.button("Desactivar proyecto"):
                    projects.deactivate_project(to_deactivate)
                    if st.session_state.active_project == to_deactivate:
                        st.session_state.active_project = None
                    log(f"Proyecto '{to_deactivate}' desactivado")
            else:
                st.write("No hay proyectos activos para desactivar.")

    elif section == "Download":
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Search", "User TL", "Retweets", "Comments", "Advanced Comments"])
        with tab1:
            search_prefix = prefix_input("Prefix", "search_prefix", allow_new=True, kinds=("search",))
            if st.button("Cargar contexto", key="search_load_ctx"):
                if not search_prefix:
                    log_error("escribe el Prefix antes de cargar el contexto")
                elif not st.session_state.active_project:
                    log_error("selecciona o crea un proyecto antes de cargar el contexto")
                else:
                    try:
                        project_dir = projects.select_project(st.session_state.active_project)
                        saved = context.get_context_search_full(project_dir, search_prefix)
                    except FileNotFoundError:
                        saved = None
                    if saved:
                        st.session_state.search_query = saved["query"]
                        st.session_state.search_product = saved["product"] or "Top"
                        st.session_state.search_from = saved["since"]
                        st.session_state.search_to = saved["until"]
                        freq_parts = saved["frequency"].split() if saved["frequency"] else []
                        st.session_state.search_freq_n = int(freq_parts[0]) if len(freq_parts) == 2 else 1
                        st.session_state.search_freq_unit = freq_parts[1] if len(freq_parts) == 2 else "hour"
                        log(f"Contexto cargado para el prefix '{search_prefix}'")
                    else:
                        st.session_state.search_query = ""
                        st.session_state.search_product = "Top"
                        st.session_state.search_from = ""
                        st.session_state.search_to = ""
                        st.session_state.search_freq_n = 1
                        st.session_state.search_freq_unit = "hour"
                        log(f"No hay contexto guardado para el prefix '{search_prefix}'")
                    st.rerun()

            search_query = st.text_input("Query", key="search_query")
            search_product = st.selectbox("Product", ["Top", "Latest"], key="search_product")
            search_from = st.text_input("From (YYYY-mm-dd HH:MM:SS)", key="search_from")
            search_to = st.text_input("To (YYYY-mm-dd HH:MM:SS)", key="search_to")
            search_freq = frequency_input("search")
            if st.button("Lanzar búsqueda"):
                date_error = validate_date_range(search_from, search_to)
                if not st.session_state.active_project:
                    log_error("selecciona o crea un proyecto antes de descargar")
                elif date_error:
                    log(date_error)
                else:
                    log(f"Lanzando historical_search ({search_product}, frequency={search_freq})")
                    output_file = download.historical_search(
                        data_path=DATA_PATH, dataset=st.session_state.active_project,
                        prefix=search_prefix, query=search_query,
                        since=search_from, until=search_to,
                        frequency=search_freq, product=search_product, log=log,
                    )
                    log(f"Resultado en {output_file}")
                    set_result(output_file)
        with tab2:
            utl_prefix = prefix_input("Prefix", "utl_prefix", allow_new=True, kinds=("users",))
            if st.button("Cargar contexto", key="utl_load_ctx"):
                if not utl_prefix:
                    log_error("escribe el Prefix antes de cargar el contexto")
                elif not st.session_state.active_project:
                    log_error("selecciona o crea un proyecto antes de cargar el contexto")
                else:
                    try:
                        project_dir = projects.select_project(st.session_state.active_project)
                        saved = context.get_context_user_full(project_dir, utl_prefix)
                    except FileNotFoundError:
                        saved = None
                    if saved:
                        st.session_state.utl_users_text = saved["list_users"]
                        st.session_state.utl_from = saved["since"]
                        st.session_state.utl_to = saved["until"]
                        st.session_state.utl_product = saved["product"] if saved.get("product") in ("Top", "Latest") else "Top"
                        freq_parts = saved["frequency"].split() if saved["frequency"] else []
                        st.session_state.utl_freq_n = int(freq_parts[0]) if len(freq_parts) == 2 else 1
                        st.session_state.utl_freq_unit = freq_parts[1] if len(freq_parts) == 2 else "hour"
                        log(f"Contexto cargado para el prefix '{utl_prefix}'")
                    else:
                        st.session_state.utl_users_text = ""
                        st.session_state.utl_from = ""
                        st.session_state.utl_to = ""
                        st.session_state.utl_product = "Top"
                        st.session_state.utl_freq_n = 1
                        st.session_state.utl_freq_unit = "hour"
                        log(f"No hay contexto guardado para el prefix '{utl_prefix}'")
                    st.rerun()

            utl_users_text = st.text_input(
                "Users list (Comma-separated list of users, without @)", key="utl_users_text"
            )
            utl_from = st.text_input("From (YYYY-mm-dd HH:MM:SS)", key="utl_from")
            utl_product = st.radio("Product", ["Top", "Latest"], horizontal=True, key="utl_product")
            utl_to = st.text_input("To (YYYY-mm-dd HH:MM:SS)", key="utl_to")
            utl_freq = frequency_input("utl")
            if st.button("Lanzar descarga TL"):
                date_error = validate_date_range(utl_from, utl_to)
                users_list, users_error = parse_users_list(utl_users_text)
                if not st.session_state.active_project:
                    log_error("selecciona o crea un proyecto antes de descargar")
                elif date_error:
                    log(date_error)
                elif users_error:
                    log(users_error)
                else:
                    log(f"Lanzando historical_timeline para {len(users_list)} usuario(s) (frequency={utl_freq})")
                    output_file = download.historical_timeline(
                        data_path=DATA_PATH, dataset=st.session_state.active_project,
                        prefix=utl_prefix, list_users=users_list,
                        since=utl_from, until=utl_to, frequency=utl_freq,
                        product=utl_product, log=log,
                    )
                    log(f"Resultado en {output_file}")
                    set_result(output_file)
        with tab3:
            rt_prefix = prefix_input("Prefix", "rt_prefix")
            rt_min = st.number_input("Min RTs", min_value=0, value=1, key="rt_min")
            if st.button("Lanzar descarga RTs"):
                if not st.session_state.active_project:
                    log_error("selecciona o crea un proyecto antes de descargar")
                elif not rt_prefix:
                    log_error("escribe el Prefix del fichero con los tweets originales")
                else:
                    log(f"Lanzando get_retweets (min_rts={int(rt_min)})")
                    try:
                        output_file = download.get_retweets(
                            data_path=DATA_PATH, dataset=st.session_state.active_project,
                            prefix=rt_prefix, min_rts=int(rt_min), log=log,
                        )
                        log(f"Resultado en {output_file}")
                        set_result(output_file)
                    except FileNotFoundError:
                        log_error(f"no existe {rt_prefix}.csv en el proyecto activo. Descarga primero esos tweets (Search/User TL).")
        with tab4:
            cm_prefix = prefix_input("Prefix", "cm_prefix")
            cm_min = st.number_input("Min Replies", min_value=0, value=1, key="cm_min")
            if st.button("Lanzar descarga comentarios"):
                if not st.session_state.active_project:
                    log_error("selecciona o crea un proyecto antes de descargar")
                elif not cm_prefix:
                    log_error("escribe el Prefix del fichero con los tweets originales")
                else:
                    log(f"Lanzando get_replies (min_replies={int(cm_min)})")
                    try:
                        output_file = download.get_replies(
                            data_path=DATA_PATH, dataset=st.session_state.active_project,
                            prefix=cm_prefix, min_replies=int(cm_min), log=log,
                        )
                        log(f"Resultado en {output_file}")
                        set_result(output_file)
                    except FileNotFoundError:
                        log_error(f"no existe {cm_prefix}.csv en el proyecto activo. Descarga primero esos tweets (Search/User TL).")
        with tab5:
            acm_prefix = prefix_input("Prefix", "acm_prefix")
            acm_min = st.number_input("Min Replies", min_value=0, value=1, key="acm_min")
            acm_last = st.number_input("Last (días)", min_value=0, value=1, key="acm_last")
            acm_freq = frequency_input("acm")
            if st.button("Lanzar descarga avanzada"):
                if not st.session_state.active_project:
                    log_error("selecciona o crea un proyecto antes de descargar")
                elif not acm_prefix:
                    log_error("escribe el Prefix del fichero con los tweets originales")
                else:
                    log(f"Lanzando get_replies_advanced (frequency={acm_freq})")
                    try:
                        output_file = download.get_replies_advanced(
                            data_path=DATA_PATH, dataset=st.session_state.active_project,
                            prefix=acm_prefix, min_replies=int(acm_min),
                            last_days=int(acm_last), frequency=acm_freq, log=log,
                        )
                        log(f"Resultado en {output_file}")
                        set_result(output_file)
                    except FileNotFoundError:
                        log_error(f"no existe {acm_prefix}.csv en el proyecto activo. Descarga primero esos tweets (Search/User TL).")

    elif section == "Tools":
        tab1, tab2, tab3 = st.tabs(["Merge files", "Clean data", "Location"])
        with tab1:
            if not st.session_state.active_project:
                st.write("Selecciona o crea un proyecto en 'Project' antes de unir ficheros.")
            else:
                project_dir = projects.select_project(st.session_state.active_project)
                available_csvs = sorted(p.name for p in project_dir.glob("*.csv"))
                if not available_csvs:
                    st.write("No hay ficheros CSV en este proyecto todavía.")
                else:
                    merge_files_selected = st.multiselect(
                        "Files a unir (deben estar en el proyecto activo)", available_csvs, key="merge_files_selected"
                    )
                    merge_output_file = st.text_input("Output file", key="merge_output_file")
                    if st.button("Combinar archivos"):
                        if len(merge_files_selected) < 2:
                            log_error("selecciona al menos 2 ficheros para unir")
                        elif not merge_output_file:
                            log_error("escribe un nombre de fichero de salida")
                        else:
                            try:
                                output_file = utils.merge_files(
                                    project_dir, merge_files_selected, merge_output_file, log=log
                                )
                                log(f"Resultado en {output_file}")
                                set_result(output_file)
                            except (ValueError, FileNotFoundError) as e:
                                log_error(str(e))
        with tab2:
            if not st.session_state.active_project:
                st.write("Selecciona o crea un proyecto en 'Project' antes de limpiar datos.")
            else:
                clean_prefix = prefix_input("Prefix (prefijo del fichero con los tweets originales)", "clean_prefix")
                clean_langs_text = st.text_input(
                    "Languages (idiomas a conservar, separados por comas, ej. es,ca; vacío = no filtra)",
                    key="clean_langs_text",
                )
                clean_positives = st.text_area(
                    "Positives: incluir los tweets que contengan alguna de esta lista de palabras separadas por comas (ej. rstats,python)",
                    key="clean_positives",
                )
                clean_false_positives = st.text_area(
                    "False positives: excluir los tweets que contengan alguna de esta lista de palabras separadas por comas (ej. futbol,humor)",
                    key="clean_false_positives",
                )
                clean_out = st.text_input("Output file", key="clean_out")
                if st.button("Limpiar datos"):
                    if not clean_prefix:
                        log_error("escribe el Prefix del fichero a limpiar")
                    elif not clean_out:
                        log_error("escribe un nombre de fichero de salida")
                    else:
                        project_dir = projects.select_project(st.session_state.active_project)
                        langs_list = [w.strip() for w in clean_langs_text.split(",") if w.strip()]
                        positives_list = [w.strip() for w in clean_positives.split(",") if w.strip()]
                        false_positives_list = [w.strip() for w in clean_false_positives.split(",") if w.strip()]
                        try:
                            output_file = utils.clean_data(
                                project_dir, clean_prefix, clean_out,
                                langs=langs_list, positives=positives_list,
                                false_positives=false_positives_list, log=log,
                            )
                            log(f"Resultado en {output_file}")
                            set_result(output_file)
                        except FileNotFoundError as e:
                            log_error(str(e))
        with tab3:
            if not st.session_state.active_project:
                st.write("Selecciona o crea un proyecto en 'Project' antes de extraer localizaciones.")
            else:
                loc_prefix = prefix_input(
                    "Prefix (prefijo del fichero con los tweets originales; genera {prefix}_loc.csv)",
                    "loc_prefix",
                )
                if st.button("Extraer localización"):
                    if not loc_prefix:
                        log_error("escribe el Prefix")
                    else:
                        project_dir = projects.select_project(st.session_state.active_project)
                        try:
                            output_file = utils.extract_locations(project_dir, loc_prefix, log=log)
                            log(f"Resultado en {output_file}")
                            set_result(output_file)
                        except FileNotFoundError as e:
                            log_error(str(e))

    elif section == "Graphs":
        if not st.session_state.active_project:
            st.write("Selecciona o crea un proyecto en 'Project' antes de trabajar con grafos.")
        else:
            project_dir = projects.select_project(st.session_state.active_project)
            import graphs as graphs_mod

            tab1, tab2, tab3, tab4 = st.tabs(
                ["Detect communities", "Generate graph", "Classify tweets", "Visualize graph"]
            )
            with tab1:
                dc_prefix = prefix_input("Prefix", "dc_prefix")
                dc_relation = st.selectbox(
                    "Relation (tipo de relación)", ["RT", "replies", "replies_advanced"], key="dc_relation"
                )
                if st.button("Detectar comunidades"):
                    if not dc_prefix:
                        log_error("escribe el Prefix")
                    else:
                        try:
                            communities_file, users_file = graphs_mod.detect_communities(
                                project_dir, dc_prefix, dc_relation, log=log
                            )
                            set_result(communities_file, users_file)
                        except FileNotFoundError as e:
                            log_error(str(e))
            with tab2:
                gg_prefix = prefix_input("Prefix", "gg_prefix")
                gg_relation = st.selectbox(
                    "Relation (tipo de relación)", ["RT", "replies", "replies_advanced"], key="gg_relation"
                )
                gg_format = st.selectbox("Format", ["gdf", "gexf"], key="gg_format")
                gg_include_communities = st.checkbox(
                    "Include communities (requiere haber ejecutado antes 'Detect communities')",
                    value=True, key="gg_include_communities",
                )
                gg_include_locations = st.checkbox(
                    "Include locations (requiere {prefix}_loc.csv, generado en Tools > Location)",
                    value=False, key="gg_include_locations",
                )
                if st.button("Generar grafo"):
                    if not gg_prefix:
                        log_error("escribe el Prefix")
                    else:
                        try:
                            graph_file = graphs_mod.generate_graph(
                                project_dir, gg_prefix, gg_relation, output_format=gg_format,
                                include_communities=gg_include_communities,
                                include_locations=gg_include_locations, log=log,
                            )
                            log(f"Grafo en {graph_file}")
                            set_result(graph_file)
                        except FileNotFoundError as e:
                            log_error(str(e))
            with tab3:
                ct_prefix = prefix_input("Prefix", "ct_prefix")
                ct_relation = st.selectbox(
                    "Relation (tipo de relación)", ["RT", "replies", "replies_advanced"], key="ct_relation"
                )
                if st.button("Clasificar tweets"):
                    if not ct_prefix:
                        log_error("escribe el Prefix")
                    else:
                        try:
                            classified_file = graphs_mod.classify_tweets(
                                project_dir, ct_prefix, ct_relation, log=log
                            )
                            log(f"Resultado en {classified_file}")
                            set_result(classified_file)
                        except FileNotFoundError as e:
                            log_error(str(e))
            with tab4:
                available_graphs = sorted(
                    p.name for p in project_dir.glob("*.gdf")
                ) + sorted(p.name for p in project_dir.glob("*.gexf"))
                if not available_graphs:
                    st.write("No hay ficheros de grafo (.gdf/.gexf) en este proyecto todavía.")
                else:
                    vg_file = st.selectbox("Select graph", available_graphs, key="vg_file")
                    vg_max_labels = st.slider(
                        "Máximo de etiquetas por comunidad", min_value=1, max_value=50, value=10, key="vg_max_labels"
                    )
                    vg_iterations = st.slider(
                        "Iteraciones de ForceAtlas2", min_value=100, max_value=2000, value=300, step=50,
                        key="vg_iterations",
                        help="El layout se calcula en el navegador en segundos. Con el modo LinLog "
                             "las comunidades se separan en unos cientos de iteraciones.",
                    )
                    if st.button("Visualizar grafo"):
                        try:
                            view_data, communities_shown = graphs_mod.graph_view_data(
                                project_dir, vg_file,
                                max_labels_per_community=vg_max_labels, log=log,
                            )
                            log(f"Comunidades mostradas: {', '.join(communities_shown)}")
                            set_result_graph_html(graphs_mod.render_graph_html(
                                view_data, vg_iterations, Path(vg_file).stem,
                            ))
                        except (FileNotFoundError, ValueError) as e:
                            log_error(str(e))

    elif section == "Charts":
        chart_type = st.radio("Graphic type", ["Tweets", "Users"], horizontal=True)
        if chart_type == "Tweets":
            if not st.session_state.active_project:
                st.write("Selecciona o crea un proyecto en 'Project' antes de generar gráficas.")
            else:
                col_prefix, col_title = st.columns(2)
                with col_prefix:
                    tg_prefix = prefix_input("Prefix", "tg_prefix", kinds=("search",))
                with col_title:
                    tg_title = st.text_input("Base title", key="tg_title")

                tg_tz = st.selectbox(
                    "Time zone", ["Europe/Berlin", "America/Chicago", "America/Caracas"], key="tg_tz"
                )

                st.markdown("Show influencers with values equal or higher")
                col_reach, col_rts = st.columns(2)
                with col_reach:
                    tg_reach = st.number_input("Min reach", min_value=0, value=10000, key="tg_reach")
                with col_rts:
                    tg_rts = st.number_input("Min RTs", min_value=0, value=1000, key="tg_rts")

                col_topics_chk, col_topics_file = st.columns([1, 2])
                with col_topics_chk:
                    tg_topics = st.checkbox("Show topics", key="tg_topics")
                with col_topics_file:
                    tg_topics_file = st.text_input(
                        "Topics file (si show_topics)", key="tg_topics_file", disabled=not tg_topics,
                        label_visibility="collapsed", placeholder="Topics file (si show_topics)",
                    )

                col_events_chk, col_events_file = st.columns([1, 2])
                with col_events_chk:
                    tg_events = st.checkbox("Show events", key="tg_events")
                with col_events_file:
                    tg_events_file = st.text_input(
                        "Events file (si show_events)", key="tg_events_file", disabled=not tg_events,
                        label_visibility="collapsed", placeholder="Events file (si show_events)",
                    )

                tg_zoom = st.checkbox("Zoom", key="tg_zoom")
                tg_zoom_min, tg_zoom_max = "", ""
                if tg_zoom:
                    col_zoom_min, col_zoom_max = st.columns(2)
                    with col_zoom_min:
                        tg_zoom_min = st.text_input(
                            "Min date zoom (yyyy-mm-dd HH:MM:SS)", key="tg_zoom_min"
                        )
                    with col_zoom_max:
                        tg_zoom_max = st.text_input(
                            "Max date zoom (yyyy-mm-dd HH:MM:SS)", key="tg_zoom_max"
                        )

                col_btn_charts, col_btn_report = st.columns(2)
                tg_do_charts = col_btn_charts.button("Generar gráfico de Tweets")
                tg_do_report = col_btn_report.button("Generar informe HTML de Tweets")
                if tg_do_charts or tg_do_report:
                    if not tg_prefix:
                        log_error("escribe el Prefix")
                    elif tg_zoom and (not tg_zoom_min.strip() or not tg_zoom_max.strip()):
                        log_error("rellena 'Min date zoom' y 'Max date zoom' o desmarca 'Zoom'")
                    else:
                        try:
                            import charts as charts_mod

                            project_dir = projects.select_project(st.session_state.active_project)
                            chart_args = dict(
                                min_reach=tg_reach, min_RTs=tg_rts,
                                show_topics=tg_topics, topics_file=tg_topics_file,
                                show_events=tg_events, events_file=tg_events_file,
                                min_date_zoom=tg_zoom_min if tg_zoom else None,
                                max_date_zoom=tg_zoom_max if tg_zoom else None,
                                log=log,
                            )
                            if tg_do_charts:
                                with st.spinner("Generando gráficas..."):
                                    figs, image_path = charts_mod.generate_tweet_charts(
                                        project_dir, tg_prefix, tg_title or tg_prefix, tg_tz,
                                        **chart_args,
                                    )
                                log(f"Tweet Graph generado: {len(figs)} gráficas en {image_path}")
                                set_result_charts(figs, image_path)
                            else:
                                with st.spinner("Generando informe HTML..."):
                                    report_html, report_path = charts_mod.generate_tweet_report(
                                        project_dir, tg_prefix, tg_title or tg_prefix, tg_tz,
                                        **chart_args,
                                    )
                                set_result_report(report_html, report_path)
                        except (FileNotFoundError, ValueError) as e:
                            log_error(str(e))
        else:
            if not st.session_state.active_project:
                st.write("Selecciona o crea un proyecto en 'Project' antes de generar gráficas.")
            else:
                col_prefix, col_username = st.columns(2)
                with col_prefix:
                    ug_prefix = prefix_input("Prefix", "ug_prefix", kinds=("users",))
                with col_username:
                    ug_username = st.text_input("Username", key="ug_username").strip()

                ug_title = st.text_input("Base title", key="ug_title")
                ug_tz = st.selectbox(
                    "Time zone", ["Europe/Berlin", "America/Chicago", "America/Caracas"], key="ug_tz"
                )

                col_topics_chk, col_topics_file = st.columns([1, 2])
                with col_topics_chk:
                    ug_topics = st.checkbox("Show topics", key="ug_topics")
                with col_topics_file:
                    ug_topics_file = st.text_input(
                        "Topics file (si show_topics)", key="ug_topics_file", disabled=not ug_topics,
                        label_visibility="collapsed", placeholder="Topics file (si show_topics)",
                    )

                col_events_chk, col_events_file = st.columns([1, 2])
                with col_events_chk:
                    ug_events = st.checkbox("Show events", key="ug_events")
                with col_events_file:
                    ug_events_file = st.text_input(
                        "Events file (si show_events)", key="ug_events_file", disabled=not ug_events,
                        label_visibility="collapsed", placeholder="Events file (si show_events)",
                    )

                col_btn_charts, col_btn_report = st.columns(2)
                ug_do_charts = col_btn_charts.button("Generar gráfico de Usuario")
                ug_do_report = col_btn_report.button("Generar informe HTML de Usuario")
                if ug_do_charts or ug_do_report:
                    if not ug_prefix or not ug_username:
                        log_error("escribe el Prefix y el Username")
                    else:
                        try:
                            import charts as charts_mod

                            project_dir = projects.select_project(st.session_state.active_project)
                            chart_args = dict(
                                show_topics=ug_topics, topics_file=ug_topics_file,
                                show_events=ug_events, events_file=ug_events_file,
                                log=log,
                            )
                            if ug_do_charts:
                                with st.spinner("Generando gráficas..."):
                                    figs, image_path = charts_mod.generate_user_charts(
                                        project_dir, ug_prefix, ug_username, ug_title or ug_username, ug_tz,
                                        **chart_args,
                                    )
                                log(f"User Graph generado: {len(figs)} gráficas en {image_path}")
                                set_result_charts(figs, image_path)
                            else:
                                with st.spinner("Generando informe HTML..."):
                                    report_html, report_path = charts_mod.generate_user_report(
                                        project_dir, ug_prefix, ug_username, ug_title or ug_username, ug_tz,
                                        **chart_args,
                                    )
                                set_result_report(report_html, report_path)
                        except (FileNotFoundError, ValueError) as e:
                            log_error(str(e))

with context_col:
    st.markdown("### Contexto")
    n_accounts = sum(1 for a in st.session_state.get("active_accounts", []) if a.get("active"))
    project_label = st.session_state.active_project or "ninguno"
    st.write(f"**Cuentas activas:** {n_accounts}")
    st.write(f"**Proyecto activo:** {project_label}")

    if st.session_state.active_project:
        project_dir = projects.select_project(st.session_state.active_project)
        prefixes = sorted({
            f.name[: -len("_search_context.csv")] for f in project_dir.glob("*_search_context.csv")
        } | {
            f.name[: -len("_users_context.csv")] for f in project_dir.glob("*_users_context.csv")
        })
        if prefixes:
            st.caption("Descargas con contexto guardado:")
            for prefix in prefixes:
                with st.expander(prefix):
                    search_ctx = context.get_context_search_full(project_dir, prefix)
                    if search_ctx:
                        st.write("**Search**")
                        st.json(search_ctx, expanded=False)
                    users_ctx = context.get_context_user_full(project_dir, prefix)
                    if users_ctx:
                        st.write("**User TL**")
                        st.json(users_ctx, expanded=False)

with right:
    st.markdown("### Resultados")
    error_msg = st.session_state.get("last_error")
    graph_html = st.session_state.get("graph_html")
    chart_figures = st.session_state.get("chart_figures")
    report_html = st.session_state.get("report_html")
    result_df = st.session_state.get("last_result_df")
    result_file = st.session_state.get("last_result_file")
    if error_msg or chart_figures or result_df is not None or graph_html or report_html or result_file:
        if st.button("Borrar resultados"):
            clear_results()
            st.rerun()

    if error_msg:
        st.error(error_msg)
    elif report_html:
        report_path = st.session_state.get("report_path", "")
        st.caption(f"Informe guardado en: {report_path}")
        st.download_button(
            "Descargar informe HTML", data=report_html,
            file_name=Path(report_path).name or "informe.html", mime="text/html",
        )
        st_components.html(report_html, height=800, scrolling=True)
    elif chart_figures:
        st.caption(f"Gráficas guardadas en: {st.session_state.get('chart_figures_path', '')}")
        # Carrusel: una gráfica cada vez, con botones para pasar de una a otra
        chart_names = list(chart_figures.keys())
        idx = st.session_state.get("chart_carousel_idx", 0) % len(chart_names)
        col_prev, col_title, col_next = st.columns([1, 6, 1])
        if col_prev.button("◀", key="chart_prev", disabled=len(chart_names) == 1):
            idx = (idx - 1) % len(chart_names)
            st.session_state.chart_carousel_idx = idx
        if col_next.button("▶", key="chart_next", disabled=len(chart_names) == 1):
            idx = (idx + 1) % len(chart_names)
            st.session_state.chart_carousel_idx = idx
        col_title.markdown(
            f"<div style='text-align: center'><b>{chart_names[idx]}</b> ({idx + 1}/{len(chart_names)})</div>",
            unsafe_allow_html=True,
        )
        st.pyplot(chart_figures[chart_names[idx]], width="content")
    elif result_df is not None:
        st.caption(st.session_state.get("last_result_df_title", ""))
        st.dataframe(result_df, use_container_width=True)
    elif graph_html:
        # Visor interactivo sigma.js; el botón "Descargar PNG" va dentro del propio visor
        st_components.html(graph_html, height=660)
    elif result_file and Path(result_file).exists():
        def _preview_file(path):
            st.caption(str(path))
            if Path(path).suffix.lower() == ".csv":
                with open(path, encoding="utf-8") as f:
                    n_rows = sum(1 for _ in f) - 1
                preview_df = pd.read_csv(path, nrows=50, encoding="utf-8")
                if n_rows > 50:
                    st.write(f"{n_rows} filas (mostrando las primeras 50)")
                else:
                    st.write(f"{n_rows} filas")
                st.dataframe(preview_df, use_container_width=preview_df.shape[1] > 3)
            else:
                with open(path, encoding="utf-8") as f:
                    preview_lines = [next(f, "") for _ in range(50)]
                st.write("Fichero no tabular (mostrando las primeras 50 líneas)")
                st.code("".join(preview_lines), language="text")

        _preview_file(result_file)
        result_file2 = st.session_state.get("last_result_file2")
        if result_file2 and Path(result_file2).exists():
            st.divider()
            _preview_file(result_file2)
    else:
        st.write("Aquí se mostrarán tablas, gráficos o archivos generados según la acción ejecutada.")
