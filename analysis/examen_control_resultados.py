"""2026 (en línea) vs Control (presencial): ¿el control se parece a lo normal?

Ahora que el examen de control presencial ya tiene resultados publicados
(ver `src/scrape_control.py`), esta viz compara, por carrera-campus, la
distribución de aciertos del examen EN LÍNEA de 2026 (ya anómala, ver
`comparativa_2026.py`/`base_sin_p75.py`) contra la del examen de CONTROL
presencial — con 2021-2025 de fondo como referencia de "lo normal".

Pregunta que responde: si el examen de control corrigió la anomalía, su
distribución debería parecerse más a 2021-2025 que a 2026. Análisis
descriptivo — no identifica aspirantes ni establece causas.

Fuentes:
    data/consolidated/resultados_todos.csv       (year==2026 y 2021-2025)
    data/consolidated/resultados_control_2026.csv (nueva, ver scrape_control.py)
    data/manifest.csv + data/manifest_control_2026.csv (para canonicalizar
    carrera/campus del examen de control con el mismo criterio que
    consolidate.py ya aplicó a resultados_todos.csv)

Uso:  python analysis/examen_control_resultados.py
Salidas en analysis/output/: examen_control_resultados.html + preview
"""

from __future__ import annotations

import html as _html
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ANALYSIS_DIR))
from src.consolidate import build_canonical_map  # noqa: E402
from examen_control import ACCENT_FIX, CONNECTORS  # noqa: E402

SRC_RESULTADOS = ROOT / "data" / "consolidated" / "resultados_todos.csv"
SRC_CONTROL = ROOT / "data" / "consolidated" / "resultados_control_2026.csv"
MANIFEST = ROOT / "data" / "manifest.csv"
MANIFEST_CONTROL = ROOT / "data" / "manifest_control_2026.csv"
OUT_DIR = ROOT / "analysis" / "output"

MIN_N = 30       # examen de control: ofertas más chicas que el resto de vizs
TOP_K = 15
GRID = np.arange(0, 121, 1.0)
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"          # 2026 en línea (rojo, ya establecido)
CTRL_LIGHT, CTRL_DARK = "#2f6fb0", "#6fa8dc"      # control presencial (azul, nuevo)
HIST_LIGHT, HIST_DARK = "#c3c2b7", "#4a4a46"      # 2021-2025 (gris, contexto)

_TOKEN_RE = re.compile(r"^(\W*)(\w*)(\W*)$", re.UNICODE)


def esc(s) -> str:
    return _html.escape(str(s))


def nice_name(s: str) -> str:
    """Mismo criterio de nombres que examen_control.py (conectores en
    minúsculas + diccionario de acentos), reusado aquí vía import."""
    out = []
    for i, tok in enumerate(str(s).split(" ")):
        m = _TOKEN_RE.match(tok)
        if not m:
            out.append(tok)
            continue
        pre, core, suf = m.groups()
        low = ACCENT_FIX.get(core.lower(), core.lower())
        if low and (i == 0 or low not in CONNECTORS):
            low = low[0].upper() + low[1:]
        out.append(pre + low + suf)
    return " ".join(out)


def gaussian_kde(sample, grid):
    n = sample.size
    std = sample.std(ddof=1) if n > 1 else 1.0
    iqr = np.subtract(*np.percentile(sample, [75, 25]))
    spread = min(std, iqr / 1.349) if iqr > 0 else std
    h = max(0.9 * spread * n ** (-0.2), 2.0)
    u = (grid[:, None] - sample[None, :]) / h
    k = np.exp(-0.5 * u * u) / np.sqrt(2 * np.pi)
    return k.mean(axis=1) / h


def _canonicalize_control(df_control: pd.DataFrame) -> pd.DataFrame:
    """Aplica el MISMO criterio de canonicalización que consolidate.py usa
    para resultados_todos.csv, pero construyendo el mapa con AMBOS
    manifiestos (regular + control) para que los nombres terminen
    idénticos y el join por (carrera, campus, modalidad) sea limpio."""
    man = pd.read_csv(MANIFEST, dtype=str, keep_default_na=False, na_filter=False)
    man_c = pd.read_csv(MANIFEST_CONTROL, dtype=str, keep_default_na=False, na_filter=False)
    maps = {}
    for col in ("carrera", "campus"):
        values = pd.concat([man[col], man_c[col]], ignore_index=True).tolist()
        maps[col] = build_canonical_map(values)
    for col in ("carrera", "campus"):
        df_control[col] = df_control[col].map(lambda v, c=col: maps[c].get(v, v))
    return df_control


def load():
    res = pd.read_csv(SRC_RESULTADOS, dtype=str, keep_default_na=False, na_filter=False)
    res["ac"] = pd.to_numeric(res["aciertos"], errors="coerce")
    res["year"] = res["year"].astype(int)
    pres = res[res["ac"].notna()].copy()
    pres["ac"] = pres["ac"].astype(int)

    ctrl = pd.read_csv(SRC_CONTROL, dtype=str, keep_default_na=False, na_filter=False)
    ctrl["ac"] = pd.to_numeric(ctrl["aciertos"], errors="coerce")
    ctrl = _canonicalize_control(ctrl)
    ctrl_pres = ctrl[ctrl["ac"].notna()].copy()
    ctrl_pres["ac"] = ctrl_pres["ac"].astype(int)

    offers = []
    keys_2026 = pres[pres["year"] == 2026][["carrera", "campus", "modalidad"]].drop_duplicates()
    for _, k in keys_2026.iterrows():
        car, cam, mod = k["carrera"], k["campus"], k["modalidad"]
        sub_online = pres[(pres["carrera"] == car) & (pres["campus"] == cam)
                          & (pres["modalidad"] == mod) & (pres["year"] == 2026)]["ac"].to_numpy()
        sub_ctrl = ctrl_pres[(ctrl_pres["carrera"] == car) & (ctrl_pres["campus"] == cam)
                             & (ctrl_pres["modalidad"] == mod)]["ac"].to_numpy()
        if sub_ctrl.size < MIN_N or sub_online.size < MIN_N:
            continue
        sub_hist = pres[(pres["carrera"] == car) & (pres["campus"] == cam)
                        & (pres["modalidad"] == mod) & (pres["year"] <= 2025)]["ac"].to_numpy()
        med_online = float(np.median(sub_online))
        med_control = float(np.median(sub_ctrl))
        med_hist = float(np.median(sub_hist)) if sub_hist.size >= MIN_N else np.nan
        denom = med_online - med_hist
        frac = (med_online - med_control) / denom if (not np.isnan(denom) and denom > 0) else np.nan
        offers.append({
            "carrera": car, "campus": cam, "modalidad": mod,
            "online": sub_online, "control": sub_ctrl, "hist": sub_hist,
            "n_online": sub_online.size, "n_control": sub_ctrl.size,
            "med_online": med_online, "med_control": med_control, "med_hist": med_hist,
            "frac_correccion": frac,
        })
    offers.sort(key=lambda o: o["n_control"], reverse=True)

    con_hist = [o for o in offers if not np.isnan(o["med_hist"])]
    fracs = np.array([o["frac_correccion"] for o in con_hist
                      if not np.isnan(o["frac_correccion"])])
    summary = {
        "n_ofertas_control": int(ctrl[["carrera", "campus", "modalidad"]].drop_duplicates().shape[0]),
        "n_ofertas_comparables": len(offers),
        "n_con_historico": len(con_hist),
        "total_presentaron_control": int(ctrl_pres.shape[0]),
        "total_aspirantes_control": int(ctrl.shape[0]),
        "d_online_hist": float(np.median([o["med_online"] - o["med_hist"] for o in con_hist])),
        "d_control_hist": float(np.median([o["med_control"] - o["med_hist"] for o in con_hist])),
        "d_online_control": float(np.median([o["med_online"] - o["med_control"] for o in offers])),
        "frac_mediana": float(np.median(fracs)) if fracs.size else float("nan"),
        "n_frac_baja": int((fracs < 0.2).sum()),
        "n_frac_media": int(((fracs >= 0.2) & (fracs < 0.6)).sum()),
        "n_frac_alta": int((fracs >= 0.6).sum()),
    }
    return offers, summary


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #

FW, FH = 300, 132
ML, MR, MT, MB = 8, 8, 6, 20
BASE, TOPy = FH - MB, MT


def xpos(v):
    return ML + min(max(v, 0), 120) / 120 * (FW - ML - MR)


def build_table(offers: list[dict]) -> str:
    head = (
        '<tr>'
        '<th class="c sortable" data-key="carrera">Carrera<span class="arrow">▾</span></th>'
        '<th class="c sortable" data-key="campus">Campus<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="modalidad">Modalidad<span class="arrow">▾</span></th>'
        '<th class="sortable sorted desc" data-key="ncontrol">n control<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="nonline">n en línea<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="medonline">Mediana en línea<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="medcontrol">Mediana control<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="medhist">Mediana histórica<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="diff">Control − histórica<span class="arrow">▾</span></th>'
        '</tr>')
    rows = []
    for o in offers:
        modal = "" if o["modalidad"] == "escolarizado" else f" · {o['modalidad']}"
        hist_txt = f"{o['med_hist']:.0f}" if not np.isnan(o["med_hist"]) else "—"
        hist_sort = o["med_hist"] if not np.isnan(o["med_hist"]) else -1
        if np.isnan(o["med_hist"]):
            diff_txt, diff_sort = "—", -999
        else:
            d = o["med_control"] - o["med_hist"]
            diff_txt, diff_sort = f"{d:+.0f}", d
        rows.append(
            f'<tr data-carrera="{esc(o["carrera"].lower())}" '
            f'data-campus="{esc(o["campus"].lower())}" data-modalidad="{esc(o["modalidad"])}" '
            f'data-ncontrol="{o["n_control"]}" data-nonline="{o["n_online"]}" '
            f'data-medonline="{o["med_online"]}" data-medcontrol="{o["med_control"]}" '
            f'data-medhist="{hist_sort}" data-diff="{diff_sort}">'
            f'<td class="c">{esc(nice_name(o["carrera"]))}</td>'
            f'<td class="c">{esc(nice_name(o["campus"]))}{esc(modal)}</td>'
            f'<td>{esc(o["modalidad"])}</td>'
            f'<td class="hl">{o["n_control"]:,}</td>'
            f'<td>{o["n_online"]:,}</td>'
            f'<td>{o["med_online"]:.0f}</td>'
            f'<td class="hlb">{o["med_control"]:.0f}</td>'
            f'<td>{hist_txt}</td>'
            f'<td>{diff_txt}</td></tr>')
    return (f'<table class="tbl" id="tblResultados"><thead>{head}</thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def facet_svg(o: dict) -> str:
    dens = {}
    if o["hist"].size >= MIN_N:
        dens["hist"] = gaussian_kde(o["hist"], GRID)
    dens["online"] = gaussian_kde(o["online"], GRID)
    dens["control"] = gaussian_kde(o["control"], GRID)
    gmax = max(d.max() for d in dens.values())
    amp = (BASE - TOPy) / gmax

    p = [f'<svg viewBox="0 0 {FW} {FH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    for t, anc in ((0, "start"), (60, "middle"), (120, "end")):
        p.append(f'<text x="{xpos(t):.1f}" y="{BASE+15}" class="tickl" text-anchor="{anc}">{t}</text>')
    p.append(f'<line x1="{ML}" y1="{BASE}" x2="{FW-MR}" y2="{BASE}" class="axis"/>')

    def poly(d):
        return " ".join(f'{xpos(GRID[i]):.1f},{BASE - d[i]*amp:.2f}' for i in range(GRID.size))

    if "hist" in dens:
        p.append(f'<polyline class="yr hist" points="{poly(dens["hist"])}"/>')
    p.append(f'<polygon class="fill-online" points="{ML},{BASE:.1f} '
             f'{poly(dens["online"])} {FW-MR},{BASE:.1f}"/>')
    p.append(f'<polygon class="fill-control" points="{ML},{BASE:.1f} '
             f'{poly(dens["control"])} {FW-MR},{BASE:.1f}"/>')
    p.append(f'<polyline class="yr online" points="{poly(dens["online"])}"/>')
    p.append(f'<polyline class="yr control" points="{poly(dens["control"])}"/>')
    p.append('</svg>')
    return "".join(p)


def facet(o: dict) -> str:
    modal = "" if o["modalidad"] == "escolarizado" else f" · {o['modalidad']}"
    hist_txt = f"{o['med_hist']:.0f}" if not np.isnan(o["med_hist"]) else "—"
    return (f'<figure class="facet">'
            f'<figcaption><span class="ca">{esc(nice_name(o["carrera"]))}</span>'
            f'<span class="cc">{esc(nice_name(o["campus"]))}{esc(modal)}</span></figcaption>'
            f'<div class="badge">mediana: en línea <b class="on">{o["med_online"]:.0f}</b> · '
            f'control <b class="ct">{o["med_control"]:.0f}</b> · histórica {hist_txt}</div>'
            f'{facet_svg(o)}</figure>')


def build_inner(offers: list[dict], summary: dict, top_k: int = TOP_K) -> str:
    top = offers[:top_k]
    table = build_table(offers)
    facets = "".join(facet(o) for o in top)

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --online:{HL_LIGHT}; --control:{CTRL_LIGHT}; --hist:{HIST_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1080px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --online:{HL_DARK}; --control:{CTRL_DARK}; --hist:{HIST_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a;
  --axis:#383835; --border:rgba(255,255,255,.10); --online:{HL_DARK}; --control:{CTRL_DARK}; --hist:{HIST_DARK}; }}
.viz-root h1 {{ font-size:20px; margin:0 0 4px; text-wrap:balance; }}
.viz-root h2 {{ font-size:14px; margin:22px 0 6px; }}
.sub {{ color:var(--text-secondary); font-size:13px; margin:0 0 3px; line-height:1.5; }}
.method {{ color:var(--muted); font-size:12px; margin:0 0 2px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--online); border-radius:8px; padding:10px 12px;
  margin:12px 0; font-size:13.5px; line-height:1.5; }}
.headline b {{ color:var(--online); }} .headline b.c {{ color:var(--control); }}
.disclaimer {{ border:1px dashed var(--border); border-radius:8px; padding:9px 12px;
  margin:10px 0; font-size:12px; color:var(--muted); line-height:1.5; font-style:italic; }}
.legend {{ display:flex; gap:16px; align-items:center; font-size:12px;
  color:var(--text-secondary); margin:10px 0 4px; flex-wrap:wrap; }}
.legend i {{ display:inline-block; width:22px; border-top:2px solid; vertical-align:middle; margin-right:6px; }}
.controls {{ display:flex; gap:10px; align-items:center; margin:14px 0 8px; flex-wrap:wrap; }}
.search {{ flex:1; min-width:200px; padding:7px 11px; border:1px solid var(--border);
  border-radius:7px; background:var(--surface-1); color:var(--text-primary); font-size:13px; }}
.search::placeholder {{ color:var(--muted); }}
.count {{ font-size:12px; color:var(--muted); white-space:nowrap; }}
.tbl-wrap {{ max-height:480px; overflow:auto; border:1px solid var(--border); border-radius:10px; }}
.tbl {{ border-collapse:collapse; width:100%; font-size:11.5px; }}
.tbl th,.tbl td {{ text-align:right; padding:6px 9px; border-bottom:1px solid var(--border);
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tbl th.c,.tbl td.c {{ text-align:left; font-variant-numeric:normal; white-space:normal; }}
.tbl thead th {{ color:var(--text-secondary); font-weight:600; background:var(--surface-1);
  position:sticky; top:0; z-index:1; }}
.tbl th.sortable {{ cursor:pointer; user-select:none; }}
.tbl th.sortable:hover {{ color:var(--online); }}
.tbl th .arrow {{ opacity:.35; font-size:9px; margin-left:3px; display:inline-block; }}
.tbl th.sorted .arrow {{ opacity:1; color:var(--online); }}
.tbl th.sorted.asc .arrow {{ transform:rotate(180deg); }}
.tbl td.hl {{ color:var(--online); font-weight:600; }}
.tbl td.hlb {{ color:var(--control); font-weight:600; }}
.tbl tbody tr:hover {{ background:var(--plane); }}
.grid-f {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:8px; }}
.facet {{ background:var(--surface-1); border:1px solid var(--border); border-radius:10px; padding:8px 8px 2px; }}
.facet figcaption {{ display:flex; flex-direction:column; line-height:1.25; }}
.facet .ca {{ font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.facet .cc {{ font-size:10.5px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.facet .badge {{ font-size:10px; color:var(--muted); font-variant-numeric:tabular-nums; margin:2px 0 0; }}
.facet .badge b.on {{ color:var(--online); }}
.facet .badge b.ct {{ color:var(--control); }}
.axis {{ stroke:var(--axis); stroke-width:1; }}
.tickl {{ fill:var(--muted); font-size:9.5px; font-variant-numeric:tabular-nums; }}
.yr {{ fill:none; stroke-width:1.6; }}
.yr.hist {{ stroke:var(--hist); stroke-width:1.4; stroke-dasharray:3 3; }}
.yr.online {{ stroke:var(--online); stroke-width:2; }}
.yr.control {{ stroke:var(--control); stroke-width:2.2; }}
.fill-online {{ fill:var(--online); fill-opacity:.10; stroke:none; }}
.fill-control {{ fill:var(--control); fill-opacity:.14; stroke:none; }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
@media (max-width:720px) {{ .grid-f {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
</style>"""

    js = """
<script>
(function(){
  var tbl=document.getElementById('tblResultados');
  var tbody=tbl.querySelector('tbody');
  var rows=Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  var countEl=document.getElementById('rowCount2');
  var searchEl=document.getElementById('searchBox2');

  function applyFilter(){
    var q=(searchEl.value||'').toLowerCase().trim();
    var shown=0;
    rows.forEach(function(tr){
      var hit=!q || tr.dataset.carrera.indexOf(q)>-1 || tr.dataset.campus.indexOf(q)>-1
        || tr.dataset.modalidad.toLowerCase().indexOf(q)>-1;
      tr.style.display=hit?'':'none';
      if(hit)shown++;
    });
    countEl.textContent='Mostrando '+shown+' de '+rows.length+' ofertas';
  }
  searchEl.addEventListener('input',applyFilter);
  applyFilter();

  var sortState={key:'ncontrol',dir:-1};
  function sortBy(key,dir){
    var numeric=['ncontrol','nonline','medonline','medcontrol','medhist','diff'];
    rows.sort(function(a,b){
      var av=a.dataset[key],bv=b.dataset[key];
      if(numeric.indexOf(key)>-1){ av=+av; bv=+bv; }
      if(av<bv)return -1*dir; if(av>bv)return 1*dir; return 0;
    });
    rows.forEach(function(tr){tbody.appendChild(tr);});
  }
  tbl.querySelectorAll('th.sortable').forEach(function(th){
    th.addEventListener('click',function(){
      var key=th.dataset.key;
      var dir = (sortState.key===key) ? -sortState.dir : -1;
      sortState={key:key,dir:dir};
      tbl.querySelectorAll('th.sortable').forEach(function(t){t.classList.remove('sorted','asc');});
      th.classList.add('sorted'); if(dir===1)th.classList.add('asc');
      sortBy(key,dir);
    });
  });
})();
</script>"""

    legend = (
        '<div class="legend">'
        '<span><i style="border-color:var(--hist);border-top-style:dashed"></i>2021–2025 (histórico)</span>'
        '<span><i style="border-color:var(--online);border-top-width:3px"></i>'
        '<b style="color:var(--online)">2026 en línea</b></span>'
        '<span><i style="border-color:var(--control);border-top-width:3px"></i>'
        '<b style="color:var(--control)">Control (presencial)</b></span></div>')

    # Ejemplos robustos para el headline: solo ofertas con muestra grande en
    # control (evita que un caso de ~100 aspirantes domine el titular).
    con_hist = [o for o in offers if not np.isnan(o["med_hist"]) and o["n_control"] >= 300]
    o_min = min(con_hist, key=lambda o: o["frac_correccion"])
    o_max = max(con_hist, key=lambda o: o["frac_correccion"])

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT},{CTRL_LIGHT}">
  <h1>2026 en línea vs. Control presencial: medianas por carrera-campus · UNAM</h1>
  <p class="sub">Ahora que el examen de control presencial tiene resultados
  publicados, comparamos su distribución de aciertos contra el <b>examen en
  línea de 2026</b> (ya anómalo) y contra <b>2021–2025</b> (la normalidad de
  referencia), por carrera-campus.</p>
  <p class="method"><b>Método:</b> de las {summary['n_ofertas_control']} ofertas
  con examen de control, {summary['n_ofertas_comparables']} tienen ≥{MIN_N}
  presentados en línea y en control (comparables); {summary['n_con_historico']}
  de ellas también tienen historial 2021–2025 suficiente. La tabla y los
  paneles muestran, para cada una, la mediana de aciertos en línea, en
  control y histórica.</p>
  <div class="disclaimer">Nota: este análisis es una interpretación propia,
  no información oficial de la UNAM ni de la Comisión Técnica. Es
  descriptivo — no identifica aspirantes ni establece causas.</div>
  <div class="headline">
    En las {summary['n_con_historico']} ofertas comparables, la mediana de
    2026 en línea estaba <b>+{summary['d_online_hist']:.0f} puntos</b> sobre
    la mediana histórica; la del control quedó en
    <b class="c">+{summary['d_control_hist']:.0f} puntos</b> sobre la
    histórica. Varía mucho por oferta: en
    {esc(nice_name(o_max["carrera"]))}-{esc(nice_name(o_max["campus"]))} las
    tres medianas fueron {o_max['med_online']:.0f} (en línea),
    <b class="c">{o_max['med_control']:.0f}</b> (control) y
    {o_max['med_hist']:.0f} (histórica); en
    {esc(nice_name(o_min["carrera"]))}-{esc(nice_name(o_min["campus"]))} fueron
    {o_min['med_online']:.0f} (en línea), <b class="c">{o_min['med_control']:.0f}</b>
    (control) y {o_min['med_hist']:.0f} (histórica).
  </div>
  {legend}
  <div class="controls">
    <input id="searchBox2" class="search" type="text"
      placeholder="Buscar carrera, campus o modalidad…">
    <span id="rowCount2" class="count"></span>
  </div>
  <div class="tbl-wrap">{table}</div>
  <h2>Top {top_k} ofertas por tamaño de muestra en el control</h2>
  <div class="grid-f">{facets}</div>
  <p class="note">Fuente: resultados DGAE-UNAM. "En línea" y "2021–2025" de
  `resultados_todos.csv`; "Control" de `resultados_control_2026.csv`
  (`src/scrape_control.py`, examen de control presencial). Solo aspirantes
  con aciertos numérico. Densidad por KDE gaussiano. Análisis descriptivo.</p>
</div>"""


def _standalone(inner: str) -> str:
    return ("<!doctype html><html lang=es><head><meta charset=utf-8>"
            "<title>2026 vs Control</title></head>"
            "<body style='margin:0'>" + inner + "</body></html>")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, summary = load()
    print("resumen:", summary)

    inner = build_inner(offers, summary)
    (OUT_DIR / "examen_control_resultados.html").write_text(inner, encoding="utf-8")
    (OUT_DIR / "_examen_control_resultados_preview.html").write_text(
        _standalone(inner), encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
