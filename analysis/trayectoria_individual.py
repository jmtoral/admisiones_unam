"""Trayectoria individual: la misma persona, 2026 en línea vs. control.

Todos los análisis anteriores de esta serie comparan DISTRIBUCIONES agregadas
por oferta (misma forma, distinta gente). Este es distinto: el número de
comprobante es el MISMO en `resultados_todos.csv` (2026) y en
`resultados_control_2026.csv` — verificado en vivo, 99.58% de quienes
presentaron el control (36,719 de 36,875) tienen comprobante que aparece en
el registro de 2026 de la misma oferta. Eso permite parear a cada persona
consigo misma: sus aciertos en línea vs. sus aciertos en control.

Privacidad: además de las vistas agregadas (mapa de calor, histograma,
medianas por oferta) se muestra un scatter a nivel de punto — un punto por
persona, incluida la sección de "quién pasó cada mínimo" por oferta — pero
NUNCA con el número de comprobante ni otro identificador junto al punto.
Ver CLAUDE.md, "No difundas datos a nivel de aspirante individual fuera del
uso agregado", y la nota de la sección de puntos.

Hallazgo: 95.4% de las personas pareadas sacó MENOS aciertos en el control
que en línea (mediana -30); casi universal por oferta (la enorme mayoría
con mediana negativa; las pocas excepciones positivas son ofertas con
muestra muy chica). Análisis descriptivo.

Uso:  python analysis/trayectoria_individual.py
Salidas en analysis/output/: trayectoria_individual.html/.png/_dark.png + .csv
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
from examen_control_resultados import _canonicalize_control  # noqa: E402
from examen_control import ACCENT_FIX, CONNECTORS  # noqa: E402

SRC_RESULTADOS = ROOT / "data" / "consolidated" / "resultados_todos.csv"
SRC_CONTROL = ROOT / "data" / "consolidated" / "resultados_control_2026.csv"
META_2026 = ROOT / "data" / "consolidated" / "metadata_carreras.csv"
META_CONTROL = ROOT / "data" / "consolidated" / "metadata_control_2026.csv"
OUT_DIR = ROOT / "analysis" / "output"

MIN_N = 1
CTRL_LIGHT, CTRL_DARK = "#2f6fb0", "#6fa8dc"
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"
CATBOTH_LIGHT, CATBOTH_DARK = "#2e8b57", "#4ade80"
_TOKEN_RE = re.compile(r"^(\W*)(\w*)(\W*)$", re.UNICODE)

# Categorías de pase/no-pase según el mínimo OFICIAL de cada examen
# (aciertos_minimos publicado, no la convocatoria estimada de examen_control.py).
CAT_AMBOS, CAT_SOLO_CTRL, CAT_SOLO_26, CAT_NINGUNO = 0, 1, 2, 3
CAT_LABELS = ["Pasó en ambos escenarios", "No pasó en línea, pero sí en control",
              "Pasó en línea, pero no en control", "No pasó en ningún escenario"]


def esc(s) -> str:
    return _html.escape(str(s))


def nice_name(s: str) -> str:
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


def load():
    res = pd.read_csv(SRC_RESULTADOS, dtype=str, keep_default_na=False, na_filter=False)
    res["ac"] = pd.to_numeric(res["aciertos"], errors="coerce")
    res["year"] = res["year"].astype(int)
    r26 = res[(res["year"] == 2026) & res["ac"].notna()].copy()
    r26["ac"] = r26["ac"].astype(int)

    ctrl = pd.read_csv(SRC_CONTROL, dtype=str, keep_default_na=False, na_filter=False)
    ctrl["ac"] = pd.to_numeric(ctrl["aciertos"], errors="coerce")
    ctrlp = ctrl[ctrl["ac"].notna()].copy()
    ctrlp["ac"] = ctrlp["ac"].astype(int)
    ctrlp = _canonicalize_control(ctrlp)
    n_ctrl_total = len(ctrlp)

    merged = ctrlp.merge(
        r26[["carrera", "campus", "modalidad", "numero_comprobante", "ac"]],
        on=["carrera", "campus", "modalidad", "numero_comprobante"],
        suffixes=("_ctrl", "_26"), how="inner",
    )
    merged["delta"] = merged["ac_ctrl"] - merged["ac_26"]

    n = len(merged)
    match_rate = n / n_ctrl_total * 100 if n_ctrl_total else 0.0
    deltas = merged["delta"].to_numpy()
    summary = {
        "n_ctrl_total": n_ctrl_total,
        "n_matched": n,
        "match_rate": match_rate,
        "median_delta": float(np.median(deltas)),
        "mean_delta": float(np.mean(deltas)),
        "pct_baja": float((deltas < 0).mean() * 100),
        "pct_igual": float((deltas == 0).mean() * 100),
        "pct_sube": float((deltas > 0).mean() * 100),
    }

    by_oferta = []
    for (car, cam, mod), sub in merged.groupby(["carrera", "campus", "modalidad"]):
        if len(sub) < MIN_N:
            continue
        d = sub["delta"].to_numpy()
        by_oferta.append({
            "carrera": car, "campus": cam, "modalidad": mod,
            "n": len(sub), "median_delta": float(np.median(d)),
            "pct_baja": float((d < 0).mean() * 100),
        })
    by_oferta.sort(key=lambda o: o["median_delta"])

    # Mínimos OFICIALES publicados (aciertos_minimos), uno por examen — no la
    # convocatoria estimada de examen_control.py. Se usan para clasificar a
    # cada persona pareada en pasó/no pasó, por examen.
    m26 = pd.read_csv(META_2026, dtype=str, keep_default_na=False, na_filter=False)
    m26["year"] = m26["year"].astype(int)
    m26 = m26[m26["year"] == 2026].copy()
    m26["min_online"] = pd.to_numeric(m26["aciertos_minimos"], errors="coerce")
    m26 = (m26[["carrera", "campus", "modalidad", "min_online"]]
           .drop_duplicates(subset=["carrera", "campus", "modalidad"]))

    mctrl = pd.read_csv(META_CONTROL, dtype=str, keep_default_na=False, na_filter=False)
    mctrl = _canonicalize_control(mctrl)
    mctrl["min_control"] = pd.to_numeric(mctrl["aciertos_minimos"], errors="coerce")
    mctrl = (mctrl[["carrera", "campus", "modalidad", "min_control"]]
             .drop_duplicates(subset=["carrera", "campus", "modalidad"]))

    merged = merged.merge(m26, on=["carrera", "campus", "modalidad"], how="left")
    merged = merged.merge(mctrl, on=["carrera", "campus", "modalidad"], how="left")

    tiene_minimos = merged["min_online"].notna() & merged["min_control"].notna()
    p26 = merged["ac_26"] >= merged["min_online"]
    pctrl = merged["ac_ctrl"] >= merged["min_control"]
    cat = np.select(
        [p26 & pctrl, (~p26) & pctrl, p26 & (~pctrl), (~p26) & (~pctrl)],
        [CAT_AMBOS, CAT_SOLO_CTRL, CAT_SOLO_26, CAT_NINGUNO], default=-1)
    merged["cat"] = np.where(tiene_minimos, cat, -1)

    search_ofertas = []
    con_minimos = merged[merged["cat"] >= 0]
    for (car, cam, mod), sub in con_minimos.groupby(["carrera", "campus", "modalidad"]):
        if len(sub) < MIN_N:
            continue
        cats = sub["cat"].to_numpy()
        n = len(sub)
        pct = [float((cats == c).mean() * 100) for c in (CAT_AMBOS, CAT_SOLO_CTRL, CAT_SOLO_26, CAT_NINGUNO)]
        search_ofertas.append({
            "carrera": car, "campus": cam, "modalidad": mod,
            "min_online": int(sub["min_online"].iloc[0]),
            "min_control": int(sub["min_control"].iloc[0]),
            "n": n, "pct": pct,
            "xs": sub["ac_26"].astype(int).tolist(),
            "ys": sub["ac_ctrl"].astype(int).tolist(),
            "cats": cats.astype(int).tolist(),
        })
    search_ofertas.sort(key=lambda o: (o["carrera"], o["campus"]))
    summary["n_search_ofertas"] = len(search_ofertas)

    return merged, summary, by_oferta, search_ofertas


# --------------------------------------------------------------------------- #
# Mapa de calor: aciertos 2026 (x) vs. aciertos control (y), binned
# --------------------------------------------------------------------------- #
SW, SH = 620, 480
SML, SMR, SMT, SMB = 54, 16, 16, 44
BIN = 5
EDGES = np.arange(0, 125, BIN)
XLABEL = "aciertos en línea, 2026 (misma persona)"
YLABEL = "aciertos en control (misma persona)"


def _fx(v: float) -> float:
    return SML + v / 120 * (SW - SML - SMR)


def _fy(v: float) -> float:
    return (SH - SMB) - v / 120 * (SH - SMB - SMT)


def _axes_svg() -> list[str]:
    p = []
    for t in range(0, 121, 20):
        x, y = _fx(t), _fy(t)
        p.append(f'<line x1="{x:.1f}" y1="{SMT}" x2="{x:.1f}" y2="{SH-SMB}" class="gridl"/>')
        p.append(f'<text x="{x:.1f}" y="{SH-SMB+16}" class="axl" text-anchor="middle">{t}</text>')
        p.append(f'<line x1="{SML}" y1="{y:.1f}" x2="{SW-SMR}" y2="{y:.1f}" class="gridl"/>')
        p.append(f'<text x="{SML-8}" y="{y+3:.1f}" class="axl" text-anchor="end">{t}</text>')
    p.append(f'<line x1="{_fx(0):.1f}" y1="{_fy(0):.1f}" x2="{_fx(120):.1f}" y2="{_fy(120):.1f}" class="refline"/>')
    p.append(f'<text x="{_fx(120)-6:.1f}" y="{_fy(120)-6:.1f}" class="axl reflbl" '
             f'text-anchor="end">mismo puntaje</text>')
    p.append(f'<text x="{(SML+SW-SMR)/2:.1f}" y="{SH-8}" class="axtitle" text-anchor="middle">{XLABEL}</text>')
    p.append(f'<text x="14" y="{(SMT+SH-SMB)/2:.1f}" class="axtitle" text-anchor="middle" '
             f'transform="rotate(-90 14 {(SMT+SH-SMB)/2:.1f})">{YLABEL}</text>')
    return p


def build_heatmap(pairs: pd.DataFrame) -> str:
    H, xedges, yedges = np.histogram2d(pairs["ac_26"], pairs["ac_ctrl"], bins=[EDGES, EDGES])
    logH = np.log1p(H)
    vmax = logH.max() if logH.max() > 0 else 1.0

    cell_w = _fx(BIN) - _fx(0)
    cell_h = _fy(0) - _fy(BIN)

    p = [f'<svg viewBox="0 0 {SW} {SH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    n_bins = len(EDGES) - 1
    for i in range(n_bins):
        for j in range(n_bins):
            cnt = int(H[i, j])
            if cnt == 0:
                continue
            x0, y0 = EDGES[i], EDGES[j]
            px, py = _fx(x0), _fy(y0 + BIN)
            op = 0.08 + 0.87 * (logH[i, j] / vmax)
            tip = {"r26": f"{x0:.0f}–{x0+BIN:.0f}", "rctrl": f"{y0:.0f}–{y0+BIN:.0f}",
                   "n": f"{cnt:,}"}
            p.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" '
                     f'class="cell" style="fill-opacity:{op:.3f}" '
                     f'data-tip=\'{_html.escape(json.dumps(tip))}\'/>')
    p.extend(_axes_svg())
    p.append('</svg>')
    return "".join(p)


def build_point_scatter(pairs: pd.DataFrame) -> str:
    """Un punto por persona (sin folio, sin ningún identificador) — dispersión
    aleatoria leve (±0.45 aciertos) solo para separar visualmente enteros
    superpuestos; la densidad real la da la superposición de alfa en canvas."""
    axes = "".join([f'<svg viewBox="0 0 {SW} {SH}" width="100%" height="100%" '
                     'style="position:absolute;inset:0;pointer-events:none;">']
                    + _axes_svg() + ['</svg>'])
    left_pct = SML / SW * 100
    top_pct = SMT / SH * 100
    w_pct = (SW - SML - SMR) / SW * 100
    h_pct = (SH - SMT - SMB) / SH * 100
    xs = ",".join(str(v) for v in pairs["ac_26"].astype(int))
    ys = ",".join(str(v) for v in pairs["ac_ctrl"].astype(int))
    canvas = (f'<canvas id="ptCanvas" style="position:absolute;left:{left_pct:.3f}%;'
              f'top:{top_pct:.3f}%;width:{w_pct:.3f}%;height:{h_pct:.3f}%;"></canvas>')
    script = f"""<script>
(function(){{
  var XS=[{xs}], YS=[{ys}];
  var canvas=document.getElementById('ptCanvas');
  if(!canvas) return;
  var ctx=canvas.getContext('2d');
  var root=document.querySelector('.viz-root');
  function col(){{ return (getComputedStyle(root).getPropertyValue('--ctrl')||'#2f6fb0').trim(); }}
  function draw(){{
    var rect=canvas.getBoundingClientRect();
    var dpr=window.devicePixelRatio||1;
    var w=Math.max(1,rect.width), h=Math.max(1,rect.height);
    canvas.width=Math.round(w*dpr); canvas.height=Math.round(h*dpr);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,w,h);
    ctx.fillStyle=col();
    ctx.globalAlpha=0.08;
    for(var i=0;i<XS.length;i++){{
      var x=(XS[i]+(Math.random()-0.5)*0.9)/120*w;
      var y=h-(YS[i]+(Math.random()-0.5)*0.9)/120*h;
      ctx.beginPath(); ctx.arc(x,y,1.3,0,6.2832); ctx.fill();
    }}
  }}
  draw();
  if(window.ResizeObserver) new ResizeObserver(draw).observe(canvas);
  new MutationObserver(draw).observe(document.documentElement,{{attributes:true,attributeFilter:['data-theme']}});
  window.addEventListener('resize', draw);
}})();
</script>"""
    return (f'<div class="scatter-wrap" style="position:relative;width:100%;'
            f'aspect-ratio:{SW}/{SH};">{axes}{canvas}{script}</div>')


# --------------------------------------------------------------------------- #
# Histograma del cambio individual (control - en línea)
# --------------------------------------------------------------------------- #
HW, HH = 620, 300
HML, HMR, HMT, HMB = 44, 16, 12, 44


def build_delta_hist(pairs: pd.DataFrame) -> str:
    edges = np.arange(-100, 45, 5)
    counts, _ = np.histogram(pairs["delta"], bins=edges)
    vmax = counts.max() if counts.max() > 0 else 1

    def fx(v):
        return HML + (v - edges[0]) / (edges[-1] - edges[0]) * (HW - HML - HMR)

    def fy(c):
        return (HH - HMB) - c / vmax * (HH - HMB - HMT)

    bar_w = fx(edges[1]) - fx(edges[0]) - 1
    p = [f'<svg viewBox="0 0 {HW} {HH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    for t in range(-100, 41, 20):
        x = fx(t)
        p.append(f'<text x="{x:.1f}" y="{HH-HMB+16}" class="axl" text-anchor="middle">{t:+d}</text>')
    x0 = fx(0)
    p.append(f'<line x1="{x0:.1f}" y1="{HMT}" x2="{x0:.1f}" y2="{HH-HMB}" class="refline"/>')
    p.append(f'<line x1="{HML}" y1="{HH-HMB}" x2="{HW-HMR}" y2="{HH-HMB}" class="axis"/>')
    for i, c in enumerate(counts):
        if c == 0:
            continue
        x = fx(edges[i])
        y = fy(c)
        tip = {"rango": f"{edges[i]:+d} a {edges[i+1]:+d}", "n": f"{int(c):,}"}
        p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{HH-HMB-y:.1f}" '
                 f'class="bar" data-tip=\'{_html.escape(json.dumps(tip))}\'/>')
    p.append(f'<text x="{(HML+HW-HMR)/2:.1f}" y="{HH-8}" class="axtitle" text-anchor="middle">'
             f'cambio individual: aciertos en control − aciertos en línea, 2026</text>')
    p.append('</svg>')
    return "".join(p)


# --------------------------------------------------------------------------- #
# Tabla por oferta
# --------------------------------------------------------------------------- #

def build_table(by_oferta: list[dict]) -> str:
    head = (
        '<tr>'
        '<th class="c sortable" data-key="carrera">Carrera<span class="arrow">▾</span></th>'
        '<th class="c sortable" data-key="campus">Campus<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="modalidad">Modalidad<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="n">Personas pareadas<span class="arrow">▾</span></th>'
        '<th class="sortable sorted" data-key="mediana">Mediana del cambio<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="pctbaja">% que bajó<span class="arrow">▾</span></th>'
        '</tr>')
    rows = []
    for o in by_oferta:
        modal = "" if o["modalidad"] == "escolarizado" else f" · {o['modalidad']}"
        rows.append(
            f'<tr data-carrera="{esc(o["carrera"].lower())}" '
            f'data-campus="{esc(o["campus"].lower())}" data-modalidad="{esc(o["modalidad"])}" '
            f'data-n="{o["n"]}" data-mediana="{o["median_delta"]:.2f}" '
            f'data-pctbaja="{o["pct_baja"]:.2f}">'
            f'<td class="c">{esc(nice_name(o["carrera"]))}</td>'
            f'<td class="c">{esc(nice_name(o["campus"]))}{esc(modal)}</td>'
            f'<td>{esc(o["modalidad"])}</td>'
            f'<td>{o["n"]:,}</td>'
            f'<td class="hl">{o["median_delta"]:+.0f}</td>'
            f'<td>{o["pct_baja"]:.1f}%</td></tr>')
    return (f'<table class="tbl" id="tblTray"><thead>{head}</thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


# --------------------------------------------------------------------------- #
# Buscador por oferta: dispersión pasó/no pasó según el mínimo de cada examen
# --------------------------------------------------------------------------- #

def build_oferta_search(search_ofertas: list[dict]) -> str:
    data = []
    for o in search_ofertas:
        modal = "" if o["modalidad"] == "escolarizado" else f" · {o['modalidad']}"
        label = f'{nice_name(o["carrera"])} — {nice_name(o["campus"])}{modal}'
        # key de búsqueda: minúsculas SIN acentos (como el resto de las cajas
        # de búsqueda de este sitio) para que "medico" encuentre "Médico".
        key = f'{o["carrera"]} {o["campus"]} {o["modalidad"]}'.lower()
        data.append({
            "label": label, "key": key, "carrera": nice_name(o["carrera"]),
            "campus": nice_name(o["campus"]) + modal,
            "min26": o["min_online"], "minc": o["min_control"],
            "n": o["n"], "pct": [round(v, 1) for v in o["pct"]],
            "xs": o["xs"], "ys": o["ys"], "cats": o["cats"],
        })
    # script[type=application/json] es "raw text": no se decodifican entidades
    # HTML, así que NO se debe html-escapar aquí — solo neutralizar "</" para
    # que un valor con esa secuencia no cierre la etiqueta antes de tiempo.
    data_json = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")

    markup = f"""
  <div class="oferta-search">
    <input id="ofertaSearch" class="search" type="text" autocomplete="off"
      placeholder="Buscar carrera, campus o modalidad…">
    <div id="ofertaResults" class="oferta-results"></div>
  </div>
  <div class="grid-cmp" style="margin-top:12px;">
    <div><div class="chart-wrap" id="ofertaChartBox"></div></div>
    <div id="ofertaLegend"></div>
  </div>
  <script type="application/json" id="ofertaData">{data_json}</script>
  <script>
(function(){{
  var DATA = JSON.parse(document.getElementById('ofertaData').textContent);
  var CATLBL = {json.dumps(CAT_LABELS)};
  var input = document.getElementById('ofertaSearch');
  var results = document.getElementById('ofertaResults');
  var chartBox = document.getElementById('ofertaChartBox');
  var legendBox = document.getElementById('ofertaLegend');

  function renderChart(idx){{
    var d = DATA[idx];
    var W=560, H=460, ML=54, MR=16, MT=20, MB=44;
    var iw=W-ML-MR, ih=H-MT-MB;
    function px(v){{ return ML+v/120*iw; }}
    function py(v){{ return (H-MB)-v/120*ih; }}
    var p=['<svg viewBox="0 0 '+W+' '+H+'" width="100%" preserveAspectRatio="xMidYMid meet">'];
    for(var t=0;t<=120;t+=20){{
      var x=px(t), y=py(t);
      p.push('<line x1="'+x.toFixed(1)+'" y1="'+MT+'" x2="'+x.toFixed(1)+'" y2="'+(H-MB)+'" class="gridl"/>');
      p.push('<text x="'+x.toFixed(1)+'" y="'+(H-MB+16)+'" class="axl" text-anchor="middle">'+t+'</text>');
      p.push('<line x1="'+ML+'" y1="'+y.toFixed(1)+'" x2="'+(W-MR)+'" y2="'+y.toFixed(1)+'" class="gridl"/>');
      p.push('<text x="'+(ML-8)+'" y="'+(y+3).toFixed(1)+'" class="axl" text-anchor="end">'+t+'</text>');
    }}
    var mx=px(d.min26), my=py(d.minc);
    p.push('<line x1="'+mx.toFixed(1)+'" y1="'+MT+'" x2="'+mx.toFixed(1)+'" y2="'+(H-MB)+'" class="thresh"/>');
    p.push('<line x1="'+ML+'" y1="'+my.toFixed(1)+'" x2="'+(W-MR)+'" y2="'+my.toFixed(1)+'" class="thresh"/>');
    p.push('<text x="'+(ML+iw/2)+'" y="'+(MT-6)+'" class="axl reflbl" text-anchor="middle">mín. en línea '+d.min26+' · mín. control '+d.minc+'</text>');
    for(var i=0;i<d.xs.length;i++){{
      var jx=(Math.random()-0.5)*0.85, jy=(Math.random()-0.5)*0.85;
      var cx=px(d.xs[i]+jx), cy=py(d.ys[i]+jy);
      p.push('<circle cx="'+cx.toFixed(1)+'" cy="'+cy.toFixed(1)+'" r="2.1" class="pt cat'+d.cats[i]+'"/>');
    }}
    p.push('<text x="'+(ML+iw/2)+'" y="'+(H-8)+'" class="axtitle" text-anchor="middle">aciertos en línea, 2026</text>');
    p.push('<text x="14" y="'+(MT+ih/2)+'" class="axtitle" text-anchor="middle" transform="rotate(-90 14 '+(MT+ih/2)+')">aciertos en control</text>');
    p.push('</svg>');
    chartBox.innerHTML = p.join('');

    var rows = CATLBL.map(function(l,i){{
      return '<span class="catrow"><i class="catdot cat'+i+'"></i>'+l+
             ': <b>'+d.pct[i].toFixed(1)+'%</b></span>';
    }}).join('');
    legendBox.innerHTML =
      '<p class="mini" style="font-size:13px;margin-bottom:2px;">'+d.carrera+'</p>'+
      '<p class="method" style="margin-bottom:8px;">'+d.campus+'</p>'+
      '<p class="method">n = '+d.n.toLocaleString('es-MX')+' personas presentaron ambos '+
      'exámenes. Mínimo en línea 2026: <b>'+d.min26+'</b> · Mínimo control: <b>'+d.minc+'</b></p>'+
      '<div class="catlegend">'+rows+'</div>';
  }}

  function renderResults(q){{
    q=(q||'').toLowerCase().trim();
    var matches=[];
    for(var i=0;i<DATA.length && matches.length<8;i++){{
      if(!q || DATA[i].key.indexOf(q)>-1) matches.push(i);
    }}
    results.innerHTML = matches.map(function(i){{
      return '<div class="oferta-item" data-i="'+i+'">'+DATA[i].label+'</div>';
    }}).join('');
    results.style.display = matches.length ? 'block' : 'none';
    results.querySelectorAll('.oferta-item').forEach(function(el){{
      el.addEventListener('click', function(){{
        var i=+el.dataset.i;
        renderChart(i);
        input.value=DATA[i].label;
        results.style.display='none';
      }});
    }});
  }}

  input.addEventListener('input', function(){{ renderResults(input.value); }});
  input.addEventListener('focus', function(){{ renderResults(input.value); }});
  document.addEventListener('click', function(e){{
    if(e.target!==input && !results.contains(e.target)) results.style.display='none';
  }});

  var defIdx=0, maxN=-1;
  DATA.forEach(function(d,i){{ if(d.n>maxN){{maxN=d.n; defIdx=i;}} }});
  input.value = DATA[defIdx].label;
  renderChart(defIdx);
}})();
  </script>"""
    return markup


def build_inner(pairs: pd.DataFrame, summary: dict, by_oferta: list[dict],
                 search_ofertas: list[dict]) -> str:
    heatmap = build_heatmap(pairs)
    point_scatter = build_point_scatter(pairs)
    delta_hist = build_delta_hist(pairs)
    table = build_table(by_oferta)
    oferta_search = build_oferta_search(search_ofertas)
    n_med_neg = sum(1 for o in by_oferta if o["median_delta"] < 0)
    n_med_pos = sum(1 for o in by_oferta if o["median_delta"] > 0)

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10); --ctrl:{CTRL_LIGHT};
  --cat26:{HL_LIGHT}; --catboth:{CATBOTH_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1080px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --ctrl:{CTRL_DARK};
  --cat26:{HL_DARK}; --catboth:{CATBOTH_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a;
  --axis:#383835; --border:rgba(255,255,255,.10); --ctrl:{CTRL_DARK};
  --cat26:{HL_DARK}; --catboth:{CATBOTH_DARK}; }}
.viz-root h1 {{ font-size:20px; margin:0 0 4px; text-wrap:balance; }}
.viz-root h2 {{ font-size:14px; margin:22px 0 6px; }}
.sub {{ color:var(--text-secondary); font-size:13px; margin:0 0 3px; line-height:1.5; }}
.method {{ color:var(--muted); font-size:12px; margin:0 0 2px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--ctrl); border-radius:8px; padding:10px 12px;
  margin:12px 0; font-size:13.5px; line-height:1.5; }}
.headline b {{ color:var(--ctrl); }}
.disclaimer {{ border:1px dashed var(--border); border-radius:8px; padding:9px 12px;
  margin:10px 0; font-size:12px; color:var(--muted); line-height:1.5; font-style:italic; }}
.disclaimer a {{ color:var(--ctrl); }}
.chart-wrap {{ background:var(--surface-1); border:1px solid var(--border);
  border-radius:10px; padding:10px; margin-top:8px; position:relative; }}
.grid-cmp {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:8px; }}
.grid-cmp .chart-wrap {{ margin-top:0; }}
.mini {{ font-size:12.5px; color:var(--text-secondary); margin:0 0 4px; font-weight:600; }}
@media (max-width:820px) {{ .grid-cmp {{ grid-template-columns:1fr; }} }}
.gridl {{ stroke:var(--grid); stroke-width:1; }}
.axis {{ stroke:var(--axis); stroke-width:1; }}
.axl {{ fill:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; }}
.axtitle {{ fill:var(--text-secondary); font-size:11px; }}
.refline {{ stroke:var(--axis); stroke-width:1.3; stroke-dasharray:4 3; }}
.reflbl {{ font-size:9.5px; }}
.cell {{ fill:var(--ctrl); stroke:none; cursor:pointer; }}
.bar {{ fill:var(--ctrl); fill-opacity:.75; cursor:pointer; }}
.bar:hover {{ fill-opacity:1; }}
.tip {{ position:fixed; pointer-events:none; z-index:9; background:var(--surface-1);
  color:var(--text-primary); border:1px solid var(--border); border-radius:8px;
  padding:8px 10px; font-size:11.5px; box-shadow:0 4px 14px rgba(0,0,0,.18);
  opacity:0; transition:opacity .1s; max-width:240px; }}
.tip b {{ color:var(--ctrl); }}
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
.tbl th.sortable:hover {{ color:var(--ctrl); }}
.tbl th .arrow {{ opacity:.35; font-size:9px; margin-left:3px; display:inline-block; }}
.tbl th.sorted .arrow {{ opacity:1; color:var(--ctrl); }}
.tbl th.sorted.asc .arrow {{ transform:rotate(180deg); }}
.tbl td.hl {{ color:var(--ctrl); font-weight:600; }}
.tbl tbody tr:hover {{ background:var(--plane); }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
.oferta-search {{ position:relative; margin-top:10px; }}
.oferta-search .search {{ width:100%; box-sizing:border-box; }}
.oferta-results {{ display:none; position:absolute; z-index:5; left:0; right:0;
  background:var(--surface-1); border:1px solid var(--border); border-radius:8px;
  margin-top:4px; max-height:230px; overflow:auto;
  box-shadow:0 6px 18px rgba(0,0,0,.16); }}
.oferta-item {{ padding:7px 11px; font-size:13px; cursor:pointer; }}
.oferta-item:hover {{ background:var(--plane); color:var(--ctrl); }}
.thresh {{ stroke:var(--muted); stroke-width:1.3; stroke-dasharray:5 3; }}
.pt {{ stroke:none; }}
.pt.cat0 {{ fill:var(--catboth); fill-opacity:.8; }}
.pt.cat1 {{ fill:var(--ctrl); fill-opacity:.8; }}
.pt.cat2 {{ fill:var(--cat26); fill-opacity:.8; }}
.pt.cat3 {{ fill:var(--muted); fill-opacity:.45; }}
.catlegend {{ display:flex; flex-direction:column; gap:7px; font-size:12.5px;
  color:var(--text-secondary); margin-top:4px; }}
.catrow b {{ color:var(--text-primary); }}
.catdot {{ display:inline-block; width:9px; height:9px; border-radius:50%;
  margin-right:6px; vertical-align:middle; }}
.catdot.cat0 {{ background:var(--catboth); }}
.catdot.cat1 {{ background:var(--ctrl); }}
.catdot.cat2 {{ background:var(--cat26); }}
.catdot.cat3 {{ background:var(--muted); }}
</style>"""

    js = """
<script>
(function(){
  var root=document.querySelector('.viz-root');
  var tip=document.createElement('div'); tip.className='tip'; root.appendChild(tip);
  root.querySelectorAll('.cell').forEach(function(c){
    c.addEventListener('mousemove',function(e){
      var d=JSON.parse(c.dataset.tip);
      tip.innerHTML='En línea 2026: <b>'+d.r26+'</b> aciertos<br>Control: <b>'+d.rctrl+'</b> aciertos'
        +'<br>Personas: <b>'+d.n+'</b>';
      tip.style.opacity=1;
      var x=e.clientX+14,y=e.clientY+14;
      if(x+220>innerWidth)x=e.clientX-230; tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    c.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });
  root.querySelectorAll('.bar').forEach(function(c){
    c.addEventListener('mousemove',function(e){
      var d=JSON.parse(c.dataset.tip);
      tip.innerHTML='Cambio: <b>'+d.rango+'</b> aciertos<br>Personas: <b>'+d.n+'</b>';
      tip.style.opacity=1;
      var x=e.clientX+14,y=e.clientY+14;
      if(x+220>innerWidth)x=e.clientX-230; tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    c.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });

  var tbl=document.getElementById('tblTray');
  var tbody=tbl.querySelector('tbody');
  var rows=Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  var countEl=document.getElementById('rowCountT');
  var searchEl=document.getElementById('searchBoxT');

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

  var sortState={key:'mediana',dir:1};
  function sortBy(key,dir){
    var numeric=['n','mediana','pctbaja'];
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
      var dir = (sortState.key===key) ? -sortState.dir : 1;
      sortState={key:key,dir:dir};
      tbl.querySelectorAll('th.sortable').forEach(function(t){t.classList.remove('sorted','asc');});
      th.classList.add('sorted'); if(dir===1)th.classList.add('asc');
      sortBy(key,dir);
    });
  });
})();
</script>"""

    return f"""{css}
<div class="viz-root" data-palette="{CTRL_LIGHT}">
  <h1>La misma persona: en línea 2026 vs. control · UNAM</h1>
  <p class="sub">Todo lo demás en esta serie compara <b>distribuciones</b> por
  oferta (misma forma, distinta gente). Esto es distinto: el número de
  comprobante es el mismo entre el registro de 2026 y el de control — se
  puede seguir a <b>la misma persona</b> y comparar sus propios aciertos.</p>
  <p class="method"><b>Método:</b> {summary['n_matched']:,} personas
  pareadas por comprobante (de {summary['n_ctrl_total']:,} que presentaron
  el control con aciertos válido — {summary['match_rate']:.1f}% de
  coincidencia). Todo se reporta en agregado (mapa de calor, histograma,
  medianas por oferta) — nunca una lista de personas.</p>
  <div class="disclaimer">Nota: es descriptivo — no identifica aspirantes ni
  establece causas. Ver también
  <a href="control-resultados.html">"Control presencial vs. 2026 en línea"</a>
  (comparación por oferta, no por persona).</div>
  <div class="headline">
    De las personas pareadas, <b>{summary['pct_baja']:.1f}%</b> sacó MENOS
    aciertos en el control que en línea, <b>{summary['pct_igual']:.1f}%</b>
    sacó lo mismo y <b>{summary['pct_sube']:.1f}%</b> sacó más — una mediana
    de <b>{summary['median_delta']:+.0f} aciertos</b> por persona. Es
    consistente entre ofertas: de las {len(by_oferta)} con al menos una
    persona pareada, <b>{n_med_neg}</b> tuvieron mediana negativa y solo
    {n_med_pos} positiva — casi siempre en ofertas muy chicas (n≤10, ruido
    de muestra pequeña; ver la tabla).
  </div>
  <h2>Aciertos en línea vs. en control, misma persona</h2>
  <p class="sub">Dos vistas del mismo pareo: agregada (bins de {BIN} aciertos) y a
  nivel de punto (una marca por persona, con dispersión aleatoria leve para
  separar enteros superpuestos — no se muestra ningún folio ni identificador).</p>
  <p class="mini">Mapa de calor (agregado)</p>
  <div class="chart-wrap">{heatmap}</div>
  <p class="mini" style="margin-top:14px;">Dispersión (un punto = una persona)</p>
  <div class="chart-wrap">{point_scatter}</div>
  <h2>Cuánto cambió cada persona (control − en línea)</h2>
  <div class="chart-wrap">{delta_hist}</div>
  <h2>Por oferta (mediana del cambio individual)</h2>
  <div class="controls">
    <input id="searchBoxT" class="search" type="text"
      placeholder="Buscar carrera, campus o modalidad…">
    <span id="rowCountT" class="count"></span>
  </div>
  <div class="tbl-wrap">{table}</div>
  <h2>Buscar una oferta: ¿quién pasó cada mínimo?</h2>
  <p class="sub">Usa el mínimo OFICIAL publicado de cada examen (no la
  convocatoria estimada de <a href="examen-control.html">"¿a quién
  convocar?"</a>) para clasificar a cada persona pareada en cuatro grupos:
  pasó en ambos, solo en línea, solo en control, o en ninguno. Solo
  {summary['n_search_ofertas']} de {len(by_oferta)} ofertas tienen mínimo
  oficial publicado en los dos exámenes y ≥{MIN_N} personas pareadas —
  esas son las que se pueden buscar aquí.</p>
  {oferta_search}
  <p class="note">Fuente: resultados DGAE-UNAM, examen en línea 2026 y examen
  de control presencial 2026, pareados por carrera+campus+modalidad+número
  de comprobante. Ofertas con ≥{MIN_N} personas pareadas. Mapa de calor:
  color más intenso = más personas en esa celda (escala logarítmica).
  Análisis descriptivo.</p>
  {js}
</div>"""


def _standalone(inner: str) -> str:
    return ("<!doctype html><html lang=es><head><meta charset=utf-8>"
            "<title>Trayectoria individual: 2026 vs Control</title></head>"
            "<body style='margin:0'>" + inner + "</body></html>")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs, summary, by_oferta, search_ofertas = load()
    print("resumen:", summary)
    print(f"ofertas con >= {MIN_N} pareadas: {len(by_oferta)}")
    print(f"ofertas buscables (mínimo oficial en ambos exámenes): {len(search_ofertas)}")
    print("las 5 con mediana MENOS negativa (menos caída):")
    for o in by_oferta[-5:]:
        print(f"  {o['median_delta']:+.0f}  n={o['n']}  {o['carrera'][:30]} - {o['campus'][:22]}")
    print("las 5 con mediana MAS negativa (mayor caída):")
    for o in by_oferta[:5]:
        print(f"  {o['median_delta']:+.0f}  n={o['n']}  {o['carrera'][:30]} - {o['campus'][:22]}")

    pd.DataFrame(by_oferta).to_csv(OUT_DIR / "trayectoria_individual.csv", index=False, encoding="utf-8")

    inner = build_inner(pairs, summary, by_oferta, search_ofertas)
    (OUT_DIR / "trayectoria_individual.html").write_text(inner, encoding="utf-8")
    (OUT_DIR / "_trayectoria_individual_preview.html").write_text(
        _standalone(inner), encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
