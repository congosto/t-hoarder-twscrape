"""graphs.py — grafos de relaciones (RT / replies) con detección de comunidades
y visor interactivo sigma.js, para t-hoarder-twscraper.

Versión auditada y mejorada (jul-2026), integrada desde la auditoría externa
(cuatro revisores, dos rondas; ver commit). API pública sin cambios:
detect_communities, generate_graph, classify_tweets, graph_view_data,
render_graph_html, load_graph_file.
"""
import csv as _csv
import math
from pathlib import Path

import networkx as nx
import pandas as pd

_NODE_ATTR_TYPES = {
    "community": "VARCHAR",
    "log_followers_count": "INT",
    "log_friends_count": "INT",
    "log_statuses_count": "INT",
    "log_favourites_count": "INT",
    "log_listed_count": "INT",
    "location_country": "VARCHAR",
    "location_region": "VARCHAR",
    "location_city": "VARCHAR",
    "create_at_year": "INT",
    "user_verified": "BOOLEAN",
    "is_blue_verified": "BOOLEAN",
    "verified_type": "VARCHAR",
}
_NODE_ATTR_COLUMNS = list(_NODE_ATTR_TYPES.keys())

# Atributos y orden en que se muestran en el tooltip/panel del visor interactivo
_TOOLTIP_ATTRS = [
    "create_at_year", "user_verified", "is_blue_verified", "verified_type",
    "log_followers_count", "log_friends_count", "log_statuses_count",
    "log_favourites_count", "log_listed_count",
    "location_country", "location_region", "location_city",
]

_AUTHOR_COLUMNS = [
    "username", "followers_count", "friends_count", "statuses_count",
    "favourites_count", "listed_count", "location", "created_at",
    "user_verified", "is_blue_verified", "verified_type",
]

_COUNT_COLUMNS = ["followers_count", "friends_count", "statuses_count",
                  "favourites_count", "listed_count"]

# Prefijos de columnas con metadatos del usuario DESTINO de la relación, si el CSV
# los trae (p.ej. "user_retweeted_followers_count"). Permite dar atributos a los
# hubs aunque no hayan tuiteado en el dataset.
_TARGET_PREFIXES = {
    "RT": "user_retweeted_",
    "replies": "in_reply_to_user_",
    "replies_advanced": "in_reply_to_user_",
}


def _norm_username(series: pd.Series) -> pd.Series:
    """Normaliza handles: sin @ inicial, sin espacios, en minúsculas.

    En X los handles son case-insensitive; sin esto '@Usuario' y 'usuario'
    acaban siendo dos nodos distintos del grafo.
    """
    return series.astype(str).str.strip().str.lstrip("@").str.lower()


def _log10(series: pd.Series) -> pd.Series:
    """Parte entera del logaritmo en base 10 (0 para valores 0 o negativos)."""
    values = pd.to_numeric(series, errors="coerce").fillna(0).clip(lower=1).apply(math.log10)
    return values.apply(math.floor).astype(int)


def _original_tweet_urls(project_dir: Path, prefix: str) -> set | None:
    """URLs de los tweets originales de {prefix}.csv, o None si no se pueden leer
    (no existe el fichero o no tiene columna 'url')."""
    tweets_file = project_dir / f"{prefix}.csv"
    if not tweets_file.exists():
        return None
    try:
        urls = pd.read_csv(tweets_file, encoding="utf-8", usecols=["url"])["url"]
    except ValueError:
        return None
    return set(urls.dropna().astype(str))


def _load_relations(project_dir: Path, prefix: str, relation: str,
                    filter_orphan_rts: bool = True, log=print) -> pd.DataFrame:
    if relation == "RT":
        path = project_dir / f"{prefix}_RTs.csv"
        if not path.exists():
            raise FileNotFoundError(f"No existe {path}. Descarga primero los Retweets.")
        df = pd.read_csv(path, encoding="utf-8")
        # Descarta RTs huérfanos: los que retuitean (url_rt) un tweet original que
        # ya no está en {prefix}.csv, p.ej. porque el dataset se limpió por idioma o
        # palabras después de bajar los RTs. Equivale al right_join con los tweets
        # originales del cuaderno R: sin esto, el grafo incluye relaciones que ya no
        # existen en el dataset limpio.
        if filter_orphan_rts and "url_rt" in df.columns:
            valid = _original_tweet_urls(project_dir, prefix)
            if valid:
                before = len(df)
                df = df[df["url_rt"].astype(str).isin(valid)]
                dropped = before - len(df)
                if dropped:
                    log(f"RTs huérfanos descartados (su tweet original ya no está en "
                        f"{prefix}.csv): {dropped} de {before}")
        df["source"] = df["username"]
        df["target"] = df["user_retweeted"]
    elif relation == "replies_advanced":
        path = project_dir / f"{prefix}_replies_advanced.csv"
        if not path.exists():
            raise FileNotFoundError(f"No existe {path}. Descarga primero las Advanced Comments.")
        df = pd.read_csv(path, encoding="utf-8")
        df["source"] = df["username"]
        df["target"] = df["in_reply_to_user_username"]
    elif relation == "replies":
        path = project_dir / f"{prefix}_replies.csv"
        if not path.exists():
            raise FileNotFoundError(f"No existe {path}. Descarga primero las Comments.")
        df = pd.read_csv(path, encoding="utf-8")
        df["source"] = df["username"]
        df["target"] = df["in_reply_to_user_username"]
    else:
        raise ValueError("relation debe ser 'RT', 'replies' o 'replies_advanced'")

    df = df.dropna(subset=["source", "target"])
    df["source"] = _norm_username(df["source"])
    df["target"] = _norm_username(df["target"])
    # astype(str) convierte NaN en "nan": ya se ha hecho dropna antes, pero por si
    # acaso se filtran también los literales vacíos/"nan"
    df = df[(df["source"] != "") & (df["target"] != "")]
    df = df[(df["source"] != "nan") & (df["target"] != "nan")]
    df = df[df["source"] != df["target"]]
    if df.empty:
        raise ValueError(f"{path.name} no contiene ninguna relación válida (¿fichero vacío?)")
    return df


def _build_giant_graph(project_dir: Path, prefix: str, relation: str, log=print,
                       min_component_size: int | None = None,
                       filter_orphan_rts: bool = True) -> tuple[nx.DiGraph, pd.DataFrame]:
    """Construye el grafo dirigido de la relación indicada.

    Por defecto (min_component_size=None) se queda solo con la componente conexa
    más grande, como antes. Si se indica min_component_size, en vez de eso
    conserva TODAS las componentes con al menos ese número de nodos: una
    botfarm que solo se retuitea entre sí forma su propia componente aislada
    y con el filtro "solo la gigante" queda completamente invisible — para
    detectar coordinación/astroturfing conviene poder incluirla.

    filter_orphan_rts (solo relación RT): descarta los RTs cuyo tweet original ya
    no está en {prefix}.csv (ver _load_relations).
    """
    relations_df = _load_relations(project_dir, prefix, relation,
                                   filter_orphan_rts=filter_orphan_rts, log=log)
    log(f"Relaciones cargadas: {len(relations_df)}")

    edges = relations_df.groupby(["source", "target"]).size().reset_index(name="weight")
    G = nx.from_pandas_edgelist(edges, source="source", target="target",
                                edge_attr="weight", create_using=nx.DiGraph)
    log(f"Grafo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

    # weakly_connected_components evita construir una copia no dirigida completa
    # del grafo solo para calcular las componentes.
    components = list(nx.weakly_connected_components(G))
    if not components:
        raise ValueError("El grafo no tiene ningún nodo tras filtrar las relaciones.")

    if min_component_size is None:
        keep = max(components, key=len)
        log(f"Componente gigante: {len(keep)} nodos de {G.number_of_nodes()}")
    else:
        big = [c for c in components if len(c) >= min_component_size]
        if not big:
            big = [max(components, key=len)]
        keep = set().union(*big)
        log(f"Componentes con >= {min_component_size} nodos: {len(big)} "
            f"({len(keep)} nodos de {G.number_of_nodes()})")
    G_giant = G.subgraph(keep).copy()

    return G_giant, relations_df


def _sum_undirected(G: nx.DiGraph) -> nx.Graph:
    """Versión no dirigida sumando pesos de aristas recíprocas.

    G.to_undirected() se queda con el peso de UNA de las dos aristas A<->B en vez
    de sumarlas, y Louvain acaba viendo pesos incorrectos justo en los pares con
    interacción mutua (la señal más fuerte de comunidad).
    """
    U = nx.Graph()
    U.add_nodes_from(G.nodes())
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 1)
        if U.has_edge(u, v):
            U[u][v]["weight"] += w
        else:
            U.add_edge(u, v, weight=w)
    return U


def _node_attributes_table(tweets_df: pd.DataFrame, relations_df: pd.DataFrame,
                           relation: str) -> pd.DataFrame:
    frames = []

    # Autores de tweets y autores de la relación ("username" es el origen).
    for df in (tweets_df, relations_df):
        cols = [c for c in _AUTHOR_COLUMNS if c in df.columns]
        if "username" in cols:
            part = df[cols].copy()
            part["username"] = _norm_username(part["username"])
            frames.append(part)

    # Metadatos del usuario DESTINO si el CSV los trae con prefijo (mejora F7:
    # sin esto los hubs —los nodos más retuiteados— se quedan sin tooltip salvo
    # que hayan tuiteado en el dataset).
    tprefix = _TARGET_PREFIXES.get(relation)
    if tprefix:
        rename = {}
        for col in _AUTHOR_COLUMNS:
            src_col = tprefix + col
            if src_col in relations_df.columns:
                rename[src_col] = col
        # el username destino ya está normalizado en la columna "target"
        if rename:
            part = relations_df[["target", *rename.keys()]].rename(columns=rename)
            part = part.rename(columns={"target": "username"})
            frames.append(part)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["username"])
    combined = combined[~combined["username"].isin(["", "nan"])]
    # primer valor NO nulo por columna: un usuario puede aparecer como autor sin
    # metadatos (fila de la relación) y como destino con ellos — hay que combinarlos
    return combined.groupby("username", sort=False).first()


def detect_communities(project_dir: Path, prefix: str, relation: str, log=print,
                       seed: int = 42, resolution: float = 1.0,
                       min_component_size: int | None = None,
                       compute_betweenness: bool = False,
                       betweenness_k: int | None = 500,
                       filter_orphan_rts: bool = True) -> tuple[Path, Path]:
    """Crea el grafo de la relación, calcula el grado con pesos y la modularidad
    (Louvain/Blondel) con semilla fija — mismo resultado en cada ejecución. Las
    comunidades se persisten aquí y el resto de pasos (generar grafo, clasificar
    tweets) las reutilizan desde estos ficheros.

    min_component_size: None (default) = solo la componente conexa más grande,
    como siempre. Si se indica, conserva TODAS las componentes con al menos ese
    número de nodos — útil para no perder botfarms/clústeres aislados que operan
    en su propio silo (ver _build_giant_graph).

    compute_betweenness: añade betweenness centrality (aproximada con
    betweenness_k muestras si el grafo es grande; exacta si betweenness_k es
    None) a la tabla de usuarios. Identifica nodos "puente" entre comunidades
    que el indegree/PageRank no detectan; coste O(V*E) exacto, por eso es opcional.

    filter_orphan_rts (solo relación RT): descarta los RTs cuyo tweet original ya
    no está en {prefix}.csv (ver _load_relations); para que las comunidades no se
    calculen sobre relaciones que ya no existen tras limpiar el dataset.

    Devuelve (communities_file, users_communities_file).
    """
    G_giant, _ = _build_giant_graph(project_dir, prefix, relation, log=log,
                                    min_component_size=min_component_size,
                                    filter_orphan_rts=filter_orphan_rts)

    indegree = dict(G_giant.in_degree(weight="weight"))
    outdegree = dict(G_giant.out_degree(weight="weight"))

    undirected = _sum_undirected(G_giant)
    communities = nx.community.louvain_communities(undirected, weight="weight",
                                                   seed=seed, resolution=resolution)
    # Numerar por tamaño descendente: la comunidad 0 es siempre la mayor
    communities = sorted(communities, key=len, reverse=True)
    log(f"Comunidades encontradas: {len(communities)}")
    community_of = {node: str(i) for i, comm in enumerate(communities) for node in comm}

    modularity = nx.community.modularity(undirected, communities, weight="weight")
    log(f"Modularidad: {modularity:.3f}")

    total = G_giant.number_of_nodes()
    counts = pd.Series(community_of).value_counts()
    communities_table = pd.DataFrame({
        "community": counts.index,
        "pct_nodes": (counts.values / total * 100).round(2),
    }).sort_values("pct_nodes", ascending=False)
    communities_file = project_dir / f"{prefix}_{relation}_communities.csv"
    communities_table.to_csv(communities_file, index=False, encoding="utf-8")

    pagerank = nx.pagerank(G_giant, weight="weight")

    users_table = pd.DataFrame({"user": list(G_giant.nodes())})
    users_table["community"] = users_table["user"].map(community_of)
    users_table["weight_indegree"] = users_table["user"].map(indegree).fillna(0).astype(int)
    users_table["weight_outdegree"] = users_table["user"].map(outdegree).fillna(0).astype(int)
    users_table["pagerank"] = users_table["user"].map(pagerank).round(6)

    if compute_betweenness:
        # Identifica nodos "puente" entre comunidades (flujo de amplificación
        # cruzada) que el indegree/PageRank no ven. k=None es exacto pero O(V*E);
        # con miles de nodos se aproxima con betweenness_k muestras (nx estándar).
        k = betweenness_k if (betweenness_k and betweenness_k < G_giant.number_of_nodes()) else None
        log(f"Calculando betweenness centrality ({'exacta' if k is None else f'aprox. k={k}'})...")
        betweenness = nx.betweenness_centrality(G_giant, k=k, weight="weight", seed=seed)
        users_table["betweenness"] = users_table["user"].map(betweenness).round(6)

    users_table = users_table.sort_values("weight_indegree", ascending=False)
    users_file = project_dir / f"{prefix}_users_{relation}_communities.csv"
    users_table.to_csv(users_file, index=False, encoding="utf-8")

    log(f"Tabla de comunidades en {communities_file}")
    log(f"Tabla de usuarios/comunidad en {users_file}")
    return communities_file, users_file


def generate_graph(project_dir: Path, prefix: str, relation: str, output_format: str = "gdf",
                   include_communities: bool = True, include_locations: bool = False,
                   min_component_size: int | None = None, filter_orphan_rts: bool = True,
                   log=print) -> Path:
    """Genera el fichero de grafo (gdf/gexf) de la relación indicada con los atributos de nodo.

    include_communities: añade 'community' desde {prefix}_users_{relation}_communities.csv
    (generado antes con 'Detect communities'; falla si no existe).
    include_locations: añade location_country/region/city desde {prefix}_loc.csv
    (generado antes en Tools > Localización; falla si no existe).
    min_component_size: debe coincidir con el usado en 'Detect communities' para
    ese mismo prefix/relation (ver _build_giant_graph) — si no, algunos nodos no
    tendrán comunidad asignada porque no estaban en el grafo con el que se calculó.
    filter_orphan_rts (solo relación RT): descarta los RTs cuyo tweet original ya no
    está en {prefix}.csv (ver _load_relations). Debe coincidir con el usado en
    'Detect communities', por lo mismo que min_component_size.
    Devuelve la ruta del fichero de grafo generado.
    """
    if output_format not in ("gdf", "gexf"):
        raise ValueError(f"output_format debe ser 'gdf' o 'gexf', no '{output_format}'")
    G_giant, relations_df = _build_giant_graph(project_dir, prefix, relation, log=log,
                                               min_component_size=min_component_size,
                                               filter_orphan_rts=filter_orphan_rts)

    tweets_file = project_dir / f"{prefix}.csv"
    if not tweets_file.exists():
        raise FileNotFoundError(f"No existe {tweets_file}")
    tweets_df = pd.read_csv(tweets_file, encoding="utf-8")

    node_attrs = _node_attributes_table(tweets_df, relations_df, relation)
    node_attrs = node_attrs.reindex(list(G_giant.nodes()))
    for col in _COUNT_COLUMNS:
        if col not in node_attrs.columns:
            node_attrs[col] = 0
        node_attrs[f"log_{col}"] = _log10(node_attrs[col])
    if "created_at" in node_attrs.columns:
        node_attrs["create_at_year"] = pd.to_datetime(
            node_attrs["created_at"], errors="coerce", utc=True).dt.year
    else:
        node_attrs["create_at_year"] = None
    for col in ("user_verified", "is_blue_verified", "verified_type"):
        if col not in node_attrs.columns:
            node_attrs[col] = None

    if include_communities:
        users_file = project_dir / f"{prefix}_users_{relation}_communities.csv"
        if not users_file.exists():
            raise FileNotFoundError(f"No existe {users_file}. Ejecuta antes 'Detect communities'.")
        users_df = pd.read_csv(users_file, encoding="utf-8").set_index("user")
        node_attrs["community"] = node_attrs.index.map(users_df["community"].astype(str).to_dict())
    else:
        node_attrs["community"] = None

    if include_locations:
        loc_file = project_dir / f"{prefix}_loc.csv"
        if not loc_file.exists():
            raise FileNotFoundError(f"No existe {loc_file}. Genéralo antes en Tools > Localización.")
        loc_df = pd.read_csv(loc_file, encoding="utf-8")
        loc_df["username"] = _norm_username(loc_df["username"])
        loc_df = loc_df.drop_duplicates("username").set_index("username")
        for col in ("location_country", "location_region", "location_city"):
            node_attrs[col] = node_attrs.index.map(loc_df[col].to_dict() if col in loc_df.columns else {})
        n_resolved = int(node_attrs["location_country"].notna().sum())
        log(f"Localizaciones unidas desde {loc_file.name}: {n_resolved}/{len(node_attrs)} nodos")
    else:
        node_attrs["location_country"] = None
        node_attrs["location_region"] = None
        node_attrs["location_city"] = None

    if output_format == "gexf":
        graph_file = project_dir / f"{prefix}_{relation}.gexf"
        _export_gexf(G_giant, node_attrs, graph_file)
    else:
        graph_file = project_dir / f"{prefix}_{relation}.gdf"
        _export_gdf(G_giant, node_attrs, graph_file)
    log(f"Grafo exportado en {graph_file}")

    return graph_file


def classify_tweets(project_dir: Path, prefix: str, relation: str, log=print) -> Path:
    """Añade a los tweets de {prefix}.csv la comunidad de su autor, leída desde
    {prefix}_users_{relation}_communities.csv (generado antes con 'Detect communities')."""
    tweets_file = project_dir / f"{prefix}.csv"
    if not tweets_file.exists():
        raise FileNotFoundError(f"No existe {tweets_file}")

    users_file = project_dir / f"{prefix}_users_{relation}_communities.csv"
    if not users_file.exists():
        raise FileNotFoundError(f"No existe {users_file}. Ejecuta antes 'Detect communities'.")

    tweets_df = pd.read_csv(tweets_file, encoding="utf-8")
    users_df = pd.read_csv(users_file, encoding="utf-8")
    community_map = users_df.set_index("user")["community"].to_dict()
    tweets_df["community"] = _norm_username(tweets_df["username"]).map(community_map)

    classified_file = project_dir / f"{prefix}_{relation}_classified.csv"
    tweets_df.to_csv(classified_file, index=False, encoding="utf-8")
    n_classified = int(tweets_df["community"].notna().sum())
    pct = (n_classified / len(tweets_df) * 100) if len(tweets_df) else 0.0
    log(f"Tweets clasificados: {n_classified}/{len(tweets_df)} ({pct:.1f}%)")
    return classified_file


def _to_native(value):
    """GEXF no acepta tipos numpy (numpy.bool_, numpy.int64...); hay que convertirlos a tipos nativos."""
    if hasattr(value, "item"):
        return value.item()
    return value


def _export_gexf(G: nx.DiGraph, node_attrs: pd.DataFrame, path: Path) -> None:
    for node in G.nodes():
        if node in node_attrs.index:
            for col in _NODE_ATTR_COLUMNS:
                value = node_attrs.loc[node, col]
                # los NaN se omiten en vez de escribir "": networkx infiere el tipo
                # del atributo del primer valor y mezclar int con "" corrompe el tipado
                if not pd.isna(value):
                    G.nodes[node][col] = _to_native(value)
    nx.write_gexf(G, path)


def _gdf_value(value, col_type: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if col_type == "VARCHAR":
        # sin apóstrofes (delimitador de VARCHAR) ni saltos de línea (el formato
        # GDF es una línea por nodo/arista; un \n en una bio/location lo rompería)
        clean = str(value).replace("'", "").replace("\r", " ").replace("\n", " ")
        return "'" + clean + "'"
    if col_type == "BOOLEAN":
        return "true" if value else "false"
    if col_type == "INT":
        return str(int(value))
    return str(value)


def _export_gdf(G: nx.DiGraph, node_attrs: pd.DataFrame, path: Path) -> None:
    node_header = "nodedef>name VARCHAR," + ",".join(f"{c} {_NODE_ATTR_TYPES[c]}" for c in _NODE_ATTR_COLUMNS)
    edge_header = "edgedef>node1 VARCHAR,node2 VARCHAR,directed BOOLEAN,weight DOUBLE"

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(node_header + "\n")
        for node in G.nodes():
            row = ["'" + str(node).replace("'", "") + "'"]
            for col in _NODE_ATTR_COLUMNS:
                value = node_attrs.loc[node, col] if node in node_attrs.index else None
                row.append(_gdf_value(value, _NODE_ATTR_TYPES[col]))
            f.write(",".join(row) + "\n")

        f.write(edge_header + "\n")
        for u, v, data in G.edges(data=True):
            u_q = "'" + str(u).replace("'", "") + "'"
            v_q = "'" + str(v).replace("'", "") + "'"
            f.write(f"{u_q},{v_q},true,{data.get('weight', 1)}\n")


def _split_gdf_line(line: str) -> list[str]:
    """Divide una línea GDF respetando comillas simples: un VARCHAR como
    'Washington, D.C.' contiene comas y un split(',') plano desalinea columnas."""
    return next(_csv.reader([line], delimiter=",", quotechar="'", skipinitialspace=True))


def _read_gdf(path: Path) -> nx.DiGraph:
    """Lee de vuelta un fichero generado por _export_gdf (no es un parser GDF genérico)."""
    with open(path, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    i = 0
    node_cols: list[str] = []
    while i < len(lines):
        if lines[i].startswith("nodedef>"):
            node_cols = [c.split()[0] for c in lines[i][len("nodedef>"):].split(",")]
            i += 1
            break
        i += 1

    G = nx.DiGraph()
    while i < len(lines) and not lines[i].startswith("edgedef>"):
        if lines[i].strip():
            values = _split_gdf_line(lines[i])
            name = values[0].strip().strip("'")
            attrs = {col: val.strip().strip("'") for col, val in zip(node_cols[1:], values[1:])}
            G.add_node(name, **attrs)
        i += 1

    i += 1  # salta la línea edgedef>
    while i < len(lines):
        if lines[i].strip():
            parts = _split_gdf_line(lines[i])
            u, v = parts[0].strip().strip("'"), parts[1].strip().strip("'")
            weight = float(parts[3]) if len(parts) > 3 else 1.0
            G.add_edge(u, v, weight=weight)
        i += 1

    return G


def load_graph_file(path: Path) -> nx.DiGraph:
    if path.suffix.lower() == ".gexf":
        G = nx.read_gexf(path)
        return G if G.is_directed() else nx.DiGraph(G)
    return _read_gdf(path)


def _sort_communities(values) -> list:
    """Ordena ids de comunidad numéricamente cuando lo son ('2' antes que '10')."""
    return sorted(values, key=lambda c: (0, int(c)) if str(c).isdigit() else (1, str(c)))


def _graph_stats(G: nx.DiGraph, communities: dict) -> dict:
    """Densidad, reciprocidad y modularidad (si hay comunidades) del grafo cargado."""
    stats = {"density": round(nx.density(G), 5)}
    try:
        stats["reciprocity"] = round(nx.overall_reciprocity(G), 4)
    except Exception:
        stats["reciprocity"] = None
    try:
        groups: dict[str, set] = {}
        for n, c in communities.items():
            groups.setdefault(c if c is not None else "_none", set()).add(n)
        stats["modularity"] = round(
            nx.community.modularity(_sum_undirected(G), list(groups.values()), weight="weight"), 4)
    except Exception:
        stats["modularity"] = None
    return stats


def graph_view_data(project_dir: Path, graph_filename: str, max_labels_per_community: int = 10,
                    min_community_pct: float = 2.0, log=print):
    """Prepara los datos de un fichero de grafo (gdf/gexf) para el visor interactivo.

    Requiere que el grafo tenga comunidades calculadas (atributo 'community' no vacío).
    Colorea por comunidad (solo las que superan min_community_pct% de los nodos; el resto
    se agrupan como 'Otros'), con tamaño de nodo según weight indegree y grosor de arista
    según weight (ambos en escala log). Lleva etiqueta fija el 5% de nodos con mayor
    weight indegree de cada comunidad (limitado a max_labels_per_community).

    Devuelve (view_data, communities_shown), donde view_data es un dict serializable a
    JSON con nodos (posición inicial aleatoria; el layout lo calcula el navegador),
    aristas, leyenda de comunidades y estadísticas del grafo.
    """
    import random

    import matplotlib.pyplot as plt
    from matplotlib.colors import to_hex

    path = project_dir / graph_filename
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")

    G = load_graph_file(path)
    n_nodes = G.number_of_nodes()
    if n_nodes == 0:
        raise ValueError(f"{graph_filename} no contiene ningún nodo.")

    # En los .gexf los atributos llegan tipados (community puede ser int); se normaliza
    # a str para que la comunidad 0 no cuente como "sin comunidad" y ordenar no mezcle tipos.
    communities = {}
    for n in G.nodes():
        c = G.nodes[n].get("community")
        communities[n] = str(c) if c is not None and str(c).strip() != "" else None
    if not any(c for c in communities.values()):
        raise ValueError("El grafo no tiene comunidades calculadas. Genera el grafo con 'Include communities' activado.")

    counts = pd.Series(communities).value_counts()
    threshold = n_nodes * (min_community_pct / 100.0)
    kept_communities = set(counts[counts > threshold].index) - {None, ""}
    log(f"Comunidades mostradas (>{min_community_pct}% de nodos): {len(kept_communities)} de {len(counts)}")

    node_list = list(G.nodes())
    node_community = {n: communities[n] if communities[n] in kept_communities else "Otros" for n in node_list}

    indegree = dict(G.in_degree(weight="weight"))
    labeled = set()
    for community in kept_communities:
        members = [n for n in node_list if node_community[n] == community]
        members.sort(key=lambda n: indegree.get(n, 0), reverse=True)
        top_n = max(1, min(max_labels_per_community, round(len(members) * 0.05)))
        labeled.update(members[:top_n])

    # tab20 alterna tono oscuro/claro del mismo color en índices consecutivos (0 y 1 son
    # ambos azules); con tab10 los colores entre comunidades distintas se distinguen bien.
    sorted_communities = _sort_communities(kept_communities)
    palette = plt.get_cmap("tab10" if len(sorted_communities) <= 10 else "tab20")
    community_color = {c: palette(i % palette.N) for i, c in enumerate(sorted_communities)}
    community_color["Otros"] = (0.7, 0.7, 0.7, 1.0)
    # Las aristas van del color de la comunidad del nodo origen (como "Edge color > Source"
    # en Gephi) aclarado hacia blanco, en vez de jugar con transparencias en WebGL.
    edge_color = {c: to_hex(tuple(0.45 * v + 0.55 for v in rgba[:3])) for c, rgba in community_color.items()}

    max_indegree = max(indegree.values()) if indegree else 0
    log_max = math.log1p(max_indegree) if max_indegree > 0 else 1.0
    size_ratio = {n: math.log1p(indegree.get(n, 0)) / log_max for n in node_list}

    # Posiciones iniciales aleatorias reproducibles; ForceAtlas2 corre en el navegador.
    rng = random.Random(42)
    nodes = [
        {
            "key": str(n),
            "x": rng.uniform(-500, 500),
            "y": rng.uniform(-500, 500),
            "size": round(2.5 + 15 * size_ratio[n], 2),
            "color": to_hex(community_color[node_community[n]]),
            "label": str(n),
            "forceLabel": n in labeled,
            "comm": node_community[n],
            "indeg": int(indegree.get(n, 0)),
            "attrs": {
                k: str(G.nodes[n][k])
                for k in _TOOLTIP_ATTRS
                if str(G.nodes[n].get(k, "")).strip() not in ("", "None", "nan")
            },
        }
        for n in node_list
    ]

    edge_weights = {(u, v): (G[u][v].get("weight", 1.0) or 1.0) for u, v in G.edges()}
    w_lo, w_hi = (min(edge_weights.values()), max(edge_weights.values())) if edge_weights else (1.0, 1.0)
    log_lo, log_hi = math.log1p(w_lo), math.log1p(w_hi)

    def edge_size(w):
        if log_hi <= log_lo:
            return 0.5
        return round(0.3 + 2.2 * (math.log1p(w) - log_lo) / (log_hi - log_lo), 2)

    edges = [
        {
            "source": str(u),
            "target": str(v),
            "size": edge_size(w),
            "color": edge_color[node_community[u]],
            "weight": w,
        }
        for (u, v), w in edge_weights.items()
    ]

    # Leyenda: comunidades ordenadas por tamaño, con 'Otros' al final si existe
    comm_counts = pd.Series(list(node_community.values())).value_counts()
    legend = []
    for c in sorted_communities:
        n = int(comm_counts.get(c, 0))
        legend.append({"id": c, "color": to_hex(community_color[c]),
                       "count": n, "pct": round(n / n_nodes * 100, 1)})
    n_otros = int(comm_counts.get("Otros", 0))
    if n_otros:
        legend.append({"id": "Otros", "color": to_hex(community_color["Otros"]),
                       "count": n_otros, "pct": round(n_otros / n_nodes * 100, 1)})

    view_data = {
        "nodes": nodes,
        "edges": edges,
        "communities": legend,
        "stats": _graph_stats(G, communities),
        "maxIndeg": int(max_indegree),
    }
    return view_data, sorted_communities


# ─────────────────────────────────────────────────────────────────────────────
# Visor interactivo: sigma.js (render WebGL) + graphology (grafo y ForceAtlas2
# calculado en el navegador, la misma arquitectura que Retina).
#
# El layout corre en tandas pequeñas dentro de requestAnimationFrame: el grafo se
# ve desplegarse en vivo (como en Gephi) y la página nunca se congela, aunque el
# grafo tenga cientos de miles de nodos. Incluye leyenda de comunidades clicable,
# resaltado de vecinos al pasar el ratón/click, buscador de usuario, panel de
# nodo con enlace al perfil, filtro por grado mínimo, Noverlap, export PNG y
# export GEXF con posiciones y colores (para seguir en Gephi).
#
# Las librerías se cargan de CDN salvo que exista vendor/ junto a este fichero
# (ver render_graph_html), en cuyo caso se incrustan y el visor funciona offline.
# ─────────────────────────────────────────────────────────────────────────────

_VENDOR_FILES = ["graphology.umd.min.js", "graphology-library.min.js", "sigma.min.js"]
_CDN_URLS = [
    "https://cdn.jsdelivr.net/npm/graphology@0.25.4/dist/graphology.umd.min.js",
    "https://cdn.jsdelivr.net/npm/graphology-library@0.8.0/dist/graphology-library.min.js",
    "https://cdn.jsdelivr.net/npm/sigma@2.4.0/build/sigma.min.js",
]

_GRAPH_VIEWER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; height: 100%; font-family: sans-serif; }
  #sigma-container { width: 100%; height: 100%; background: white; }
  .box {
    position: absolute; z-index: 10; font-size: 12px;
    background: rgba(255,255,255,0.93); border: 1px solid #ddd; border-radius: 4px;
  }
  #controls {
    top: 8px; left: 8px; padding: 6px 8px; display: flex; gap: 8px;
    align-items: center; flex-wrap: wrap; max-width: 62%;
  }
  #controls input[type="number"] { width: 52px; }
  #controls input[type="search"] { width: 130px; }
  #controls button { padding: 3px 9px; border: 1px solid #bbb; border-radius: 4px;
    background: #fff; cursor: pointer; font-size: 12px; }
  #controls button.primary { font-weight: bold; }
  #toolbar { top: 8px; right: 8px; padding: 4px; display: flex; gap: 6px; }
  #toolbar button { padding: 4px 10px; border: 1px solid #ccc; border-radius: 4px;
    background: rgba(255,255,255,0.9); cursor: pointer; font-size: 13px; }
  #status {
    position: absolute; bottom: 8px; left: 8px; z-index: 10;
    font-size: 11px; color: #666; background: rgba(255,255,255,0.85); padding: 2px 6px;
  }
  #legend { bottom: 30px; left: 8px; padding: 6px 8px; max-height: 45%; overflow-y: auto; }
  #legend .item { display: flex; align-items: center; gap: 6px; cursor: pointer;
    padding: 1px 2px; user-select: none; }
  #legend .item.off { opacity: 0.35; text-decoration: line-through; }
  #legend .sw { width: 11px; height: 11px; border-radius: 2px; flex: none; }
  #panel {
    top: 50px; right: 8px; width: 250px; padding: 9px 11px; display: none;
    box-shadow: 0 1px 5px rgba(0,0,0,0.2);
  }
  #panel h3 { margin: 0 0 4px; font-size: 14px; }
  #panel table { border-collapse: collapse; margin-top: 4px; }
  #panel td { padding: 1px 6px 1px 0; color: #444; font-size: 12px; }
  #panel td:first-child { color: #888; }
  #panel a { color: #1d6fd6; }
  #panel .close { float: right; cursor: pointer; color: #999; font-size: 15px; }
  #tooltip {
    position: absolute; z-index: 20; display: none; pointer-events: none;
    background: rgba(255,255,255,0.96); border: 1px solid #bbb; border-radius: 4px;
    padding: 6px 9px; font-size: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.25);
    max-width: 280px;
  }
  #tooltip b { font-size: 13px; }
  #tooltip table { border-collapse: collapse; margin-top: 3px; }
  #tooltip td { padding: 0 6px 0 0; color: #444; }
  #tooltip td:first-child { color: #888; }
</style>
</head>
<body>
<div id="sigma-container"></div>
<div id="controls" class="box">
  <button id="c-run" class="primary">&#9654; Layout</button>
  <span>Iter <input type="number" id="c-iter" min="10" step="100"></span>
  <span>Scaling <input type="number" id="c-scaling" value="10" min="1" step="1"></span>
  <span>Gravity <input type="number" id="c-gravity" value="1" min="0" step="0.1"></span>
  <label><input type="checkbox" id="c-linlog"> LinLog</label>
  <label><input type="checkbox" id="c-dissuade"> Disuadir hubs</label>
  <button id="c-noverlap" title="Despega nodos solapados">Noverlap</button>
  <span>Grado &ge; <input type="number" id="c-mindeg" value="0" min="0" step="1"
    title="Oculta nodos con weight indegree menor"></span>
  <input type="search" id="c-search" list="node-options" placeholder="Buscar usuario...">
  <datalist id="node-options"></datalist>
</div>
<div id="toolbar" class="box">
  <button id="save-png">PNG</button>
  <button id="save-gexf" title="GEXF con posiciones y colores, para abrir en Gephi">GEXF</button>
</div>
<div id="legend" class="box"></div>
<div id="panel" class="box"></div>
<div id="status">Cargando...</div>
<div id="tooltip"></div>
__LIB_TAGS__
<script>
const DATA = __DATA__;
const ATTR_ORDER = __ATTR_ORDER__;
const Graph = graphology.Graph || graphology;
const graph = new Graph({ type: "directed" });
DATA.nodes.forEach(n => graph.addNode(n.key, n));
DATA.edges.forEach(e => {
  if (graph.hasNode(e.source) && graph.hasNode(e.target) && !graph.hasEdge(e.source, e.target)) {
    graph.addEdge(e.source, e.target, e);
  }
});

const $ = id => document.getElementById(id);
const statusEl = $("status");
const fa2 = graphologyLibrary.layoutForceAtlas2;
$("c-iter").value = DATA.iterations;

// ── Estado de filtros y resaltado ────────────────────────────────────────────
const hiddenComms = new Set();
let minDeg = 0;
let hoveredNode = null, hoveredNeighbors = null;
let selectedNode = null, selectedNeighbors = null;

function nodeVisible(key, attrs) {
  return !hiddenComms.has(attrs.comm) && (attrs.indeg || 0) >= minDeg;
}

function neighborsOf(node) {
  const s = new Set();
  graph.forEachNeighbor(node, n => s.add(n));
  return s;
}

// ── Renderer con reducers (filtros + resaltado de vecindario) ───────────────
const renderer = new Sigma(graph, $("sigma-container"), {
  defaultEdgeType: "arrow",
  labelRenderedSizeThreshold: 8,
  labelDensity: 1,
  labelFont: "sans-serif",
  nodeReducer(node, data) {
    const res = Object.assign({}, data);
    if (!nodeVisible(node, data)) { res.hidden = true; return res; }
    const focus = selectedNode || hoveredNode;
    if (focus) {
      const nbrs = selectedNode ? selectedNeighbors : hoveredNeighbors;
      if (node === focus) {
        res.highlighted = true; res.zIndex = 2;
      } else if (!nbrs || !nbrs.has(node)) {
        res.color = "#e5e5e5"; res.label = null; res.forceLabel = false; res.zIndex = 0;
      } else {
        res.zIndex = 1;
      }
    }
    return res;
  },
  edgeReducer(edge, data) {
    const res = Object.assign({}, data);
    const s = graph.source(edge), t = graph.target(edge);
    if (!nodeVisible(s, graph.getNodeAttributes(s)) ||
        !nodeVisible(t, graph.getNodeAttributes(t))) { res.hidden = true; return res; }
    const focus = selectedNode || hoveredNode;
    if (focus && s !== focus && t !== focus) res.hidden = true;
    return res;
  },
});

// ── Layout ForceAtlas2 por tandas en requestAnimationFrame ───────────────────
// fa2.assign continúa desde las posiciones actuales, así que ejecutarlo en tandas
// pequeñas anima el layout en vivo sin congelar el navegador (el fallo clásico de
// lanzar todas las iteraciones de golpe en el hilo principal). El tamaño de tanda
// se adapta para que cada frame ronde los 60 ms.
// Parámetros clásicos de Gephi (gravity 1, scaling 10, sin LinLog ni strong
// gravity): el hub de cada comunidad queda centrado en su halo y las comunidades
// bien separadas. barnesHut y slowDown se toman de inferSettings.
const layout = { running: false, done: 0, total: 0, batch: 3, settings: null, raf: null };

function currentSettings() {
  const s = fa2.inferSettings(graph);
  s.linLogMode = $("c-linlog").checked;
  s.outboundAttractionDistribution = $("c-dissuade").checked;
  s.strongGravityMode = false;
  s.gravity = parseFloat($("c-gravity").value) || 1;
  s.scalingRatio = parseFloat($("c-scaling").value) || 10;
  s.edgeWeightInfluence = 1;
  return s;
}

function layoutStep() {
  if (!layout.running) return;
  const n = Math.min(layout.batch, layout.total - layout.done);
  const t0 = performance.now();
  fa2.assign(graph, { iterations: n, settings: layout.settings, getEdgeWeight: "weight" });
  const dt = performance.now() - t0;
  layout.done += n;
  if (dt < 30 && layout.batch < 50) layout.batch = Math.min(50, layout.batch * 2);
  else if (dt > 120 && layout.batch > 1) layout.batch = Math.max(1, Math.floor(layout.batch / 2));
  statusEl.textContent = baseStatus() + " — layout " + layout.done + "/" + layout.total;
  if (layout.done >= layout.total) { stopLayout(); return; }
  layout.raf = requestAnimationFrame(layoutStep);
}

function startLayout() {
  if (layout.running) return;
  layout.settings = currentSettings();
  layout.total = parseInt($("c-iter").value, 10) || 300;
  layout.done = 0;
  layout.running = true;
  $("c-run").innerHTML = "&#9646;&#9646; Parar";
  layout.raf = requestAnimationFrame(layoutStep);
}

function stopLayout() {
  layout.running = false;
  if (layout.raf) cancelAnimationFrame(layout.raf);
  $("c-run").innerHTML = "&#9654; Layout";
  statusEl.textContent = baseStatus() + " — layout detenido en " + layout.done + " iter";
}

$("c-run").addEventListener("click", () => layout.running ? stopLayout() : startLayout());

$("c-noverlap").addEventListener("click", () => {
  if (layout.running) stopLayout();
  const nl = graphologyLibrary.layoutNoverlap;
  nl.assign(graph, { maxIterations: 120, settings: nl.inferSettings ? nl.inferSettings(graph) : {} });
  statusEl.textContent = baseStatus() + " — noverlap aplicado";
});

function baseStatus() {
  const st = DATA.stats || {};
  let extra = [];
  if (st.density != null) extra.push("densidad " + st.density);
  if (st.reciprocity != null) extra.push("reciprocidad " + st.reciprocity);
  if (st.modularity != null) extra.push("modularidad " + st.modularity);
  return graph.order + " nodos, " + graph.size + " aristas" + (extra.length ? " · " + extra.join(" · ") : "");
}

// ── Leyenda de comunidades (click para ocultar/mostrar) ──────────────────────
const legendEl = $("legend");
(DATA.communities || []).forEach(c => {
  const item = document.createElement("div");
  item.className = "item";
  item.innerHTML = '<span class="sw" style="background:' + c.color + '"></span>' +
    "<span>" + escHtml(c.id) + " &middot; " + c.pct + "% (" + c.count + ")</span>";
  item.addEventListener("click", () => {
    if (hiddenComms.has(c.id)) { hiddenComms.delete(c.id); item.classList.remove("off"); }
    else { hiddenComms.add(c.id); item.classList.add("off"); }
    renderer.refresh();
  });
  legendEl.appendChild(item);
});

// ── Filtro por grado mínimo ──────────────────────────────────────────────────
$("c-mindeg").max = DATA.maxIndeg || 0;
$("c-mindeg").addEventListener("change", () => {
  minDeg = parseInt($("c-mindeg").value, 10) || 0;
  renderer.refresh();
});

// ── Buscador de usuario ──────────────────────────────────────────────────────
const datalist = $("node-options");
graph.nodes()
  .sort((a, b) => (graph.getNodeAttribute(b, "indeg") || 0) - (graph.getNodeAttribute(a, "indeg") || 0))
  .slice(0, 2000)
  .forEach(n => {
    const o = document.createElement("option");
    o.value = n;
    datalist.appendChild(o);
  });
$("c-search").addEventListener("change", e => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) return;
  const node = graph.hasNode(q) ? q : graph.findNode(n => n.toLowerCase() === q);
  if (!node) { statusEl.textContent = baseStatus() + ' — no existe "' + q + '"'; return; }
  selectNode(node);
  const pos = renderer.getNodeDisplayData(node);
  if (pos) renderer.getCamera().animate({ x: pos.x, y: pos.y, ratio: 0.08 }, { duration: 500 });
});

// ── Panel de nodo (click) ────────────────────────────────────────────────────
const panel = $("panel");
function selectNode(node) {
  selectedNode = node;
  selectedNeighbors = neighborsOf(node);
  const a = graph.getNodeAttributes(node);
  let html = '<span class="close" id="panel-close">&#10005;</span>' +
    "<h3>" + escHtml(a.label) + "</h3>" +
    '<div><a href="https://x.com/' + encodeURIComponent(a.label) + '" target="_blank" rel="noopener">Ver perfil en X &#8599;</a></div>' +
    "<table>" +
    "<tr><td>comunidad</td><td><span class='sw' style='display:inline-block;width:9px;height:9px;background:" +
      a.color + "'></span> " + escHtml(a.comm) + "</td></tr>" +
    "<tr><td>weight indegree</td><td>" + (a.indeg || 0) + "</td></tr>" +
    "<tr><td>conexiones</td><td>" + graph.inDegree(node) + " entrantes / " + graph.outDegree(node) + " salientes</td></tr>";
  const attrs = a.attrs || {};
  ATTR_ORDER.filter(k => k in attrs).forEach(k => {
    html += "<tr><td>" + escHtml(k) + "</td><td>" + escHtml(attrs[k]) + "</td></tr>";
  });
  html += "</table>";
  panel.innerHTML = html;
  panel.style.display = "block";
  $("panel-close").addEventListener("click", deselectNode);
  renderer.refresh();
}
function deselectNode() {
  selectedNode = null; selectedNeighbors = null;
  panel.style.display = "none";
  renderer.refresh();
}
renderer.on("clickNode", ({ node }) => selectNode(node));
renderer.on("clickStage", deselectNode);

// ── Tooltip al pasar el ratón ────────────────────────────────────────────────
const tooltip = $("tooltip");
const container = $("sigma-container");
let mouse = { x: 0, y: 0 };
container.addEventListener("mousemove", e => {
  mouse = { x: e.clientX, y: e.clientY };
  if (tooltip.style.display === "block") placeTooltip();
});
function placeTooltip() {
  const pad = 14;
  let x = mouse.x + pad, y = mouse.y + pad;
  const r = tooltip.getBoundingClientRect();
  if (x + r.width > window.innerWidth - 4) x = mouse.x - r.width - pad;
  if (y + r.height > window.innerHeight - 4) y = mouse.y - r.height - pad;
  tooltip.style.left = x + "px";
  tooltip.style.top = y + "px";
}
function escHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;");
}
renderer.on("enterNode", ({ node }) => {
  hoveredNode = node;
  hoveredNeighbors = neighborsOf(node);
  const a = graph.getNodeAttributes(node);
  let html = "<b>" + escHtml(a.label) + "</b>";
  const attrs = a.attrs || {};
  const rows = ATTR_ORDER.filter(k => k in attrs)
    .map(k => "<tr><td>" + escHtml(k) + "</td><td>" + escHtml(attrs[k]) + "</td></tr>");
  if (rows.length) html += "<table>" + rows.join("") + "</table>";
  tooltip.innerHTML = html;
  tooltip.style.display = "block";
  placeTooltip();
  renderer.refresh();
});
renderer.on("leaveNode", () => {
  hoveredNode = null; hoveredNeighbors = null;
  tooltip.style.display = "none";
  renderer.refresh();
});

// ── Export PNG (canvas 2D a alta resolución, con leyenda) ────────────────────
$("save-png").addEventListener("click", () => {
  const W = 2400, margin = 100;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  graph.forEachNode((n, a) => {
    if (!nodeVisible(n, a)) return;
    minX = Math.min(minX, a.x); maxX = Math.max(maxX, a.x);
    minY = Math.min(minY, a.y); maxY = Math.max(maxY, a.y);
  });
  if (minX === Infinity) return;
  const spanX = maxX - minX || 1, spanY = maxY - minY || 1;
  const scale = (W - 2 * margin) / Math.max(spanX, spanY);
  const H = Math.round(spanY * scale + 2 * margin);
  // El eje Y se invierte: en sigma crece hacia arriba, en canvas hacia abajo.
  const px = x => margin + (x - minX) * scale;
  const py = y => H - margin - (y - minY) * scale;

  const canvas = document.createElement("canvas");
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, W, H);

  ctx.globalAlpha = 0.5;
  graph.forEachEdge((e, attrs, s, t, sa, ta) => {
    if (!nodeVisible(s, sa) || !nodeVisible(t, ta)) return;
    ctx.strokeStyle = attrs.color;
    ctx.lineWidth = (attrs.size || 0.5) * 1.2;
    ctx.beginPath();
    ctx.moveTo(px(sa.x), py(sa.y));
    ctx.lineTo(px(ta.x), py(ta.y));
    ctx.stroke();
  });
  ctx.globalAlpha = 1;
  // Se dibujan primero los nodos GRANDES y encima los pequeños: en orden de
  // inserción del grafo un hub podía quedar tapado por decenas de nodos
  // pequeños insertados después, distorsionando qué se ve como "más importante".
  const nodesBySize = [];
  graph.forEachNode((n, a) => { if (nodeVisible(n, a)) nodesBySize.push([n, a]); });
  nodesBySize.sort((x, y) => (y[1].size || 0) - (x[1].size || 0));
  nodesBySize.forEach(([n, a]) => {
    ctx.fillStyle = a.color;
    ctx.beginPath();
    ctx.arc(px(a.x), py(a.y), (a.size || 0.5) * 1.6, 0, 2 * Math.PI);
    ctx.fill();
  });
  graph.forEachNode((n, a) => {
    if (!a.forceLabel || !nodeVisible(n, a)) return;
    const fontSize = 18 + a.size * 1.6;
    ctx.font = "bold " + fontSize + "px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 4;
    ctx.strokeStyle = "white";
    ctx.strokeText(a.label, px(a.x), py(a.y) - a.size * 1.6 - fontSize / 2);
    ctx.fillStyle = "black";
    ctx.fillText(a.label, px(a.x), py(a.y) - a.size * 1.6 - fontSize / 2);
  });

  // Leyenda de comunidades visibles
  const legend = (DATA.communities || []).filter(c => !hiddenComms.has(c.id));
  if (legend.length) {
    const lh = 34, boxW = 460, boxH = legend.length * lh + 24;
    const bx = 20, by = H - boxH - 20;
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.fillRect(bx, by, boxW, boxH);
    ctx.strokeStyle = "#cccccc"; ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, boxW, boxH);
    ctx.font = "24px sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    legend.forEach((c, i) => {
      const y = by + 22 + i * lh;
      ctx.fillStyle = c.color;
      ctx.fillRect(bx + 14, y - 10, 20, 20);
      ctx.fillStyle = "black";
      ctx.fillText(c.id + " \\u00b7 " + c.pct + "%", bx + 46, y);
    });
  }

  canvas.toBlob(blob => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = DATA.pngName + ".png";
    link.click();
    URL.revokeObjectURL(link.href);
  });
});

// ── Export GEXF con posiciones y colores (para continuar en Gephi) ───────────
function escXml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}
function hexToRgb(hex) {
  const h = hex.replace("#", "");
  return [parseInt(h.substr(0, 2), 16), parseInt(h.substr(2, 2), 16), parseInt(h.substr(4, 2), 16)];
}
$("save-gexf").addEventListener("click", () => {
  const parts = ['<?xml version="1.0" encoding="UTF-8"?>',
    '<gexf xmlns="http://www.gexf.net/1.3" xmlns:viz="http://www.gexf.net/1.3/viz" version="1.3">',
    '<graph defaultedgetype="directed">',
    '<attributes class="node">',
    '<attribute id="0" title="community" type="string"/>',
    '<attribute id="1" title="weight_indegree" type="integer"/>',
    '</attributes>', '<nodes>'];
  graph.forEachNode((n, a) => {
    if (!nodeVisible(n, a)) return;
    const [r, g, b] = hexToRgb(a.color);
    parts.push('<node id="' + escXml(n) + '" label="' + escXml(a.label) + '">' +
      '<attvalues><attvalue for="0" value="' + escXml(a.comm) + '"/>' +
      '<attvalue for="1" value="' + (a.indeg || 0) + '"/></attvalues>' +
      '<viz:position x="' + a.x.toFixed(2) + '" y="' + a.y.toFixed(2) + '" z="0"/>' +
      '<viz:size value="' + a.size + '"/>' +
      '<viz:color r="' + r + '" g="' + g + '" b="' + b + '"/></node>');
  });
  parts.push("</nodes>", "<edges>");
  let eid = 0;
  graph.forEachEdge((e, attrs, s, t, sa, ta) => {
    if (!nodeVisible(s, sa) || !nodeVisible(t, ta)) return;
    parts.push('<edge id="' + (eid++) + '" source="' + escXml(s) + '" target="' + escXml(t) +
      '" weight="' + (attrs.weight || 1) + '"/>');
  });
  parts.push("</edges>", "</graph>", "</gexf>");
  const blob = new Blob([parts.join("\\n")], { type: "application/xml" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = DATA.pngName + ".gexf";
  link.click();
  URL.revokeObjectURL(link.href);
});

// ── Arranque ─────────────────────────────────────────────────────────────────
statusEl.textContent = baseStatus();
startLayout();
</script>
</body>
</html>
"""


def _lib_tags() -> str:
    """Tags <script> de las librerías JS: incrustadas desde vendor/ si existen
    (funciona offline) o desde CDN en su defecto."""
    vendor = Path(__file__).parent / "vendor"
    files = [vendor / name for name in _VENDOR_FILES]
    if all(f.exists() for f in files):
        # solo hay que neutralizar la secuencia exacta '</script' (cerraría el tag);
        # escapar cualquier '</' corrompe el código JS fuera de literales de cadena
        return "\n".join(
            "<script>\n"
            + f.read_text(encoding="utf-8").replace("</script", "<\\/script").replace("</SCRIPT", "<\\/SCRIPT")
            + "\n</script>"
            for f in files
        )
    return "\n".join(f'<script src="{url}"></script>' for url in _CDN_URLS)


def render_graph_html(view_data: dict, iterations: int, png_name: str) -> str:
    """Genera el HTML autocontenido del visor interactivo para st.components.v1.html."""
    import json

    payload = dict(view_data)
    payload["iterations"] = iterations
    payload["pngName"] = png_name
    # '<\\/' evita que un '</script>' dentro de los datos rompa el bloque <script>
    data_js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = _GRAPH_VIEWER_TEMPLATE.replace("__LIB_TAGS__", _lib_tags())
    html = html.replace("__DATA__", data_js)
    return html.replace("__ATTR_ORDER__", json.dumps(_TOOLTIP_ATTRS))
