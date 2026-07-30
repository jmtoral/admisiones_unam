"""La base no se movió, pero la línea de ingreso saltó lejísimos.

Igual que base_sin_p75 (densidad de la base ≤ p75 histórico, que coincide entre
años), pero AÑADE el puntaje mínimo necesario para ser admitido — el corte de
ingreso — como líneas verticales: gris = mínimo histórico (2021-2025), rojo =
mínimo 2026. Muestra que la base sigue igual pero el corte para entrar se fue muy
por encima de ella. Eje completo 0-120 para que quepan las líneas.

Mismas ofertas que MÁS cambiaron en total (mayor W1). Análisis descriptivo.

Uso:  python analysis/base_sin_p75_linea.py
Salidas en analysis/output/: base_sin_p75_linea.html + _base_linea_preview.html
"""

from __future__ import annotations

import html as _html
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "consolidated" / "resultados_todos.csv"
MDS = ROOT / "data" / "consolidated" / "metadata_carreras.csv"
OUT_DIR = ROOT / "analysis" / "output"

MIN_N = 50
MIN_SUB = 30
TOP_K = 15
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
XMAX = 120                   # eje completo: la línea de ingreso 2026 llega a ~117
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


def _load_minimos():
    m = pd.read_csv(MDS, dtype=str, keep_default_na=False, na_filter=False)
    m["am"] = pd.to_numeric(m["aciertos_minimos"], errors="coerce")
    m["year"] = m["year"].astype(int)
    m = m[m["am"].notna()]
    out = {}
    for (car, cam, mod), s in m.groupby(["carrera", "campus", "modalidad"]):
        out[(car, cam, mod)] = {int(y): float(v) for y, v in zip(s["year"], s["am"])}
    return out


def load():
    df = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
    df["ac"] = pd.to_numeric(df["aciertos"], errors="coerce")
    df["year"] = df["year"].astype(int)
    pres = df[df["ac"].notna()].copy()
    pres["ac"] = pres["ac"].astype(int)
    minimos = _load_minimos()

    offers = []
    for (car, cam, mod), sub in pres.groupby(["carrera", "campus", "modalidad"]):
        by = {int(y): s["ac"].to_numpy() for y, s in sub.groupby("year")}
        if 2025 not in by or 2026 not in by:
            continue
        if by[2025].size < MIN_N or by[2026].size < MIN_N:
            continue
        mby = minimos.get((car, cam, mod), {})
        if 2026 not in mby:
            continue
        hist = [mby[y] for y in (2021, 2022, 2023, 2024, 2025) if y in mby]
        if not hist:
            continue
        w1 = float(np.abs(_cdf(by[2025]) - _cdf(by[2026])).sum())
        pre = np.concatenate([by[y] for y in by if y <= 2025])
        cutoff = float(np.percentile(pre, 75))
        offers.append({"carrera": car, "campus": cam, "modalidad": mod,
                       "by": by, "w1": w1, "cutoff": cutoff,
                       "min_hist": float(np.mean(hist)), "min_26": mby[2026]})
    offers.sort(key=lambda o: -o["w1"])

    agg = {
        "min_hist": float(np.mean([o["min_hist"] for o in offers])),
        "min_26": float(np.mean([o["min_26"] for o in offers])),
        "n": len(offers),
    }
    return offers, agg


# --------------------------------------------------------------------------- #
FW, FH = 300, 132
ML, MR, MT, MB = 8, 8, 6, 20
BASE, TOPy = FH - MB, MT


def xpos(v):
    return ML + min(v, XMAX) / XMAX * (FW - ML - MR)


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
    for t, anc in ((0, "start"), (60, "middle"), (120, "end")):
        p.append(f'<text x="{xpos(t):.1f}" y="{BASE+15}" class="tickl" text-anchor="{anc}">{t}</text>')
    p.append(f'<line x1="{ML}" y1="{BASE}" x2="{FW-MR}" y2="{BASE}" class="axis"/>')

    def poly(d):
        return " ".join(f'{xpos(GRID[i]):.1f},{BASE - d[i]*amp:.2f}' for i in range(GRID.size))
    # relleno de la base 2026 (detrás de todo)
    if 2026 in dens:
        p.append(f'<polygon class="fill26" points="{ML},{BASE:.1f} '
                 f'{poly(dens[2026])} {xpos(o["cutoff"]):.1f},{BASE:.1f}"/>')
    for y in [yy for yy in YEARS if yy != 2026 and yy in dens]:
        p.append(f'<polyline class="yr y{y}" points="{poly(dens[y])}"/>')
    if 2026 in dens:
        p.append(f'<polyline class="yr y2026" points="{poly(dens[2026])}"/>')

    # líneas verticales del puntaje mínimo de ingreso (encima de las densidades)
    xh, x26 = xpos(o["min_hist"]), xpos(o["min_26"])
    p.append(f'<line x1="{xh:.1f}" y1="{TOPy}" x2="{xh:.1f}" y2="{BASE}" class="minh"/>')
    p.append(f'<line x1="{x26:.1f}" y1="{TOPy}" x2="{x26:.1f}" y2="{BASE}" class="min26"/>')
    p.append(f'<text x="{x26+2.5:.1f}" y="{TOPy+7}" class="minlbl">{o["min_26"]:.0f}</text>')
    p.append('</svg>')
    return "".join(p)


def facet(o):
    mod = "" if o["modalidad"] == "escolarizado" else f' · {o["modalidad"]}'
    return (f'<figure class="facet">'
            f'<figcaption><span class="ca">{esc(o["carrera"].title())}</span>'
            f'<span class="cc">{esc(o["campus"].title())}{esc(mod)}</span></figcaption>'
            f'<div class="badge">base ≤{o["cutoff"]:.0f} · '
            f'ingreso {o["min_hist"]:.0f}<span class="arw">→</span>'
            f'<b>{o["min_26"]:.0f}</b></div>'
            f'{facet_svg(o)}</figure>')


def build_inner(offers, agg):
    top = offers[:TOP_K]
    facets = "".join(facet(o) for o in top)
    top_hist = float(np.mean([o["min_hist"] for o in top]))
    top_26 = float(np.mean([o["min_26"] for o in top]))
    gl = "".join(f"--y{y}:{GREY_LIGHT[y]};" for y in GREY_LIGHT)
    gd = "".join(f"--y{y}:{GREY_DARK[y]};" for y in GREY_DARK)

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --axis:#c3c2b7; --minh:#6f6e67; --border:rgba(11,11,11,.10);
  {gl} --y2026:{HL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1080px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --axis:#383835; --minh:#9a998f;
  --border:rgba(255,255,255,.10); {gd} --y2026:{HL_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --axis:#383835;
  --minh:#9a998f; --border:rgba(255,255,255,.10); {gd} --y2026:{HL_DARK}; }}
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
.legend .v {{ display:inline-block; width:0; height:12px; border-left:2px solid;
  vertical-align:middle; margin-right:7px; }}
.grid-f {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:8px; }}
.facet {{ background:var(--surface-1); border:1px solid var(--border); border-radius:10px; padding:8px 8px 2px; }}
.facet figcaption {{ display:flex; flex-direction:column; line-height:1.25; }}
.facet .ca {{ font-size:12px; font-weight:600; }}
.facet .cc {{ font-size:10.5px; color:var(--muted); }}
.facet .badge {{ font-size:10px; color:var(--muted); font-variant-numeric:tabular-nums; margin:2px 0 0; }}
.facet .badge b {{ color:var(--y2026); }} .facet .arw {{ margin:0 2px; }}
.axis {{ stroke:var(--axis); stroke-width:1; }}
.minh {{ stroke:var(--minh); stroke-width:1.4; stroke-dasharray:2 2; }}
.min26 {{ stroke:var(--y2026); stroke-width:2; }}
.minlbl {{ fill:var(--y2026); font-size:9px; font-weight:600; font-variant-numeric:tabular-nums; }}
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
        '<span><i style="border-color:var(--y2021)"></i>base 2021</span>'
        '<span><i style="border-color:var(--y2025);border-top-width:2px"></i>base 2025</span>'
        '<span><i style="border-color:var(--y2026);border-top-width:3px"></i>'
        '<b style="color:var(--y2026)">base 2026</b></span>'
        '<span style="margin-left:auto">'
        '<span class="v" style="border-color:var(--minh);border-left-style:dashed"></span>'
        'mín. ingreso histórico &nbsp;'
        '<span class="v" style="border-color:var(--y2026)"></span>'
        '<b style="color:var(--y2026)">mín. ingreso 2026</b></span></div>')

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT}">
  <h1>La base no se movió — la línea para entrar sí · UNAM</h1>
  <p class="sub">Cada panel repite la densidad de la <b>base</b> (solo quienes
  quedaron ≤ el p75 histórico de la oferta): las curvas de todos los años quedan
  <b>encimadas</b>. Encima se marcan las líneas del <b>puntaje mínimo necesario
  para ser admitido</b>: gris = histórico (2021–2025), <b style="color:var(--y2026)">roja
  = 2026</b>.</p>
  <p class="method"><b>Paneles:</b> las {TOP_K} ofertas que MÁS cambiaron en total
  (mayor distancia de Wasserstein 2026 vs 2025). Eje 0–120 (rango completo).</p>
  <div class="headline">
    La base es la misma, pero <b>el corte para entrar se disparó</b>: en estas
    ofertas el puntaje mínimo de ingreso pasó de <b>~{top_hist:.0f}</b> aciertos
    (histórico) a <b>~{top_26:.0f} en 2026</b>. La línea roja cae muy a la
    derecha de la base — casi nadie de la base fue admitido.
  </div>
  {legend}
  <div class="grid-f">{facets}</div>
  <p class="note">Fuente: resultados DGAE-UNAM 2021–2026 (densidad de aciertos) y
  campo <i>Aciertos Mínimos</i> (puntaje del último admitido). Base = subconjunto
  ≤ p75 histórico por oferta; densidad por KDE gaussiano. Mínimo histórico = promedio
  2021–2025. Análisis descriptivo.</p>
</div>"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, agg = load()
    print(f"ofertas con mínimo de ingreso: {agg['n']}")
    print(f"top-{TOP_K} mín. ingreso: hist ~{agg['min_hist']:.0f} -> 2026 ~{agg['min_26']:.0f}")
    inner = build_inner(offers, agg)
    (OUT_DIR / "base_sin_p75_linea.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Base sin p75 + línea de ingreso</title></head>"
               "<body style='margin:0'>" + inner + "</body></html>")
    (OUT_DIR / "_base_linea_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
