"""Análisis exploratorio: distribución de aciertos de las 20 carreras con mayor
mediana (UNAM 2026).

Lee `data/consolidated/resultados_todos.csv`, se queda con quienes presentaron
examen (aciertos numérico), agrupa por carrera, calcula la mediana y una densidad
(KDE gaussiano) por carrera, y genera un ridgeline como HTML autocontenido.

Datos AGREGADOS (medianas y densidades por carrera), no a nivel de aspirante:
consistente con el contrato de privacidad.

Uso:
    python analysis/top20_medianas.py
Salidas:
    analysis/output/top20_medianas_2026.csv   (tabla resumen)
    analysis/output/top20_aciertos_2026.html  (page content para Artifact)
    analysis/output/_preview.html              (standalone, para screenshot)
"""

from __future__ import annotations

import html as _html
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC_CSV = ROOT / "data" / "consolidated" / "resultados_todos.csv"
OUT_DIR = ROOT / "analysis" / "output"

YEAR = 2026
MIN_N = 50          # mínimo de presentados para incluir una carrera
TOP_K = 20
X_MIN, X_MAX = 0, 120   # rango de aciertos del examen
GRID = np.arange(X_MIN, X_MAX + 1, 1.0)

# --- Paleta (de references/palette.md), como variables CSS por tema --------- #
# Rampa secuencial azul de 5 bandas: la banda alta = mediana mayor.
SEQ_LIGHT = ["#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab"]
SEQ_DARK  = ["#1c5cab", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"]


def gaussian_kde(sample: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """KDE gaussiano 1-D con numpy. Ancho de banda de Silverman con piso (los
    aciertos son enteros, un piso evita picos artificiales)."""
    n = sample.size
    std = sample.std(ddof=1) if n > 1 else 1.0
    iqr = np.subtract(*np.percentile(sample, [75, 25]))
    spread = min(std, iqr / 1.349) if iqr > 0 else std
    h = 0.9 * spread * n ** (-0.2)
    h = max(h, 2.0)
    # densidad(x) = media_i K((x - xi)/h) / h
    u = (grid[:, None] - sample[None, :]) / h
    k = np.exp(-0.5 * u * u) / np.sqrt(2 * np.pi)
    return k.mean(axis=1) / h


def load_top() -> list[dict]:
    df = pd.read_csv(SRC_CSV, dtype=str, keep_default_na=False, na_filter=False)
    df["ac"] = pd.to_numeric(df["aciertos"], errors="coerce")
    pres = df[df["ac"].notna()].copy()

    stats = []
    for carrera, sub in pres.groupby("carrera"):
        vals = sub["ac"].to_numpy()
        if vals.size < MIN_N:
            continue
        stats.append({
            "carrera": carrera,
            "n": int(vals.size),
            "median": float(np.median(vals)),
            "mean": float(vals.mean()),
            "q1": float(np.percentile(vals, 25)),
            "q3": float(np.percentile(vals, 75)),
            "vmin": int(vals.min()),
            "vmax": int(vals.max()),
            "vals": vals,
        })
    stats.sort(key=lambda d: (-d["median"], -d["n"], d["carrera"]))
    top = stats[:TOP_K]
    for d in top:
        d["density"] = gaussian_kde(d["vals"], GRID)
    return top


# --------------------------------------------------------------------------- #
# Render SVG ridgeline
# --------------------------------------------------------------------------- #

W = 980
PAD_L, LABEL_W = 20, 250
PAD_R = 26
TOP_M = 14
ROW_STEP = 30
RIDGE_AMP = 62
AXIS_H = 62

PLOT_L = PAD_L + LABEL_W
PLOT_R = W - PAD_R
PLOT_W = PLOT_R - PLOT_L


def xpos(v: float) -> float:
    return PLOT_L + (v - X_MIN) / (X_MAX - X_MIN) * PLOT_W


def band_for(median: float, mlo: float, mhi: float) -> int:
    if mhi <= mlo:
        return 2
    t = (median - mlo) / (mhi - mlo)
    return min(4, int(t * 5))


def esc(s: str) -> str:
    return _html.escape(str(s))


def build_svg(top: list[dict]) -> str:
    n = len(top)
    height = TOP_M + RIDGE_AMP + (n - 1) * ROW_STEP + AXIS_H
    gmax = max(d["density"].max() for d in top)
    amp = RIDGE_AMP / gmax
    medians = [d["median"] for d in top]
    mlo, mhi = min(medians), max(medians)
    axis_y = TOP_M + RIDGE_AMP + (n - 1) * ROW_STEP + 16

    parts = [
        f'<svg viewBox="0 0 {W} {height}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Ridgeline de distribución de aciertos por carrera">'
    ]

    # Gridlines verticales + ticks del eje x
    for tick in range(0, 121, 20):
        gx = xpos(tick)
        parts.append(f'<line x1="{gx:.1f}" y1="{TOP_M}" x2="{gx:.1f}" '
                     f'y2="{axis_y:.1f}" class="grid"/>')
        parts.append(f'<text x="{gx:.1f}" y="{axis_y + 16:.1f}" '
                     f'class="axis-lbl" text-anchor="middle">{tick}</text>')
    parts.append(f'<text x="{(PLOT_L + PLOT_R) / 2:.1f}" y="{axis_y + 34:.1f}" '
                 f'class="axis-title" text-anchor="middle">Aciertos '
                 f'(respuestas correctas, de 120)</text>')

    # Ridges: de arriba (mayor mediana) a abajo -> se dibuja back-to-front
    ridge_svg, tick_svg, label_svg = [], [], []
    for i, d in enumerate(top):
        base = TOP_M + RIDGE_AMP + i * ROW_STEP
        b = band_for(d["median"], mlo, mhi)
        dens = d["density"] * amp
        pts = [f'{xpos(X_MIN):.1f},{base:.1f}']
        pts += [f'{xpos(GRID[k]):.1f},{base - dens[k]:.2f}'
                for k in range(GRID.size)]
        pts.append(f'{xpos(X_MAX):.1f},{base:.1f}')
        poly = " ".join(pts)
        ridge_svg.append(
            f'<g class="ridge b{b}" data-carrera="{esc(d["carrera"])}" '
            f'data-median="{d["median"]:.0f}" data-mean="{d["mean"]:.1f}" '
            f'data-q1="{d["q1"]:.0f}" data-q3="{d["q3"]:.0f}" '
            f'data-n="{d["n"]}" data-min="{d["vmin"]}" data-max="{d["vmax"]}">'
            f'<polygon class="ridge-fill" points="{poly}"/>'
            f'<rect class="hit" x="{PLOT_L}" y="{base - ROW_STEP:.1f}" '
            f'width="{PLOT_W}" height="{ROW_STEP + 6}"/></g>'
        )
        # Marca de la mediana (tick vertical sobre la base)
        mx = xpos(d["median"])
        tick_svg.append(
            f'<line x1="{mx:.1f}" y1="{base:.1f}" x2="{mx:.1f}" '
            f'y2="{base - 13:.1f}" class="median-tick"/>')
        # Etiqueta directa (columna izquierda)
        ty = base - 4
        label_svg.append(
            f'<text x="{PLOT_L - 12:.1f}" y="{ty:.1f}" class="row-lbl" '
            f'text-anchor="end">{esc(d["carrera"].title())}</text>'
            f'<text x="{PLOT_L - 12:.1f}" y="{ty + 12:.1f}" class="row-sub" '
            f'text-anchor="end">med {d["median"]:.0f} · n={d["n"]:,}</text>')

    # Eje x baseline
    parts.append(f'<line x1="{PLOT_L}" y1="{axis_y:.1f}" x2="{PLOT_R}" '
                 f'y2="{axis_y:.1f}" class="axis-line"/>')
    parts += ridge_svg + tick_svg + label_svg
    parts.append('</svg>')
    return "".join(parts)


def build_table(top: list[dict]) -> str:
    rows = "".join(
        f'<tr><td class="c">{esc(d["carrera"].title())}</td>'
        f'<td>{d["median"]:.0f}</td><td>{d["mean"]:.1f}</td>'
        f'<td>{d["q1"]:.0f}–{d["q3"]:.0f}</td>'
        f'<td>{d["vmin"]}–{d["vmax"]}</td><td>{d["n"]:,}</td></tr>'
        for d in top)
    return (
        '<table class="tbl"><thead><tr>'
        '<th class="c">Carrera</th><th>Mediana</th><th>Media</th>'
        '<th>Q1–Q3</th><th>Mín–Máx</th><th>n</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>')


def legend_swatches(seq_role: str) -> str:
    sw = "".join(f'<span class="sw" style="background:var(--seq-{k})"></span>'
                 for k in range(5))
    return sw


def build_inner(top: list[dict]) -> str:
    svg = build_svg(top)
    table = build_table(top)
    mlo = min(d["median"] for d in top)
    mhi = max(d["median"] for d in top)
    css = f"""
<style>
.viz-root {{
  color-scheme: light;
  --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --seq-0:{SEQ_LIGHT[0]}; --seq-1:{SEQ_LIGHT[1]}; --seq-2:{SEQ_LIGHT[2]};
  --seq-3:{SEQ_LIGHT[3]}; --seq-4:{SEQ_LIGHT[4]};
  font-family: system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary);
  padding:24px; max-width:1040px; margin:0 auto;
}}
@media (prefers-color-scheme:dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme:dark;
    --surface-1:#1a1a19; --plane:#0d0d0d;
    --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
    --seq-0:{SEQ_DARK[0]}; --seq-1:{SEQ_DARK[1]}; --seq-2:{SEQ_DARK[2]};
    --seq-3:{SEQ_DARK[3]}; --seq-4:{SEQ_DARK[4]};
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme:dark;
  --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --seq-0:{SEQ_DARK[0]}; --seq-1:{SEQ_DARK[1]}; --seq-2:{SEQ_DARK[2]};
  --seq-3:{SEQ_DARK[3]}; --seq-4:{SEQ_DARK[4]};
}}
.viz-root h1 {{ font-size:20px; margin:0 0 4px; }}
.viz-root .sub {{ color:var(--text-secondary); font-size:13px; margin:0 0 2px; line-height:1.5; }}
.viz-root .note {{ color:var(--muted); font-size:12px; margin:2px 0 14px; }}
.card {{ background:var(--surface-1); border:1px solid var(--border);
  border-radius:12px; padding:14px 12px 8px; }}
.legend {{ display:flex; align-items:center; gap:8px; font-size:12px;
  color:var(--text-secondary); margin:2px 0 12px; flex-wrap:wrap; }}
.legend .sw {{ display:inline-block; width:22px; height:12px; border-radius:3px;
  border:1px solid var(--border); }}
.grid {{ stroke:var(--grid); stroke-width:1; }}
.axis-line {{ stroke:var(--axis); stroke-width:1.5; }}
.axis-lbl {{ fill:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }}
.axis-title {{ fill:var(--text-secondary); font-size:12px; }}
.ridge-fill {{ stroke-width:2; fill-opacity:.82; }}
.ridge.b0 .ridge-fill {{ fill:var(--seq-0); stroke:var(--seq-1); }}
.ridge.b1 .ridge-fill {{ fill:var(--seq-1); stroke:var(--seq-2); }}
.ridge.b2 .ridge-fill {{ fill:var(--seq-2); stroke:var(--seq-3); }}
.ridge.b3 .ridge-fill {{ fill:var(--seq-3); stroke:var(--seq-4); }}
.ridge.b4 .ridge-fill {{ fill:var(--seq-4); stroke:var(--seq-4); }}
.ridge .hit {{ fill:transparent; }}
.ridge.active .ridge-fill {{ fill-opacity:.96; stroke-width:2.5; }}
.median-tick {{ stroke:var(--text-primary); stroke-width:1.5; opacity:.7; }}
.row-lbl {{ fill:var(--text-primary); font-size:12px; font-weight:600; }}
.row-sub {{ fill:var(--muted); font-size:10.5px; font-variant-numeric:tabular-nums; }}
.tip {{ position:fixed; pointer-events:none; z-index:9; background:var(--surface-1);
  color:var(--text-primary); border:1px solid var(--border); border-radius:8px;
  padding:8px 10px; font-size:12px; box-shadow:0 4px 14px rgba(0,0,0,.18);
  opacity:0; transition:opacity .1s; max-width:240px; }}
.tip b {{ display:block; margin-bottom:3px; font-size:12.5px; }}
.tip span {{ color:var(--text-secondary); }}
details {{ margin-top:14px; }}
summary {{ cursor:pointer; color:var(--text-secondary); font-size:13px; }}
.tbl {{ border-collapse:collapse; width:100%; margin-top:10px; font-size:12px; }}
.tbl th, .tbl td {{ text-align:right; padding:4px 8px;
  border-bottom:1px solid var(--border); font-variant-numeric:tabular-nums; }}
.tbl th.c, .tbl td.c {{ text-align:left; font-variant-numeric:normal; }}
.tbl thead th {{ color:var(--text-secondary); font-weight:600; }}
.scroll {{ overflow-x:auto; }}
</style>"""

    js = """
<script>
(function(){
  var root = document.querySelector('.viz-root');
  var tip = document.createElement('div'); tip.className='tip'; root.appendChild(tip);
  root.querySelectorAll('.ridge').forEach(function(g){
    var hit = g.querySelector('.hit');
    hit.addEventListener('mousemove', function(e){
      g.classList.add('active');
      var d=g.dataset;
      tip.innerHTML='<b>'+d.carrera.replace(/\\b\\w/g,c=>c.toUpperCase())+'</b>'+
        '<span>Mediana '+d.median+' · Media '+d.mean+'<br>'+
        'Q1–Q3 '+d.q1+'–'+d.q3+' · Rango '+d.min+'–'+d.max+'<br>'+
        'n = '+Number(d.n).toLocaleString('es-MX')+' presentaron examen</span>';
      tip.style.opacity=1;
      var x=e.clientX+14, y=e.clientY+14;
      if(x+240>innerWidth) x=e.clientX-254;
      tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    hit.addEventListener('mouseleave', function(){
      g.classList.remove('active'); tip.style.opacity=0;
    });
  });
})();
</script>"""

    return f"""{css}
<div class="viz-root" data-palette="{','.join(SEQ_LIGHT)}">
  <h1>¿Qué tan competida es cada carrera? · UNAM 2026</h1>
  <p class="sub">Distribución de <b>aciertos</b> (respuestas correctas en el examen
  de selección) de las {TOP_K} carreras con mayor <b>mediana</b>, de mayor a menor.
  Cada cresta es una densidad de probabilidad; más a la derecha = puntajes más altos.</p>
  <div class="legend">
    <span>Mediana menor</span>{legend_swatches('seq')}<span>mayor
    ({mlo:.0f}&nbsp;→&nbsp;{mhi:.0f} aciertos)</span>
    <span style="margin-left:auto">▏ marca = mediana de la carrera</span>
  </div>
  <div class="card"><div class="scroll">{svg}</div></div>
  <p class="note">Fuente: resultados DGAE-UNAM 2026 (concurso de selección a
  licenciatura). Solo aspirantes que presentaron examen (aciertos numérico).
  Carreras con al menos {MIN_N} presentados; agregado por nombre de carrera sobre
  todas las modalidades y campus. Datos agregados, no a nivel de aspirante.</p>
  <details><summary>Ver tabla de valores</summary>
    <div class="scroll">{table}</div></details>
  {js}
</div>"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    top = load_top()

    # CSV resumen
    summary = pd.DataFrame([{k: d[k] for k in
                             ("carrera", "n", "median", "mean", "q1", "q3",
                              "vmin", "vmax")} for d in top])
    summary.to_csv(OUT_DIR / "top20_medianas_2026.csv", index=False,
                   encoding="utf-8")

    inner = build_inner(top)
    (OUT_DIR / "top20_aciertos_2026.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Top 20</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_preview.html").write_text(preview, encoding="utf-8")

    print(f"top {len(top)} carreras. Salidas en {OUT_DIR}")
    for d in top:
        print(f"  med={d['median']:5.1f}  n={d['n']:6d}  {d['carrera']}")


if __name__ == "__main__":
    main()
