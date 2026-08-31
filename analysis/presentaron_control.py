"""¿Dónde se presentó menos gente al control? · Asistencia de convocados.

Compara, por carrera-campus, cuántos aspirantes PRESENTARON el examen de
control presencial (`src/scrape_control.py`) contra cuántas PERSONAS
FUERON CONVOCADAS a presentarlo — no contra el total que presentó el
examen en línea de 2026.

Importante: no todos los que presentaron en 2026 fueron convocados al
control, solo quienes alcanzaron el mínimo (el de 2026 o el histórico más
bajo de 2021-2025, el que fuera menor) — el mismo criterio de la Comisión
Técnica ya calculado en `examen_control.py` (es una ESTIMACIÓN propia, no
la lista oficial; de ahí que algunos % de asistencia superen 100%). Usar
el total de 2026 como denominador (como hacía una versión anterior de este
análisis) subestima la asistencia real: p. ej. Médico Cirujano-Facultad de
Medicina parecía tener 8% de "participación" contra el total de 2026, pero
65% contra sus 1,701 convocados reales — justo la mediana, nada extremo.

También incluye una segunda comparación: entre quienes SÍ presentaron
examen, ¿qué % fue admitido en 2026 vs. en el control? (más alta en
control: el grupo de convocados ya viene preseleccionado).

Unidad = carrera + campus + modalidad. Se requieren ≥MIN_N personas
convocadas (evita que ofertas con un puñado de convocados generen
porcentajes ruidosos). Análisis descriptivo.

Uso:  python analysis/presentaron_control.py
Salidas en analysis/output/: presentaron_control.html/.png/_dark.png + .csv
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
import examen_control as ec  # noqa: E402

SRC_CONTROL = ROOT / "data" / "consolidated" / "metadata_control_2026.csv"
OUT_DIR = ROOT / "analysis" / "output"

MIN_N = 10
TOP_K = 20
CTRL_LIGHT, CTRL_DARK = "#2f6fb0", "#6fa8dc"

_TOKEN_RE = re.compile(r"^(\W*)(\w*)(\W*)$", re.UNICODE)


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
    df_ec, _ = ec.load()  # carrera/campus/modalidad/presentaron_2026/convocados_examen_control/...

    mc = pd.read_csv(SRC_CONTROL, dtype=str, keep_default_na=False, na_filter=False)
    mc["presc"] = pd.to_numeric(mc["presentaron_examen"], errors="coerce")
    mc["selc"] = pd.to_numeric(mc["seleccionados"], errors="coerce")
    mc = _canonicalize_control(mc)
    mc = mc[mc["presc"].notna()][["carrera", "campus", "modalidad", "presc", "selc"]]

    merged = df_ec.merge(mc, on=["carrera", "campus", "modalidad"], how="inner")
    merged = merged[merged["convocados_examen_control"] >= MIN_N]

    offers = []
    for row in merged.itertuples():
        conv = float(row.convocados_examen_control)
        presc = float(row.presc)
        pres26 = float(row.presentaron_2026)
        sel26 = float(row.seleccionados_2026) if not np.isnan(row.seleccionados_2026) else 0.0
        selc = float(row.selc) if not np.isnan(row.selc) else 0.0
        offers.append({
            "carrera": row.carrera, "campus": row.campus, "modalidad": row.modalidad,
            "pres26_total": pres26, "convocados": conv, "presc": presc,
            "pct": presc / conv * 100 if conv else 0.0,
            "sel26": sel26, "selc": selc,
            "pct_admit_2026": sel26 / pres26 * 100 if pres26 else 0.0,
            "pct_admit_control": selc / presc * 100 if presc else 0.0,
            "umbral_final": int(row.umbral_final), "fuente_umbral": row.fuente_umbral,
        })
    offers.sort(key=lambda o: o["pct"])

    total_conv = sum(o["convocados"] for o in offers)
    total_presc = sum(o["presc"] for o in offers)
    total_pres26 = sum(o["pres26_total"] for o in offers)
    total_sel26 = sum(o["sel26"] for o in offers)
    total_selc = sum(o["selc"] for o in offers)
    pcts = np.array([o["pct"] for o in offers])
    admit_ok = [o for o in offers if o["pres26_total"] and o["presc"]]
    summary = {
        "n": len(offers),
        "total_conv": int(total_conv),
        "total_presc": int(total_presc),
        "overall_pct": total_presc / total_conv * 100 if total_conv else 0.0,
        "median_pct": float(np.median(pcts)) if pcts.size else 0.0,
        "n_bajo": int((pcts < 50).sum()),
        "n_medio": int(((pcts >= 50) & (pcts < 75)).sum()),
        "n_alto": int((pcts >= 75).sum()),
        "n_admit": len(admit_ok),
        "overall_admit_2026": total_sel26 / total_pres26 * 100 if total_pres26 else 0.0,
        "overall_admit_control": total_selc / total_presc * 100 if total_presc else 0.0,
        "median_admit_2026": float(np.median([o["pct_admit_2026"] for o in admit_ok])) if admit_ok else 0.0,
        "median_admit_control": float(np.median([o["pct_admit_control"] for o in admit_ok])) if admit_ok else 0.0,
        "n_admit_sube": sum(1 for o in admit_ok if o["pct_admit_control"] > o["pct_admit_2026"]),
        "n_admit_baja": sum(1 for o in admit_ok if o["pct_admit_control"] < o["pct_admit_2026"]),
    }
    return offers, summary


# --------------------------------------------------------------------------- #
# Scatter (log-log): convocados vs. presentaron control
# --------------------------------------------------------------------------- #
SW, SH = 620, 430
SML, SMR, SMT, SMB = 54, 16, 16, 44


def _log_scale(vmin, vmax, pmin, pmax):
    lo, hi = np.log10(vmin), np.log10(vmax)

    def f(v):
        return pmin + (np.log10(max(v, vmin)) - lo) / (hi - lo) * (pmax - pmin)
    return f


def build_scatter(offers: list[dict]) -> str:
    xs = [o["convocados"] for o in offers]
    ys = [o["presc"] for o in offers]
    xmin, xmax = 10 ** np.floor(np.log10(min(xs))), 10 ** np.ceil(np.log10(max(xs)))
    ymin, ymax = 10 ** np.floor(np.log10(max(min(ys), 1))), 10 ** np.ceil(np.log10(max(ys)))

    fx = _log_scale(xmin, xmax, SML, SW - SMR)
    fy = _log_scale(ymin, ymax, SH - SMB, SMT)

    def ticks(vmin, vmax):
        t, v = [], vmin
        while v <= vmax * 1.0001:
            t.append(v)
            v *= 10
        return t

    p = [f'<svg viewBox="0 0 {SW} {SH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    for t in ticks(xmin, xmax):
        x = fx(t)
        p.append(f'<line x1="{x:.1f}" y1="{SMT}" x2="{x:.1f}" y2="{SH-SMB}" class="gridl"/>')
        p.append(f'<text x="{x:.1f}" y="{SH-SMB+16}" class="axl" text-anchor="middle">{t:,.0f}</text>')
    for t in ticks(ymin, ymax):
        y = fy(t)
        p.append(f'<line x1="{SML}" y1="{y:.1f}" x2="{SW-SMR}" y2="{y:.1f}" class="gridl"/>')
        p.append(f'<text x="{SML-8}" y="{y+3:.1f}" class="axl" text-anchor="end">{t:,.0f}</text>')
    t0, t1 = max(xmin, ymin), min(xmax, ymax)
    if t0 < t1:
        x0, y0 = fx(t0), fy(t0)
        x1, y1 = fx(t1), fy(t1)
        p.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" class="refline"/>')
        p.append(f'<text x="{x1-6:.1f}" y="{y1-6:.1f}" class="axl reflbl" '
                 f'text-anchor="end">100% (asistieron todos los convocados)</text>')
    p.append(f'<text x="{(SML+SW-SMR)/2:.1f}" y="{SH-8}" class="axtitle" text-anchor="middle">'
             f'personas convocadas al examen de control (escala log)</text>')
    p.append(f'<text x="14" y="{(SMT+SH-SMB)/2:.1f}" class="axtitle" text-anchor="middle" '
             f'transform="rotate(-90 14 {(SMT+SH-SMB)/2:.1f})">presentaron en control (escala log)</text>')

    for o in offers:
        cx, cy = fx(o["convocados"]), fy(max(o["presc"], 1))
        tip = {"carrera": nice_name(o["carrera"]), "campus": nice_name(o["campus"]),
               "modalidad": o["modalidad"], "convocados": f'{o["convocados"]:.0f}',
               "presc": f'{o["presc"]:.0f}', "pct": f'{o["pct"]:.1f}'}
        p.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" class="pt" '
                 f'data-tip=\'{_html.escape(json.dumps(tip))}\'/>')
    p.append('</svg>')
    return "".join(p)


def build_admit_scatter(offers: list[dict]) -> str:
    """% admitidos entre quienes presentaron: 2026 (x) vs. control (y).
    Escala lineal 0-100 (son porcentajes), con referencia y=x."""
    pts = [o for o in offers if o["pres26_total"] and o["presc"]]

    def fx(v):
        return SML + v / 100 * (SW - SML - SMR)

    def fy(v):
        return (SH - SMB) - v / 100 * (SH - SMB - SMT)

    p = [f'<svg viewBox="0 0 {SW} {SH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    for t in range(0, 101, 20):
        x, y = fx(t), fy(t)
        p.append(f'<line x1="{x:.1f}" y1="{SMT}" x2="{x:.1f}" y2="{SH-SMB}" class="gridl"/>')
        p.append(f'<text x="{x:.1f}" y="{SH-SMB+16}" class="axl" text-anchor="middle">{t}%</text>')
        p.append(f'<line x1="{SML}" y1="{y:.1f}" x2="{SW-SMR}" y2="{y:.1f}" class="gridl"/>')
        p.append(f'<text x="{SML-8}" y="{y+3:.1f}" class="axl" text-anchor="end">{t}%</text>')
    p.append(f'<line x1="{fx(0):.1f}" y1="{fy(0):.1f}" x2="{fx(100):.1f}" y2="{fy(100):.1f}" class="refline"/>')
    p.append(f'<text x="{fx(100)-6:.1f}" y="{fy(100)-6:.1f}" class="axl reflbl" '
             f'text-anchor="end">misma tasa de admisión</text>')
    p.append(f'<text x="{(SML+SW-SMR)/2:.1f}" y="{SH-8}" class="axtitle" text-anchor="middle">'
             f'% admitidos entre quienes presentaron en línea, 2026</text>')
    p.append(f'<text x="14" y="{(SMT+SH-SMB)/2:.1f}" class="axtitle" text-anchor="middle" '
             f'transform="rotate(-90 14 {(SMT+SH-SMB)/2:.1f})">% admitidos entre quienes presentaron control</text>')

    for o in pts:
        cx, cy = fx(min(o["pct_admit_2026"], 100)), fy(min(o["pct_admit_control"], 100))
        tip = {"carrera": nice_name(o["carrera"]), "campus": nice_name(o["campus"]),
               "modalidad": o["modalidad"],
               "admit26": f'{o["pct_admit_2026"]:.1f}', "sel26": f'{o["sel26"]:.0f}',
               "pres26": f'{o["pres26_total"]:.0f}', "admitc": f'{o["pct_admit_control"]:.1f}',
               "selc": f'{o["selc"]:.0f}', "presc": f'{o["presc"]:.0f}'}
        p.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" class="pt2" '
                 f'data-tip2=\'{_html.escape(json.dumps(tip))}\'/>')
    p.append('</svg>')
    return "".join(p)


def build_barh(offers: list[dict], top_k: int = TOP_K) -> str:
    low = offers[:top_k]
    rows = []
    for o in low:
        modal = "" if o["modalidad"] == "escolarizado" else f" · {o['modalidad']}"
        rows.append(
            f'<div class="barh-row">'
            f'<span class="barh-label">{esc(nice_name(o["carrera"]))}'
            f'<i>{esc(nice_name(o["campus"]))}{esc(modal)}</i></span>'
            f'<span class="barh-track"><span class="barh-fill" '
            f'style="width:{min(o["pct"],100):.1f}%"></span></span>'
            f'<span class="barh-val">{o["pct"]:.1f}%'
            f'<i>{o["presc"]:.0f}/{o["convocados"]:.0f}</i></span></div>')
    return "".join(rows)


def build_table(offers: list[dict]) -> str:
    head = (
        '<tr>'
        '<th class="c sortable sorted" data-key="carrera">Carrera<span class="arrow">▾</span></th>'
        '<th class="c sortable" data-key="campus">Campus<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="modalidad">Modalidad<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="pres26">Presentaron 2026 (total)<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="convocados">Personas convocadas<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="presc">Presentaron control<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="pct">% asistencia<span class="arrow">▾</span></th>'
        '</tr>')
    rows = []
    for o in offers:
        modal = "" if o["modalidad"] == "escolarizado" else f" · {o['modalidad']}"
        rows.append(
            f'<tr data-carrera="{esc(o["carrera"].lower())}" '
            f'data-campus="{esc(o["campus"].lower())}" data-modalidad="{esc(o["modalidad"])}" '
            f'data-pres26="{o["pres26_total"]:.0f}" data-convocados="{o["convocados"]:.0f}" '
            f'data-presc="{o["presc"]:.0f}" data-pct="{o["pct"]:.2f}">'
            f'<td class="c">{esc(nice_name(o["carrera"]))}</td>'
            f'<td class="c">{esc(nice_name(o["campus"]))}{esc(modal)}</td>'
            f'<td>{esc(o["modalidad"])}</td>'
            f'<td>{o["pres26_total"]:,.0f}</td>'
            f'<td>{o["convocados"]:,.0f}</td>'
            f'<td>{o["presc"]:,.0f}</td>'
            f'<td class="hl">{o["pct"]:.1f}%</td></tr>')
    return (f'<table class="tbl" id="tblPres"><thead>{head}</thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def build_admit_table(offers: list[dict]) -> str:
    """Tabla de la sección "% de admitidos entre quienes presentaron"."""
    pts = [o for o in offers if o["pres26_total"] and o["presc"]]
    pts = sorted(pts, key=lambda o: o["pct_admit_control"] - o["pct_admit_2026"])
    head = (
        '<tr>'
        '<th class="c sortable sorted" data-key="carrera">Carrera<span class="arrow">▾</span></th>'
        '<th class="c sortable" data-key="campus">Campus<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="modalidad">Modalidad<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="pres26">Presentaron 2026<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="admit26">% admitidos 2026<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="presc">Presentaron control<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="admitc">% admitidos control<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="diff">Diferencia (control − 2026)<span class="arrow">▾</span></th>'
        '</tr>')
    rows = []
    for o in pts:
        modal = "" if o["modalidad"] == "escolarizado" else f" · {o['modalidad']}"
        diff = o["pct_admit_control"] - o["pct_admit_2026"]
        rows.append(
            f'<tr data-carrera="{esc(o["carrera"].lower())}" '
            f'data-campus="{esc(o["campus"].lower())}" data-modalidad="{esc(o["modalidad"])}" '
            f'data-pres26="{o["pres26_total"]:.0f}" data-admit26="{o["pct_admit_2026"]:.2f}" '
            f'data-presc="{o["presc"]:.0f}" data-admitc="{o["pct_admit_control"]:.2f}" '
            f'data-diff="{diff:.2f}">'
            f'<td class="c">{esc(nice_name(o["carrera"]))}</td>'
            f'<td class="c">{esc(nice_name(o["campus"]))}{esc(modal)}</td>'
            f'<td>{esc(o["modalidad"])}</td>'
            f'<td>{o["pres26_total"]:,.0f}</td>'
            f'<td>{o["pct_admit_2026"]:.1f}%</td>'
            f'<td>{o["presc"]:,.0f}</td>'
            f'<td class="hl">{o["pct_admit_control"]:.1f}%</td>'
            f'<td>{diff:+.1f} pp</td></tr>')
    return (f'<table class="tbl" id="tblAdmit"><thead>{head}</thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def build_inner(offers: list[dict], summary: dict) -> str:
    ordered = sorted(offers, key=lambda o: o["pct"])
    scatter = build_scatter(offers)
    barh = build_barh(ordered, TOP_K)
    table = build_table(ordered)
    admit_scatter = build_admit_scatter(offers)
    admit_table = build_admit_table(offers)

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10); --ctrl:{CTRL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1080px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --ctrl:{CTRL_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a;
  --axis:#383835; --border:rgba(255,255,255,.10); --ctrl:{CTRL_DARK}; }}
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
.chart-wrap {{ background:var(--surface-1); border:1px solid var(--border);
  border-radius:10px; padding:10px; margin-top:8px; position:relative; }}
.gridl {{ stroke:var(--grid); stroke-width:1; }}
.axl {{ fill:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; }}
.axtitle {{ fill:var(--text-secondary); font-size:11px; }}
.refline {{ stroke:var(--axis); stroke-width:1.3; stroke-dasharray:4 3; }}
.reflbl {{ font-size:9.5px; }}
.pt, .pt2 {{ fill:var(--ctrl); fill-opacity:.55; stroke:var(--surface-1); stroke-width:.6; cursor:pointer; }}
.pt:hover, .pt2:hover {{ fill-opacity:.9; }}
.disclaimer a {{ color:var(--ctrl); }}
.tip {{ position:fixed; pointer-events:none; z-index:9; background:var(--surface-1);
  color:var(--text-primary); border:1px solid var(--border); border-radius:8px;
  padding:8px 10px; font-size:11.5px; box-shadow:0 4px 14px rgba(0,0,0,.18);
  opacity:0; transition:opacity .1s; max-width:240px; }}
.tip b {{ color:var(--ctrl); }}
.barh-wrap {{ margin-top:6px; }}
.barh-row {{ display:grid; grid-template-columns:220px 1fr 70px; align-items:center;
  gap:10px; padding:4px 0; }}
.barh-label {{ font-size:11.5px; color:var(--text-primary); white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; }}
.barh-label i {{ display:block; font-style:normal; font-size:10px; color:var(--muted);
  overflow:hidden; text-overflow:ellipsis; }}
.barh-track {{ position:relative; height:14px; background:var(--grid); border-radius:4px; }}
.barh-fill {{ position:absolute; left:0; top:0; bottom:0; background:var(--ctrl);
  border-radius:0 4px 4px 0; }}
.barh-val {{ font-size:11.5px; color:var(--text-secondary); text-align:right;
  font-variant-numeric:tabular-nums; }}
.barh-val i {{ display:block; font-style:normal; font-size:9.5px; color:var(--muted); }}
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
</style>"""

    js = """
<script>
(function(){
  var root=document.querySelector('.viz-root');
  var tip=document.createElement('div'); tip.className='tip'; root.appendChild(tip);
  root.querySelectorAll('.pt').forEach(function(c){
    c.addEventListener('mousemove',function(e){
      var d=JSON.parse(c.dataset.tip);
      tip.innerHTML='<b>'+d.carrera+'</b><br>'+d.campus
        +(d.modalidad!=='escolarizado'?' · '+d.modalidad:'')
        +'<br>Personas convocadas: 100% ('+d.convocados+')'
        +'<br>Presentaron control: <b>'+d.pct+'%</b> ('+d.presc+')';
      tip.style.opacity=1;
      var x=e.clientX+14,y=e.clientY+14;
      if(x+250>innerWidth)x=e.clientX-260; tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    c.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });
  root.querySelectorAll('.pt2').forEach(function(c){
    c.addEventListener('mousemove',function(e){
      var d=JSON.parse(c.dataset.tip2);
      tip.innerHTML='<b>'+d.carrera+'</b><br>'+d.campus
        +(d.modalidad!=='escolarizado'?' · '+d.modalidad:'')
        +'<br>2026: <b>'+d.admit26+'%</b> admitidos ('+d.sel26+' de '+d.pres26+' presentados)'
        +'<br>Control: <b>'+d.admitc+'%</b> admitidos ('+d.selc+' de '+d.presc+' presentados)';
      tip.style.opacity=1;
      var x=e.clientX+14,y=e.clientY+14;
      if(x+250>innerWidth)x=e.clientX-260; tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    c.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });

  function setupTable(tblId, countId, searchId, numericKeys, defaultKey, defaultDir){
    var tbl=document.getElementById(tblId);
    var tbody=tbl.querySelector('tbody');
    var rows=Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    var countEl=document.getElementById(countId);
    var searchEl=document.getElementById(searchId);

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

    var sortState={key:defaultKey,dir:defaultDir};
    function sortBy(key,dir){
      rows.sort(function(a,b){
        var av=a.dataset[key],bv=b.dataset[key];
        if(numericKeys.indexOf(key)>-1){ av=+av; bv=+bv; }
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
  }

  setupTable('tblPres','rowCountP','searchBoxP',
    ['pres26','convocados','presc','pct'], 'pct', 1);
  setupTable('tblAdmit','rowCountA','searchBoxA',
    ['pres26','admit26','presc','admitc','diff'], 'diff', 1);
})();
</script>"""

    return f"""{css}
<div class="viz-root" data-palette="{CTRL_LIGHT}">
  <h1>¿Dónde se presentó menos gente al control? · UNAM</h1>
  <p class="sub">Compara, por carrera-campus, cuántos aspirantes
  <b>presentaron</b> el examen de control presencial contra cuántas
  <b>personas fueron convocadas</b> a presentarlo. <b>No todos los que
  presentaron el examen en línea de 2026 fueron convocados</b> — solo
  quienes alcanzaron el mínimo de 2026 o el histórico más bajo de
  2021–2025 (el que fuera menor), el mismo criterio de
  <a href="examen-control.html">"Examen de control: ¿a quién convocar?"</a>.</p>
  <p class="method"><b>Método:</b> {summary['n']} ofertas con ≥{MIN_N}
  personas convocadas y dato de presentaron en control. "% asistencia" =
  presentaron control ÷ personas convocadas (no ÷ total que presentó en 2026).</p>
  <div class="disclaimer">Nota: "personas convocadas" es una <b>estimación
  propia</b> con base en el mínimo histórico (ver la metodología en
  <a href="examen-control.html">"Examen de control: ¿a quién convocar?"</a>),
  no la lista oficial de convocados de la UNAM — por eso algunos porcentajes
  de asistencia superan 100% (se presentó más gente de la que esta
  estimación habría convocado). Es descriptivo — no identifica aspirantes
  ni establece causas.</div>
  <div class="headline">
    De <b>{summary['total_conv']:,}</b> personas convocadas (en estas
    {summary['n']} ofertas), <b>{summary['total_presc']:,}</b> presentaron el
    control — <b>{summary['overall_pct']:.1f}%</b> en conjunto (mediana por
    oferta: {summary['median_pct']:.1f}%). <b>{summary['n_bajo']}</b> ofertas
    tuvieron menos del 50% de asistencia, <b>{summary['n_medio']}</b> entre
    50% y 75%, y <b>{summary['n_alto']}</b> el 75% o más.
  </div>
  <h2>Personas convocadas vs. presentaron control (cada punto, una oferta)</h2>
  <div class="chart-wrap">{scatter}</div>
  <h2>Las {TOP_K} ofertas con menor % de asistencia</h2>
  <div class="barh-wrap">{barh}</div>
  <h2>Tabla completa (ordenada de menor a mayor % de asistencia)</h2>
  <div class="controls">
    <input id="searchBoxP" class="search" type="text"
      placeholder="Buscar carrera, campus o modalidad…">
    <span id="rowCountP" class="count"></span>
  </div>
  <div class="tbl-wrap">{table}</div>
  <h2>% de admitidos entre quienes presentaron: 2026 vs. control</h2>
  <p class="method">Entre quienes SÍ presentaron examen (no entre
  convocados), ¿qué proporción fue admitida en cada fase? Un punto por
  encima de la diagonal significa que la tasa de admisión subió en el
  control respecto a 2026; por debajo, que bajó.</p>
  <div class="headline">
    Entre quienes presentaron, <b>{summary['overall_admit_2026']:.1f}%</b>
    fue admitido en 2026 (mediana por oferta: {summary['median_admit_2026']:.1f}%)
    y <b class="c">{summary['overall_admit_control']:.1f}%</b> en el control
    (mediana: {summary['median_admit_control']:.1f}%), sobre
    {summary['n_admit']} ofertas con datos en ambas fases. La tasa de
    admisión subió en <b>{summary['n_admit_sube']}</b> ofertas y bajó en
    <b>{summary['n_admit_baja']}</b>.
  </div>
  <div class="chart-wrap">{admit_scatter}</div>
  <div class="controls">
    <input id="searchBoxA" class="search" type="text"
      placeholder="Buscar carrera, campus o modalidad…">
    <span id="rowCountA" class="count"></span>
  </div>
  <div class="tbl-wrap">{admit_table}</div>
  <p class="note">Fuente: resultados y metadata DGAE-UNAM, examen en línea
  2026 y examen de control presencial 2026. "Personas convocadas" es una
  estimación propia (criterio de la Comisión Técnica); presentaron y
  admitidos en el control, de la metadata oficial. "Presentaron 2026
  (total)" se muestra solo como contexto — NO es el denominador del % de
  asistencia. Escalas logarítmica (primer scatter) y lineal 0-100%
  (segundo). Análisis descriptivo.</p>
  {js}
</div>"""


def _standalone(inner: str) -> str:
    return ("<!doctype html><html lang=es><head><meta charset=utf-8>"
            "<title>Presentaron: convocados vs Control</title></head>"
            "<body style='margin:0'>" + inner + "</body></html>")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, summary = load()
    print("resumen:", summary)
    print("Top 10 con menor % de asistencia:")
    for o in offers[:10]:
        print(f"  {o['pct']:5.1f}%  {o['presc']:.0f}/{o['convocados']:.0f}  "
              f"{o['carrera'][:30]} - {o['campus'][:22]} [{o['modalidad']}]")

    pd.DataFrame(offers).to_csv(OUT_DIR / "presentaron_control.csv", index=False, encoding="utf-8")

    inner = build_inner(offers, summary)
    (OUT_DIR / "presentaron_control.html").write_text(inner, encoding="utf-8")
    (OUT_DIR / "_presentaron_control_preview.html").write_text(
        _standalone(inner), encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
