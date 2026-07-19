"""Casi perfecto 2026: bimodalidad poblacional y proporción de puntajes altos.

Dos paneles:
  1. Distribución agregada de aciertos (todos los sustentantes) por año. En 2026
     la campana unimodal se aplana y se corre a la derecha (aparece masa alta).
  2. Proporción de sustentantes con puntaje "casi perfecto" (≥100 y ≥110) por año.

Años 2021–2025 sobrios, 2026 resaltado. Análisis descriptivo.

Uso:  python analysis/casi_perfecto_2026.py
Salidas en analysis/output/: casi_perfecto_2026.html + _casi_perfecto_preview.html
"""

from __future__ import annotations

import html as _html
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC_CSV = ROOT / "data" / "consolidated" / "resultados_todos.csv"
OUT_DIR = ROOT / "analysis" / "output"

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
GRID = np.arange(0, 121, 1.0)

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


def load():
    df = pd.read_csv(SRC_CSV, dtype=str, keep_default_na=False, na_filter=False)
    df["ac"] = pd.to_numeric(df["aciertos"], errors="coerce")
    df["year"] = df["year"].astype(int)
    pres = df[df["ac"].notna()].copy()
    pres["ac"] = pres["ac"].astype(int)
    per = {}
    for y, s in pres.groupby("year"):
        ac = s["ac"].to_numpy()
        per[y] = {
            "dens": gaussian_kde(ac, GRID),
            "median": float(np.median(ac)),
            "n": int(ac.size),
            "p100": float(np.mean(ac >= 100)),
            "p110": float(np.mean(ac >= 110)),
        }
    return per


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #

def esc(s):
    return _html.escape(str(s))


# Panel 1: densidad agregada por año
P1W, P1H = 620, 300
ML1, MR1, MT1, MB1 = 44, 14, 14, 34
BASE1 = P1H - MB1


def x1(v):
    return ML1 + v / 120 * (P1W - ML1 - MR1)


def density_panel(per) -> str:
    gmax = max(per[y]["dens"].max() for y in per)
    amp = (BASE1 - MT1) / gmax
    p = [f'<svg viewBox="0 0 {P1W} {P1H}" width="100%" preserveAspectRatio="xMidYMid meet">']
    # grid + eje x
    for t in range(0, 121, 20):
        p.append(f'<line x1="{x1(t):.1f}" y1="{MT1}" x2="{x1(t):.1f}" y2="{BASE1}" class="grid"/>')
        p.append(f'<text x="{x1(t):.1f}" y="{BASE1+16}" class="axl" text-anchor="middle">{t}</text>')
    p.append(f'<text x="{(ML1+P1W-MR1)/2:.1f}" y="{BASE1+30}" class="axt" text-anchor="middle">Aciertos (de 120)</text>')
    p.append(f'<line x1="{ML1}" y1="{BASE1}" x2="{P1W-MR1}" y2="{BASE1}" class="axis"/>')

    def poly(d):
        return " ".join(f'{x1(GRID[i]):.1f},{BASE1 - d[i]*amp:.2f}' for i in range(GRID.size))
    for y in [yy for yy in YEARS if yy != 2026]:
        p.append(f'<polyline class="yr y{y}" points="{poly(per[y]["dens"])}"/>')
    d = per[2026]["dens"]
    area = f'{x1(0):.1f},{BASE1:.1f} ' + poly(d) + f' {x1(120):.1f},{BASE1:.1f}'
    p.append(f'<polygon class="y2026-fill" points="{area}"/>')
    p.append(f'<polyline class="yr y2026" points="{poly(d)}"/>')
    p.append('</svg>')
    return "".join(p)


# Panel 2: barras de proporción casi perfecto
P2W, P2H = 620, 300
ML2, MR2, MT2, MB2 = 44, 14, 16, 40
BASE2 = P2H - MB2


def bars_panel(per) -> str:
    ymax = max(per[y]["p100"] for y in per) * 1.15
    plotw = P2W - ML2 - MR2
    ploth = BASE2 - MT2
    gw = plotw / len(YEARS)          # ancho por grupo (año)
    bw = gw * 0.30                   # ancho de barra
    p = [f'<svg viewBox="0 0 {P2W} {P2H}" width="100%" preserveAspectRatio="xMidYMid meet">']
    # eje y (%)
    for frac in (0, 0.05, 0.10, 0.15):
        yy = BASE2 - frac / ymax * ploth
        p.append(f'<line x1="{ML2}" y1="{yy:.1f}" x2="{P2W-MR2}" y2="{yy:.1f}" class="grid"/>')
        p.append(f'<text x="{ML2-6}" y="{yy+4:.1f}" class="axl" text-anchor="end">{int(frac*100)}%</text>')
    p.append(f'<line x1="{ML2}" y1="{BASE2}" x2="{P2W-MR2}" y2="{BASE2}" class="axis"/>')

    for i, y in enumerate(YEARS):
        cx = ML2 + gw * (i + 0.5)
        hl = (y == 2026)
        # barra ≥100 (tono claro) y ≥110 (tono fuerte), lado a lado
        h100 = per[y]["p100"] / ymax * ploth
        h110 = per[y]["p110"] / ymax * ploth
        x100 = cx - bw - 1
        x110 = cx + 1
        c100 = "b100-26" if hl else "b100"
        c110 = "b110-26" if hl else "b110"
        p.append(f'<rect class="{c100}" x="{x100:.1f}" y="{BASE2-h100:.1f}" '
                 f'width="{bw:.1f}" height="{h100:.1f}" rx="2"/>')
        p.append(f'<rect class="{c110}" x="{x110:.1f}" y="{BASE2-h110:.1f}" '
                 f'width="{bw:.1f}" height="{h110:.1f}" rx="2"/>')
        # etiqueta año
        cls = "axl26" if hl else "axl"
        p.append(f'<text x="{cx:.1f}" y="{BASE2+16}" class="{cls}" text-anchor="middle">{y}</text>')
        # valor ≥110 encima
        p.append(f'<text x="{x110+bw/2:.1f}" y="{BASE2-h110-4:.1f}" '
                 f'class="{"vlab26" if hl else "vlab"}" text-anchor="middle">'
                 f'{per[y]["p110"]*100:.1f}%</text>')
    p.append(f'<text x="{ML2}" y="{P2H-6}" class="axt" text-anchor="start">'
             f'Barra clara = ≥100 aciertos · barra fuerte = ≥110 (casi perfecto)</text>')
    p.append('</svg>')
    return "".join(p)


def build_inner(per) -> str:
    s = 1.0
    gl = "".join(f"--y{y}:{GREY_LIGHT[y]};" for y in GREY_LIGHT)
    gd = "".join(f"--y{y}:{GREY_DARK[y]};" for y in GREY_DARK)
    p110_25 = per[2025]["p110"] * 100
    p110_26 = per[2026]["p110"] * 100
    p100_25 = per[2025]["p100"] * 100
    p100_26 = per[2026]["p100"] * 100
    med25, med26 = per[2025]["median"], per[2026]["median"]

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  {gl} --y2026:{HL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1080px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); {gd} --y2026:{HL_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a;
  --axis:#383835; --border:rgba(255,255,255,.10); {gd} --y2026:{HL_DARK}; }}
.viz-root h1 {{ font-size:21px; margin:0 0 4px; text-wrap:balance; }}
.sub {{ color:var(--text-secondary); font-size:13.5px; margin:0 0 10px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--y2026); border-radius:8px; padding:11px 13px;
  margin:12px 0 16px; font-size:14px; line-height:1.55; }}
.headline b {{ color:var(--y2026); }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
.card {{ background:var(--surface-1); border:1px solid var(--border);
  border-radius:10px; padding:12px 12px 6px; }}
.card h2 {{ font-size:14px; margin:0 0 2px; }}
.card p {{ font-size:12px; color:var(--muted); margin:0 0 6px; line-height:1.45; }}
.legend {{ display:flex; gap:16px; align-items:center; font-size:12.5px;
  color:var(--text-secondary); margin:6px 0 2px; flex-wrap:wrap; }}
.legend i {{ display:inline-block; width:22px; height:0; border-top-width:2px;
  border-top-style:solid; vertical-align:middle; margin-right:6px; }}
.grid {{ stroke:var(--grid); stroke-width:1; }}
.axis {{ stroke:var(--axis); stroke-width:1.2; }}
.axl {{ fill:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }}
.axl26 {{ fill:var(--y2026); font-size:11.5px; font-weight:700; font-variant-numeric:tabular-nums; }}
.axt {{ fill:var(--text-secondary); font-size:11px; }}
.vlab {{ fill:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; }}
.vlab26 {{ fill:var(--y2026); font-size:12px; font-weight:700; font-variant-numeric:tabular-nums; }}
.yr {{ fill:none; stroke-width:1.6; }}
.y2021 {{ stroke:var(--y2021); }} .y2022 {{ stroke:var(--y2022); }}
.y2023 {{ stroke:var(--y2023); }} .y2024 {{ stroke:var(--y2024); }}
.y2025 {{ stroke:var(--y2025); stroke-width:1.8; }}
.y2026 {{ stroke:var(--y2026); stroke-width:2.8; }}
.y2026-fill {{ fill:var(--y2026); fill-opacity:.13; }}
.b100 {{ fill:var(--y2024); }} .b110 {{ fill:var(--y2025); }}
.b100-26 {{ fill:var(--y2026); fill-opacity:.45; }} .b110-26 {{ fill:var(--y2026); }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
@media (max-width:720px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
</style>"""

    legend = (
        '<div class="legend">'
        '<span><i style="border-top-color:var(--y2021)"></i>2021</span>'
        '<span><i style="border-top-color:var(--y2023)"></i>2023</span>'
        '<span><i style="border-top-color:var(--y2025);border-top-width:2px"></i>2025</span>'
        '<span><i style="border-top-color:var(--y2026);border-top-width:3px"></i>'
        '<b style="color:var(--y2026)">2026 (examen en línea)</b></span></div>')

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT}">
  <h1>Puntajes casi perfectos: el patrón 2026 · UNAM</h1>
  <p class="sub">Todos los sustentantes de licenciatura, 2021–2026. La mediana
  agregada de aciertos estuvo en 51–52 durante cinco años y saltó a
  {med26:.0f} en 2026.</p>
  <div class="headline">
    En 2026, <b>{p100_26:.1f}%</b> de los sustentantes obtuvo <b>≥100 aciertos</b> y
    <b>{p110_26:.1f}%</b> obtuvo <b>≥110 (casi perfecto)</b>, contra {p100_25:.1f}% y
    {p110_25:.1f}% en 2025. La proporción de casi perfectos se multiplicó por
    <b>{p110_26/p110_25:.0f}</b>.
  </div>
  {legend}
  <div class="grid2">
    <div class="card"><h2>Distribución agregada de aciertos</h2>
      <p>La campana unimodal de 2021–2025 se aplana y se corre a la derecha en 2026.</p>
      {density_panel(per)}</div>
    <div class="card"><h2>Proporción con puntaje alto por año</h2>
      <p>Sustentantes con ≥100 y ≥110 aciertos. El salto es exclusivo de 2026.</p>
      {bars_panel(per)}</div>
  </div>
  <p class="note">Fuente: resultados DGAE-UNAM 2021–2026. Solo aspirantes que
  presentaron examen (aciertos numérico). Densidad por KDE gaussiano. Análisis
  descriptivo: muestra corrimientos, no causas.</p>
</div>"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per = load()
    for y in YEARS:
        print(f"{y}: mediana {per[y]['median']:.0f}  ≥100 {per[y]['p100']*100:.1f}%  "
              f"≥110 {per[y]['p110']*100:.1f}%  n={per[y]['n']:,}")
    inner = build_inner(per)
    (OUT_DIR / "casi_perfecto_2026.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Casi perfecto 2026</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_casi_perfecto_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
