"""Puntaje mínimo de ingreso, 2021-2026 + Control: la línea continúa.

Extiende `minimo_ingreso.py`: agrega el examen de control presencial (ver
`scrape_control.py`) como una 7a posición en la trayectoria del puntaje
mínimo de cada oferta — el salto 2025→2026 (rojo) sigue con un tramo
2026→Control (azul). El tamaño de cada punto ya no es fijo: representa el
número de admitidos (`seleccionados`) en esa fase.

Unidad = carrera + campus + modalidad. Mismo criterio de selección que
`minimo_ingreso.py` (top 50 por incremento 2025→2026), restringido a las
ofertas que también tienen dato de control (para que la línea tenga con qué
continuar). Análisis descriptivo.

Uso:  python analysis/minimo_ingreso_control.py
Salidas en analysis/output/: minimo_ingreso_control.html/.png/_dark.png + .csv
"""

from __future__ import annotations

import html as _html
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ANALYSIS_DIR))
from examen_control_resultados import _canonicalize_control  # noqa: E402

SRC = ROOT / "data" / "consolidated" / "metadata_carreras.csv"
SRC_CONTROL = ROOT / "data" / "consolidated" / "metadata_control_2026.csv"
OUT_DIR = ROOT / "analysis" / "output"

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
POS = YEARS + ["control"]                       # 7 posiciones en el eje x
TOP_K = 50
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"         # 2026 (rojo, ya establecido)
CTRL_LIGHT, CTRL_DARK = "#2f6fb0", "#6fa8dc"     # control (azul, ya establecido)


def load():
    m = pd.read_csv(SRC, dtype=str, keep_default_na=False, na_filter=False)
    m["am"] = pd.to_numeric(m["aciertos_minimos"], errors="coerce")
    m["sel"] = pd.to_numeric(m["seleccionados"], errors="coerce")
    m["year"] = m["year"].astype(int)
    m = m[m["am"].notna()]

    mc = pd.read_csv(SRC_CONTROL, dtype=str, keep_default_na=False, na_filter=False)
    mc["am"] = pd.to_numeric(mc["aciertos_minimos"], errors="coerce")
    mc["sel"] = pd.to_numeric(mc["seleccionados"], errors="coerce")
    mc = _canonicalize_control(mc)
    mc = mc[mc["am"].notna()]
    ctrl_by_key = {(r["carrera"], r["campus"], r["modalidad"]): (r["am"], r["sel"])
                   for _, r in mc.iterrows()}

    offers = []
    for (car, cam, mod), sub in m.groupby(["carrera", "campus", "modalidad"]):
        by = dict(zip(sub["year"], sub["am"]))
        sel = dict(zip(sub["year"], sub["sel"]))
        if 2025 not in by or 2026 not in by:
            continue
        ctrl = ctrl_by_key.get((car, cam, mod))
        if ctrl is None or np.isnan(ctrl[0]):
            continue
        by["control"] = float(ctrl[0])
        sel["control"] = float(ctrl[1]) if not np.isnan(ctrl[1]) else 0.0

        offers.append({
            "carrera": car, "campus": cam, "modalidad": mod,
            "by": {k: float(v) for k, v in by.items() if not np.isnan(v)},
            "sel": {k: float(v) for k, v in sel.items() if not np.isnan(v)},
            "inc": by[2026] - by[2025],
        })
    offers.sort(key=lambda o: -o["inc"])

    def mean_inc(a, b):
        d = [o["by"][b] - o["by"][a] for o in offers if a in o["by"] and b in o["by"]]
        return float(np.mean(d)) if d else 0.0

    summary = {
        "n": len(offers),
        "up": sum(1 for o in offers if o["inc"] > 0),
        "down": sum(1 for o in offers if o["inc"] < 0),
        "mean_2526": mean_inc(2025, 2026),
        "mean_26ctrl": mean_inc(2026, "control"),
        "prev": {f"{a}-{b}": mean_inc(a, b) for a, b in zip(YEARS, YEARS[1:-1])},
    }
    return offers, summary


# --------------------------------------------------------------------------- #
# Sparkline por oferta
# --------------------------------------------------------------------------- #
FW, FH = 214, 66
ML, MR, MT, MB = 8, 8, 8, 8
BASE, TOPy = FH - MB, MT
R_MIN, R_MAX = 1.3, 4.5


def xpos(pos):
    return ML + POS.index(pos) / (len(POS) - 1) * (FW - ML - MR)


def esc(s):
    return _html.escape(str(s))


def _radius_fn(sel: dict):
    """r ∝ sqrt(admitidos): el ÁREA del punto es proporcional al número de
    admitidos, escalado al rango propio de CADA oferta (mismo criterio que
    el eje Y: resalta la forma, no compara niveles absolutos entre paneles)."""
    vals = [v for v in sel.values() if v > 0]
    if not vals:
        return lambda k: (R_MIN + R_MAX) / 2
    sq = {k: np.sqrt(v) for k, v in sel.items() if v > 0}
    sqmin, sqmax = min(sq.values()), max(sq.values())

    def r(k):
        v = sq.get(k)
        if v is None:
            return R_MIN
        if sqmax <= sqmin:
            return (R_MIN + R_MAX) / 2
        frac = (v - sqmin) / (sqmax - sqmin)
        return R_MIN + frac * (R_MAX - R_MIN)
    return r


def spark(o):
    ys = [p for p in POS if p in o["by"]]
    vals = [o["by"][p] for p in ys]
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.18, 2)
    lo, hi = lo - pad, hi + pad

    def yp(v):
        return BASE - (v - lo) / (hi - lo) * (BASE - TOPy)

    r = _radius_fn(o["sel"])
    pre = [p for p in ys if isinstance(p, int) and p <= 2025]

    p = [f'<svg viewBox="0 0 {FW} {FH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    if len(pre) >= 2:
        pts = " ".join(f'{xpos(y):.1f},{yp(o["by"][y]):.1f}' for y in pre)
        p.append(f'<polyline class="ln" points="{pts}"/>')
    if 2025 in o["by"] and 2026 in o["by"]:
        p.append(f'<line class="ln26" x1="{xpos(2025):.1f}" y1="{yp(o["by"][2025]):.1f}" '
                 f'x2="{xpos(2026):.1f}" y2="{yp(o["by"][2026]):.1f}"/>')
    if 2026 in o["by"] and "control" in o["by"]:
        p.append(f'<line class="lnctrl" x1="{xpos(2026):.1f}" y1="{yp(o["by"][2026]):.1f}" '
                 f'x2="{xpos("control"):.1f}" y2="{yp(o["by"]["control"]):.1f}"/>')
    for y in pre:
        p.append(f'<circle class="dot" cx="{xpos(y):.1f}" cy="{yp(o["by"][y]):.1f}" r="{r(y):.2f}"/>')
    if 2026 in o["by"]:
        p.append(f'<circle class="dot26" cx="{xpos(2026):.1f}" cy="{yp(o["by"][2026]):.1f}" r="{r(2026):.2f}"/>')
    if "control" in o["by"]:
        p.append(f'<circle class="dotctrl" cx="{xpos("control"):.1f}" '
                 f'cy="{yp(o["by"]["control"]):.1f}" r="{r("control"):.2f}"/>')
    p.append('</svg>')
    return "".join(p)


def card(o):
    mod = "" if o["modalidad"] == "escolarizado" else f' · {o["modalidad"]}'
    ctrl_val = o["by"].get("control")
    ctrl_txt = f' → {ctrl_val:.0f}' if ctrl_val is not None else ""

    sel26 = o["sel"].get(2026)
    selc = o["sel"].get("control")
    if sel26 and selc is not None:
        pct = selc / sel26 * 100
        pct_txt = f'control: <b class="c">{pct:.0f}%</b> de personas admitidas en 2026 ({selc:.0f} de {sel26:.0f})'
    else:
        pct_txt = "sin personas admitidas suficientes para comparar"

    tip = {
        "carrera": o["carrera"].title(), "campus": o["campus"].title() + mod,
        "admitidos": {(str(p) if isinstance(p, int) else "Control"): f'{o["sel"].get(p, 0):.0f}'
                      for p in POS if p in o["by"]},
    }

    return (
        f'<figure class="facet" data-tip=\'{_html.escape(json.dumps(tip))}\'>'
        f'<figcaption><span class="ca">{esc(o["carrera"].title())}</span>'
        f'<span class="cc">{esc(o["campus"].title())}{esc(mod)}</span></figcaption>'
        f'<div class="badge">mín {o["by"][2025]:.0f} → {o["by"][2026]:.0f}'
        f'<b class="c">{esc(ctrl_txt)}</b></div>'
        f'<div class="badge2">{pct_txt}</div>'
        f'{spark(o)}</figure>')


def build_inner(offers, summary, top_k: int = TOP_K):
    # Selección: top top_k por incremento 2025->2026 (igual que antes;
    # top_k=len(offers) o mayor incluye todas las comparables).
    # Orden de despliegue: del mínimo 2026 más alto al más bajo.
    top = sorted(offers[:top_k], key=lambda o: -o["by"][2026])
    facets = "".join(card(o) for o in top)
    if top_k >= len(offers):
        eligen_txt = "todas las ofertas comparables (con 2025, 2026 y control)"
    else:
        eligen_txt = (f"las <b>{len(top)}</b> ofertas con mayor incremento del "
                     "puntaje mínimo de 2025 a 2026, restringidas a las que "
                     "también tienen dato de control")
    prev_txt = ", ".join(f"{k.replace('-', '→')}: {v:+.1f}"
                         for k, v in summary["prev"].items())
    rows = "".join(
        f'<tr><td class=c>{esc(o["carrera"].title())}</td>'
        f'<td class=c>{esc(o["campus"].title())}</td><td>{esc(o["modalidad"])}</td>'
        + "".join(f'<td>{o["by"][y]:.0f}</td>' if y in o["by"] else "<td>·</td>"
                  for y in YEARS)
        + f'<td>{o["by"].get("control", 0):.0f}</td>'
        + f'<td class=hl>+{o["inc"]:.0f}</td></tr>'
        for o in top)
    table = ('<table class=tbl><thead><tr><th class=c>Carrera</th><th class=c>Campus</th>'
             '<th>Modalidad</th>' + "".join(f'<th>{y}</th>' for y in YEARS)
             + '<th>Control</th><th>Δ25→26</th></tr></thead><tbody>' + rows + '</tbody></table>')

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --line:#8a8980; --dot:#a1a099; --grid:#e1e0d9; --axis:#c3c2b7;
  --border:rgba(11,11,11,.10); --y2026:{HL_LIGHT}; --ctrl:{CTRL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1160px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --line:#77766d; --dot:#68675f;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10); --y2026:{HL_DARK}; --ctrl:{CTRL_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --line:#77766d;
  --dot:#68675f; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10); --y2026:{HL_DARK}; --ctrl:{CTRL_DARK}; }}
.viz-root h1 {{ font-size:22px; margin:0 0 4px; text-wrap:balance; }}
.sub {{ color:var(--text-secondary); font-size:14px; margin:0 0 3px; line-height:1.5; }}
.method {{ color:var(--muted); font-size:12.5px; margin:0 0 2px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--y2026); border-radius:8px; padding:11px 13px;
  margin:12px 0; font-size:14px; line-height:1.55; }}
.headline b {{ color:var(--y2026); }} .headline b.c {{ color:var(--ctrl); }}
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
.facet .badge b {{ color:var(--y2026); }} .facet .badge b.c {{ color:var(--ctrl); }}
.facet .badge2 {{ font-size:9.5px; color:var(--muted); font-variant-numeric:tabular-nums; margin:0 0 3px;
  line-height:1.3; min-height:2.6em; }}
.facet .badge2 b.c {{ color:var(--ctrl); }}
.tip {{ position:fixed; pointer-events:none; z-index:9; background:var(--surface-1);
  color:var(--text-primary); border:1px solid var(--border); border-radius:8px;
  padding:8px 10px; font-size:11.5px; box-shadow:0 4px 14px rgba(0,0,0,.18);
  opacity:0; transition:opacity .1s; }}
.tip table {{ border-collapse:collapse; }} .tip td {{ padding:1px 6px; }}
.tip .yl {{ color:var(--text-secondary); }} .tip .hc {{ color:var(--ctrl); font-weight:600; }}
.tip .h26 {{ color:var(--y2026); font-weight:600; }}
.ln {{ fill:none; stroke:var(--line); stroke-width:1.5; }}
.ln26 {{ stroke:var(--y2026); stroke-width:2.4; }}
.lnctrl {{ stroke:var(--ctrl); stroke-width:2.4; }}
.dot {{ fill:var(--dot); }} .dot26 {{ fill:var(--y2026); }} .dotctrl {{ fill:var(--ctrl); }}
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

    js = """
<script>
(function(){
  var root=document.querySelector('.viz-root');
  var tip=document.createElement('div'); tip.className='tip'; root.appendChild(tip);
  root.querySelectorAll('.facet').forEach(function(f){
    f.addEventListener('mousemove',function(e){
      var d=JSON.parse(f.dataset.tip);
      var rows='<tr><td colspan=2><b>'+d.carrera+'</b><br>'+d.campus+'</td></tr>'
        +'<tr><td colspan=2 class=yl>personas admitidas por fase:</td></tr>';
      Object.keys(d.admitidos).forEach(function(k){
        var cls=k==='Control'?' class=hc':(k==='2026'?' class=h26':' class=yl');
        rows+='<tr'+cls+'><td'+cls+'>'+k+'</td><td'+cls+'>'+d.admitidos[k]+'</td></tr>';
      });
      tip.innerHTML='<table>'+rows+'</table>'; tip.style.opacity=1;
      var x=e.clientX+14,y=e.clientY+14;
      if(x+200>innerWidth)x=e.clientX-210; tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    f.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });
})();
</script>"""

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT},{CTRL_LIGHT}">
  <h1>Puntaje mínimo de ingreso: 2021–2026 + Control · UNAM</h1>
  <p class="sub">Puntaje mínimo = aciertos de la persona admitida con menor
  puntaje (campo <i>Aciertos Mínimos</i> de la DGAE), por carrera-campus.
  Cada mini-gráfica es la trayectoria del mínimo, extendida con el
  <b style="color:var(--ctrl)">examen de control presencial</b> como una
  posición más después de 2026. El tamaño de cada punto es el <b>número de
  personas admitidas</b> en esa fase (no un tamaño fijo); pasa el mouse
  sobre un panel para ver el número exacto en cada una.</p>
  <p class="method"><b>Cómo se eligen:</b> {eligen_txt}
  (para que la línea tenga con qué continuar); se muestran ordenadas de
  mayor a menor mínimo 2026.</p>
  <div class="headline">
    El puntaje mínimo subió en <b>{summary['up']} de {summary['n']}</b> ofertas
    comparables de 2025 a 2026 (bajó en {summary['down']}). El alza media fue de
    <b>+{summary['mean_2526']:.1f} puntos</b>, frente a {prev_txt} en las
    transiciones previas. De 2026 al control, el cambio medio fue de
    <b class="c">{summary['mean_26ctrl']:+.1f} puntos</b>.
  </div>
  <div class="legend">
    <span><i style="border-color:var(--line)"></i>2021–2025</span>
    <span><i style="border-color:var(--y2026);border-top-width:3px"></i>
    <b style="color:var(--y2026)">2026</b></span>
    <span><i style="border-color:var(--ctrl);border-top-width:3px"></i>
    <b style="color:var(--ctrl)">Control</b></span>
    <span style="margin-left:auto">eje Y y tamaño de punto: escala propia de cada panel ·
    pasa el mouse para ver personas admitidas</span>
  </div>
  <div class="grid-f">{facets}</div>
  <details><summary>Ver tabla (mínimo por año + control, {len(top)} ofertas)</summary>
    <div class="scroll">{table}</div></details>
  <p class="note">Fuente: resultados y metadata DGAE-UNAM 2021–2026
  (campo Aciertos Mínimos) y `metadata_control_2026.csv`
  (`src/scrape_control.py`, examen de control presencial). El eje Y y el
  tamaño de los puntos de cada panel se escalan a su propio rango (destacan
  la forma, no comparan niveles absolutos entre paneles; ver la tabla para
  los valores). Análisis descriptivo.</p>
  {js}
</div>"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, summary = load()
    print(f"ofertas comparables (con control): {summary['n']} "
          f"(subió {summary['up']}, bajó {summary['down']})")
    print(f"alza media minimo 2025->2026: +{summary['mean_2526']:.2f} | "
          f"2026->control: {summary['mean_26ctrl']:+.2f} | previas: {summary['prev']}")
    print("Top 10:")
    for o in offers[:10]:
        print(f"  +{o['inc']:.0f}  {o['by'][2025]:.0f}->{o['by'][2026]:.0f}->"
              f"{o['by']['control']:.0f}  {o['carrera'][:30]} — {o['campus'][:24]} [{o['modalidad']}]")

    pd.DataFrame([{
        "carrera": o["carrera"], "campus": o["campus"], "modalidad": o["modalidad"],
        **{f"min_{y}": o["by"].get(y, "") for y in YEARS},
        "min_control": o["by"].get("control", ""),
        **{f"sel_{y}": o["sel"].get(y, "") for y in YEARS},
        "sel_control": o["sel"].get("control", ""),
        "inc_25_26": o["inc"],
    } for o in offers]).to_csv(OUT_DIR / "minimo_ingreso_control.csv", index=False, encoding="utf-8")

    inner = build_inner(offers, summary)
    (OUT_DIR / "minimo_ingreso_control.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Puntaje mínimo + Control</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_minimo_control_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
