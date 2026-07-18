"""Dashboard interactivo (HTML autocontenido) para datasets de tweets.

Genera un único HTML sin dependencias externas (SVG/JS vanilla, sin Plotly):
filtros en el navegador que recalculan KPIs, dos gráficas (ritmo temporal y
mapa de calor de top posts) y una tabla de top posts filtrados, con export CSV.

La descarga usa el product y la frecuencia del formulario; este módulo solo
consume el {prefix}.csv resultante. Caché: se regenera si el CSV es más nuevo
que el HTML (o con force=True)."""
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

_TRUE = {"true", "1", "yes", "sí", "si"}


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return pd.Series(0, index=df.index, dtype=int)


def _str(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col in df.columns:
        return df[col].fillna(default).astype(str)
    return pd.Series(default, index=df.index, dtype=object)


def _cap(s: str, n: int = 500) -> str:
    """Recorta textos muy largos (protege el peso del HTML sin afectar a tweets
    normales; la búsqueda sigue cubriendo los primeros n caracteres)."""
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _post_type(df: pd.DataFrame) -> pd.Series:
    """quote si is_quote_status; reply si in_reply_to_tweet_id_str; si no original."""
    ttype = pd.Series("original", index=df.index, dtype=object)
    if "in_reply_to_tweet_id_str" in df.columns:
        s = df["in_reply_to_tweet_id_str"].fillna("").astype(str).str.strip()
        ttype[(s != "") & (s.str.lower() != "nan")] = "reply"
    if "is_quote_status" in df.columns:
        q = df["is_quote_status"].fillna("").astype(str).str.lower().isin(_TRUE)
        ttype[q] = "quote"  # quote tiene prioridad sobre reply
    return ttype


def _build_payload(df: pd.DataFrame, title: str) -> dict:
    df = df.copy()
    df["_dt"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["_dt"])
    if df.empty:
        raise ValueError("No rows with a valid 'date' column to build the dashboard.")

    dt = df["_dt"]
    lang = _str(df, "lang", "und").replace("", "und")

    # codificación columnar (una lista por campo, claves de 1 letra) para no
    # repetir los nombres de campo en cada registro: reduce mucho el peso del
    # HTML embebido, clave para que cargue en móvil. El JS reconstruye los objetos.
    cols = {
        "u": _str(df, "username").tolist(),
        "d": dt.dt.strftime("%Y-%m-%d").tolist(),
        "l": dt.dt.strftime("%Y-%m-%d %H:%M").tolist(),
        "h": dt.dt.hour.astype(int).tolist(),
        "x": [_cap(t) for t in _str(df, "text").tolist()],
        "r": _str(df, "url", "#").tolist(),
        "v": _num(df, "views_count").tolist(),
        "k": _num(df, "like_count").tolist(),
        "t": _num(df, "retweet_count").tolist(),
        "p": _num(df, "reply_count").tolist(),
        "q": _num(df, "quote_count").tolist(),
        "f": _num(df, "followers_count").tolist(),
        "c": _str(df, "created_at").tolist(),
        "g": lang.tolist(),
        "y": _post_type(df).tolist(),
    }
    days = cols["d"]
    languages = sorted({g for g in cols["g"] if str(g).strip()})
    return {
        "cols": cols,
        "meta": {
            "title": title,
            "total": len(days),
            "minDate": min(days),
            "maxDate": max(days),
            "languages": languages,
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
    }


def _render_html(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (
        _TEMPLATE
        .replace("__TITLE__", html_lib.escape(payload["meta"]["title"]))
        .replace("__GENERATED__", html_lib.escape(payload["meta"]["generatedAt"]))
        .replace("__DATA_JSON__", data_json)
    )


def generate_dashboard(project_dir, prefix: str, title: str | None = None,
                       log=print, force: bool = False):
    """Genera (o reutiliza) el dashboard de {prefix}.csv (mismo para datasets
    de search y de users). Devuelve (html, path). Si el HTML existe y es igual
    o más nuevo que el CSV y no se fuerza, lo reutiliza; si el CSV es más nuevo,
    regenera."""
    project_dir = Path(project_dir)
    csv_path = project_dir / f"{prefix}.csv"
    html_path = project_dir / f"{prefix}_dashboard.html"
    if not csv_path.exists():
        raise FileNotFoundError(f"{prefix}.csv does not exist in the active project.")

    # regenera si el CSV o este propio módulo (plantilla/lógica) son más nuevos
    # que el HTML: así los cambios de código se reflejan sin borrar la caché
    code_mtime = Path(__file__).stat().st_mtime
    if (html_path.exists() and not force
            and html_path.stat().st_mtime >= csv_path.stat().st_mtime
            and html_path.stat().st_mtime >= code_mtime):
        log(f"Dashboard up to date, reusing {html_path.name}")
        return html_path.read_text(encoding="utf-8"), html_path

    log(f"Generating dashboard for '{prefix}'...")
    dtype = {c: str for c in _ID_COLS}
    df = pd.read_csv(csv_path, encoding="utf-8", dtype=dtype)
    payload = _build_payload(df, title or prefix)
    html = _render_html(payload)
    html_path.write_text(html, encoding="utf-8")
    log(f"Dashboard saved to {html_path.name} ({payload['meta']['total']} posts)")
    return html, html_path


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard · __TITLE__</title>
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
  .row{display:grid;gap:10px;margin-bottom:14px;}
  .row1{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));}
  .row2{grid-template-columns:repeat(auto-fit,minmax(160px,1fr));}
  .kpis{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);padding:12px 14px;}
  .control label{display:block;color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px;}
  .control input,.control select{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:9px;background:#fff;color:var(--text);font:inherit;}
  .actions{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;}
  .actions button{flex:1;padding:9px 10px;border:1px solid #bfdbfe;border-radius:9px;background:var(--accent-soft);color:var(--accent);font-weight:700;cursor:pointer;}
  .kpi .eyebrow{color:var(--muted);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;}
  .kpi .value{font-size:22px;font-weight:800;line-height:1.1;}
  .charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:16px;}
  .panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;box-shadow:var(--shadow);padding:14px;overflow:hidden;}
  .panel h2{margin:0 0 4px;font-size:16px;}
  .panel .status{color:var(--muted);font-size:12px;margin-bottom:8px;}
  .heat-scroll{max-height:520px;overflow:auto;}
  table{width:100%;border-collapse:collapse;font-size:12px;}
  th{text-align:left;color:var(--muted);background:#f8fafc;font-size:10px;letter-spacing:.05em;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid var(--border);position:sticky;top:0;}
  td{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top;}
  td.num{text-align:right;font-variant-numeric:tabular-nums;}
  tr:last-child td{border-bottom:none;}
  a{color:var(--accent);text-decoration:none;font-weight:600;}
  .table-wrap{max-height:520px;overflow:auto;}
  .empty{padding:22px;color:var(--muted);text-align:center;border:1px dashed var(--border);border-radius:12px;background:#fcfdff;}
  .content-cell{max-width:520px;}
  @media(max-width:1000px){.charts{grid-template-columns:1fr;}}
</style>
</head>
<body>
<main class="shell">
  <section class="hero">
    <h1>__TITLE__</h1>
    <div class="sub">Dashboard · generated __GENERATED__</div>
  </section>

  <section class="row row1">
    <div class="card control"><label for="startDate">Start date</label><input id="startDate" type="date"></div>
    <div class="card control"><label for="endDate">End date</label><input id="endDate" type="date"></div>
    <div class="card control"><label for="postType">Post type</label>
      <select id="postType"><option value="all">All</option><option value="original">Original</option><option value="reply">Reply</option><option value="quote">Quote</option></select></div>
    <div class="card control"><label for="language">Language</label><select id="language"><option value="all">All</option></select></div>
    <div class="card control"><label for="queryText">Search text</label><input id="queryText" type="search" placeholder="word or phrase"></div>
    <div class="card control"><label for="minViews">Min views</label><input id="minViews" type="number" min="0" step="1" value="0"></div>
    <div class="card control"><label for="topN">Top N</label>
      <select id="topN"><option>10</option><option selected>20</option><option>30</option><option>50</option><option>100</option></select></div>
  </section>

  <section class="row row2">
    <div class="card control"><label for="sortBy">Sort by</label>
      <select id="sortBy">
        <option value="views" selected>Views</option>
        <option value="retweets">Retweets</option>
        <option value="replies">Replies</option>
        <option value="quotes">Quotes</option>
        <option value="likes">Likes</option>
        <option value="followers">Followers</option>
        <option value="createdAt">Account created</option>
        <option value="day">Date</option>
      </select></div>
    <div class="card control"><label for="sortDir">Direction</label>
      <select id="sortDir"><option value="desc" selected>Descending</option><option value="asc">Ascending</option></select></div>
    <div class="card control actions"><button id="resetBtn" type="button">Reset filters</button><button id="exportBtn" type="button">Export CSV</button></div>
  </section>

  <section class="row kpis" id="kpiGrid"></section>

  <section class="charts">
    <section class="panel"><h2>Posting rhythm</h2><div class="status" id="rhythmStatus"></div><div id="rhythmChart"></div></section>
    <section class="panel"><h2>Top posts heatmap</h2><div class="status">Per-column normalized (views · RTs · replies · quotes)</div><div class="heat-scroll" id="heatmapChart"></div></section>
  </section>

  <section class="panel">
    <h2>Top filtered posts</h2>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Date</th><th>username</th><th>Content</th><th>views</th><th>Likes</th>
          <th>Retweets</th><th>replies</th><th>quotes</th><th>Language</th><th>Type</th><th>URL</th>
        </tr></thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </section>
</main>

<script id="dashboard-data" type="application/json">__DATA_JSON__</script>
<script>
const DATA = JSON.parse(document.getElementById('dashboard-data').textContent);
const META = DATA.meta, C = DATA.cols;
const POSTS = [];
for(let i=0,n=C.d.length;i<n;i++){
  POSTS.push({username:C.u[i],day:C.d[i],label:C.l[i],hour:C.h[i],text:C.x[i],url:C.r[i],
    views:C.v[i],likes:C.k[i],retweets:C.t[i],replies:C.p[i],quotes:C.q[i],
    followers:C.f[i],createdAt:C.c[i],lang:C.g[i],type:C.y[i]});
}
const $ = id => document.getElementById(id);
let lastFiltered = [];

function fmt(n){ return new Intl.NumberFormat('en-US').format(n||0); }
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
function trunc(s,n){ s=String(s||''); return s.length>n? s.slice(0,n-1)+'…' : s; }
function safeHref(v){ const raw=String(v||'').trim(); if(!raw) return '#'; try{ const u=new URL(raw); return (u.protocol==='http:'||u.protocol==='https:')?u.href:'#'; }catch(e){ return '#'; } }
function emptyBox(msg){ return '<div class="empty">'+esc(msg)+'</div>'; }

function fillLanguages(){ for(const l of META.languages){ const o=document.createElement('option'); o.value=l; o.textContent=l; $('language').appendChild(o); } }

function currentFilters(){
  return {
    startDate:$('startDate').value, endDate:$('endDate').value,
    postType:$('postType').value, language:$('language').value,
    queryText:$('queryText').value.trim().toLowerCase(),
    minViews:Number($('minViews').value||0),
    topN:Number($('topN').value||20),
    sortBy:$('sortBy').value, sortDir:$('sortDir').value,
  };
}

function applyFilters(){
  const f=currentFilters();
  let r=POSTS.filter(p=> p.day>=f.startDate && p.day<=f.endDate);
  if(f.postType!=='all') r=r.filter(p=>p.type===f.postType);
  if(f.language!=='all') r=r.filter(p=>p.lang===f.language);
  if(f.minViews>0) r=r.filter(p=>p.views>=f.minViews);
  if(f.queryText) r=r.filter(p=>(p.text||'').toLowerCase().includes(f.queryText));
  const fac=f.sortDir==='asc'?1:-1;
  r=[...r].sort((a,b)=>{
    let x=a[f.sortBy], y=b[f.sortBy];
    if(f.sortBy==='day'||f.sortBy==='createdAt'){ x=a[f.sortBy]; y=b[f.sortBy]; return String(x).localeCompare(String(y))*fac; }
    return ((x||0)-(y||0))*fac;
  });
  return {f,r};
}

function renderKpis(r){
  const sum=k=>r.reduce((a,p)=>a+(p[k]||0),0);
  let peak='—';
  if(r.length){
    const m=new Map();
    for(const p of r){ const key=p.day+' '+String(p.hour).padStart(2,'0')+':00'; m.set(key,(m.get(key)||0)+1); }
    let best=null; for(const [k,v] of m){ if(!best||v>best.v) best={k,v}; }
    if(best) peak=best.k;
  }
  const cards=[
    ['Total posts', fmt(META.total)],
    ['Posts (filtered)', fmt(r.length)],
    ['Views', fmt(sum('views'))],
    ['Retweets', fmt(sum('retweets'))],
    ['Replies', fmt(sum('replies'))],
    ['Quotes', fmt(sum('quotes'))],
    ['Peak date/hour', peak],
  ];
  $('kpiGrid').innerHTML=cards.map(([t,v])=>`<div class="card kpi"><div class="eyebrow">${esc(t)}</div><div class="value">${esc(v)}</div></div>`).join('');
}

function renderRhythm(r){
  const el=$('rhythmChart');
  if(!r.length){ el.innerHTML=emptyBox('No data for the current filter.'); $('rhythmStatus').textContent=''; return; }
  // ¿por horas o por días? si el rango con datos abarca menos de una semana, por horas
  let minKey=null,maxKey=null;
  for(const p of r){ if(minKey===null||p.day<minKey)minKey=p.day; if(maxKey===null||p.day>maxKey)maxKey=p.day; }
  const spanDays=(Date.parse(maxKey+'T00:00:00Z')-Date.parse(minKey+'T00:00:00Z'))/86400000;
  const byHour = spanDays < 7;
  $('rhythmStatus').textContent = fmt(r.length)+' posts · '+(byHour?'by hour':'by day');
  const m=new Map();
  if(byHour){ for(const p of r){ const k=p.day+'T'+String(p.hour).padStart(2,'0'); m.set(k,(m.get(k)||0)+1); } }
  else { for(const p of r){ m.set(p.day,(m.get(p.day)||0)+1); } }
  const keys=[...m.keys()].sort(); const vals=keys.map(d=>m.get(d));
  // etiquetas del eje X adaptadas a la medida de tiempo del periodo mostrado:
  // años -> %Y, meses -> %b/%Y, días -> %d-%b/%Y, horas -> %d-%Hh/%b
  // (dos líneas cuando hace falta, siempre en horizontal)
  const MON=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Set','Oct','Nov','Dic'];
  const mon=k=>MON[parseInt(k.slice(5,7),10)-1];
  const mode = byHour ? 'hour' : (spanDays<=92 ? 'day' : (spanDays<=731 ? 'month' : 'year'));
  const labelOf=k=>{
    if(mode==='hour') return [k.slice(8,10)+'-'+k.slice(11,13)+'h', mon(k)];
    if(mode==='day')  return [k.slice(8,10)+'-'+mon(k), k.slice(0,4)];
    if(mode==='month')return [mon(k), k.slice(0,4)];
    return [k.slice(0,4), ''];
  };
  const tipOf=k=> byHour ? (k.slice(0,10)+' '+k.slice(11,13)+':00') : k;
  // ancho real en px (sin preserveAspectRatio="none", que deformaba el texto)
  const W=Math.max(320,Math.floor(el.clientWidth||760)), H=300;
  const pL=44,pR=16,pT=30,pB=44, iw=W-pL-pR, ih=H-pT-pB;  // pT alto: aire para el número del pico
  const maxV=Math.max(...vals,1), n=keys.length;
  // eje X proporcional al TIEMPO (no al índice de días con datos): con densidad
  // desigual o huecos, las marcas de mes/año caen donde les toca y no se juntan
  const T=keys.map(k=> Date.parse(byHour ? k+':00:00Z' : k+'T00:00:00Z'));
  const t0=T[0], t1=T[n-1];
  const X=i=> (n===1||t1===t0) ? pL+iw/2 : pL+iw*(T[i]-t0)/(t1-t0);
  const Y=v=> pT+ih*(1-v/maxV);
  const pts=keys.map((d,i)=>X(i).toFixed(1)+','+Y(vals[i]).toFixed(1));
  const area='M '+pL+','+(pT+ih)+' L '+pts.join(' L ')+' L '+X(n-1).toFixed(1)+','+(pT+ih)+' Z';
  const line='M '+pts.join(' L ');
  // etiquetas del eje X: horizontales y repartidas sin solaparse; en modo
  // month/year las marcas caen en el arranque natural de cada mes/año, y en
  // todos los modos se descarta cualquier marca a menos de labelPx px de la
  // anterior (con eje proporcional al tiempo el reparto por índices no basta)
  const labelPx = mode==='hour' ? 56 : (mode==='day' ? 52 : 44);
  const maxLabels = Math.max(2, Math.floor(iw/labelPx));
  let cand=[];
  if(n===1){ cand=[0]; }
  else if(mode==='month'||mode==='year'){
    const cut = mode==='month' ? 7 : 4; let seen=null;
    for(let i=0;i<n;i++){ const g=keys[i].slice(0,cut); if(g!==seen){ cand.push(i); seen=g; } }
    if(cand.length>maxLabels){ const st=Math.ceil(cand.length/maxLabels); cand=cand.filter((_,j)=>j%st===0); }
  }
  else { cand=keys.map((_,i)=>i); }
  const idxs=[]; let lastX=-1e9;
  for(const i of cand){ const xx=X(i); if(xx-lastX>=labelPx){ idxs.push(i); lastX=xx; } }
  if((mode==='hour'||mode==='day') && n>1 && idxs[idxs.length-1]!==n-1
     && X(n-1)-X(idxs[idxs.length-1])>=labelPx*0.55){ idxs.push(n-1); }
  let xl='';
  for(const i of idxs){ const anc= i===0?'start':(i===n-1?'end':'middle'); const L=labelOf(keys[i]);
    xl+='<text x="'+X(i).toFixed(1)+'" y="'+(H-pB+20)+'" font-size="12" text-anchor="'+anc+'" fill="#475569">'+esc(L[0])+'</text>';
    if(L[1]) xl+='<text x="'+X(i).toFixed(1)+'" y="'+(H-pB+34)+'" font-size="11" text-anchor="'+anc+'" fill="#64748b">'+esc(L[1])+'</text>'; }
  const dots=keys.map((d,i)=>'<circle cx="'+X(i).toFixed(1)+'" cy="'+Y(vals[i]).toFixed(1)+'" r="2.5" fill="#1d4ed8"><title>'+esc(tipOf(d))+': '+fmt(vals[i])+'</title></circle>').join('');
  const pk=vals.indexOf(maxV), pkX=X(pk), pkY=Y(maxV);
  const pkAnchor= pk===0?'start' : (pk===n-1?'end':'middle');
  const pkLabelY=Math.max(18,pkY-12);
  const peakLabel='<text x="'+pkX.toFixed(1)+'" y="'+pkLabelY.toFixed(1)+'" font-size="16" font-weight="700" text-anchor="'+pkAnchor+'" fill="#1d4ed8">'+fmt(maxV)+'</text>';
  el.innerHTML='<svg viewBox="0 0 '+W+' '+H+'" width="'+W+'" height="'+H+'" style="display:block;max-width:100%">'
    +'<line x1="'+pL+'" y1="'+(pT+ih)+'" x2="'+(W-pR)+'" y2="'+(pT+ih)+'" stroke="#cbd5e1"/>'
    +'<path d="'+area+'" fill="rgba(29,78,216,.12)"/>'
    +'<path d="'+line+'" fill="none" stroke="#1d4ed8" stroke-width="2"/>'
    +'<text x="'+(pL-8)+'" y="'+(Y(0))+'" font-size="11" text-anchor="end" fill="#475569">0</text>'
    +'<text x="'+(pL-8)+'" y="'+(Y(maxV)+4)+'" font-size="11" text-anchor="end" fill="#475569">'+fmt(maxV)+'</text>'
    +dots+peakLabel+xl+'</svg>';
}

function lerp(t){ const a=[239,246,255],b=[29,78,216]; const c=a.map((v,i)=>Math.round(v+(b[i]-v)*t)); return 'rgb('+c[0]+','+c[1]+','+c[2]+')'; }

function renderHeatmap(r,topN){
  const el=$('heatmapChart'); const top=r.slice(0,topN);
  if(!top.length){ el.innerHTML=emptyBox('No data for the current filter.'); return; }
  const metrics=[['views','Views'],['retweets','RTs'],['replies','Replies'],['quotes','Quotes']];
  const st={}; for(const [k] of metrics){ const vs=top.map(p=>p[k]); st[k]={min:Math.min(...vs),max:Math.max(...vs)}; }
  const labelW=250,colW=88,rowH=24,headH=26;
  const W=labelW+colW*metrics.length, H=headH+rowH*top.length;
  // tamaño explícito en px (evita el bug de altura 0 en móvil); el contenedor
  // .heat-scroll permite scroll horizontal/vertical si no cabe
  let s='<svg viewBox="0 0 '+W+' '+H+'" width="'+W+'" height="'+H+'" style="display:block">';
  metrics.forEach(([k,lab],ci)=>{ s+='<text x="'+(labelW+colW*ci+colW/2)+'" y="'+(headH-9)+'" font-size="11" font-weight="700" text-anchor="middle" fill="#475569">'+esc(lab)+'</text>'; });
  top.forEach((p,ri)=>{
    const yy=headH+rowH*ri;
    const rl=p.username+' · '+p.day;
    s+='<text x="4" y="'+(yy+rowH/2+4)+'" font-size="11" fill="#0f172a">'+esc(trunc(rl,36))+'</text>';
    metrics.forEach(([k],ci)=>{
      const c=st[k], v=p[k], t=c.max>c.min? (v-c.min)/(c.max-c.min):0, xx=labelW+colW*ci;
      s+='<rect x="'+xx+'" y="'+yy+'" width="'+(colW-2)+'" height="'+(rowH-2)+'" fill="'+lerp(t)+'"><title>'+esc(rl)+' — '+esc(k)+': '+fmt(v)+'</title></rect>';
      s+='<text x="'+(xx+colW/2)+'" y="'+(yy+rowH/2+4)+'" font-size="10" text-anchor="middle" fill="'+(t>0.55?'#fff':'#0f172a')+'">'+fmt(v)+'</text>';
    });
  });
  el.innerHTML=s+'</svg>';
}

function renderTable(r,topN){
  const rows=r.slice(0,topN);
  if(!rows.length){ $('tableBody').innerHTML='<tr><td colspan="11">'+emptyBox('No posts for the current filter.')+'</td></tr>'; return; }
  $('tableBody').innerHTML=rows.map(p=>'<tr>'
    +'<td>'+esc(p.label)+'</td>'
    +'<td>'+esc(p.username)+'</td>'
    +'<td class="content-cell">'+esc(trunc(p.text,200))+'</td>'
    +'<td class="num">'+fmt(p.views)+'</td>'
    +'<td class="num">'+fmt(p.likes)+'</td>'
    +'<td class="num">'+fmt(p.retweets)+'</td>'
    +'<td class="num">'+fmt(p.replies)+'</td>'
    +'<td class="num">'+fmt(p.quotes)+'</td>'
    +'<td>'+esc(p.lang)+'</td>'
    +'<td>'+esc(p.type)+'</td>'
    +'<td><a href="'+safeHref(p.url)+'" target="_blank" rel="noopener noreferrer">open</a></td>'
    +'</tr>').join('');
}

function exportCsv(){
  const rows=lastFiltered; if(!rows.length) return;
  const head=['Date','username','Content','views','Likes','Retweets','replies','quotes','Language','Type','URL'];
  const q=v=>{ const s=String(v==null?'':v); return /[",\n]/.test(s)? '"'+s.replace(/"/g,'""')+'"' : s; };
  const lines=[head.join(',')];
  for(const p of rows){ lines.push([p.label,p.username,p.text,p.views,p.likes,p.retweets,p.replies,p.quotes,p.lang,p.type,p.url].map(q).join(',')); }
  const blob=new Blob([lines.join('\n')],{type:'text/csv;charset=utf-8;'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='dashboard_filtered_'+new Date().toISOString().slice(0,10)+'.csv';
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(a.href);
}

function render(){
  const {f,r}=applyFilters(); lastFiltered=r;
  // cada paso aislado: si uno falla (p.ej. render SVG en un navegador móvil),
  // los demás siguen y el error se ve en pantalla en vez de dejar todo vacío
  const step=(fn,el,tag)=>{ try{ fn(); }catch(e){ if(el) el.innerHTML='<div class="empty">'+tag+' error: '+esc(e.message)+'</div>'; } };
  step(()=>renderKpis(r), $('kpiGrid'), 'kpi');
  step(()=>renderRhythm(r), $('rhythmChart'), 'chart');
  step(()=>renderHeatmap(r,f.topN), $('heatmapChart'), 'heatmap');
  step(()=>renderTable(r,f.topN), null, 'table');
}

function reset(){
  $('startDate').value=META.minDate; $('endDate').value=META.maxDate;
  $('postType').value='all'; $('language').value='all'; $('queryText').value='';
  $('minViews').value='0'; $('topN').value='20'; $('sortBy').value='views'; $('sortDir').value='desc';
  render();
}

fillLanguages();
$('startDate').value=META.minDate; $('startDate').min=META.minDate; $('startDate').max=META.maxDate;
$('endDate').value=META.maxDate; $('endDate').min=META.minDate; $('endDate').max=META.maxDate;
['startDate','endDate','postType','language','minViews','topN','sortBy','sortDir'].forEach(id=>$(id).addEventListener('change',render));
$('queryText').addEventListener('input',render);
$('resetBtn').addEventListener('click',reset);
$('exportBtn').addEventListener('click',exportCsv);
// la gráfica de ritmo se dibuja al ancho real del panel: redibujar al redimensionar
let _rz; window.addEventListener('resize',()=>{ clearTimeout(_rz); _rz=setTimeout(render,150); });
render();
</script>
</body>
</html>"""
