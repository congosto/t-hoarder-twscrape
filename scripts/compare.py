"""Comparador de datasets (HTML autocontenido).

Compara dos o más datasets del mismo proyecto (p. ej. una descarga Latest frente
a una Top): métricas por dataset, tweets compartidos por todos (solape por id de
tweet) y una línea temporal de tweets por unidad de tiempo (hora/día/semana/mes),
con un color por dataset. Genera un único HTML sin dependencias externas, del mismo
estilo que el dashboard, y se muestra igual (set_result_report).

Caché: se regenera si alguno de los CSV de origen o este propio módulo son más
nuevos que el HTML, o con force=True."""
import hashlib
import html as html_lib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# columnas de id: se leen como texto para no perder dígitos (los ids de X son
# enteros de 19 cifras que pandas convertiría a float y redondearía)
_ID_COLS = [
    "id", "user_id", "conversation_id_str",
    "in_reply_to_tweet_id_str", "in_reply_to_user_id_str",
]

# un color por dataset (mismo orden en la tabla, el solape y la línea temporal)
_PALETTE = [
    "#1d4ed8", "#dc2626", "#059669", "#d97706",
    "#7c3aed", "#0891b2", "#db2777", "#65a30d",
]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return pd.Series(0, index=df.index, dtype=int)


def _load(csv_path: Path) -> pd.DataFrame:
    dtype = {c: str for c in _ID_COLS}
    df = pd.read_csv(csv_path, encoding="utf-8", dtype=dtype)
    df["_dt"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    return df.dropna(subset=["_dt"])


def _dataset_stats(name: str, df: pd.DataFrame, color: str):
    """Devuelve (meta, id_set, buckets_horarios) de un dataset ya cargado."""
    dt = df["_dt"]
    ids = set()
    if "id" in df.columns:
        ids = set(df["id"].dropna().astype(str))
        ids.discard("")
        ids.discard("nan")
    # buckets horarios: base mínima para reagrupar por hora/día/semana/mes en el
    # navegador (todas las unidades pedidas son >= hora)
    counts = dt.dt.strftime("%Y-%m-%dT%H").value_counts().sort_index()
    meta = {
        "name": name,
        "color": color,
        "ini": dt.min().strftime("%Y-%m-%d %H:%M"),
        "fin": dt.max().strftime("%Y-%m-%d %H:%M"),
        "tweets": int(len(df)),
        "views": int(_num(df, "views_count").sum()),
        "rts": int(_num(df, "retweet_count").sum()),
        "replies": int(_num(df, "reply_count").sum()),
        "quotes": int(_num(df, "quote_count").sum()),
        "unique": len(ids),
    }
    buckets = [[k, int(v)] for k, v in counts.items()]
    return meta, ids, buckets


def _build_payload(project_dir: Path, datasets: list[str], title: str) -> dict:
    metas, id_sets, series = [], [], []
    for i, name in enumerate(datasets):
        csv_path = project_dir / f"{name}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"{name}.csv does not exist in the active project.")
        df = _load(csv_path)
        if df.empty:
            raise ValueError(f"'{name}' has no rows with a valid 'date' column.")
        color = _PALETTE[i % len(_PALETTE)]
        meta, ids, buckets = _dataset_stats(name, df, color)
        metas.append(meta)
        id_sets.append(ids)
        series.append({"name": name, "color": color, "buckets": buckets})

    # solape: tweets (por id) presentes en TODOS los datasets
    shared = set.intersection(*id_sets) if id_sets else set()
    union = set.union(*id_sets) if id_sets else set()
    shared_n = len(shared)
    pct = [round(shared_n / m["unique"] * 100, 1) if m["unique"] else 0.0 for m in metas]
    return {
        "meta": {
            "title": title,
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "datasets": metas,
            "shared": {"count": shared_n, "pct": pct, "union": len(union)},
        },
        "series": series,
    }


def _render_html(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (
        _TEMPLATE
        .replace("__TITLE__", html_lib.escape(payload["meta"]["title"]))
        .replace("__GENERATED__", html_lib.escape(payload["meta"]["generatedAt"]))
        .replace("__DATA_JSON__", data_json)
    )


def _output_path(project_dir: Path, datasets: list[str]) -> Path:
    """Nombre determinista a partir de los datasets (para que la caché funcione);
    si sale muy largo, se recorta y se le añade un hash corto."""
    key = "-".join(datasets)
    if len(key) > 60:
        key = key[:52] + "_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return project_dir / f"cmp_{key}.html"


def generate_comparison(project_dir, datasets: list[str], title: str | None = None,
                        log=print, force: bool = False):
    """Genera (o reutiliza) el HTML de comparación de >= 2 datasets del proyecto.
    Devuelve (html, path)."""
    project_dir = Path(project_dir)
    if len(datasets) < 2:
        raise ValueError("select at least 2 datasets to compare.")
    csv_paths = [project_dir / f"{d}.csv" for d in datasets]
    for path, name in zip(csv_paths, datasets):
        if not path.exists():
            raise FileNotFoundError(f"{name}.csv does not exist in the active project.")

    html_path = _output_path(project_dir, datasets)
    newest_src = max(p.stat().st_mtime for p in csv_paths)
    code_mtime = Path(__file__).stat().st_mtime
    if (html_path.exists() and not force
            and html_path.stat().st_mtime >= newest_src
            and html_path.stat().st_mtime >= code_mtime):
        log(f"Comparison up to date, reusing {html_path.name}")
        return html_path.read_text(encoding="utf-8"), html_path

    log(f"Comparing {len(datasets)} datasets...")
    payload = _build_payload(project_dir, datasets, title or " vs ".join(datasets))
    html = _render_html(payload)
    html_path.write_text(html, encoding="utf-8")
    log(f"Comparison saved to {html_path.name}")
    return html, html_path


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparison · __TITLE__</title>
<style>
  :root{
    --bg:#f8fafc; --panel:#fff; --border:#e2e8f0; --text:#0f172a; --muted:#475569;
    --accent:#1d4ed8; --accent-soft:#dbeafe; --shadow:0 10px 30px rgba(15,23,42,.07);
  }
  *{box-sizing:border-box;}
  body{margin:0;font-family:Inter,"Segoe UI",Arial,sans-serif;color:var(--text);background:var(--bg);}
  .shell{max-width:1440px;margin:0 auto;padding:20px;}
  .hero{padding:18px 22px;border:1px solid var(--border);border-radius:16px;background:var(--panel);box-shadow:var(--shadow);margin-bottom:16px;}
  .hero h1{margin:0 0 4px;font-size:24px;}
  .hero .sub{color:var(--muted);font-size:13px;}
  .panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;box-shadow:var(--shadow);padding:14px;margin-bottom:16px;overflow:hidden;}
  .panel h2{margin:0 0 10px;font-size:16px;}
  .panel .status{color:var(--muted);font-size:12px;margin-bottom:8px;}
  .control label{display:block;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px;}
  .control select{padding:8px 10px;border:1px solid var(--border);border-radius:9px;background:#fff;color:var(--text);font:inherit;min-width:160px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th{text-align:left;color:var(--muted);background:#f8fafc;font-size:10px;letter-spacing:.05em;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid var(--border);}
  td{padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:middle;}
  td.num{text-align:right;font-variant-numeric:tabular-nums;}
  tr:last-child td{border-bottom:none;}
  .table-wrap{overflow-x:auto;}
  .sw{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:7px;vertical-align:middle;}
  .shared .big{font-size:34px;font-weight:800;line-height:1.05;}
  .shared .sub{color:var(--muted);font-size:13px;margin-top:4px;}
  .legend{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:10px;}
  .lg{font-size:13px;color:var(--text);}
  .empty{padding:22px;color:var(--muted);text-align:center;border:1px dashed var(--border);border-radius:12px;background:#fcfdff;}
</style>
</head>
<body>
<main class="shell">
  <section class="hero">
    <h1>__TITLE__</h1>
    <div class="sub">Dataset comparison · generated __GENERATED__</div>
  </section>

  <section class="panel">
    <h2>Per dataset</h2>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Dataset</th><th>From</th><th>To</th><th>Tweets</th>
          <th>Views</th><th>RTs</th><th>Replies</th><th>Quotes</th>
        </tr></thead>
        <tbody id="summaryBody"></tbody>
      </table>
    </div>
  </section>

  <section class="panel shared">
    <h2>Shared tweets</h2>
    <div id="sharedBox"></div>
  </section>

  <section class="panel">
    <h2>Timeline</h2>
    <div class="control" style="margin-bottom:12px">
      <label for="unit">Time unit</label>
      <select id="unit">
        <option value="hour">Hour</option>
        <option value="day" selected>Day</option>
        <option value="week">Week</option>
        <option value="month">Month</option>
      </select>
    </div>
    <div class="legend" id="tlLegend"></div>
    <div id="tlChart"></div>
  </section>
</main>

<script id="cmp-data" type="application/json">__DATA_JSON__</script>
<script>
const DATA = JSON.parse(document.getElementById('cmp-data').textContent);
const META = DATA.meta;
const $ = id => document.getElementById(id);
function fmt(n){ return new Intl.NumberFormat('en-US').format(n||0); }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
function emptyBox(msg){ return '<div class="empty">'+esc(msg)+'</div>'; }

function renderSummary(){
  const ds=META.datasets;
  $('summaryBody').innerHTML=ds.map(d=>'<tr>'
    +'<td><span class="sw" style="background:'+d.color+'"></span>'+esc(d.name)+'</td>'
    +'<td>'+esc(d.ini)+'</td><td>'+esc(d.fin)+'</td>'
    +'<td class="num">'+fmt(d.tweets)+'</td>'
    +'<td class="num">'+fmt(d.views)+'</td>'
    +'<td class="num">'+fmt(d.rts)+'</td>'
    +'<td class="num">'+fmt(d.replies)+'</td>'
    +'<td class="num">'+fmt(d.quotes)+'</td>'
    +'</tr>').join('');
  const sh=META.shared;
  const parts=ds.map((d,i)=>esc(d.name)+' '+sh.pct[i]+'%');
  $('sharedBox').innerHTML='<div class="big">'+fmt(sh.count)+'</div>'
    +'<div class="sub">tweets present in all '+ds.length+' datasets · '+fmt(sh.union)+' unique across the union</div>'
    +'<div class="sub">share of each dataset (by unique tweet id): '+parts.join(' · ')+'</div>';
}

// reagrupa los buckets horarios de cada dataset a la unidad elegida
function bucketKey(hourKey, unit){
  if(unit==='hour') return hourKey;            // YYYY-MM-DDTHH
  if(unit==='day')  return hourKey.slice(0,10);
  if(unit==='month')return hourKey.slice(0,7);
  const d=new Date(Date.parse(hourKey.slice(0,10)+'T00:00:00Z')); // week -> lunes (UTC)
  d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));
  return d.toISOString().slice(0,10);
}
function bucketLabel(key, unit){
  if(unit==='hour') return key.slice(5,10)+' '+key.slice(11,13)+'h';
  if(unit==='month')return key;                // YYYY-MM
  return key.slice(5);                          // day / week -> MM-DD
}
function rebucket(unit){
  const domain=new Set();
  const maps=DATA.series.map(s=>{
    const m=new Map();
    for(const [hk,c] of s.buckets){ const k=bucketKey(hk,unit); m.set(k,(m.get(k)||0)+c); domain.add(k); }
    return m;
  });
  return {keys:[...domain].sort(), maps};
}

// unidad por defecto: horas si el rango total abarca menos de una semana, días
// en el resto (mismo criterio que el ritmo del dashboard)
function defaultUnit(){
  let lo=Infinity, hi=-Infinity;
  for(const d of META.datasets){
    const a=Date.parse(d.ini.replace(' ','T')+'Z'), b=Date.parse(d.fin.replace(' ','T')+'Z');
    if(a<lo) lo=a; if(b>hi) hi=b;
  }
  return (hi-lo)/86400000 < 7 ? 'hour' : 'day';
}

function renderTimeline(){
  const unit=$('unit').value, el=$('tlChart');
  const {keys,maps}=rebucket(unit);
  const series=DATA.series.map((s,i)=>({name:s.name,color:s.color,vals:keys.map(k=>maps[i].get(k)||0)}));
  $('tlLegend').innerHTML=series.map(se=>'<span class="lg"><span class="sw" style="background:'+se.color+'"></span>'+esc(se.name)+'</span>').join('');
  if(!keys.length){ el.innerHTML=emptyBox('No data for the timeline.'); return; }
  const maxV=Math.max(1,...series.reduce((a,se)=>a.concat(se.vals),[]));
  const W=Math.max(320,Math.floor(el.clientWidth||760)), H=340;
  const pL=52,pR=16,pT=16,pB=46, iw=W-pL-pR, ih=H-pT-pB, n=keys.length;
  const X=i=> n===1? pL+iw/2 : pL+iw*i/(n-1);
  const Y=v=> pT+ih*(1-v/maxV);
  // etiquetas del eje X: horizontales, repartidas sin solaparse (según el ancho real)
  const labelPx = unit==='hour'?64:(unit==='month'?58:48);
  const maxLabels=Math.max(2,Math.floor(iw/labelPx));
  const idxs=[];
  if(n===1){ idxs.push(0); }
  else { const st=Math.max(1,Math.ceil((n-1)/(maxLabels-1))); for(let i=0;i<n;i+=st) idxs.push(i);
    const last=idxs[idxs.length-1]; if(last!==n-1){ if(n-1-last<st*0.5) idxs[idxs.length-1]=n-1; else idxs.push(n-1); } }
  let xl='';
  for(const i of idxs){ const anc=i===0?'start':(i===n-1?'end':'middle'); xl+='<text x="'+X(i).toFixed(1)+'" y="'+(H-pB+22)+'" font-size="12" text-anchor="'+anc+'" fill="#475569">'+esc(bucketLabel(keys[i],unit))+'</text>'; }
  let s='<svg viewBox="0 0 '+W+' '+H+'" width="'+W+'" height="'+H+'" style="display:block;max-width:100%">';
  s+='<line x1="'+pL+'" y1="'+(pT+ih)+'" x2="'+(W-pR)+'" y2="'+(pT+ih)+'" stroke="#cbd5e1"/>';
  s+='<text x="'+(pL-8)+'" y="'+Y(0).toFixed(1)+'" font-size="11" text-anchor="end" fill="#475569">0</text>';
  s+='<text x="'+(pL-8)+'" y="'+(Y(maxV)+4).toFixed(1)+'" font-size="11" text-anchor="end" fill="#475569">'+fmt(maxV)+'</text>';
  for(const se of series){
    const pts=se.vals.map((v,i)=>X(i).toFixed(1)+','+Y(v).toFixed(1));
    s+='<path d="M '+pts.join(' L ')+'" fill="none" stroke="'+se.color+'" stroke-width="2"/>';
    s+=se.vals.map((v,i)=>'<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(v).toFixed(1)+'" r="2" fill="'+se.color+'"><title>'+esc(se.name+' · '+bucketLabel(keys[i],unit))+': '+fmt(v)+'</title></circle>').join('');
  }
  el.innerHTML=s+xl+'</svg>';
}

renderSummary();
$('unit').value=defaultUnit();
renderTimeline();
$('unit').addEventListener('change',renderTimeline);
let _rz; window.addEventListener('resize',()=>{ clearTimeout(_rz); _rz=setTimeout(renderTimeline,150); });
</script>
</body>
</html>"""
