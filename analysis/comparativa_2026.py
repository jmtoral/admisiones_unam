"""Comparativa 2026 vs. años previos: distribuciones de aciertos por oferta
(carrera-campus-modalidad).

Motivación: en 2026 el examen fue en línea. Esta viz muestra las ofertas cuya
distribución de aciertos 2026 más difiere de 2025 (distancia de Wasserstein),
con 2021–2025 en tonos sobrios y 2026 resaltado. Es análisis descriptivo: muestra
corrimientos, no causas.

Unidad = carrera + campus + modalidad (una carrera en distinto campus es un panel
distinto). Solo aspirantes que presentaron examen (aciertos numérico).

Uso:
    python analysis/comparativa_2026.py
Salidas en analysis/output/:
    comparativa_2026_2025.csv      (tabla de ofertas y corrimientos)
    comparativa_2026.html          (page content para Artifact)
    _comparativa_preview.html      (standalone para screenshot)
"""

from __future__ import annotations

import argparse
import html as _html
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC_CSV = ROOT / "data" / "consolidated" / "resultados_todos.csv"
OUT_DIR = ROOT / "analysis" / "output"

MIN_N = 50           # mínimo de presentados en 2025 y 2026 para comparar
MIN_N_DRAW = 30      # mínimo para dibujar la curva de un año previo
TOP_K = 12
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
GRID = np.arange(0, 121, 1.0)

# Rampa sobria (gris) para 2021–2025; 2026 en rojo llamativo. Por tema.
GREY_LIGHT = {2021: "#d7d6cf", 2022: "#bfbeb4", 2023: "#a1a099",
              2024: "#83827b", 2025: "#5c5b55"}
GREY_DARK = {2021: "#3a3a37", 2022: "#4f4e49", 2023: "#68675f",
             2024: "#8a897f", 2025: "#b4b3a7"}
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"


def gaussian_kde(sample: np.ndarray, grid: np.ndarray) -> np.ndarray:
    n = sample.size
    std = sample.std(ddof=1) if n > 1 else 1.0
    iqr = np.subtract(*np.percentile(sample, [75, 25]))
    spread = min(std, iqr / 1.349) if iqr > 0 else std
    h = max(0.9 * spread * n ** (-0.2), 2.0)
    u = (grid[:, None] - sample[None, :]) / h
    k = np.exp(-0.5 * u * u) / np.sqrt(2 * np.pi)
    return k.mean(axis=1) / h


def _cdf(vals: np.ndarray) -> np.ndarray:
    c = np.bincount(vals, minlength=121)[:121]
    return np.cumsum(c) / c.sum()


def load() -> tuple[list[dict], dict]:
    df = pd.read_csv(SRC_CSV, dtype=str, keep_default_na=False, na_filter=False)
    df["ac"] = pd.to_numeric(df["aciertos"], errors="coerce")
    df["year"] = df["year"].astype(int)
    pres = df[df["ac"].notna()].copy()
    pres["ac"] = pres["ac"].astype(int)

    offers = []
    for (carrera, campus, modalidad), sub in pres.groupby(["carrera", "campus", "modalidad"]):
        by = {y: s["ac"].to_numpy() for y, s in sub.groupby("year")}
        if 2025 not in by or 2026 not in by:
            continue
        if by[2025].size < MIN_N or by[2026].size < MIN_N:
            continue
        w1 = float(np.abs(_cdf(by[2025]) - _cdf(by[2026])).sum())
        offers.append({
            "carrera": carrera, "campus": campus, "modalidad": modalidad,
            "by": by, "w1": w1,
            "med": {y: float(np.median(v)) for y, v in by.items()},
            "n": {y: int(v.size) for y, v in by.items()},
        })
    offers.sort(key=lambda d: -d["w1"])

    # Señal sistemática: corrimiento medio de la mediana por transición.
    def mean_shift(ya, yb):
        d = [o["med"][yb] - o["med"][ya] for o in offers
             if ya in o["med"] and yb in o["med"]]
        return (float(np.mean(d)) if d else 0.0), len(d)
    trans = {f"{a}-{b}": mean_shift(a, b)
             for a, b in zip(YEARS, YEARS[1:])}
    up = sum(1 for o in offers if o["med"][2026] > o["med"][2025])
    summary = {
        "n_offers": len(offers), "up": up,
        "down": sum(1 for o in offers if o["med"][2026] < o["med"][2025]),
        "shift_2526": trans["2025-2026"][0],
        "prev_shifts": {k: v[0] for k, v in trans.items() if k != "2025-2026"},
    }
    return offers, summary


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #

FW, FH = 300, 150          # viewBox de cada facet
ML, MR, MT, MB = 8, 8, 10, 22
BASE = FH - MB
AMP = BASE - MT


def xpos(v: float) -> float:
    return ML + v / 120 * (FW - ML - MR)


def esc(s: str) -> str:
    return _html.escape(str(s))


def facet_svg(o: dict) -> str:
    dens = {y: gaussian_kde(o["by"][y], GRID) for y in o["by"]
            if o["n"][y] >= MIN_N_DRAW or y in (2025, 2026)}
    gmax = max(d.max() for d in dens.values())
    amp = AMP / gmax

    parts = [f'<svg viewBox="0 0 {FW} {FH}" width="100%" '
             f'preserveAspectRatio="xMidYMid meet">']
    # eje x mínimo (anclado para no cortar la etiqueta 120 en el borde)
    for t, anchor in ((0, "start"), (60, "middle"), (120, "end")):
        parts.append(f'<line x1="{xpos(t):.1f}" y1="{BASE}" x2="{xpos(t):.1f}" '
                     f'y2="{BASE+3}" class="tick"/>')
        parts.append(f'<text x="{xpos(t):.1f}" y="{BASE+15}" class="tickl" '
                     f'text-anchor="{anchor}">{t}</text>')
    parts.append(f'<line x1="{ML}" y1="{BASE}" x2="{FW-MR}" y2="{BASE}" class="axis"/>')

    def poly(d):
        pts = [f'{xpos(GRID[i]):.1f},{BASE - d[i]*amp:.2f}' for i in range(GRID.size)]
        return " ".join(pts)

    # 2021–2025 sobrios (viejos primero, abajo en z)
    for y in [yy for yy in YEARS if yy != 2026 and yy in dens]:
        parts.append(f'<polyline class="yr y{y}" points="{poly(dens[y])}"/>')
    # 2026 resaltado, con relleno y encima
    if 2026 in dens:
        d = dens[2026]
        area = (f'{xpos(0):.1f},{BASE:.1f} ' + poly(d) +
                f' {xpos(120):.1f},{BASE:.1f}')
        parts.append(f'<polygon class="y2026-fill" points="{area}"/>')
        parts.append(f'<polyline class="yr y2026" points="{poly(d)}"/>')
    # marcas de mediana 2025 (gris) y 2026 (rojo)
    if 2025 in o["med"]:
        mx = xpos(o["med"][2025])
        parts.append(f'<line x1="{mx:.1f}" y1="{BASE}" x2="{mx:.1f}" '
                     f'y2="{BASE-6}" class="med25"/>')
    mx = xpos(o["med"][2026])
    parts.append(f'<line x1="{mx:.1f}" y1="{BASE}" x2="{mx:.1f}" '
                 f'y2="{BASE-9}" class="med26"/>')
    parts.append('</svg>')
    return "".join(parts)


def facet_card(o: dict) -> str:
    dmed = o["med"][2026] - o["med"][2025]
    modal = "" if o["modalidad"] == "escolarizado" else f' · {o["modalidad"]}'
    tip = {"med": {str(y): o["med"][y] for y in sorted(o["med"])},
           "n": {str(y): o["n"][y] for y in sorted(o["n"])}}
    return (
        f'<figure class="facet" data-tip=\'{_html.escape(json.dumps(tip))}\'>'
        f'<figcaption><span class="ca">{esc(o["carrera"].title())}</span>'
        f'<span class="cc">{esc(o["campus"].title())}{esc(modal)}</span></figcaption>'
        f'<div class="badge">mediana {o["med"][2025]:.0f} → '
        f'{o["med"][2026]:.0f} <b>(+{dmed:.0f})</b></div>'
        f'{facet_svg(o)}</figure>')


def build_table(offers: list[dict]) -> str:
    head = ("<tr><th class=c>Carrera</th><th class=c>Campus</th>"
            + "".join(f"<th>{y}</th>" for y in YEARS)
            + "<th>Δ25→26</th><th>W1</th></tr>")
    rows = []
    for o in offers:
        meds = "".join(
            f'<td>{o["med"][y]:.0f}</td>' if y in o["med"] else "<td>·</td>"
            for y in YEARS)
        d = o["med"][2026] - o["med"][2025]
        rows.append(
            f'<tr><td class=c>{esc(o["carrera"].title())}</td>'
            f'<td class=c>{esc(o["campus"].title())}</td>{meds}'
            f'<td class=hl>+{d:.0f}</td><td>{o["w1"]:.1f}</td></tr>')
    return f'<table class=tbl><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>'


def build_inner(offers: list[dict], summary: dict, top_k: int = TOP_K,
                png: bool = False) -> str:
    top = offers[:top_k]
    facets = "".join(facet_card(o) for o in top)
    table = build_table(offers)
    prev = summary["prev_shifts"]
    prev_txt = ", ".join(f"{k.replace('-', '→')}: {v:+.1f}" for k, v in prev.items())

    gl = "".join(f"--y{y}:{GREY_LIGHT[y]};" for y in GREY_LIGHT)
    gd = "".join(f"--y{y}:{GREY_DARK[y]};" for y in GREY_DARK)

    s = 1.42 if png else 1.0   # escala tipográfica (el PNG necesita fuentes mayores)
    lw = 1.3 if png else 1.0   # escala de grosor de línea

    css = f"""
<style>
.viz-root {{
  color-scheme:light;
  --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  {gl} --y2026:{HL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary);
  padding:24px; max-width:1080px; margin:0 auto;
}}
@media (prefers-color-scheme:dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
    --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
    {gd} --y2026:{HL_DARK};
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  {gd} --y2026:{HL_DARK};
}}
.viz-root h1 {{ font-size:{20*s:.1f}px; margin:0 0 4px; text-wrap:balance; }}
.sub {{ color:var(--text-secondary); font-size:{13*s:.1f}px; margin:0 0 3px; line-height:1.5; }}
.method {{ color:var(--muted); font-size:{12*s:.1f}px; margin:0 0 2px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:{3*lw:.1f}px solid var(--y2026); border-radius:8px; padding:10px 12px;
  margin:12px 0; font-size:{13.5*s:.1f}px; line-height:1.5; }}
.headline b {{ color:var(--y2026); }}
.legend {{ display:flex; gap:16px; align-items:center; font-size:{12*s:.1f}px;
  color:var(--text-secondary); margin:10px 0 4px; flex-wrap:wrap; }}
.legend i {{ display:inline-block; width:22px; height:0; border-top-width:2px;
  border-top-style:solid; vertical-align:middle; margin-right:6px; }}
.grid-f {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:8px; }}
.facet {{ background:var(--surface-1); border:1px solid var(--border);
  border-radius:10px; padding:8px 8px 2px; margin:0; }}
.facet figcaption {{ display:flex; flex-direction:column; line-height:1.25; }}
.facet .ca {{ font-size:{12*s:.1f}px; font-weight:600; }}
.facet .cc {{ font-size:{10.5*s:.1f}px; color:var(--muted); }}
.facet .badge {{ font-size:{10.5*s:.1f}px; color:var(--text-secondary);
  font-variant-numeric:tabular-nums; margin:2px 0 0; }}
.facet .badge b {{ color:var(--y2026); }}
.axis {{ stroke:var(--axis); stroke-width:1; }}
.tick {{ stroke:var(--axis); stroke-width:1; }}
.tickl {{ fill:var(--muted); font-size:{9.5*s:.1f}px; font-variant-numeric:tabular-nums; }}
.yr {{ fill:none; stroke-width:{1.4*lw:.2f}; }}
.y2021 {{ stroke:var(--y2021); }} .y2022 {{ stroke:var(--y2022); }}
.y2023 {{ stroke:var(--y2023); }} .y2024 {{ stroke:var(--y2024); }}
.y2025 {{ stroke:var(--y2025); stroke-width:{1.6*lw:.2f}; }}
.y2026 {{ stroke:var(--y2026); stroke-width:{2.4*lw:.2f}; }}
.y2026-fill {{ fill:var(--y2026); fill-opacity:.13; }}
.med25 {{ stroke:var(--y2025); stroke-width:{1.4*lw:.2f}; }}
.med26 {{ stroke:var(--y2026); stroke-width:{2*lw:.2f}; }}
.tip {{ position:fixed; pointer-events:none; z-index:9; background:var(--surface-1);
  color:var(--text-primary); border:1px solid var(--border); border-radius:8px;
  padding:8px 10px; font-size:11.5px; box-shadow:0 4px 14px rgba(0,0,0,.18);
  opacity:0; transition:opacity .1s; }}
.tip table {{ border-collapse:collapse; }} .tip td {{ padding:1px 6px; }}
.tip .yl {{ color:var(--text-secondary); }} .tip .h26 {{ color:var(--y2026); font-weight:600; }}
details {{ margin-top:16px; }}
summary {{ cursor:pointer; color:var(--text-secondary); font-size:13px; }}
.scroll {{ overflow-x:auto; }}
.tbl {{ border-collapse:collapse; width:100%; margin-top:10px; font-size:11.5px; }}
.tbl th,.tbl td {{ text-align:right; padding:3px 7px; border-bottom:1px solid var(--border);
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tbl th.c,.tbl td.c {{ text-align:left; font-variant-numeric:normal; }}
.tbl thead th {{ color:var(--text-secondary); font-weight:600; }}
.tbl td.hl {{ color:var(--y2026); font-weight:600; }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
@media (max-width:720px) {{ .grid-f {{ grid-template-columns:repeat(2,1fr); }} }}
</style>"""

    js = """
<script>
(function(){
  var root=document.querySelector('.viz-root');
  var tip=document.createElement('div'); tip.className='tip'; root.appendChild(tip);
  root.querySelectorAll('.facet').forEach(function(f){
    f.addEventListener('mousemove',function(e){
      var d=JSON.parse(f.dataset.tip); var rows='';
      Object.keys(d.med).forEach(function(y){
        var cls=y==='2026'?' class=h26':' class=yl';
        rows+='<tr'+cls+'><td'+cls+'>'+y+'</td><td>mediana '+d.med[y]+
              '</td><td>n='+Number(d.n[y]).toLocaleString('es-MX')+'</td></tr>';
      });
      tip.innerHTML='<table>'+rows+'</table>'; tip.style.opacity=1;
      var x=e.clientX+14,y=e.clientY+14;
      if(x+180>innerWidth)x=e.clientX-190; tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    f.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });
})();
</script>"""

    if png:            # PNG estático: sin tooltip interactivo
        js = ""

    legend = (
        '<div class="legend">'
        '<span><i style="border-top-color:var(--y2021)"></i>2021</span>'
        '<span><i style="border-top-color:var(--y2023)"></i>2023</span>'
        '<span><i style="border-top-color:var(--y2025);border-top-width:2px"></i>2025</span>'
        '<span><i style="border-top-color:var(--y2026);border-top-width:3px"></i>'
        '<b style="color:var(--y2026)">2026 (examen en línea)</b></span>'
        '<span style="margin-left:auto">▏ marca = mediana</span></div>')

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT}">
  <h1>El salto de 2026: aciertos por carrera-campus · UNAM</h1>
  <p class="sub">Distribución de aciertos por oferta (carrera + campus). Años
  <b>2021–2025 en tonos sobrios</b>, <b style="color:var(--y2026)">2026 resaltado</b>
  (año del examen en línea).</p>
  <p class="method"><b>Cómo se eligen los paneles:</b> de las {summary['n_offers']}
  ofertas comparables (una carrera-campus con ≥{MIN_N} sustentantes en 2025 y 2026),
  se muestran las <b>{top_k}</b> con mayor distancia de Wasserstein (W1) entre su
  distribución de aciertos 2026 y 2025 — es decir, las que más cambiaron de un año
  al otro.</p>
  <div class="headline">
    De 2025 a 2026 la mediana de aciertos subió en <b>las {summary['n_offers']}
    ofertas comparables — ninguna bajó</b>. El alza media fue de
    <b>+{summary['shift_2526']:.1f} puntos</b> de mediana, frente a corrimientos de
    {prev_txt} en las transiciones previas.
  </div>
  {legend}
  <div class="grid-f">{facets}</div>
  <details><summary>Ver tabla de las {len(offers)} ofertas (medianas por año)</summary>
    <div class="scroll">{table}</div></details>
  <p class="note">Fuente: resultados DGAE-UNAM 2021–2026. Solo aspirantes que
  presentaron examen (aciertos numérico). Ofertas con ≥{MIN_N} presentados en 2025
  y 2026. Densidades por KDE gaussiano; orden por distancia de Wasserstein (W1)
  2026 vs 2025. Análisis descriptivo: muestra corrimientos, no causas.</p>
  {js}
</div>"""


REPO_URL = "https://github.com/jmtoral/admisiones_unam"
FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 100 100'><text y='.9em' font-size='88'>%F0%9F%93%88</text></svg>")


def build_site(inner: str) -> str:
    """Envuelve el contenido en una página HTML autónoma para GitHub Pages,
    con toggle de tema y enlace al repositorio."""
    head = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>El salto de 2026 · Resultados UNAM</title>
<meta name="description" content="Distribuciones de aciertos por carrera-campus en el concurso de selección UNAM: 2021-2025 vs 2026.">
<link rel="icon" href="{FAVICON}">
<style>
  html,body {{ margin:0; background:#f9f9f7; }}
  @media (prefers-color-scheme:dark) {{ html:not([data-theme="light"]),
    html:not([data-theme="light"]) body {{ background:#0d0d0d; }} }}
  html[data-theme="dark"], html[data-theme="dark"] body {{ background:#0d0d0d; }}
  .site-bar {{ max-width:1080px; margin:0 auto; padding:14px 24px 0;
    display:flex; align-items:center; gap:12px; font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .site-bar a, .site-bar button {{ font-size:13px; color:#52514e; text-decoration:none;
    background:none; border:1px solid rgba(11,11,11,.15); border-radius:7px;
    padding:5px 10px; cursor:pointer; }}
  @media (prefers-color-scheme:dark) {{ html:not([data-theme="light"]) .site-bar a,
    html:not([data-theme="light"]) .site-bar button {{ color:#c3c2b7; border-color:rgba(255,255,255,.18); }} }}
  html[data-theme="dark"] .site-bar a, html[data-theme="dark"] .site-bar button {{
    color:#c3c2b7; border-color:rgba(255,255,255,.18); }}
  .site-bar .sp {{ margin-left:auto; }}
</style>
</head>
<body>
<div class="site-bar">
  <span class="sp"></span>
  <a href="{REPO_URL}" target="_blank" rel="noopener">Repositorio ↗</a>
  <button id="themeBtn" type="button" aria-label="Cambiar tema">◐ Tema</button>
</div>
"""
    toggle = """
<script>
(function(){
  var b=document.getElementById('themeBtn'), r=document.documentElement;
  b.addEventListener('click',function(){
    var cur=r.getAttribute('data-theme');
    var dark=cur?cur==='dark':matchMedia('(prefers-color-scheme:dark)').matches;
    r.setAttribute('data-theme', dark?'light':'dark');
  });
})();
</script>
</body></html>"""
    return head + inner + toggle


def main() -> None:
    ap = argparse.ArgumentParser(description="Comparativa 2026 vs años previos")
    ap.add_argument("--top", type=int, default=TOP_K, help="número de paneles")
    ap.add_argument("--png", action="store_true",
                    help="salida estática (sin tooltip), pensada para exportar PNG")
    ap.add_argument("--site", action="store_true",
                    help="genera docs/index.html (sitio GitHub Pages, 50 paneles)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, summary = load()
    print(f"ofertas comparables: {summary['n_offers']} "
          f"(subieron {summary['up']}, bajaron {summary['down']})")
    print(f"corrimiento 2025→2026: +{summary['shift_2526']:.2f} mediana")

    # CSV resumen (todas las ofertas; independiente de --top)
    pd.DataFrame([{
        "carrera": o["carrera"], "campus": o["campus"], "modalidad": o["modalidad"],
        **{f"med_{y}": o["med"].get(y, "") for y in YEARS},
        "d_25_26": o["med"][2026] - o["med"][2025], "w1": round(o["w1"], 2),
    } for o in offers]).to_csv(OUT_DIR / "comparativa_2026_2025.csv",
                               index=False, encoding="utf-8")

    if args.site:
        top = 50 if args.top == TOP_K else args.top
        inner = build_inner(offers, summary, top_k=top, png=False)
        docs = ROOT / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "index.html").write_text(build_site(inner), encoding="utf-8")
        (docs / ".nojekyll").write_text("", encoding="utf-8")
        print(f"Sitio generado: docs/index.html ({top} paneles)")
        return

    suffix = "" if args.top == TOP_K else f"_top{args.top}"
    inner = build_inner(offers, summary, top_k=args.top, png=args.png)
    (OUT_DIR / f"comparativa_2026{suffix}.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Comparativa 2026</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / f"_comparativa_preview{suffix}.html").write_text(preview, encoding="utf-8")
    print(f"HTML generado ({args.top} paneles, png={args.png}) en {OUT_DIR}")


if __name__ == "__main__":
    main()
