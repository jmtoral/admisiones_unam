"""Puntaje mínimo de ingreso (aciertos mínimos) — evolución 2021-2026.

Réplica extendida del comparativo de "puntaje mínimo de ingreso" que circuló en
redes. El puntaje mínimo = campo `Aciertos Mínimos` del <h5> (aciertos de la
persona admitida con menor puntaje). Se muestran las TOP 50 ofertas por
incremento 2025->2026, con su trayectoria completa 2021-2026 (no solo el salto).

Unidad = carrera + campus + modalidad. Años 2021-2025 sobrios, 2026 resaltado.
Análisis descriptivo.

Uso:  python analysis/minimo_ingreso.py
Salidas en analysis/output/: minimo_ingreso.html/.png/_dark.png + minimo_ingreso.csv
"""

from __future__ import annotations

import html as _html
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "consolidated" / "metadata_carreras.csv"
OUT_DIR = ROOT / "analysis" / "output"

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
TOP_K = 50
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"


def load():
    m = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
    m["am"] = pd.to_numeric(m["aciertos_minimos"], errors="coerce")
    m["asp"] = pd.to_numeric(m["aspirantes"], errors="coerce")
    m["year"] = m["year"].astype(int)
    m = m[m["am"].notna()]

    offers = []
    for (car, cam, mod), sub in m.groupby(["carrera", "campus", "modalidad"]):
        by = dict(zip(sub["year"], sub["am"]))
        if 2025 not in by or 2026 not in by:
            continue
        asp26 = sub.loc[sub["year"] == 2026, "asp"]
        offers.append({
            "carrera": car, "campus": cam, "modalidad": mod,
            "by": {int(y): float(v) for y, v in by.items()},
            "inc": by[2026] - by[2025],
            "asp26": int(asp26.iloc[0]) if len(asp26) and not np.isnan(asp26.iloc[0]) else 0,
        })
    offers.sort(key=lambda o: -o["inc"])

    def mean_inc(a, b):
        d = [o["by"][b] - o["by"][a] for o in offers if a in o["by"] and b in o["by"]]
        return (float(np.mean(d)) if d else 0.0)
    summary = {
        "n": len(offers),
        "up": sum(1 for o in offers if o["inc"] > 0),
        "down": sum(1 for o in offers if o["inc"] < 0),
        "mean_2526": mean_inc(2025, 2026),
        "prev": {f"{a}-{b}": mean_inc(a, b) for a, b in zip(YEARS, YEARS[1:-1])},
    }
    return offers, summary


# --------------------------------------------------------------------------- #
# Sparkline por oferta
# --------------------------------------------------------------------------- #
FW, FH = 214, 66
ML, MR, MT, MB = 8, 8, 8, 8
BASE, TOPy = FH - MB, MT


def xpos(y):
    return ML + (y - 2021) / 5 * (FW - ML - MR)


def esc(s):
    return _html.escape(str(s))


def spark(o):
    ys = sorted(o["by"])
    vals = [o["by"][y] for y in ys]
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.18, 2)
    lo, hi = lo - pad, hi + pad

    def yp(v):
        return BASE - (v - lo) / (hi - lo) * (BASE - TOPy)

    pre = [y for y in ys if y <= 2025]
    p = [f'<svg viewBox="0 0 {FW} {FH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    # línea gris 2021-2025
    if len(pre) >= 2:
        pts = " ".join(f'{xpos(y):.1f},{yp(o["by"][y]):.1f}' for y in pre)
        p.append(f'<polyline class="ln" points="{pts}"/>')
    # segmento rojo 2025->2026
    if 2025 in o["by"] and 2026 in o["by"]:
        p.append(f'<line class="ln26" x1="{xpos(2025):.1f}" y1="{yp(o["by"][2025]):.1f}" '
                 f'x2="{xpos(2026):.1f}" y2="{yp(o["by"][2026]):.1f}"/>')
    # puntos grises + punto rojo 2026
    for y in pre:
        p.append(f'<circle class="dot" cx="{xpos(y):.1f}" cy="{yp(o["by"][y]):.1f}" r="1.7"/>')
    p.append(f'<circle class="dot26" cx="{xpos(2026):.1f}" cy="{yp(o["by"][2026]):.1f}" r="2.8"/>')
    p.append('</svg>')
    return "".join(p)


def card(o):
    mod = "" if o["modalidad"] == "escolarizado" else f' · {o["modalidad"]}'
    asp = f' · {o["asp26"]:,} asp' if o["asp26"] else ""
    return (
        f'<figure class="facet">'
        f'<figcaption><span class="ca">{esc(o["carrera"].title())}</span>'
        f'<span class="cc">{esc(o["campus"].title())}{esc(mod)}</span></figcaption>'
        f'<div class="badge">mín {o["by"][2025]:.0f} → {o["by"][2026]:.0f} '
        f'<b>(+{o["inc"]:.0f})</b><span class="asp">{esc(asp)}</span></div>'
        f'{spark(o)}</figure>')


def build_inner(offers, summary):
    top = offers[:TOP_K]
    facets = "".join(card(o) for o in top)
    prev_txt = ", ".join(f"{k.replace('-', '→')}: {v:+.1f}"
                         for k, v in summary["prev"].items())
    rows = "".join(
        f'<tr><td class=c>{esc(o["carrera"].title())}</td>'
        f'<td class=c>{esc(o["campus"].title())}</td><td>{esc(o["modalidad"])}</td>'
        + "".join(f'<td>{o["by"][y]:.0f}</td>' if y in o["by"] else "<td>·</td>"
                  for y in YEARS)
        + f'<td class=hl>+{o["inc"]:.0f}</td></tr>'
        for o in top)
    table = ('<table class=tbl><thead><tr><th class=c>Carrera</th><th class=c>Campus</th>'
             '<th>Modalidad</th>' + "".join(f'<th>{y}</th>' for y in YEARS)
             + '<th>Δ25→26</th></tr></thead><tbody>' + rows + '</tbody></table>')

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --line:#8a8980; --dot:#a1a099; --grid:#e1e0d9; --axis:#c3c2b7;
  --border:rgba(11,11,11,.10); --y2026:{HL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1160px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --line:#77766d; --dot:#68675f;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10); --y2026:{HL_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --line:#77766d;
  --dot:#68675f; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10); --y2026:{HL_DARK}; }}
.viz-root h1 {{ font-size:22px; margin:0 0 4px; text-wrap:balance; }}
.sub {{ color:var(--text-secondary); font-size:14px; margin:0 0 3px; line-height:1.5; }}
.method {{ color:var(--muted); font-size:12.5px; margin:0 0 2px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--y2026); border-radius:8px; padding:11px 13px;
  margin:12px 0; font-size:14px; line-height:1.55; }}
.headline b {{ color:var(--y2026); }}
.legend {{ display:flex; gap:16px; align-items:center; font-size:12.5px;
  color:var(--text-secondary); margin:8px 0 10px; flex-wrap:wrap; }}
.legend i {{ display:inline-block; width:20px; border-top:2px solid; vertical-align:middle; margin-right:6px; }}
.grid-f {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:9px; }}
.facet {{ background:var(--surface-1); border:1px solid var(--border);
  border-radius:9px; padding:7px 8px 3px; margin:0; }}
.facet figcaption {{ display:flex; flex-direction:column; line-height:1.2; }}
.facet .ca {{ font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.facet .cc {{ font-size:10px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.facet .badge {{ font-size:10.5px; color:var(--text-secondary); font-variant-numeric:tabular-nums; margin:2px 0 1px; }}
.facet .badge b {{ color:var(--y2026); }} .facet .asp {{ color:var(--muted); }}
.ln {{ fill:none; stroke:var(--line); stroke-width:1.5; }}
.ln26 {{ stroke:var(--y2026); stroke-width:2.4; }}
.dot {{ fill:var(--dot); }} .dot26 {{ fill:var(--y2026); }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
details {{ margin-top:16px; }} summary {{ cursor:pointer; color:var(--text-secondary); font-size:13px; }}
.scroll {{ overflow-x:auto; }}
.tbl {{ border-collapse:collapse; width:100%; margin-top:10px; font-size:11.5px; }}
.tbl th,.tbl td {{ text-align:right; padding:3px 7px; border-bottom:1px solid var(--border);
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tbl th.c,.tbl td.c {{ text-align:left; font-variant-numeric:normal; }}
.tbl thead th {{ color:var(--text-secondary); font-weight:600; }}
.tbl td.hl {{ color:var(--y2026); font-weight:600; }}
@media (max-width:900px) {{ .grid-f {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
@media (max-width:560px) {{ .grid-f {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
</style>"""

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT}">
  <h1>Puntaje mínimo de ingreso: la evolución 2021–2026 · UNAM</h1>
  <p class="sub">Puntaje mínimo = aciertos de la persona admitida con menor
  puntaje (campo <i>Aciertos Mínimos</i> de la DGAE), por carrera-campus.
  Cada mini-gráfica es la trayectoria del mínimo; <b>2021–2025 en gris</b>,
  <b style="color:var(--y2026)">salto a 2026 en rojo</b>.</p>
  <p class="method"><b>Cómo se eligen:</b> las <b>{TOP_K}</b> ofertas con mayor
  incremento del puntaje mínimo de 2025 a 2026 (todas las modalidades).</p>
  <div class="headline">
    El puntaje mínimo subió en <b>{summary['up']} de {summary['n']}</b> ofertas
    comparables de 2025 a 2026 (bajó en {summary['down']}). El alza media fue de
    <b>+{summary['mean_2526']:.1f} puntos</b>, frente a {prev_txt} en las
    transiciones previas.
  </div>
  <div class="legend">
    <span><i style="border-color:var(--line)"></i>2021–2025</span>
    <span><i style="border-color:var(--y2026);border-top-width:3px"></i>
    <b style="color:var(--y2026)">2026</b></span>
    <span style="margin-left:auto">cada panel: eje Y propio (resalta la forma)</span>
  </div>
  <div class="grid-f">{facets}</div>
  <details><summary>Ver tabla (mínimo por año, {len(top)} ofertas)</summary>
    <div class="scroll">{table}</div></details>
  <p class="note">Fuente: resultados DGAE-UNAM 2021–2026 (campo Aciertos Mínimos).
  El eje Y de cada panel se escala a su propio rango (destaca la forma, no compara
  niveles absolutos entre paneles; ver la tabla para los valores). Ofertas
  pequeñas (pocos aspirantes) tienen un mínimo más volátil. Análisis descriptivo.</p>
</div>"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, summary = load()
    print(f"ofertas comparables: {summary['n']} (subió {summary['up']}, bajó {summary['down']})")
    print(f"alza media mínimo 2025→2026: +{summary['mean_2526']:.2f}  | previas: {summary['prev']}")
    print("Top 10:")
    for o in offers[:10]:
        print(f"  +{o['inc']:.0f}  {o['by'][2025]:.0f}->{o['by'][2026]:.0f}  "
              f"{o['carrera'][:30]} — {o['campus'][:24]} [{o['modalidad']}]")

    pd.DataFrame([{
        "carrera": o["carrera"], "campus": o["campus"], "modalidad": o["modalidad"],
        **{f"min_{y}": o["by"].get(y, "") for y in YEARS},
        "inc_25_26": o["inc"], "aspirantes_2026": o["asp26"],
    } for o in offers]).to_csv(OUT_DIR / "minimo_ingreso.csv", index=False, encoding="utf-8")

    inner = build_inner(offers, summary)
    (OUT_DIR / "minimo_ingreso.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Puntaje mínimo</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_minimo_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
