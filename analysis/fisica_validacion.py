"""Imagen de validación (dos paneles) para Física-Facultad de Ciencias.

Responde a una comparación externa que decía "comparando folio va folio la
distribución dice otra cosa": esa comparación en realidad usaba
CONVOCADOS (n=134, el criterio propio de examen_control.py — quienes ya
superaban el mínimo histórico) contra TODO quien presentó el control
(n=107), no un pareo por folio.

Dos paneles, misma carrera-campus (FISICA, FACULTAD DE CIENCIAS,
escolarizado), para separar dos preguntas distintas:
  1. Arriba: ¿el control se parece a lo normal? Población COMPLETA de 2025
     (año típico, antes de la anomalía) vs. población COMPLETA del
     control — sin parear, dos grupos de personas distintos.
  2. Abajo: ¿qué le pasó a cada persona? Solo quienes presentaron AMBOS
     (en línea 2026 y control), pareados por número de comprobante —
     mismas 106 personas en las dos curvas.

No es una página del sitio: genera un HTML standalone que se recorta a
JPG con Playwright.

Uso:  python analysis/fisica_validacion.py
Salida: analysis/output/fisica_validacion.html/.jpg (+ _dark.jpg)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ANALYSIS_DIR))
from examen_control_resultados import _canonicalize_control  # noqa: E402
from comparativa_2026 import gaussian_kde  # noqa: E402

SRC_RESULTADOS = ROOT / "data" / "consolidated" / "resultados_todos.csv"
SRC_CONTROL = ROOT / "data" / "consolidated" / "resultados_control_2026.csv"
OUT_DIR = ROOT / "analysis" / "output"

CARRERA, CAMPUS, MODALIDAD = "FISICA", "FACULTAD DE CIENCIAS", "escolarizado"
TITULO_OFERTA = "Física — Facultad de Ciencias"

HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"          # 2026 en línea
CTRL_LIGHT, CTRL_DARK = "#2f6fb0", "#6fa8dc"      # control presencial
HIST_LIGHT, HIST_DARK = "#7a7970", "#a3a299"      # histórico (2025)
GRID = np.arange(0, 121, 1.0)


def load():
    res = pd.read_csv(SRC_RESULTADOS, dtype=str, keep_default_na=False, na_filter=False)
    res["ac"] = pd.to_numeric(res["aciertos"], errors="coerce")
    res["year"] = res["year"].astype(int)
    pres = res[res["ac"].notna()].copy()
    pres["ac"] = pres["ac"].astype(int)
    r26 = pres[pres["year"] == 2026]

    ctrl = pd.read_csv(SRC_CONTROL, dtype=str, keep_default_na=False, na_filter=False)
    ctrl["ac"] = pd.to_numeric(ctrl["aciertos"], errors="coerce")
    ctrlp = ctrl[ctrl["ac"].notna()].copy()
    ctrlp["ac"] = ctrlp["ac"].astype(int)
    ctrlp = _canonicalize_control(ctrlp)

    def sel(df, year=None):
        m = (df["carrera"] == CARRERA) & (df["campus"] == CAMPUS) & (df["modalidad"] == MODALIDAD)
        if year is not None:
            m &= df["year"] == year
        return df[m]

    full_2025 = sel(pres, 2025)["ac"].to_numpy()
    full_ctrl = sel(ctrlp)["ac"].to_numpy()

    merged = sel(ctrlp).merge(
        sel(r26)[["numero_comprobante", "ac"]],
        on="numero_comprobante", suffixes=("_ctrl", "_26"), how="inner")

    return {
        "top": {"a": full_2025, "b": full_ctrl,
                "label_a": "2025 (población completa)", "label_b": "Control (población completa)"},
        "bottom": {"a": merged["ac_26"].to_numpy(), "b": merged["ac_ctrl"].to_numpy(),
                   "label_a": "En línea 2026 (solo pareados)", "label_b": "Control (solo pareados)"},
    }


# --------------------------------------------------------------------------- #
# Render: una curva KDE por panel, dos series, con leyenda media/mediana/n
# --------------------------------------------------------------------------- #
FW, FH = 900, 420
ML, MR, MT, MB = 50, 20, 20, 40
BASE, AMP_TOP = FH - MB, FH - MB - MT


def xpos(v: float) -> float:
    return ML + v / 120 * (FW - ML - MR)


def _stats(a: np.ndarray) -> dict:
    return {"n": a.size, "media": float(a.mean()), "mediana": float(np.median(a))}


def panel_svg(a: np.ndarray, b: np.ndarray, color_a: str, color_b: str) -> str:
    dens_a, dens_b = gaussian_kde(a, GRID), gaussian_kde(b, GRID)
    gmax = max(dens_a.max(), dens_b.max())
    amp = AMP_TOP / gmax

    def poly(d):
        return " ".join(f"{xpos(GRID[i]):.1f},{BASE - d[i]*amp:.2f}" for i in range(GRID.size))

    def area(d, color_var):
        pts = f"{xpos(0):.1f},{BASE:.1f} " + poly(d) + f" {xpos(120):.1f},{BASE:.1f}"
        return f'<polygon class="curve-fill" style="fill:var({color_var})" points="{pts}"/>'

    p = [f'<svg viewBox="0 0 {FW} {FH}" width="100%" preserveAspectRatio="xMidYMid meet">']
    for t in (0, 20, 40, 60, 80, 100, 120):
        x = xpos(t)
        p.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{BASE}" class="gridl"/>')
        p.append(f'<text x="{x:.1f}" y="{BASE+18}" class="axl" text-anchor="middle">{t}</text>')
    p.append(f'<line x1="{ML}" y1="{BASE}" x2="{FW-MR}" y2="{BASE}" class="axis"/>')
    p.append(area(dens_a, color_a))
    p.append(area(dens_b, color_b))
    p.append(f'<polyline class="curve" style="stroke:var({color_a})" points="{poly(dens_a)}"/>')
    p.append(f'<polyline class="curve" style="stroke:var({color_b})" points="{poly(dens_b)}"/>')
    for arr, color_var in ((a, color_a), (b, color_b)):
        mx = xpos(float(np.median(arr)))
        p.append(f'<line x1="{mx:.1f}" y1="{BASE}" x2="{mx:.1f}" y2="{BASE-10}" '
                 f'class="medmk" style="stroke:var({color_var})"/>')
    p.append('</svg>')
    return "".join(p)


def legend_line(label: str, color_var: str, st: dict) -> str:
    return (f'<span class="lg"><i style="background:var({color_var})"></i>{label} · '
            f'media <b>{st["media"]:.1f}</b> · mediana <b>{st["mediana"]:.1f}</b> · '
            f'n={st["n"]:,}</span>')


def build(data: dict) -> str:
    top, bot = data["top"], data["bottom"]
    st_top_a, st_top_b = _stats(top["a"]), _stats(top["b"])
    st_bot_a, st_bot_b = _stats(bot["a"]), _stats(bot["b"])

    panel_top = panel_svg(top["a"], top["b"], "--hist", "--ctrl")
    panel_bot = panel_svg(bot["a"], bot["b"], "--hl", "--ctrl")

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --hl:{HL_LIGHT}; --ctrl:{CTRL_LIGHT}; --hist:{HIST_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:26px; max-width:1000px; margin:0 auto; }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a;
  --axis:#383835; --border:rgba(255,255,255,.10);
  --hl:{HL_DARK}; --ctrl:{CTRL_DARK}; --hist:{HIST_DARK}; }}
.viz-root h1 {{ font-size:19px; margin:0 0 4px; text-wrap:balance; }}
.viz-root h2 {{ font-size:14.5px; margin:0 0 4px; }}
.sub {{ color:var(--text-secondary); font-size:12.5px; margin:0 0 14px; line-height:1.5; max-width:78ch; }}
.panel {{ background:var(--surface-1); border:1px solid var(--border); border-radius:12px;
  padding:14px 16px 8px; margin-top:14px; }}
.panel h2 {{ margin-bottom:2px; }}
.pnote {{ color:var(--muted); font-size:11.5px; margin:0 0 8px; }}
.legend-row {{ display:flex; gap:18px; flex-wrap:wrap; margin:6px 0 4px; font-size:12.5px;
  color:var(--text-secondary); }}
.lg i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:6px;
  vertical-align:middle; }}
.lg b {{ color:var(--text-primary); font-variant-numeric:tabular-nums; }}
.gridl {{ stroke:var(--grid); stroke-width:1; }}
.axis {{ stroke:var(--axis); stroke-width:1; }}
.axl {{ fill:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }}
.curve {{ fill:none; stroke-width:2.4; }}
.curve-fill {{ fill-opacity:.18; }}
.medmk {{ stroke-width:3; }}
.foot {{ color:var(--muted); font-size:11.5px; margin-top:16px; line-height:1.5; }}
</style>"""

    return f"""{css}
<div class="viz-root">
  <h1>{TITULO_OFERTA}: dos formas de comparar en línea 2026 vs. control</h1>
  <p class="sub">Arriba, TODA la población de cada examen, sin parear —
  distinto número de personas en cada curva. Abajo, SOLO las personas que
  presentaron ambos exámenes, pareadas por número de comprobante (misma
  gente en las dos curvas). Análisis descriptivo.</p>
  <div class="panel">
    <h2>¿Se parece el control a un año normal? (2025 vs. control, poblaciones completas)</h2>
    <p class="pnote">Grupos DISTINTOS de personas — no es un pareo.</p>
    <div class="legend-row">
      {legend_line(top['label_a'], '--hist', st_top_a)}
      {legend_line(top['label_b'], '--ctrl', st_top_b)}
    </div>
    {panel_top}
  </div>
  <div class="panel">
    <h2>¿Qué le pasó a cada persona? (en línea 2026 vs. control, solo pareados por folio)</h2>
    <p class="pnote">Las MISMAS {st_bot_a['n']} personas en las dos curvas.</p>
    <div class="legend-row">
      {legend_line(bot['label_a'], '--hl', st_bot_a)}
      {legend_line(bot['label_b'], '--ctrl', st_bot_b)}
    </div>
    {panel_bot}
  </div>
  <p class="foot">Fuente: resultados DGAE-UNAM, examen en línea 2026 y examen de control
  presencial 2026. Densidad por KDE gaussiano; marca vertical = mediana.
  jmtoral.github.io/admisiones_unam</p>
</div>"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load()
    for k in ("top", "bottom"):
        a, b = _stats(data[k]["a"]), _stats(data[k]["b"])
        print(k, data[k]["label_a"], a, "|", data[k]["label_b"], b)
    inner = build(data)
    (OUT_DIR / "fisica_validacion.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>Física: validación</title></head><body style='margin:0'>"
               + inner + "</body></html>")
    (OUT_DIR / "_fisica_validacion_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
