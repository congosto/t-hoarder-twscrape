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

# Atributos y orden en que se muestran en el tooltip del visor interactivo
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


def _log10(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0).clip(lower=0).add(1).apply(math.log10)
    return values.round().astype(int)


def _load_relations(project_dir: Path, prefix: str, relation: str) -> pd.DataFrame:
    if relation == "RT":
        path = project_dir / f"{prefix}_RTs.csv"
        if not path.exists():
            raise FileNotFoundError(f"No existe {path}. Descarga primero los Retweets.")
        df = pd.read_csv(path, encoding="utf-8")
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
    df = df[df["source"] != df["target"]]
    return df


def _build_giant_graph(project_dir: Path, prefix: str, relation: str, log=print) -> tuple[nx.DiGraph, pd.DataFrame]:
    """Construye el grafo dirigido de la relación indicada y se queda solo con la
    componente gigante, descartando el resto de nodos."""
    relations_df = _load_relations(project_dir, prefix, relation)
    log(f"Relaciones cargadas: {len(relations_df)}")

    edges = relations_df.groupby(["source", "target"]).size().reset_index(name="weight")

    G = nx.DiGraph()
    for _, row in edges.iterrows():
        G.add_edge(row["source"], row["target"], weight=int(row["weight"]))
    log(f"Grafo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")

    undirected = G.to_undirected()
    giant = max(nx.connected_components(undirected), key=len)
    log(f"Componente gigante: {len(giant)} nodos de {G.number_of_nodes()}")
    G_giant = G.subgraph(giant).copy()

    return G_giant, relations_df


def _node_attributes_table(tweets_df: pd.DataFrame, relations_df: pd.DataFrame) -> pd.DataFrame:
    # "username" en relations_df ya es el autor/origen (= "source"), no hace falta renombrar.
    from_tweets = tweets_df[[c for c in _AUTHOR_COLUMNS if c in tweets_df.columns]].copy()
    from_relations = relations_df[[c for c in _AUTHOR_COLUMNS if c in relations_df.columns]].copy()

    combined = pd.concat([from_tweets, from_relations], ignore_index=True)
    combined = combined.dropna(subset=["username"]).drop_duplicates(subset="username", keep="first")
    return combined.set_index("username")


def detect_communities(project_dir: Path, prefix: str, relation: str, log=print) -> tuple[Path, Path]:
    """Crea el grafo de la relación, se queda con la componente gigante, calcula el grado
    con pesos y la modularidad (Louvain/Blondel). Como el algoritmo de Louvain da resultados
    distintos cada vez que se invoca, las comunidades se calculan y persisten aquí, y el resto
    de pasos (generar grafo, clasificar tweets) las reutilizan desde estos ficheros.

    Devuelve (communities_file, users_communities_file).
    """
    G_giant, _ = _build_giant_graph(project_dir, prefix, relation, log=log)

    indegree = dict(G_giant.in_degree(weight="weight"))
    outdegree = dict(G_giant.out_degree(weight="weight"))

    communities = nx.community.louvain_communities(G_giant.to_undirected(), weight="weight")
    log(f"Comunidades encontradas: {len(communities)}")
    community_of = {node: str(i) for i, comm in enumerate(communities) for node in comm}

    total = G_giant.number_of_nodes()
    counts = pd.Series(community_of).value_counts()
    communities_table = pd.DataFrame({
        "community": counts.index,
        "pct_nodes": (counts.values / total * 100).round(2),
    }).sort_values("pct_nodes", ascending=False)
    communities_file = project_dir / f"{prefix}_{relation}_communities.csv"
    communities_table.to_csv(communities_file, index=False, encoding="utf-8")

    users_table = pd.DataFrame({"user": list(G_giant.nodes())})
    users_table["community"] = users_table["user"].map(community_of)
    users_table["weight_indegree"] = users_table["user"].map(indegree).fillna(0).astype(int)
    users_table["weight_outdegree"] = users_table["user"].map(outdegree).fillna(0).astype(int)
    users_table = users_table.sort_values("weight_indegree", ascending=False)
    users_file = project_dir / f"{prefix}_users_{relation}_communities.csv"
    users_table.to_csv(users_file, index=False, encoding="utf-8")

    log(f"Tabla de comunidades en {communities_file}")
    log(f"Tabla de usuarios/comunidad en {users_file}")
    return communities_file, users_file


def generate_graph(project_dir: Path, prefix: str, relation: str, output_format: str = "gdf",
                    include_communities: bool = True, include_locations: bool = False,
                    log=print) -> Path:
    """Genera el fichero de grafo (gdf/gexf) de la relación indicada con los atributos de nodo.

    include_communities: añade 'community' desde {prefix}_users_{relation}_communities.csv
    (generado antes con 'Detect communities'; falla si no existe).
    include_locations: añade location_country/region/city desde {prefix}_loc.csv
    (generado antes en Tools > Localización; falla si no existe).
    Devuelve la ruta del fichero de grafo generado.
    """
    G_giant, relations_df = _build_giant_graph(project_dir, prefix, relation, log=log)

    tweets_file = project_dir / f"{prefix}.csv"
    if not tweets_file.exists():
        raise FileNotFoundError(f"No existe {tweets_file}")
    tweets_df = pd.read_csv(tweets_file, encoding="utf-8")

    node_attrs = _node_attributes_table(tweets_df, relations_df)
    node_attrs = node_attrs.reindex(list(G_giant.nodes()))
    node_attrs["log_followers_count"] = _log10(node_attrs["followers_count"])
    node_attrs["log_friends_count"] = _log10(node_attrs["friends_count"])
    node_attrs["log_statuses_count"] = _log10(node_attrs["statuses_count"])
    node_attrs["log_favourites_count"] = _log10(node_attrs["favourites_count"])
    node_attrs["log_listed_count"] = _log10(node_attrs["listed_count"])
    node_attrs["create_at_year"] = pd.to_datetime(node_attrs["created_at"], errors="coerce", utc=True).dt.year

    if include_communities:
        users_file = project_dir / f"{prefix}_users_{relation}_communities.csv"
        if not users_file.exists():
            raise FileNotFoundError(f"No existe {users_file}. Ejecuta antes 'Detect communities'.")
        users_df = pd.read_csv(users_file, encoding="utf-8").set_index("user")
        node_attrs["community"] = node_attrs.index.map(users_df["community"].to_dict())
    else:
        node_attrs["community"] = None

    if include_locations:
        loc_file = project_dir / f"{prefix}_loc.csv"
        if not loc_file.exists():
            raise FileNotFoundError(f"No existe {loc_file}. Genéralo antes en Tools > Localización.")
        loc_df = pd.read_csv(loc_file, encoding="utf-8").set_index("username")
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
    tweets_df["community"] = tweets_df["username"].map(community_map)

    classified_file = project_dir / f"{prefix}_{relation}_classified.csv"
    tweets_df.to_csv(classified_file, index=False, encoding="utf-8")
    n_classified = int(tweets_df["community"].notna().sum())
    log(f"Tweets clasificados: {n_classified}/{len(tweets_df)} ({n_classified / len(tweets_df) * 100:.1f}%)")
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
                G.nodes[node][col] = "" if pd.isna(value) else _to_native(value)
    nx.write_gexf(G, path)


def _gdf_value(value, col_type: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if col_type == "VARCHAR":
        return "'" + str(value).replace("'", "") + "'"
    if col_type == "BOOLEAN":
        return "true" if value else "false"
    if col_type == "INT":
        return str(int(value))
    return str(value)


def _export_gdf(G: nx.DiGraph, node_attrs: pd.DataFrame, path: Path) -> None:
    node_header = "nodedef>name VARCHAR," + ",".join(f"{c} {_NODE_ATTR_TYPES[c]}" for c in _NODE_ATTR_COLUMNS)
    edge_header = "edgedef>node1 VARCHAR,node2 VARCHAR,directed BOOLEAN,weight DOUBLE"

    with open(path, "w", encoding="utf-8") as f:
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
        values = lines[i].split(",")
        name = values[0].strip().strip("'")
        attrs = {col: val.strip().strip("'") for col, val in zip(node_cols[1:], values[1:])}
        G.add_node(name, **attrs)
        i += 1

    i += 1  # salta la línea edgedef>
    while i < len(lines):
        if lines[i].strip():
            parts = lines[i].split(",")
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


def graph_view_data(project_dir: Path, graph_filename: str, max_labels_per_community: int = 10,
                     log=print):
    """Prepara los datos de un fichero de grafo (gdf/gexf) para el visor interactivo.

    Requiere que el grafo tenga comunidades calculadas (atributo 'community' no vacío).
    Colorea por comunidad (solo las que superan el 2% de los nodos; el resto se agrupan
    como 'Otros'), con tamaño de nodo según weight indegree y grosor de arista según
    weight (ambos en escala log: en grafos de RTs un par de hubs acaparan casi todo y con
    escala lineal el resto sale al tamaño mínimo). Lleva etiqueta fija el 5% de nodos con
    mayor weight indegree de cada comunidad (limitado a max_labels_per_community).

    Devuelve (view_data, communities_shown), donde view_data es un dict serializable a
    JSON con los nodos (posición inicial aleatoria; el layout lo calcula el navegador)
    y las aristas.
    """
    import random

    import matplotlib.pyplot as plt
    from matplotlib.colors import to_hex

    path = project_dir / graph_filename
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")

    G = load_graph_file(path)
    n_nodes = G.number_of_nodes()

    communities = {n: G.nodes[n].get("community") for n in G.nodes()}
    if not any(c for c in communities.values()):
        raise ValueError("El grafo no tiene comunidades calculadas. Genera el grafo con 'Include communities' activado.")

    counts = pd.Series(communities).value_counts()
    threshold = n_nodes * 0.02
    kept_communities = set(counts[counts > threshold].index) - {None, ""}
    log(f"Comunidades mostradas (>2% de nodos): {len(kept_communities)} de {len(counts)}")

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
    sorted_communities = sorted(kept_communities)
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

    view_data = {"nodes": nodes, "edges": edges}
    return view_data, sorted(kept_communities)


# Visor interactivo: sigma.js (render WebGL) + graphology (grafo y ForceAtlas2 LinLog
# calculado en el navegador, la misma arquitectura que Retina). Las librerías se cargan
# de CDN, así que ver un grafo requiere conexión a internet.
_GRAPH_VIEWER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; height: 100%; font-family: sans-serif; }
  #sigma-container { width: 100%; height: 100%; background: white; }
  #toolbar { position: absolute; top: 8px; right: 8px; z-index: 10; }
  #toolbar button {
    padding: 4px 10px; border: 1px solid #ccc; border-radius: 4px;
    background: rgba(255,255,255,0.9); cursor: pointer; font-size: 13px;
  }
  #status {
    position: absolute; bottom: 8px; left: 8px; z-index: 10;
    font-size: 11px; color: #888; background: rgba(255,255,255,0.8); padding: 2px 6px;
  }
  #controls {
    position: absolute; top: 8px; left: 8px; z-index: 10;
    font-size: 12px; background: rgba(255,255,255,0.92); border: 1px solid #ddd;
    border-radius: 4px; padding: 6px 8px; display: flex; gap: 8px; align-items: center;
    flex-wrap: wrap; max-width: 70%;
  }
  #controls input[type="number"] { width: 52px; }
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
<div id="controls">
  <span>Scaling <input type="number" id="c-scaling" value="10" min="1" step="1"></span>
  <span>Gravity <input type="number" id="c-gravity" value="1" min="0" step="0.1"></span>
  <label><input type="checkbox" id="c-linlog"> LinLog</label>
  <label><input type="checkbox" id="c-dissuade"> Disuadir hubs</label>
  <span>Iter <input type="number" id="c-iter" min="10" step="100"></span>
  <button id="c-run">Recalcular</button>
</div>
<div id="toolbar"><button id="save-png">Descargar PNG</button></div>
<div id="status">Calculando layout...</div>
<div id="tooltip"></div>
<script src="https://cdn.jsdelivr.net/npm/graphology@0.25.4/dist/graphology.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/graphology-library@0.8.0/dist/graphology-library.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/sigma@2.4.0/build/sigma.min.js"></script>
<script>
const DATA = __DATA__;
const Graph = graphology.Graph || graphology;
const graph = new Graph({ multi: true, type: "directed" });
DATA.nodes.forEach(n => graph.addNode(n.key, n));
DATA.edges.forEach(e => {
  if (graph.hasNode(e.source) && graph.hasNode(e.target)) {
    graph.addEdge(e.source, e.target, e);
  }
});

// Layout ForceAtlas2 con los parámetros clásicos de Gephi (gravity 1, scaling 10, sin
// LinLog ni strong gravity): con ellos el hub de cada comunidad queda centrado en su halo
// y las comunidades bien separadas (probado sobre data/prueba/panas_RT.gdf; con LinLog o
// con la strong gravity que infiere graphology el grafo colapsa en una bola). barnesHut y
// slowDown sí se toman de inferSettings, que los ajusta al tamaño del grafo.
const fa2 = graphologyLibrary.layoutForceAtlas2;
document.getElementById("c-iter").value = DATA.iterations;

function runLayout() {
  const settings = fa2.inferSettings(graph);
  settings.linLogMode = document.getElementById("c-linlog").checked;
  settings.outboundAttractionDistribution = document.getElementById("c-dissuade").checked;
  settings.strongGravityMode = false;
  settings.gravity = parseFloat(document.getElementById("c-gravity").value) || 1;
  settings.scalingRatio = parseFloat(document.getElementById("c-scaling").value) || 10;
  settings.edgeWeightInfluence = 1;
  const iterations = parseInt(document.getElementById("c-iter").value, 10) || 300;
  const t0 = performance.now();
  fa2.assign(graph, { iterations: iterations, settings: settings, getEdgeWeight: "weight" });
  const secs = ((performance.now() - t0) / 1000).toFixed(1);
  document.getElementById("status").textContent =
    graph.order + " nodos, " + graph.size + " aristas — layout " + iterations + " iteraciones en " + secs + " s";
}
runLayout();

const renderer = new Sigma(graph, document.getElementById("sigma-container"), {
  defaultEdgeType: "arrow",
  labelRenderedSizeThreshold: 8,
  labelDensity: 1,
  labelFont: "sans-serif",
});

// Recalcular continúa desde las posiciones actuales (como darle otra vez a Run en Gephi)
document.getElementById("c-run").addEventListener("click", () => {
  document.getElementById("status").textContent = "Calculando layout...";
  setTimeout(() => { runLayout(); renderer.refresh(); }, 30);
});

// Tooltip con los metadatos del usuario al pasar el ratón por un nodo
const ATTR_ORDER = __ATTR_ORDER__;
const tooltip = document.getElementById("tooltip");
const container = document.getElementById("sigma-container");
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
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
renderer.on("enterNode", ({ node }) => {
  const a = graph.getNodeAttributes(node);
  let html = "<b>" + esc(a.label) + "</b>";
  const attrs = a.attrs || {};
  const rows = ATTR_ORDER.filter(k => k in attrs)
    .map(k => "<tr><td>" + esc(k) + "</td><td>" + esc(attrs[k]) + "</td></tr>");
  if (rows.length) html += "<table>" + rows.join("") + "</table>";
  tooltip.innerHTML = html;
  tooltip.style.display = "block";
  placeTooltip();
});
renderer.on("leaveNode", () => { tooltip.style.display = "none"; });

// Exporta la vista a PNG dibujando el grafo en un canvas 2D a alta resolución
// (los canvas WebGL de sigma no se pueden volcar directamente).
document.getElementById("save-png").addEventListener("click", () => {
  const W = 2400, margin = 100;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  graph.forEachNode((n, a) => {
    minX = Math.min(minX, a.x); maxX = Math.max(maxX, a.x);
    minY = Math.min(minY, a.y); maxY = Math.max(maxY, a.y);
  });
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
    ctx.strokeStyle = attrs.color;
    ctx.lineWidth = attrs.size * 1.2;
    ctx.beginPath();
    ctx.moveTo(px(sa.x), py(sa.y));
    ctx.lineTo(px(ta.x), py(ta.y));
    ctx.stroke();
  });
  ctx.globalAlpha = 1;
  graph.forEachNode((n, a) => {
    ctx.fillStyle = a.color;
    ctx.beginPath();
    ctx.arc(px(a.x), py(a.y), a.size * 1.6, 0, 2 * Math.PI);
    ctx.fill();
  });
  graph.forEachNode((n, a) => {
    if (!a.forceLabel) return;
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

  canvas.toBlob(blob => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = DATA.pngName + ".png";
    link.click();
    URL.revokeObjectURL(link.href);
  });
});
</script>
</body>
</html>
"""


def render_graph_html(view_data: dict, iterations: int, png_name: str) -> str:
    """Genera el HTML autocontenido del visor interactivo para st.components.v1.html."""
    import json

    payload = dict(view_data)
    payload["iterations"] = iterations
    payload["pngName"] = png_name
    # '<\\/' evita que un '</script>' dentro de los datos rompa el bloque <script>
    data_js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = _GRAPH_VIEWER_TEMPLATE.replace("__DATA__", data_js)
    return html.replace("__ATTR_ORDER__", json.dumps(_TOOLTIP_ATTRS))
