"""Examen de control presencial: ¿a quiénes convocar por carrera-campus?

La Comisión Técnica para la Revisión del Proceso de Ingreso a la Licenciatura
2026 de la UNAM recomienda un examen de control presencial. Este análisis
calcula, para CADA carrera-campus-modalidad (incluidas las de <50 aspirantes:
no se aplica el MIN_N usado en las demás vizes), a cuántos aspirantes de 2026
habría que convocar bajo el criterio:

    convocar si aciertos_2026 >= mínimo_2026          ("quienes pasaron")
            o  aciertos_2026 >= mínimo histórico       (el MÁS BAJO de
                                                        2021-2025 para esa
                                                        oferta)

Como {x>=a} ∪ {x>=b} = {x >= min(a,b)}, el umbral final por oferta es
simplemente min(mínimo_2026, mínimo histórico más bajo 2021-2025), y se
registra de qué año salió ese histórico (si aplica).

Unidad = carrera + campus + modalidad. Usa TODAS las ofertas con dato de
`aciertos_minimos` en 2026, sin importar su tamaño.

Uso:  python analysis/examen_control.py
Salidas en analysis/output/:
    examen_control.csv              (una fila por oferta, las 220)
    examen_control.html             (page content para el sitio)
    _examen_control_preview.html    (standalone, para screenshot)
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "data" / "consolidated" / "metadata_carreras.csv"
RES = ROOT / "data" / "consolidated" / "resultados_todos.csv"
OUT_DIR = ROOT / "analysis" / "output"

HIST_YEARS = [2021, 2022, 2023, 2024, 2025]
TOP_K = 15
HL_LIGHT, HL_DARK = "#e0342a", "#ff5c4f"


def esc(s) -> str:
    return _html.escape(str(s))


def load() -> tuple[pd.DataFrame, dict]:
    m = pd.read_csv(META, dtype=str, keep_default_na=False, na_filter=False)
    m["year"] = m["year"].astype(int)
    m["am"] = pd.to_numeric(m["aciertos_minimos"], errors="coerce")
    m["oferta_n"] = pd.to_numeric(m["oferta"], errors="coerce")
    m["seleccionados_n"] = pd.to_numeric(m["seleccionados"], errors="coerce")

    r = pd.read_csv(RES, dtype=str, keep_default_na=False, na_filter=False)
    r["ac"] = pd.to_numeric(r["aciertos"], errors="coerce")
    r["year"] = r["year"].astype(int)
    r2026 = r[(r["year"] == 2026) & r["ac"].notna()].copy()
    r2026["ac"] = r2026["ac"].astype(int)

    rows = []
    for (car, cam, mod), sub in m.groupby(["carrera", "campus", "modalidad"]):
        by_year = dict(zip(sub["year"], sub["am"]))
        th_2026 = by_year.get(2026)
        if th_2026 is None or pd.isna(th_2026):
            continue  # sin mínimo 2026 publicado: no aplica el criterio

        hist = {y: by_year[y] for y in HIST_YEARS
                if y in by_year and not pd.isna(by_year[y])}
        if hist:
            anio_hist_min = min(hist, key=hist.get)
            th_hist = hist[anio_hist_min]
        else:
            anio_hist_min, th_hist = None, None

        if th_hist is not None:
            final_th = min(th_2026, th_hist)
            fuente = "2026" if th_2026 <= th_hist else str(anio_hist_min)
        else:
            final_th = th_2026
            fuente = "2026*"

        g = r2026[(r2026["carrera"] == car) & (r2026["campus"] == cam)
                   & (r2026["modalidad"] == mod)]
        n_presentaron = len(g)
        n_pasaron_2026 = int((g["ac"] >= th_2026).sum())
        n_convocados = int((g["ac"] >= final_th).sum())

        o26 = sub[sub["year"] == 2026]
        oferta_n = float(o26["oferta_n"].iloc[0]) if len(o26) else np.nan
        seleccionados_2026 = float(o26["seleccionados_n"].iloc[0]) if len(o26) else np.nan

        rows.append({
            "carrera": car, "campus": cam, "modalidad": mod,
            "umbral_2026": int(th_2026),
            "umbral_historico_min": (int(th_hist) if th_hist is not None else None),
            "anio_historico_min": anio_hist_min,
            "umbral_final": int(final_th),
            "fuente_umbral": fuente,
            "presentaron_2026": n_presentaron,
            "pasaron_2026": n_pasaron_2026,
            "convocados_examen_control": n_convocados,
            "oferta_2026": oferta_n,
            "seleccionados_2026": seleccionados_2026,
        })

    df = pd.DataFrame(rows).sort_values(
        "convocados_examen_control", ascending=False).reset_index(drop=True)

    total_presentaron = int(df["presentaron_2026"].sum())
    total_pasaron = int(df["pasaron_2026"].sum())
    total_convocados = int(df["convocados_examen_control"].sum())
    summary = {
        "n_ofertas": len(df),
        "n_sin_hist": int(df["anio_historico_min"].isna().sum()),
        "n_fuente_hist": int((~df["fuente_umbral"].str.startswith("2026")).sum()),
        "total_presentaron": total_presentaron,
        "total_pasaron": total_pasaron,
        "total_convocados": total_convocados,
        "pct_pasaron": total_pasaron / total_presentaron * 100 if total_presentaron else 0.0,
        "pct_convocados": total_convocados / total_presentaron * 100 if total_presentaron else 0.0,
    }
    return df, summary


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #

def build_table(df: pd.DataFrame) -> str:
    head = (
        '<tr>'
        '<th class="c sortable" data-key="carrera">Carrera<span class="arrow">▾</span></th>'
        '<th class="c sortable" data-key="campus">Campus<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="modalidad">Modalidad<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="presentaron">Presentaron 26<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="pasaron">Pasaron 26<span class="arrow">▾</span></th>'
        '<th class="sortable sorted desc" data-key="convocados">Convocados<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="umbral2026">Umbral 26<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="umbralfinal">Umbral final<span class="arrow">▾</span></th>'
        '<th class="sortable" data-key="anio">Año umbral<span class="arrow">▾</span></th>'
        '</tr>')
    rows = []
    for o in df.itertuples():
        modal = "" if o.modalidad == "escolarizado" else f" · {o.modalidad}"
        anio_txt = "2026" if o.fuente_umbral == "2026*" else o.fuente_umbral
        sort_anio = 2026 if o.fuente_umbral in ("2026", "2026*") else int(o.fuente_umbral)
        rows.append(
            f'<tr data-carrera="{esc(o.carrera.lower())}" '
            f'data-campus="{esc(o.campus.lower())}" data-modalidad="{esc(o.modalidad)}" '
            f'data-presentaron="{o.presentaron_2026}" data-pasaron="{o.pasaron_2026}" '
            f'data-convocados="{o.convocados_examen_control}" '
            f'data-umbral2026="{o.umbral_2026}" data-umbralfinal="{o.umbral_final}" '
            f'data-anio="{sort_anio}">'
            f'<td class="c">{esc(o.carrera.title())}</td>'
            f'<td class="c">{esc(o.campus.title())}{esc(modal)}</td>'
            f'<td>{esc(o.modalidad)}</td>'
            f'<td>{o.presentaron_2026:,}</td>'
            f'<td>{o.pasaron_2026:,}</td>'
            f'<td class="hl">{o.convocados_examen_control:,}</td>'
            f'<td>{o.umbral_2026}</td>'
            f'<td>{o.umbral_final}</td>'
            f'<td>{anio_txt}</td></tr>')
    return (f'<table class="tbl" id="tblControl"><thead>{head}</thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def build_barh(df: pd.DataFrame, top_k: int = TOP_K) -> str:
    top = df.head(top_k)
    gmax = float(top["convocados_examen_control"].max())
    rows = []
    for o in top.itertuples():
        modal = "" if o.modalidad == "escolarizado" else f" · {o.modalidad}"
        pct = o.convocados_examen_control / gmax * 100
        anio_txt = "2026" if o.fuente_umbral == "2026*" else o.fuente_umbral
        tip = {
            "carrera": o.carrera.title(), "campus": o.campus.title() + modal,
            "convocados": f"{o.convocados_examen_control:,}",
            "presentaron": f"{o.presentaron_2026:,}",
            "umbral": f"{o.umbral_final} (umbral 2026: {o.umbral_2026}, de {anio_txt})",
        }
        rows.append(
            f'<div class="barh-row" data-tip=\'{_html.escape(json.dumps(tip))}\'>'
            f'<span class="barh-label">{esc(o.carrera.title())}'
            f'<i>{esc(o.campus.title())}{esc(modal)}</i></span>'
            f'<span class="barh-track"><span class="barh-fill" '
            f'style="width:{pct:.1f}%"></span></span>'
            f'<span class="barh-val">{o.convocados_examen_control:,}</span></div>')
    return "".join(rows)


def build_inner(df: pd.DataFrame, summary: dict) -> str:
    table = build_table(df)
    barh = build_barh(df)

    css = f"""
<style>
.viz-root {{ color-scheme:light; --surface-1:#fcfcfb; --plane:#f9f9f7;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10); --accent:{HL_LIGHT};
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
  background:var(--plane); color:var(--text-primary); padding:24px; max-width:1080px; margin:0 auto; }}
@media (prefers-color-scheme:dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d; --text-primary:#fff;
  --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
  --border:rgba(255,255,255,.10); --accent:{HL_DARK}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme:dark; --surface-1:#1a1a19; --plane:#0d0d0d;
  --text-primary:#fff; --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a;
  --axis:#383835; --border:rgba(255,255,255,.10); --accent:{HL_DARK}; }}
.viz-root h1 {{ font-size:20px; margin:0 0 4px; text-wrap:balance; }}
.viz-root h2 {{ font-size:14px; margin:22px 0 6px; }}
.sub {{ color:var(--text-secondary); font-size:13px; margin:0 0 3px; line-height:1.5; }}
.method {{ color:var(--muted); font-size:12px; margin:0 0 2px; line-height:1.5; }}
.headline {{ background:var(--surface-1); border:1px solid var(--border);
  border-left:3px solid var(--accent); border-radius:8px; padding:10px 12px;
  margin:12px 0; font-size:13.5px; line-height:1.5; }}
.headline b {{ color:var(--accent); }}
.controls {{ display:flex; gap:10px; align-items:center; margin:14px 0 8px; flex-wrap:wrap; }}
.search {{ flex:1; min-width:200px; padding:7px 11px; border:1px solid var(--border);
  border-radius:7px; background:var(--surface-1); color:var(--text-primary); font-size:13px; }}
.search::placeholder {{ color:var(--muted); }}
.count {{ font-size:12px; color:var(--muted); white-space:nowrap; }}
.tbl-wrap {{ max-height:560px; overflow:auto; border:1px solid var(--border); border-radius:10px; }}
.tbl {{ border-collapse:collapse; width:100%; font-size:11.5px; }}
.tbl th,.tbl td {{ text-align:right; padding:6px 9px; border-bottom:1px solid var(--border);
  font-variant-numeric:tabular-nums; white-space:nowrap; }}
.tbl th.c,.tbl td.c {{ text-align:left; font-variant-numeric:normal; white-space:normal; }}
.tbl thead th {{ color:var(--text-secondary); font-weight:600; background:var(--surface-1);
  position:sticky; top:0; z-index:1; }}
.tbl th.sortable {{ cursor:pointer; user-select:none; }}
.tbl th.sortable:hover {{ color:var(--accent); }}
.tbl th .arrow {{ opacity:.35; font-size:9px; margin-left:3px; display:inline-block; }}
.tbl th.sorted .arrow {{ opacity:1; color:var(--accent); }}
.tbl th.sorted.asc .arrow {{ transform:rotate(180deg); }}
.tbl td.hl {{ color:var(--accent); font-weight:600; }}
.tbl tbody tr:hover {{ background:var(--plane); }}
.barh-wrap {{ margin-top:6px; }}
.barh-row {{ display:grid; grid-template-columns:200px 1fr 52px; align-items:center;
  gap:10px; padding:4px 0; }}
.barh-label {{ font-size:11.5px; color:var(--text-primary); white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; }}
.barh-label i {{ display:block; font-style:normal; font-size:10px; color:var(--muted);
  overflow:hidden; text-overflow:ellipsis; }}
.barh-track {{ position:relative; height:16px; background:var(--grid); border-radius:4px; }}
.barh-fill {{ position:absolute; left:0; top:0; bottom:0; background:var(--accent);
  border-radius:0 4px 4px 0; }}
.barh-val {{ font-size:11.5px; color:var(--text-secondary); text-align:right;
  font-variant-numeric:tabular-nums; }}
.tip {{ position:fixed; pointer-events:none; z-index:9; background:var(--surface-1);
  color:var(--text-primary); border:1px solid var(--border); border-radius:8px;
  padding:8px 10px; font-size:11.5px; box-shadow:0 4px 14px rgba(0,0,0,.18);
  opacity:0; transition:opacity .1s; max-width:240px; }}
.tip b {{ color:var(--accent); }}
.note {{ color:var(--muted); font-size:12px; margin:14px 0 0; line-height:1.5; }}
@media (max-width:640px) {{ .barh-row {{ grid-template-columns:120px 1fr 42px; }} }}
</style>"""

    js = """
<script>
(function(){
  var root=document.querySelector('.viz-root');
  var tbl=document.getElementById('tblControl');
  var tbody=tbl.querySelector('tbody');
  var rows=Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  var countEl=document.getElementById('rowCount');
  var searchEl=document.getElementById('searchBox');

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

  var sortState={key:'convocados',dir:-1};
  function sortBy(key,dir){
    var numeric=['presentaron','pasaron','convocados','umbral2026','umbralfinal','anio'];
    rows.sort(function(a,b){
      var av=a.dataset[key],bv=b.dataset[key];
      if(numeric.indexOf(key)>-1){ av=+av; bv=+bv; }
      if(av<bv)return -1*dir; if(av>bv)return 1*dir; return 0;
    });
    rows.forEach(function(tr){tbody.appendChild(tr);});
  }
  tbl.querySelectorAll('th.sortable').forEach(function(th){
    th.addEventListener('click',function(){
      var key=th.dataset.key;
      var dir = (sortState.key===key) ? -sortState.dir : -1;
      sortState={key:key,dir:dir};
      tbl.querySelectorAll('th.sortable').forEach(function(t){t.classList.remove('sorted','asc');});
      th.classList.add('sorted'); if(dir===1)th.classList.add('asc');
      sortBy(key,dir);
    });
  });

  var tip=document.createElement('div'); tip.className='tip'; root.appendChild(tip);
  root.querySelectorAll('.barh-row').forEach(function(f){
    f.addEventListener('mousemove',function(e){
      var d=JSON.parse(f.dataset.tip);
      tip.innerHTML='<b>'+d.carrera+'</b><br>'+d.campus+'<br>'
        +'Convocados: <b>'+d.convocados+'</b><br>Presentaron 2026: '+d.presentaron
        +'<br>Umbral final: '+d.umbral;
      tip.style.opacity=1;
      var x=e.clientX+14,y=e.clientY+14;
      if(x+250>innerWidth)x=e.clientX-260; tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    f.addEventListener('mouseleave',function(){tip.style.opacity=0;});
  });
})();
</script>"""

    return f"""{css}
<div class="viz-root" data-palette="{HL_LIGHT}">
  <h1>Examen de control: ¿a quién convocar? · UNAM</h1>
  <p class="sub">La Comisión Técnica para la Revisión del Proceso de Ingreso a la
  Licenciatura 2026 recomienda un examen de control presencial. Este análisis
  calcula, para <b>cada carrera-campus</b> (incluidas las de pocos aspirantes),
  a cuántos sustentantes de 2026 habría que convocar bajo su criterio: quienes
  <b>pasaron 2026</b> (≥ mínimo 2026) <b>o</b> quienes hubieran pasado con el
  <b>mínimo histórico más bajo</b> de 2021–2025 de esa oferta.</p>
  <p class="method"><b>Método:</b> el umbral final por oferta es
  mín(umbral 2026, umbral histórico más bajo 2021–2025) — matemáticamente
  equivalente a la unión de ambos criterios. Se muestran las
  <b>{summary['n_ofertas']}</b> ofertas con umbral 2026 publicado (todas las de
  2026, sin filtro de tamaño); {summary['n_sin_hist']} son nuevas y no tienen
  historial 2021–2025 (se usa solo su umbral 2026, marcado <b>2026*</b>).</p>
  <div class="headline">
    De <b>{summary['total_presentaron']:,}</b> aspirantes que presentaron examen
    en 2026, <b>{summary['total_pasaron']:,}</b> ({summary['pct_pasaron']:.1f}%)
    pasaron con el mínimo de 2026. Bajo el criterio de la Comisión habría que
    convocar a <b>{summary['total_convocados']:,}</b> ({summary['pct_convocados']:.1f}%)
    — <b>{summary['total_convocados']-summary['total_pasaron']:,} más</b> que
    solo "quienes pasaron 2026". En <b>{summary['n_fuente_hist']}</b> de
    {summary['n_ofertas']} ofertas el umbral bajó por el histórico: el mínimo de
    2026 fue más exigente que el peor año de 2021–2025.
  </div>
  <div class="controls">
    <input id="searchBox" class="search" type="text"
      placeholder="Buscar carrera, campus o modalidad…">
    <span id="rowCount" class="count"></span>
  </div>
  <div class="tbl-wrap">{table}</div>
  <h2>Top {TOP_K} ofertas por número de convocados</h2>
  <div class="barh-wrap">{barh}</div>
  <p class="note">Fuente: resultados y metadata DGAE-UNAM 2021–2026 (campos
  Aciertos y Aciertos Mínimos). Se excluyen registros con estatus "Cancelado"
  (presentaron el examen pero su resultado fue anulado) y los pocos casos sin
  aciertos capturados en la fuente: no hay umbral que aplicarles. Análisis
  descriptivo — no identifica aspirantes ni establece causas.</p>
  {js}
</div>"""


def _standalone(inner: str) -> str:
    return ("<!doctype html><html lang=es><head><meta charset=utf-8>"
            "<title>Examen de control</title></head>"
            "<body style='margin:0'>" + inner + "</body></html>")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, summary = load()
    df.to_csv(OUT_DIR / "examen_control.csv", index=False, encoding="utf-8")

    print(f"Ofertas evaluadas (con mínimo 2026 publicado): {summary['n_ofertas']}")
    print(f"  sin historial 2021-2025: {summary['n_sin_hist']}")
    print(f"  umbral final vino de un año histórico (no de 2026): "
          f"{summary['n_fuente_hist']}")
    print(f"Total presentaron examen 2026: {summary['total_presentaron']:,}")
    print(f"Total pasaron 2026: {summary['total_pasaron']:,} "
          f"({summary['pct_pasaron']:.1f}%)")
    print(f"Total a convocar: {summary['total_convocados']:,} "
          f"({summary['pct_convocados']:.1f}%)")

    inner = build_inner(df, summary)
    (OUT_DIR / "examen_control.html").write_text(inner, encoding="utf-8")
    (OUT_DIR / "_examen_control_preview.html").write_text(
        _standalone(inner), encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
