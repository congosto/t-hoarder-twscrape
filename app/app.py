"""Interfaz de t-hoarder-twscrape. Settings>New Account y Download>Search ya están conectados a scripts reales."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import accounts, compare, context, dashboard, download, projects, scraping, utils  # noqa: E402
from async_utils import run_async  # noqa: E402

DATA_PATH = str(REPO_ROOT / "data")

FREQ_UNITS = ["min", "hour", "day", "week", "month", "year"]


def frequency_input(key_prefix: str) -> str:
    col_n, col_unit = st.columns(2)
    with col_n:
        n = st.number_input("Frequency (amount)", min_value=1, value=1, key=f"{key_prefix}_freq_n")
    with col_unit:
        unit = st.selectbox("Frequency (unit)", FREQ_UNITS, key=f"{key_prefix}_freq_unit")
    return f"{int(n)} {unit}"


def validate_date_range(since: str, until: str) -> str | None:
    """Devuelve un mensaje de error si las fechas están vacías o mal formadas; None si son válidas."""
    if not since.strip() or not until.strip():
        return "Error: fill in 'From' and 'To' with date YYYY-mm-dd HH:MM:SS"
    try:
        pd.Timestamp(since)
        pd.Timestamp(until)
    except (ValueError, TypeError):
        return "Error: 'From'/'To' must have format YYYY-mm-dd HH:MM:SS"
    return None


def parse_users_list(text: str) -> tuple[list[str], str | None]:
    """Parsea una lista de usuarios separada por comas. Devuelve (lista, error).
    Si algún usuario lleva '@', se devuelve error en vez de quitarlo silenciosamente."""
    users = [u.strip() for u in text.split(",") if u.strip()]
    if not users:
        return [], "Error: enter at least one username in 'Users list'"
    with_at = [u for u in users if u.startswith("@")]
    if with_at:
        return [], f"Error: do not include '@' in usernames ({', '.join(with_at)})"
    return users, None

LOGO_PATH = str(REPO_ROOT / "logo_t-hoarder.png")
ICON_PATH = str(REPO_ROOT / "t-hoarder.ico")

st.set_page_config(page_title="t-hoarder-twscrape", page_icon=ICON_PATH, layout="wide")

# Settings al final: es la sección que menos se usa una vez configuradas las cuentas
SECTIONS = ["Project", "Download", "Dashboard", "Tools", "Graphs", "Charts", "Settings"]

if "section" not in st.session_state:
    st.session_state.section = "Project"
if "console" not in st.session_state:
    st.session_state.console = ["> console ready..."]
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
    st.markdown("## t-hoarder-twscrape")

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
st.markdown("### Console")
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


# tipo de dataset -> sufijo del log de contexto (un dataset combinado/limpio
# hereda el log de su origen, así que sigue siendo search o users)
_PREFIX_KIND_SUFFIXES = {
    "search": "_search_context.csv",
    "users": "_users_context.csv",
}
_ALL_KINDS = ("search", "users")


def _ensure_migrated(project_dir):
    """Migra el contexto del proyecto al formato log una vez por sesión."""
    migrated = st.session_state.setdefault("_migrated_projects", set())
    key = str(project_dir)
    if key not in migrated:
        context.migrate_project(project_dir)
        migrated.add(key)


def project_prefixes(project_dir, kinds=_ALL_KINDS):
    """Datasets del proyecto, del más reciente al más antiguo (fecha del contexto).

    kinds filtra por origen: 'search' (historical_search) y/o 'users'
    (historical_timeline). Un dataset combinado/limpio hereda el tipo de su origen."""
    _ensure_migrated(project_dir)
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


_NEW_PREFIX_OPTION = "➕ nuevo dataset..."


_DATA_EXTS = (".csv", ".gdf", ".gexf", ".txt", ".tsv", ".json")


def _backup_label(path):
    """Etiqueta legible de un backup {name}_prev_<YYYYMMDD-HHMMSS>.csv: fecha + tamaño."""
    import re
    m = re.search(r"_prev_(\d{8})-(\d{6})\.csv$", path.name)
    fecha = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]} {m.group(2)[:2]}:{m.group(2)[2:4]}:{m.group(2)[4:]}" if m else path.name
    mb = path.stat().st_size / (1024 * 1024)
    return f"{fecha} · {mb:.1f} MB"


def _strip_extension(name):
    """El dataset es el prefijo de los ficheros, sin extensión: si el usuario
    escribe 'panas.csv' se queda 'panas' (evita generar 'panas.csv.csv')."""
    low = name.lower()
    for ext in _DATA_EXTS:
        if low.endswith(ext):
            return name[: -len(ext)]
    return name


def _new_dataset_input(key):
    """Campo de texto para un dataset nuevo, quitándole la extensión si la lleva."""
    raw = st.text_input("New dataset", key=f"{key}_new").strip()
    name = _strip_extension(raw)
    if name != raw:
        st.caption(f"Dataset names have no extension; '{name}' will be used.")
    return name


def prefix_input(label, key, allow_new=False, kinds=_ALL_KINDS):
    """Entrada de Dataset como desplegable con los datasets del proyecto activo,
    el más reciente preseleccionado (así se trabaja por defecto con lo último).

    Un dataset es el prefijo (sin extensión) de los ficheros que produce; los
    ficheros derivados son {dataset}.csv, {dataset}_RTs.csv, etc.
    Con allow_new (Search y User TL) el desplegable incluye la opción de crear
    un dataset nuevo, que despliega un campo de texto. En el resto de casos el
    dataset tiene que existir. Sin proyecto activo, campo de texto plano.
    kinds limita el origen de los datasets listados (ver project_prefixes).
    """
    if not st.session_state.active_project:
        return _strip_extension(st.text_input(label, key=f"{key}_txt").strip())
    options = project_prefixes(projects.select_project(st.session_state.active_project), kinds=kinds)
    if allow_new:
        options = options + [_NEW_PREFIX_OPTION]
    if not options:
        st.caption("No datasets in this project yet.")
        return ""
    choice = st.selectbox(label, options, key=f"{key}_sel")
    if choice == _NEW_PREFIX_OPTION:
        return _new_dataset_input(key)
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
            if st.button("Create account"):
                cookies = f"auth_token={new_auth_token}; ct0={new_ct0}"
                log(f"Adding account @{new_username}...")
                result = run_async(accounts.add_account(
                    new_username, new_password, new_email, new_email_password, cookies
                ))
                if result.get("success") and result.get("active"):
                    log(f"Account @{new_username} added and active")
                elif result.get("success"):
                    log(f"Account @{new_username} added but not active (check cookies)")
                else:
                    log_error(f"{result.get('message')}")
        with tab2:
            if st.button("Refresh list"):
                st.session_state.active_accounts = run_async(accounts.list_accounts())
            data = st.session_state.get("active_accounts", [])
            if data:
                set_result_df(pd.DataFrame(data)[["username", "email", "active"]], "Cuentas activas")
            else:
                st.write("No data. Click 'Refresh list'.")
        with tab3:
            del_username = st.text_input("Username to delete", key="del_username")
            if st.button("Delete account"):
                result = run_async(accounts.delete_account(del_username))
                if result.get("success"):
                    log(f"Account @{del_username} deleted")
                else:
                    log_error(f"{result.get('message')}")

    elif section == "Project":
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Select project", "New project", "Active projects", "Deactivate project", "Reactivate project"]
        )
        with tab1:
            active_list = projects.list_active_projects()
            if active_list:
                chosen = st.selectbox("Project name", active_list)
                if st.button("Select project"):
                    st.session_state.active_project = chosen
                    log(f"Active project: {chosen}")
            else:
                st.write("No projects. Create one in 'New project'.")
        with tab2:
            new_project_name = st.text_input("Project name (new)", key="new_project_name")
            if st.button("Create project"):
                try:
                    projects.new_project(new_project_name)
                    st.session_state.active_project = new_project_name
                    log(f"Project '{new_project_name}' created and activated")
                except (ValueError, FileExistsError) as e:
                    log_error(str(e))
        with tab3:
            active_list = projects.list_active_projects()
            if active_list:
                set_result_df(pd.DataFrame({"project": active_list}), "Active projects")
            else:
                st.write("No active projects.")
        with tab4:
            active_list = projects.list_active_projects()
            if active_list:
                to_deactivate = st.selectbox("Project name to deactivate", active_list, key="deact_select")
                st.caption("t-hoarder never deletes a project: it just moves it to data/desactivated/.")
                if st.button("Deactivate project"):
                    projects.deactivate_project(to_deactivate)
                    if st.session_state.active_project == to_deactivate:
                        st.session_state.active_project = None
                    log(f"Project '{to_deactivate}' deactivated")
                    st.rerun()
            else:
                st.write("No active projects to deactivate.")
        with tab5:
            inactive_list = projects.list_inactive_projects()
            if inactive_list:
                to_reactivate = st.selectbox("Deactivated project to reactivate", inactive_list, key="react_select")
                if st.button("Reactivate project"):
                    try:
                        projects.reactivate_project(to_reactivate)
                        st.session_state.active_project = to_reactivate
                        log(f"Project '{to_reactivate}' reactivated and set as active")
                        st.rerun()
                    except (FileNotFoundError, FileExistsError) as e:
                        log_error(str(e))
            else:
                st.write("No deactivated projects.")

    elif section == "Download":
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Search", "User TL", "Retweets", "Comments", "Advanced Comments"])
        with tab1:
            search_prefix = prefix_input("Dataset", "search_prefix", allow_new=True, kinds=("search",))
            if st.button("Load context", key="search_load_ctx"):
                if not search_prefix:
                    log_error("enter the Dataset before loading the context")
                elif not st.session_state.active_project:
                    log_error("select or create a project before loading the context")
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
                        log(f"Context loaded for dataset '{search_prefix}'")
                    else:
                        st.session_state.search_query = ""
                        st.session_state.search_product = "Top"
                        st.session_state.search_from = ""
                        st.session_state.search_to = ""
                        st.session_state.search_freq_n = 1
                        st.session_state.search_freq_unit = "hour"
                        log(f"No saved context for dataset '{search_prefix}'")
                    st.rerun()

            search_query = st.text_input("Query", key="search_query")
            search_product = st.radio("Product", ["Top", "Latest"], horizontal=True, key="search_product")
            search_from = st.text_input("From (YYYY-mm-dd HH:MM:SS)", key="search_from")
            search_to = st.text_input("To (YYYY-mm-dd HH:MM:SS)", key="search_to")
            search_freq = frequency_input("search")
            if st.button("Launch search"):
                date_error = validate_date_range(search_from, search_to)
                if not st.session_state.active_project:
                    log_error("select or create a project before downloading")
                elif date_error:
                    log(date_error)
                else:
                    log(f"Launching historical_search ({search_product}, frequency={search_freq})")
                    output_file = download.historical_search(
                        data_path=DATA_PATH, dataset=st.session_state.active_project,
                        prefix=search_prefix, query=search_query,
                        since=search_from, until=search_to,
                        frequency=search_freq, product=search_product, log=log,
                    )
                    log(f"Result in {output_file}")
                    set_result(output_file)
        with tab2:
            utl_prefix = prefix_input("Dataset", "utl_prefix", allow_new=True, kinds=("users",))
            if st.button("Load context", key="utl_load_ctx"):
                if not utl_prefix:
                    log_error("enter the Dataset before loading the context")
                elif not st.session_state.active_project:
                    log_error("select or create a project before loading the context")
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
                        log(f"Context loaded for dataset '{utl_prefix}'")
                    else:
                        st.session_state.utl_users_text = ""
                        st.session_state.utl_from = ""
                        st.session_state.utl_to = ""
                        st.session_state.utl_product = "Top"
                        st.session_state.utl_freq_n = 1
                        st.session_state.utl_freq_unit = "hour"
                        log(f"No saved context for dataset '{utl_prefix}'")
                    st.rerun()

            utl_users_text = st.text_input(
                "Users list (Comma-separated list of users, without @)", key="utl_users_text"
            )
            utl_product = st.radio("Product", ["Top", "Latest"], horizontal=True, key="utl_product")
            utl_from = st.text_input("From (YYYY-mm-dd HH:MM:SS)", key="utl_from")
            utl_to = st.text_input("To (YYYY-mm-dd HH:MM:SS)", key="utl_to")
            utl_freq = frequency_input("utl")
            if st.button("Launch TL download"):
                date_error = validate_date_range(utl_from, utl_to)
                users_list, users_error = parse_users_list(utl_users_text)
                if not st.session_state.active_project:
                    log_error("select or create a project before downloading")
                elif date_error:
                    log(date_error)
                elif users_error:
                    log(users_error)
                else:
                    log(f"Launching historical_timeline for {len(users_list)} user(s) (frequency={utl_freq})")
                    output_file = download.historical_timeline(
                        data_path=DATA_PATH, dataset=st.session_state.active_project,
                        prefix=utl_prefix, list_users=users_list,
                        since=utl_from, until=utl_to, frequency=utl_freq,
                        product=utl_product, log=log,
                    )
                    log(f"Result in {output_file}")
                    set_result(output_file)
        with tab3:
            rt_prefix = prefix_input("Dataset", "rt_prefix")
            rt_min = st.number_input("Min RTs", min_value=0, value=1, key="rt_min")
            if st.button("Launch RTs download"):
                if not st.session_state.active_project:
                    log_error("select or create a project before downloading")
                elif not rt_prefix:
                    log_error("enter the Dataset of the file with the original tweets")
                else:
                    log(f"Launching get_retweets (min_rts={int(rt_min)})")
                    try:
                        output_file = download.get_retweets(
                            data_path=DATA_PATH, dataset=st.session_state.active_project,
                            prefix=rt_prefix, min_rts=int(rt_min), log=log,
                        )
                        log(f"Result in {output_file}")
                        set_result(output_file)
                    except FileNotFoundError:
                        log_error(f"{rt_prefix}.csv does not exist in the active project. Download those tweets first (Search/User TL).")
        with tab4:
            cm_prefix = prefix_input("Dataset", "cm_prefix")
            cm_min = st.number_input("Min Replies", min_value=0, value=1, key="cm_min")
            if st.button("Launch comments download"):
                if not st.session_state.active_project:
                    log_error("select or create a project before downloading")
                elif not cm_prefix:
                    log_error("enter the Dataset of the file with the original tweets")
                else:
                    log(f"Launching get_replies (min_replies={int(cm_min)})")
                    try:
                        output_file = download.get_replies(
                            data_path=DATA_PATH, dataset=st.session_state.active_project,
                            prefix=cm_prefix, min_replies=int(cm_min), log=log,
                        )
                        log(f"Result in {output_file}")
                        set_result(output_file)
                    except FileNotFoundError:
                        log_error(f"{cm_prefix}.csv does not exist in the active project. Download those tweets first (Search/User TL).")
        with tab5:
            acm_prefix = prefix_input("Dataset", "acm_prefix")
            acm_min = st.number_input("Min Replies", min_value=0, value=1, key="acm_min")
            acm_last = st.number_input("Last (days)", min_value=0, value=1, key="acm_last")
            acm_freq = frequency_input("acm")
            if st.button("Launch advanced download"):
                if not st.session_state.active_project:
                    log_error("select or create a project before downloading")
                elif not acm_prefix:
                    log_error("enter the Dataset of the file with the original tweets")
                else:
                    log(f"Launching get_replies_advanced (frequency={acm_freq})")
                    try:
                        output_file = download.get_replies_advanced(
                            data_path=DATA_PATH, dataset=st.session_state.active_project,
                            prefix=acm_prefix, min_replies=int(acm_min),
                            last_days=int(acm_last), frequency=acm_freq, log=log,
                        )
                        log(f"Result in {output_file}")
                        set_result(output_file)
                    except FileNotFoundError:
                        log_error(f"{acm_prefix}.csv does not exist in the active project. Download those tweets first (Search/User TL).")

    elif section == "Dashboard":
        if not st.session_state.active_project:
            st.write("Select or create a project in 'Project' before opening a dashboard.")
        else:
            db_prefix = prefix_input("Dataset", "db_prefix")
            db_title = st.text_input("Title (optional)", key="db_title")
            if st.button("Show dashboard", key="db_show"):
                if not db_prefix:
                    log_error("select a Dataset")
                else:
                    try:
                        project_dir = projects.select_project(st.session_state.active_project)
                        with st.spinner("Building dashboard..."):
                            html, path = dashboard.generate_dashboard(
                                project_dir, db_prefix, db_title or db_prefix, log=log,
                            )
                        set_result_report(html, path)
                    except (FileNotFoundError, ValueError) as e:
                        log_error(str(e))

    elif section == "Tools":
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Merge datasets", "Clean dataset", "Restore dataset", "Compare datasets", "Location"]
        )
        with tab1:
            if not st.session_state.active_project:
                st.write("Select or create a project in 'Project' before merging datasets.")
            else:
                project_dir = projects.select_project(st.session_state.active_project)
                available_datasets = project_prefixes(project_dir)
                if not available_datasets:
                    st.write("No datasets in this project yet.")
                else:
                    merge_datasets_selected = st.multiselect(
                        "Datasets to merge (must be in the active project)",
                        available_datasets, key="merge_datasets_selected",
                    )
                    merge_dest = _strip_extension(st.text_input("Destination dataset", key="merge_dest").strip())
                    if st.button("Combine datasets"):
                        if len(merge_datasets_selected) < 2:
                            log_error("select at least 2 datasets to merge")
                        elif not merge_dest:
                            log_error("enter the destination dataset name")
                        else:
                            try:
                                output_file = utils.merge_datasets(
                                    project_dir, merge_datasets_selected, merge_dest, log=log
                                )
                                log(f"Result in {output_file}")
                                set_result(output_file)
                                # rerun para que el dataset combinado aparezca ya en las
                                # listas (la lista se calculó antes de crear su contexto)
                                st.rerun()
                            except (ValueError, FileNotFoundError) as e:
                                log_error(str(e))
        with tab2:
            if not st.session_state.active_project:
                st.write("Select or create a project in 'Project' before cleaning data.")
            else:
                clean_prefix = prefix_input("Dataset (prefix of the file with the original tweets)", "clean_prefix")
                clean_langs_text = st.text_input(
                    "Languages (to keep, comma-separated, e.g. es,ca; empty = no filter)",
                    key="clean_langs_text",
                )
                clean_positives = st.text_area(
                    "Positives: keep tweets containing any of these comma-separated words (e.g. rstats,python)",
                    key="clean_positives",
                )
                clean_false_positives = st.text_area(
                    "False positives: exclude tweets containing any of these comma-separated words (e.g. futbol,humor)",
                    key="clean_false_positives",
                )
                clean_dest = _strip_extension(st.text_input("Destination dataset", key="clean_dest").strip())
                if st.button("Clean dataset"):
                    if not clean_prefix:
                        log_error("enter the Dataset to clean")
                    elif not clean_dest:
                        log_error("enter the destination dataset name")
                    else:
                        project_dir = projects.select_project(st.session_state.active_project)
                        langs_list = [w.strip() for w in clean_langs_text.split(",") if w.strip()]
                        positives_list = [w.strip() for w in clean_positives.split(",") if w.strip()]
                        false_positives_list = [w.strip() for w in clean_false_positives.split(",") if w.strip()]
                        try:
                            output_file, before, after, discarded = utils.clean_dataset(
                                project_dir, clean_prefix, clean_dest,
                                langs=langs_list, positives=positives_list,
                                false_positives=false_positives_list, log=log,
                            )
                            pct = round((before - after) / before * 100, 1) if before else 0.0
                            log(f"Result in {output_file}")
                            set_result_df(
                                discarded,
                                f"'{clean_dest}': {before:,} → {after:,} tweets · "
                                f"{pct}% removed ({before - after:,}). Discarded tweets:",
                            )
                            # rerun para que el dataset limpio aparezca ya en las listas
                            st.rerun()
                        except FileNotFoundError as e:
                            log_error(str(e))
        with tab3:
            if not st.session_state.active_project:
                st.write("Select or create a project in 'Project' before restoring datasets.")
            else:
                project_dir = projects.select_project(st.session_state.active_project)
                restorable = utils.datasets_with_backups(project_dir)
                if not restorable:
                    st.write("No datasets have previous versions. They are created when merging, "
                             "cleaning or restoring a dataset (files {dataset}_prev_<date>.csv).")
                else:
                    rst_dataset = st.selectbox("Dataset", restorable, key="rst_dataset")
                    backups = utils.dataset_backups(project_dir, rst_dataset)
                    labels = {_backup_label(f): f.name for f in backups}
                    rst_choice = st.selectbox("Version to restore (previous versions, newest first)",
                                              list(labels.keys()), key="rst_version")
                    st.caption("Restoring replaces the current dataset with that previous version "
                               "(the current one is saved first as a new _prev_, so it is reversible).")
                    if st.button("Restore dataset"):
                        try:
                            path, total = utils.restore_dataset(
                                project_dir, rst_dataset, labels[rst_choice], log=log
                            )
                            log(f"Restored {path.name} ({total} tweets)")
                            set_result(path)
                            st.rerun()
                        except FileNotFoundError as e:
                            log_error(str(e))
        with tab4:
            if not st.session_state.active_project:
                st.write("Select or create a project in 'Project' before comparing datasets.")
            else:
                project_dir = projects.select_project(st.session_state.active_project)
                available_datasets = project_prefixes(project_dir)
                if not available_datasets:
                    st.write("No datasets in this project yet.")
                else:
                    cmp_selected = st.multiselect(
                        "Datasets to compare (must be in the active project)",
                        available_datasets, key="cmp_selected",
                    )
                    st.caption("Compares metrics per dataset, tweets shared by all of them "
                               "(overlap by tweet id) and a timeline by hour/day/week/month.")
                    if st.button("Compare datasets", key="cmp_btn"):
                        if len(cmp_selected) < 2:
                            log_error("select at least 2 datasets to compare")
                        else:
                            try:
                                with st.spinner("Building comparison..."):
                                    html, path = compare.generate_comparison(
                                        project_dir, cmp_selected, log=log,
                                    )
                                set_result_report(html, path)
                            except (ValueError, FileNotFoundError) as e:
                                log_error(str(e))
        with tab5:
            if not st.session_state.active_project:
                st.write("Select or create a project in 'Project' before extracting locations.")
            else:
                loc_prefix = prefix_input(
                    "Dataset (dataset with the original tweets; generates {dataset}_loc.csv)",
                    "loc_prefix",
                )
                if st.button("Extract location"):
                    if not loc_prefix:
                        log_error("enter the Dataset")
                    else:
                        project_dir = projects.select_project(st.session_state.active_project)
                        try:
                            output_file = utils.extract_locations(project_dir, loc_prefix, log=log)
                            log(f"Result in {output_file}")
                            set_result(output_file)
                        except FileNotFoundError as e:
                            log_error(str(e))

    elif section == "Graphs":
        if not st.session_state.active_project:
            st.write("Select or create a project in 'Project' before working with graphs.")
        else:
            project_dir = projects.select_project(st.session_state.active_project)
            import graphs as graphs_mod

            tab1, tab2, tab3, tab4 = st.tabs(
                ["Detect communities", "Generate graph", "Classify tweets", "Visualize graph"]
            )
            with tab1:
                dc_prefix = prefix_input("Dataset", "dc_prefix")
                dc_relation = st.selectbox(
                    "Relation (relation type)", ["RT", "replies", "replies_advanced"], key="dc_relation"
                )
                if st.button("Detect communities"):
                    if not dc_prefix:
                        log_error("enter the Dataset")
                    else:
                        try:
                            communities_file, users_file = graphs_mod.detect_communities(
                                project_dir, dc_prefix, dc_relation, log=log
                            )
                            set_result(communities_file, users_file)
                        except FileNotFoundError as e:
                            log_error(str(e))
            with tab2:
                gg_prefix = prefix_input("Dataset", "gg_prefix")
                gg_relation = st.selectbox(
                    "Relation (relation type)", ["RT", "replies", "replies_advanced"], key="gg_relation"
                )
                gg_format = st.selectbox("Format", ["gdf", "gexf"], key="gg_format")
                gg_include_communities = st.checkbox(
                    "Include communities (requires running 'Detect communities' first)",
                    value=True, key="gg_include_communities",
                )
                gg_include_locations = st.checkbox(
                    "Include locations (requires {prefix}_loc.csv, generated in Tools > Location)",
                    value=False, key="gg_include_locations",
                )
                if st.button("Generate graph"):
                    if not gg_prefix:
                        log_error("enter the Dataset")
                    else:
                        try:
                            graph_file = graphs_mod.generate_graph(
                                project_dir, gg_prefix, gg_relation, output_format=gg_format,
                                include_communities=gg_include_communities,
                                include_locations=gg_include_locations, log=log,
                            )
                            log(f"Graph in {graph_file}")
                            set_result(graph_file)
                        except FileNotFoundError as e:
                            log_error(str(e))
            with tab3:
                ct_prefix = prefix_input("Dataset", "ct_prefix")
                ct_relation = st.selectbox(
                    "Relation (relation type)", ["RT", "replies", "replies_advanced"], key="ct_relation"
                )
                if st.button("Classify tweets"):
                    if not ct_prefix:
                        log_error("enter the Dataset")
                    else:
                        try:
                            classified_file = graphs_mod.classify_tweets(
                                project_dir, ct_prefix, ct_relation, log=log
                            )
                            log(f"Result in {classified_file}")
                            set_result(classified_file)
                        except FileNotFoundError as e:
                            log_error(str(e))
            with tab4:
                available_graphs = sorted(
                    p.name for p in project_dir.glob("*.gdf")
                ) + sorted(p.name for p in project_dir.glob("*.gexf"))
                if not available_graphs:
                    st.write("No graph files (.gdf/.gexf) in this project yet.")
                else:
                    vg_file = st.selectbox("Select graph", available_graphs, key="vg_file")
                    vg_max_labels = st.slider(
                        "Max labels per community", min_value=1, max_value=50, value=10, key="vg_max_labels"
                    )
                    vg_iterations = st.slider(
                        "ForceAtlas2 iterations", min_value=100, max_value=2000, value=300, step=50,
                        key="vg_iterations",
                        help="The layout is computed in the browser in seconds. With LinLog mode "
                             "communities separate within a few hundred iterations.",
                    )
                    if st.button("Visualize graph"):
                        try:
                            view_data, communities_shown = graphs_mod.graph_view_data(
                                project_dir, vg_file,
                                max_labels_per_community=vg_max_labels, log=log,
                            )
                            log(f"Communities shown: {', '.join(communities_shown)}")
                            set_result_graph_html(graphs_mod.render_graph_html(
                                view_data, vg_iterations, Path(vg_file).stem,
                            ))
                        except (FileNotFoundError, ValueError) as e:
                            log_error(str(e))

    elif section == "Charts":
        chart_type = st.radio("Chart type", ["Tweets", "Users"], horizontal=True)
        if chart_type == "Tweets":
            if not st.session_state.active_project:
                st.write("Select or create a project in 'Project' before generating charts.")
            else:
                col_prefix, col_title = st.columns(2)
                with col_prefix:
                    tg_prefix = prefix_input("Dataset", "tg_prefix", kinds=("search",))
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

                col_comm_chk, col_comm_rel = st.columns([1, 2])
                with col_comm_chk:
                    tg_communities = st.checkbox("Show communities", key="tg_communities")
                with col_comm_rel:
                    tg_comm_relation = st.selectbox(
                        "Communities relation", ["RT", "replies", "replies_advanced"],
                        key="tg_comm_relation", disabled=not tg_communities,
                        label_visibility="collapsed",
                    )

                col_topics_chk, col_topics_file = st.columns([1, 2])
                with col_topics_chk:
                    tg_topics = st.checkbox("Show topics", key="tg_topics")
                with col_topics_file:
                    tg_topics_file = st.text_input(
                        "Topics file (CSV columns: topics, color)", key="tg_topics_file", disabled=not tg_topics,
                        label_visibility="collapsed", placeholder="Topics file (CSV columns: topics, color)",
                    )

                col_events_chk, col_events_file = st.columns([1, 2])
                with col_events_chk:
                    tg_events = st.checkbox("Show events", key="tg_events")
                with col_events_file:
                    tg_events_file = st.text_input(
                        "Events file (CSV columns: date, event)", key="tg_events_file", disabled=not tg_events,
                        label_visibility="collapsed", placeholder="Events file (CSV columns: date, event)",
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
                tg_do_charts = col_btn_charts.button("Generate Tweets chart")
                tg_do_report = col_btn_report.button("Generate Tweets HTML report")
                if tg_do_charts or tg_do_report:
                    if not tg_prefix:
                        log_error("enter the Dataset")
                    elif tg_zoom and (not tg_zoom_min.strip() or not tg_zoom_max.strip()):
                        log_error("fill in 'Min date zoom' and 'Max date zoom' or uncheck 'Zoom'")
                    else:
                        try:
                            import charts as charts_mod

                            project_dir = projects.select_project(st.session_state.active_project)
                            chart_args = dict(
                                min_reach=tg_reach, min_RTs=tg_rts,
                                show_topics=tg_topics, topics_file=tg_topics_file,
                                show_events=tg_events, events_file=tg_events_file,
                                show_communities=tg_communities, communities_relation=tg_comm_relation,
                                min_date_zoom=tg_zoom_min if tg_zoom else None,
                                max_date_zoom=tg_zoom_max if tg_zoom else None,
                                log=log,
                            )
                            if tg_do_charts:
                                with st.spinner("Generating charts..."):
                                    figs, image_path = charts_mod.generate_tweet_charts(
                                        project_dir, tg_prefix, tg_title or tg_prefix, tg_tz,
                                        **chart_args,
                                    )
                                log(f"Tweet Graph generated: {len(figs)} charts in {image_path}")
                                set_result_charts(figs, image_path)
                            else:
                                with st.spinner("Generating HTML report..."):
                                    report_html, report_path = charts_mod.generate_tweet_report(
                                        project_dir, tg_prefix, tg_title or tg_prefix, tg_tz,
                                        **chart_args,
                                    )
                                set_result_report(report_html, report_path)
                        except (FileNotFoundError, ValueError) as e:
                            log_error(str(e))
        else:
            if not st.session_state.active_project:
                st.write("Select or create a project in 'Project' before generating charts.")
            else:
                col_prefix, col_username = st.columns(2)
                with col_prefix:
                    ug_prefix = prefix_input("Dataset", "ug_prefix", kinds=("users",))
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
                        "Topics file (CSV columns: topics, color)", key="ug_topics_file", disabled=not ug_topics,
                        label_visibility="collapsed", placeholder="Topics file (CSV columns: topics, color)",
                    )

                col_events_chk, col_events_file = st.columns([1, 2])
                with col_events_chk:
                    ug_events = st.checkbox("Show events", key="ug_events")
                with col_events_file:
                    ug_events_file = st.text_input(
                        "Events file (CSV columns: date, event)", key="ug_events_file", disabled=not ug_events,
                        label_visibility="collapsed", placeholder="Events file (CSV columns: date, event)",
                    )

                col_btn_charts, col_btn_report = st.columns(2)
                ug_do_charts = col_btn_charts.button("Generate User chart")
                ug_do_report = col_btn_report.button("Generate User HTML report")
                if ug_do_charts or ug_do_report:
                    if not ug_prefix or not ug_username:
                        log_error("enter the Dataset and Username")
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
                                with st.spinner("Generating charts..."):
                                    figs, image_path = charts_mod.generate_user_charts(
                                        project_dir, ug_prefix, ug_username, ug_title or ug_username, ug_tz,
                                        **chart_args,
                                    )
                                log(f"User Graph generated: {len(figs)} charts in {image_path}")
                                set_result_charts(figs, image_path)
                            else:
                                with st.spinner("Generating HTML report..."):
                                    report_html, report_path = charts_mod.generate_user_report(
                                        project_dir, ug_prefix, ug_username, ug_title or ug_username, ug_tz,
                                        **chart_args,
                                    )
                                set_result_report(report_html, report_path)
                        except (FileNotFoundError, ValueError) as e:
                            log_error(str(e))

with context_col:
    st.markdown("### Context")
    n_accounts = sum(1 for a in st.session_state.get("active_accounts", []) if a.get("active"))
    project_label = st.session_state.active_project or "ninguno"
    st.write(f"**Active accounts:** {n_accounts}")
    st.write(f"**Active project:** {project_label}")

    if st.session_state.active_project:
        project_dir = projects.select_project(st.session_state.active_project)
        prefixes = project_prefixes(project_dir)
        if prefixes:
            st.caption("Datasets and their context log:")
            for prefix in prefixes:
                with st.expander(prefix):
                    log_df = context.get_log(project_dir, prefix)
                    if log_df is not None and not log_df.empty:
                        st.dataframe(log_df, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No operations recorded.")

with right:
    st.markdown("### Results")
    error_msg = st.session_state.get("last_error")
    graph_html = st.session_state.get("graph_html")
    chart_figures = st.session_state.get("chart_figures")
    report_html = st.session_state.get("report_html")
    result_df = st.session_state.get("last_result_df")
    result_file = st.session_state.get("last_result_file")
    if error_msg or chart_figures or result_df is not None or graph_html or report_html or result_file:
        if st.button("Clear results"):
            clear_results()
            st.rerun()

    if error_msg:
        st.error(error_msg)
    elif report_html:
        report_path = st.session_state.get("report_path", "")
        st.caption(f"Report saved to: {report_path}")
        st.download_button(
            "Download HTML report", data=report_html,
            file_name=Path(report_path).name or "informe.html", mime="text/html",
        )
        st_components.html(report_html, height=800, scrolling=True)
    elif chart_figures:
        st.caption(f"Charts saved to: {st.session_state.get('chart_figures_path', '')}")
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
                    st.write(f"{n_rows} rows (showing first 50)")
                else:
                    st.write(f"{n_rows} rows")
                st.dataframe(preview_df, use_container_width=preview_df.shape[1] > 3)
            else:
                with open(path, encoding="utf-8") as f:
                    preview_lines = [next(f, "") for _ in range(50)]
                st.write("Non-tabular file (showing first 50 lines)")
                st.code("".join(preview_lines), language="text")

        _preview_file(result_file)
        result_file2 = st.session_state.get("last_result_file2")
        if result_file2 and Path(result_file2).exists():
            st.divider()
            _preview_file(result_file2)
    else:
        st.write("Tables, charts or generated files will appear here depending on the action.")
