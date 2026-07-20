"""¿La base de la distribución es la misma? (quitando el cuartil superior)

Como comparativa_2026, pero cada densidad se calcula SOLO con quienes sacaron
<= el p75 histórico (2021-2025) de esa oferta. Si el cambio de 2026 fuera solo un
bulto de puntajes altos añadido, la base (debajo del corte) debería coincidir
entre 2021-2025 y 2026. Spoiler del dato: coincide.

Se muestran las mismas ofertas que MÁS cambiaron en total (mayor W1), para probar
que incluso ahí la base es igual. Análisis descriptivo.

Uso:  python analysis/base_sin_p75.py
Salidas en analysis/output/: base_sin_p75.html + _base_preview.html
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "consolidated" / "resultados_todos.csv"
OUT_DIR = ROOT / "analysis" / "output"

MIN_N = 50
MIN_SUB = 30
TOP_K = 15
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
XMAX = 80                    # eje x acotado a la base
GRID = np.arange(0, XMAX + 1, 1.0)

GREY_LIGHT = {2021: "#d7d6cf", 2022: "#bfbeb4", 2023: "#a1a099",
              2024: "#83827b", 2025: "#5c5b55"}
GREY_DARK = {2021: "#3a3a37", 2022: "#4f4e49", 2023: "#68675f",
             2024: "#8a897f", 2025: "#b4b3a7"}
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"


def gaussian_kde(sample, grid):
    n = sample.size
    std = sample.std(ddof=1) if n > 1 else 1.0
    iqr = np.subtract(*np.percentile(sample, [75, 25]))
    spread = min(std, iqr / 1.349) if iqr > 0 else std
    h = max(0.9 * spread * n ** (-0.2), 2.0)
    u = (grid[:, None] - sample[None, :]) / h
    k = np.exp(-0.5 * u * u) / np.sqrt(2 * np.pi)
    return k.mean(axis=1) / h


def _cdf(vals):
    c = np.bincount(vals, minlength=121)[:121]
    return np.cumsum(c) / c.sum()


def load():
    df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
    df["ac"] = pd.to_numeric(df["aciertos"], errors="coerce")
    df["year"] = df["year"].astype(int)
    pres = df[df["ac"].notna()].copy()
    pres["ac"] = pres["ac"].astype(int)

    offers = []
    for (car, cam, mod), sub in pres.groupby(["carrera", "campus", "modalidad"]):
        by = {int(y): s["ac"].to_numpy() for y, s in sub.groupby("year")}
        if 2025 not in by or 2026 not in by:
            continue
        if by[2025].size < MIN_N or by[2026].size < MIN_N:
            continue
        w1 = float(np.abs(_cdf(by[2025]) - _cdf(by[2026])).sum())
        pre = np.concatenate([by[y] for y in by if y <= 2025])
        cutoff = float(np.percentile(pre, 75))
        offers.append({"carrera": car, "campus": cam, "modalidad": mod,
                       "by": by, "w1": w1, "cutoff": cutoff})
    offers.sort(key=lambda o: -o["w1"])

    # % que quedó por encima del corte histórico (agregado), por año
    pre_all = pres[pres["year"] <= 2025]["ac"].to_numpy()
    gcut = float(np.percentile(pre_all, 75))
    frac_above = {}
    for y, s in pres.groupby("year"):
        a = s["ac"].to_numpy()
        frac_above[int(y)] = float(np.mean(a > gcut))
    return offers, gcut, frac_above


# --------------------------------------------------------------------------- #
FW, FH = 300, 172
ML, MR, MT, MB = 8, 8, 8, 22
BASE, TOPy = FH - MB, MT


def xpos(v):
    return ML + v / XMAX * (FW - ML - MR)


def esc(s):
    return _html.escape(str(s))


def facet_svg(o):
    dens = {}
    for y in o["by"]:
        sub = o["by"][y][o["by"][y] <= o["cutoff"]]
        if sub.size >= MIN_SUB or y in (2025, 2026):
            if sub.size >= 5:
                dens[y] = gaussian_kde(sub, GRID)
    gmax = max((d.max() for d in dens.values()), default=1.0)
    amp = (BASE - TOPy) / gmax

    p = [f'<svg viewBox="0 0 {FW} {FH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    for t, anc in ((0, "start"), (40, "middle"), (80, "end")):
        p.append(f'<text x="{xpos(t):.1f}" y="{BASE+15}" class="tickl" text-anchor="{anc}">{t}</text>')
    p.append(f'<line x1="{ML}" y1="{BASE}" x2="{FW-MR}" y2="{BASE}" class="axis"/>')
    # línea del corte (p75 histórico)
    cx = xpos(min(o["cutoff"], XMAX))
    p.append(f'<line x1="{cx:.1f}" y1="{TOPy}" x2="{cx:.1f}" y2="{BASE}" class="cut"/>')

    def poly(d):
        return " ".join(f'{xpos(GRID[i]):.1f},{BASE - d[i]*amp:.2f}' for i in range(GRID.size))
    # relleno de 2026 (peso visual, detrás de las líneas para no tapar el traslape)
    if 2026 in dens:
        p.append(f'<polygon class="fill26" points="{ML},{BASE:.1f} '
                 f'{poly(dens[2026])} {FW-MR},{BASE:.1f}"/>')
    for y in [yy for yy in YEARS if yy != 2026 and yy in dens]:
        p.append(f'<polyline class="yr y{y}" points="{poly(dens[y])}"/>')
    if 2026 in dens:
        p.append(f'<polyline class="yr y2026" points="{poly(dens[2026])}"/>')
    p.append('</svg>')
    return "".join(p)


def facet(o):
    mod = "" if o["modalidad"] == "escolarizado" else f' · {o["modalidad"]}'
    return (f'<figure class="facet">'
            f'<figcaption><span class="ca">{esc(o["carrera"].title())}</span>'
            f'<span class="cc">{esc(o["campus"].title())}{esc(mod)}</span></figcaption>'
            f'<div class="badge">base ≤ p75 histórico ({o["cutoff"]:.0f})</div>'
            f'{facet_svg(o)}</figure>')


def build_inner(offers, gcut, frac_above):
    top = offers[:TOP_K]
    facets = "".join(facet(o) for o in top)
    fa_prev = np.mean([frac_above[y] for y in (2021, 2022, 2023, 2024, 2025)]) * 100
    fa_26 = frac_above[2026] * 100
    gl = "".join(f"--y{y}:{GREY_LIGHT[y]};" for y in GREY_LIGHT)
    gd = "".join(f"--y{y}:{GREY_DARK[y]};" for y in GREY_DARK)

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --axis:#c3c2b7; --cut:#c3c2b7; --border:rgba(11,11,11,.10);
  {gl} --y2026:{HL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1080px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --axis:#383835; --cut:#4a4a46;
  --border:rgba(255,255,255,.10); {gd} --y2026:{HL_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --axis:#383835;
  --cut:#4a4a46; --border:rgba(255,255,255,.10); {gd} --y2026:{HL_DARK}; }}
.viz-root h1 {{ font-size:20px; margin:0 0 4px; text-wrap:balance; }}
.sub {{ color:var(--text-secondary); font-size:13px; margin:0 0 3px; line-height:1.5; }}
.method {{ color:var(--muted); font-size:12px; margin:0 0 2px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--y2026); border-radius:8px; padding:10px 12px;
  margin:12px 0; font-size:13.5px; line-height:1.5; }}
.headline b {{ color:var(--y2026); }}
.legend {{ display:flex; gap:16px; align-items:center; font-size:12px;
  color:var(--text-secondary); margin:10px 0 4px; flex-wrap:wrap; }}
.legend i {{ display:inline-block; width:22px; border-top:2px solid; vertical-align:middle; margin-right:6px; }}
.grid-f {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:8px; }}
.facet {{ background:var(--surface-1); border:1px solid var(--border); border-radius:10px; padding:8px 8px 2px; }}
.facet figcaption {{ display:flex; flex-direction:column; line-height:1.25; }}
.facet .ca {{ font-size:12px; font-weight:600; }}
.facet .cc {{ font-size:10.5px; color:var(--muted); }}
.facet .badge {{ font-size:10px; color:var(--muted); font-variant-numeric:tabular-nums; margin:2px 0 0; }}
.axis {{ stroke:var(--axis); stroke-width:1; }}
.cut {{ stroke:var(--cut); stroke-width:1; stroke-dasharray:3 3; }}
.tickl {{ fill:var(--muted); font-size:9.5px; font-variant-numeric:tabular-nums; }}
.fill26 {{ fill:var(--y2026); fill-opacity:.11; stroke:none; }}
.yr {{ fill:none; stroke-width:1.5; }}
.y2021 {{ stroke:var(--y2021); }} .y2022 {{ stroke:var(--y2022); }}
.y2023 {{ stroke:var(--y2023); }} .y2024 {{ stroke:var(--y2024); }}
.y2025 {{ stroke:var(--y2025); stroke-width:1.7; }}
.y2026 {{ stroke:var(--y2026); stroke-width:2.4; }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
@media (max-width:720px) {{ .grid-f {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
</style>"""

    legend = (
        '<div class="legend">'
        '<span><i style="border-color:var(--y2021)"></i>2021</span>'
        '<span><i style="border-color:var(--y2023)"></i>2023</span>'
        '<span><i style="border-color:var(--y2025);border-top-width:2px"></i>2025</span>'
        '<span><i style="border-color:var(--y2026);border-top-width:3px"></i>'
        '<b style="color:var(--y2026)">2026</b></span>'
        '<span style="margin-left:auto">┊ corte = p75 histórico</span></div>')

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT}">
  <h1>Quita el cuartil superior: la base es la misma · UNAM</h1>
  <p class="sub">Densidad de aciertos usando <b>solo a quienes quedaron por debajo
  del p75 histórico</b> (2021–2025) de cada oferta. Si el resto de la distribución
  no cambió, las curvas de todos los años deben quedar <b>encimadas</b>.</p>
  <p class="method"><b>Paneles:</b> las {TOP_K} ofertas que MÁS cambiaron en total
  (mayor distancia de Wasserstein 2026 vs 2025) — para probar que incluso ahí la
  base es igual.</p>
  <div class="headline">
    Debajo del corte, la distribución de <b>2026 coincide</b> con 2021–2025. El
    cambio está solo arriba: en promedio ~{fa_prev:.0f}% de los aspirantes superaba
    ese techo en años previos (por definición, ~25%); en <b>2026 lo superó
    {fa_26:.0f}%</b>. La base no mejoró — un subgrupo se fue por encima.
  </div>
  {legend}
  <div class="grid-f">{facets}</div>
  <p class="note">Fuente: resultados DGAE-UNAM 2021–2026. Solo quienes presentaron
  examen. Corte = p75 de 2021–2025 por oferta; cada densidad se calcula con el
  subconjunto ≤ corte. Densidad por KDE gaussiano. Análisis descriptivo.</p>
</div>"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, gcut, fa = load()
    print(f"corte global p75(2021-2025) = {gcut:.0f}")
    print("% por encima del corte por año:", {y: round(fa[y]*100, 1) for y in YEARS})
    inner = build_inner(offers, gcut, fa)
    (OUT_DIR / "base_sin_p75.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Base sin p75</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_base_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
