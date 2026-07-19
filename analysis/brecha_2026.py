"""Brecha y forma de la distribución de aciertos, 2021-2026.

¿En 2026 todo subió parejo o cambió la forma? Fan de percentiles (p10, p25,
mediana, p75, p90) del aciertos por año, más el corte mínimo de ingreso (mediana
de `aciertos_minimos`). Muestra que la distribución no se comprimió: se ensanchó,
la mitad alta se disparó y la baja apenas se movió.

Todos los sustentantes de licenciatura. Análisis descriptivo.

Uso:  python analysis/brecha_2026.py
Salidas en analysis/output/: brecha_2026.html + _brecha_preview.html
"""

from __future__ import annotations

import html as _html
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data" / "consolidated"
OUT_DIR = ROOT / "analysis" / "output"

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
BLUE_L, BLUE_D = "#3987e5", "#6da7ec"
HL_L, HL_D = "#e0342a", "#ff5c4f"


def load():
    res = pd.read_csv(D / "resultados_todos.csv", dtype=str, keep_default_na=False, na_filter=False)
    meta = pd.read_csv(D / "metadata_carreras.csv", dtype=str, keep_default_na=False, na_filter=False)
    res["ac"] = pd.to_numeric(res["aciertos"], errors="coerce")
    res["year"] = res["year"].astype(int)
    meta["am"] = pd.to_numeric(meta["aciertos_minimos"], errors="coerce")
    meta["year"] = meta["year"].astype(int)
    pres = res[res["ac"].notna()]
    per = {}
    for y, s in pres.groupby("year"):
        ac = s["ac"].to_numpy()
        corte = meta[meta["year"] == y]["am"].dropna()
        per[int(y)] = {
            "p10": float(np.percentile(ac, 10)), "p25": float(np.percentile(ac, 25)),
            "med": float(np.median(ac)), "p75": float(np.percentile(ac, 75)),
            "p90": float(np.percentile(ac, 90)),
            "corte": float(np.median(corte)),
        }
    return per


def esc(s):
    return _html.escape(str(s))


PW, PH = 900, 440
ML, MR, MT, MB = 46, 96, 20, 40
X0, X1 = ML, PW - MR
Y_LO, Y_HI = 25, 112


def xp(y):
    return X0 + (y - 2021) / 5 * (X1 - X0)


def yp(v):
    return (PH - MB) - (v - Y_LO) / (Y_HI - Y_LO) * (PH - MB - MT)


def _band(per, lo, hi, cls):
    top = " ".join(f'{xp(y):.1f},{yp(per[y][hi]):.1f}' for y in YEARS)
    bot = " ".join(f'{xp(y):.1f},{yp(per[y][lo]):.1f}' for y in reversed(YEARS))
    return f'<polygon class="{cls}" points="{top} {bot}"/>'


def _line(per, k, cls):
    pts = " ".join(f'{xp(y):.1f},{yp(per[y][k]):.1f}' for y in YEARS)
    return f'<polyline class="{cls}" points="{pts}"/>'


def build_svg(per) -> str:
    p = [f'<svg viewBox="0 0 {PW} {PH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    for v in (40, 60, 80, 100):
        p.append(f'<line x1="{X0}" y1="{yp(v):.1f}" x2="{X1}" y2="{yp(v):.1f}" class="grid"/>')
        p.append(f'<text x="{X0-8}" y="{yp(v)+4:.1f}" class="axl" text-anchor="end">{v}</text>')
    for y in YEARS:
        p.append(f'<text x="{xp(y):.1f}" y="{PH-MB+18:.1f}" class="{"axl26" if y==2026 else "axl"}" '
                 f'text-anchor="middle">{y}</text>')
    p.append(f'<text x="{X0}" y="{yp(Y_HI)-2:.1f}" class="axl" text-anchor="start">aciertos</text>')

    p.append(_band(per, "p10", "p90", "band-out"))
    p.append(_band(per, "p25", "p75", "band-iqr"))
    p.append(_line(per, "corte", "corte"))
    p.append(_line(per, "med", "med"))
    for y in YEARS:
        p.append(f'<circle cx="{xp(y):.1f}" cy="{yp(per[y]["med"]):.1f}" r="{3.2 if y==2026 else 2.4}" '
                 f'class="{"dot26" if y==2026 else "dot"}"/>')

    # etiquetas a la derecha (2026)
    lab = [("p90", per[2026]["p90"], "p90"), ("p75", per[2026]["p75"], "p75"),
           ("mediana", per[2026]["med"], "med-lab"), ("corte mín.", per[2026]["corte"], "corte-lab"),
           ("p25", per[2026]["p25"], "p25"), ("p10", per[2026]["p10"], "p10")]
    for name, val, cls in lab:
        p.append(f'<text x="{X1+8}" y="{yp(val)+4:.1f}" class="rlab {cls}">{name} {val:.0f}</text>')
    p.append('</svg>')
    return "".join(p)


def build_inner(per) -> str:
    iqr21 = per[2021]["p75"] - per[2021]["p25"]
    iqr26 = per[2026]["p75"] - per[2026]["p25"]
    d_p75 = per[2026]["p75"] - per[2025]["p75"]
    d_p10 = per[2026]["p10"] - per[2025]["p10"]
    d_med = per[2026]["med"] - per[2025]["med"]

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --blue:{BLUE_L}; --hl:{HL_L};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1000px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --blue:{BLUE_D}; --hl:{HL_D}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a;
  --axis:#383835; --border:rgba(255,255,255,.10); --blue:{BLUE_D}; --hl:{HL_D}; }}
.viz-root h1 {{ font-size:22px; margin:0 0 4px; text-wrap:balance; }}
.sub {{ color:var(--text-secondary); font-size:14px; margin:0 0 10px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--hl); border-radius:8px; padding:11px 13px;
  margin:12px 0 14px; font-size:14px; line-height:1.55; }}
.headline b {{ color:var(--hl); }}
.card {{ background:var(--surface-1); border:1px solid var(--border); border-radius:10px; padding:14px 12px 8px; }}
.legend {{ display:flex; gap:16px; align-items:center; font-size:12.5px;
  color:var(--text-secondary); margin:4px 0 10px; flex-wrap:wrap; }}
.legend .sw {{ display:inline-block; width:20px; height:11px; border-radius:3px; vertical-align:middle; margin-right:6px; border:1px solid var(--border); }}
.legend i {{ display:inline-block; width:22px; border-top:2px solid; vertical-align:middle; margin-right:6px; }}
.grid {{ stroke:var(--grid); stroke-width:1; }}
.axl {{ fill:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }}
.axl26 {{ fill:var(--hl); font-size:12.5px; font-weight:700; font-variant-numeric:tabular-nums; }}
.band-out {{ fill:var(--blue); fill-opacity:.16; }}
.band-iqr {{ fill:var(--blue); fill-opacity:.34; }}
.med {{ fill:none; stroke:var(--text-primary); stroke-width:2.6; }}
.corte {{ fill:none; stroke:var(--hl); stroke-width:2; stroke-dasharray:5 4; }}
.dot {{ fill:var(--text-primary); }} .dot26 {{ fill:var(--text-primary); }}
.rlab {{ font-size:11.5px; font-variant-numeric:tabular-nums; }}
.rlab.p90,.rlab.p75,.rlab.p25,.rlab.p10 {{ fill:var(--text-secondary); }}
.rlab.med-lab {{ fill:var(--text-primary); font-weight:700; }}
.rlab.corte-lab {{ fill:var(--hl); font-weight:700; }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
</style>"""

    legend = (
        '<div class="legend">'
        '<span><span class="sw" style="background:var(--blue);opacity:.34"></span>rango intercuartil (p25–p75)</span>'
        '<span><span class="sw" style="background:var(--blue);opacity:.16"></span>p10–p90</span>'
        '<span><i style="border-color:var(--text-primary);border-top-width:3px"></i>mediana</span>'
        '<span><i style="border-color:var(--hl);border-top-style:dashed"></i>corte mínimo de ingreso</span>'
        '</div>')

    return f"""{css}
<div class="viz-root" data-palette="{BLUE_L},{HL_L}">
  <h1>¿Subieron parejo? La forma de la distribución · UNAM</h1>
  <p class="sub">Percentiles del aciertos de todos los sustentantes por año
  (p10, p25, mediana, p75, p90) y el corte mínimo de ingreso. Si todo subiera
  parejo, la banda solo se desplazaría hacia arriba sin cambiar de grosor.</p>
  <div class="headline">
    En 2026 la distribución <b>no se comprimió: se ensanchó</b>. El cuartil alto
    (p75) saltó <b>+{d_p75:.0f}</b> y la mediana +{d_med:.0f}, pero el bajo (p10)
    solo +{d_p10:.0f}. El rango intercuartil pasó de <b>{iqr21:.0f} a {iqr26:.0f}</b>
    aciertos: la mitad de arriba se disparó y la de abajo se quedó.
  </div>
  {legend}
  <div class="card">{build_svg(per)}</div>
  <p class="note">Fuente: resultados DGAE-UNAM 2021–2026. Solo quienes presentaron
  examen. Corte mínimo = mediana de <i>Aciertos Mínimos</i> entre ofertas.
  Análisis descriptivo: muestra corrimientos, no causas.</p>
</div>"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per = load()
    for y in YEARS:
        d = per[y]
        print(f"{y}: p10={d['p10']:.0f} p25={d['p25']:.0f} med={d['med']:.0f} "
              f"p75={d['p75']:.0f} p90={d['p90']:.0f} corte={d['corte']:.0f}")
    inner = build_inner(per)
    (OUT_DIR / "brecha_2026.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Brecha 2026</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_brecha_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
