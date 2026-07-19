"""Casi cero 2026: el otro extremo de la distribución de aciertos.

Espejo de casi_perfecto_2026.py. Dos paneles:
  1. Proporción con <30 aciertos por año (tramo bajo "común"): estable, sin cambio.
  2. Proporción con <20 y <10 aciertos por año (casi cero): casi 0 durante cinco
     años y aparece en 2026 — puntajes casi imposibles por azar en opción múltiple.

Años 2021–2025 sobrios, 2026 resaltado. Análisis descriptivo.

Uso:  python analysis/casi_cero_2026.py
Salidas en analysis/output/: casi_cero_2026.html + _casi_cero_preview.html
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

GREY_LIGHT = {2021: "#d7d6cf", 2022: "#bfbeb4", 2023: "#a1a099",
              2024: "#83827b", 2025: "#5c5b55"}
GREY_DARK = {2021: "#3a3a37", 2022: "#4f4e49", 2023: "#68675f",
             2024: "#8a897f", 2025: "#b4b3a7"}
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"


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
            "n": int(ac.size), "median": float(np.median(ac)),
            "p30": float(np.mean(ac < 30)),
            "p20": float(np.mean(ac < 20)), "p10": float(np.mean(ac < 10)),
            "c20": int((ac < 20).sum()), "c10": int((ac < 10).sum()),
        }
    return per


def esc(s):
    return _html.escape(str(s))


PW, PH = 620, 300
ML, MR, MT, MB = 46, 14, 16, 40
BASE = PH - MB


def _axis_and_grid(p, ymax, ticks, fmt):
    plotw = PW - ML - MR
    for frac in ticks:
        yy = BASE - frac / ymax * (BASE - MT)
        p.append(f'<line x1="{ML}" y1="{yy:.1f}" x2="{PW-MR}" y2="{yy:.1f}" class="grid"/>')
        p.append(f'<text x="{ML-6}" y="{yy+4:.1f}" class="axl" text-anchor="end">{fmt(frac)}</text>')
    p.append(f'<line x1="{ML}" y1="{BASE}" x2="{PW-MR}" y2="{BASE}" class="axis"/>')
    return plotw


def panel_p30(per) -> str:
    ymax = 0.04
    p = [f'<svg viewBox="0 0 {PW} {PH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    plotw = _axis_and_grid(p, ymax, [0, .01, .02, .03, .04], lambda f: f"{f*100:.0f}%")
    gw = plotw / len(YEARS)
    bw = gw * 0.5
    for i, y in enumerate(YEARS):
        cx = ML + gw * (i + 0.5)
        hl = (y == 2026)
        h = per[y]["p30"] / ymax * (BASE - MT)
        p.append(f'<rect class="{"bar26" if hl else "bar"}" x="{cx-bw/2:.1f}" '
                 f'y="{BASE-h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2"/>')
        p.append(f'<text x="{cx:.1f}" y="{BASE+16}" class="{"axl26" if hl else "axl"}" '
                 f'text-anchor="middle">{y}</text>')
        p.append(f'<text x="{cx:.1f}" y="{BASE-h-4:.1f}" class="{"vlab26" if hl else "vlab"}" '
                 f'text-anchor="middle">{per[y]["p30"]*100:.1f}%</text>')
    p.append('</svg>')
    return "".join(p)


def panel_low(per) -> str:
    ymax = 0.006
    p = [f'<svg viewBox="0 0 {PW} {PH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    plotw = _axis_and_grid(p, ymax, [0, .002, .004, .006], lambda f: f"{f*100:.1f}%")
    gw = plotw / len(YEARS)
    bw = gw * 0.30
    for i, y in enumerate(YEARS):
        cx = ML + gw * (i + 0.5)
        hl = (y == 2026)
        h20 = per[y]["p20"] / ymax * (BASE - MT)
        h10 = per[y]["p10"] / ymax * (BASE - MT)
        x20, x10 = cx - bw - 1, cx + 1
        p.append(f'<rect class="{"b20-26" if hl else "b20"}" x="{x20:.1f}" '
                 f'y="{BASE-h20:.1f}" width="{bw:.1f}" height="{h20:.1f}" rx="2"/>')
        p.append(f'<rect class="{"b10-26" if hl else "b10"}" x="{x10:.1f}" '
                 f'y="{BASE-h10:.1f}" width="{bw:.1f}" height="{h10:.1f}" rx="2"/>')
        p.append(f'<text x="{cx:.1f}" y="{BASE+16}" class="{"axl26" if hl else "axl"}" '
                 f'text-anchor="middle">{y}</text>')
        if hl:  # etiqueta con conteos absolutos en 2026
            p.append(f'<text x="{x20+bw/2:.1f}" y="{BASE-h20-4:.1f}" class="vlab26" '
                     f'text-anchor="middle">{per[y]["c20"]}</text>')
            p.append(f'<text x="{x10+bw/2:.1f}" y="{BASE-h10-4:.1f}" class="vlab26" '
                     f'text-anchor="middle">{per[y]["c10"]}</text>')
    p.append(f'<text x="{ML}" y="{PH-6}" class="axt" text-anchor="start">'
             f'Barra clara = &lt;20 aciertos · barra fuerte = &lt;10 (nº = personas en 2026)</text>')
    p.append('</svg>')
    return "".join(p)


def build_inner(per) -> str:
    gl = "".join(f"--y{y}:{GREY_LIGHT[y]};" for y in GREY_LIGHT)
    gd = "".join(f"--y{y}:{GREY_DARK[y]};" for y in GREY_DARK)
    c20_26, c10_26 = per[2026]["c20"], per[2026]["c10"]
    c20_prev = int(np.mean([per[y]["c20"] for y in (2021, 2022, 2023, 2024, 2025)]))
    c10_prev = int(np.mean([per[y]["c10"] for y in (2021, 2022, 2023, 2024, 2025)]))
    p30_26 = per[2026]["p30"] * 100

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
.grid {{ stroke:var(--grid); stroke-width:1; }}
.axis {{ stroke:var(--axis); stroke-width:1.2; }}
.axl {{ fill:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }}
.axl26 {{ fill:var(--y2026); font-size:11.5px; font-weight:700; font-variant-numeric:tabular-nums; }}
.axt {{ fill:var(--text-secondary); font-size:11px; }}
.vlab {{ fill:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; }}
.vlab26 {{ fill:var(--y2026); font-size:12px; font-weight:700; font-variant-numeric:tabular-nums; }}
.bar {{ fill:var(--y2024); }} .bar26 {{ fill:var(--y2026); }}
.b20 {{ fill:var(--y2024); }} .b10 {{ fill:var(--y2025); }}
.b20-26 {{ fill:var(--y2026); fill-opacity:.45; }} .b10-26 {{ fill:var(--y2026); }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
@media (max-width:720px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
</style>"""

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT}">
  <h1>El otro extremo: puntajes casi cero · UNAM</h1>
  <p class="sub">Todos los sustentantes de licenciatura, 2021–2026. En un examen
  de opción múltiple, por puro azar casi nadie baja de ~25 aciertos: una cola muy
  baja no debería existir.</p>
  <div class="headline">
    El tramo bajo <b>común</b> (&lt;30 aciertos) casi no cambió: {p30_26:.1f}% en
    2026, como en años previos. Pero apareció una cola <b>ultra-baja</b>:
    <b>{c20_26}</b> sustentantes con &lt;20 aciertos y <b>{c10_26}</b> con &lt;10
    en 2026 — contra un promedio de {c20_prev} y {c10_prev} en 2021–2025.
    Son puntajes casi imposibles por azar.
  </div>
  <div class="grid2">
    <div class="card"><h2>Tramo bajo común (&lt;30) por año</h2>
      <p>Estable en ~2.4–3.2% todos los años, 2026 incluido. Sin anomalía.</p>
      {panel_p30(per)}</div>
    <div class="card"><h2>Cola ultra-baja (&lt;20 y &lt;10) por año</h2>
      <p>Casi inexistente 2021–2025; surge de golpe en 2026.</p>
      {panel_low(per)}</div>
  </div>
  <p class="note">Fuente: resultados DGAE-UNAM 2021–2026. Solo aspirantes que
  presentaron examen (aciertos numérico). Análisis descriptivo: muestra
  corrimientos, no causas. Espejo de <i>Puntajes casi perfectos</i>.</p>
</div>"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per = load()
    for y in YEARS:
        print(f"{y}: <30 {per[y]['p30']*100:.1f}%  <20 {per[y]['c20']}  <10 {per[y]['c10']}")
    inner = build_inner(per)
    (OUT_DIR / "casi_cero_2026.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Casi cero 2026</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_casi_cero_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
