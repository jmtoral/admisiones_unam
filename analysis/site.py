"""Genera el sitio estático (GitHub Pages) en docs/.

Una galería (index) + una página interactiva por visualización, reusando el
`build_inner` de cada análisis. Toggle de tema persistente y navegación común.

Uso:  python analysis/site.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "analysis"
OUT = ANALYSIS / "output"
DOCS = ROOT / "docs"
sys.path.insert(0, str(ANALYSIS))

import base_sin_p75 as m_base             # noqa: E402
import brecha_2026 as m_brecha            # noqa: E402
import casi_cero_2026 as m_ccero          # noqa: E402
import casi_perfecto_2026 as m_cperf       # noqa: E402
import comparativa_2026 as m_comp          # noqa: E402
import minimo_ingreso as m_min             # noqa: E402
import top20_medianas as m_top20           # noqa: E402

REPO_URL = "https://github.com/jmtoral/admisiones_unam"
FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 100 100'><text y='.9em' font-size='88'>%F0%9F%93%88</text></svg>")

# Orden y metadatos de la galería. thumb = PNG en analysis/output/.
PAGES = [
    dict(slug="comparativa", title="El salto de 2026 por carrera-campus",
         desc="Distribuciones de aciertos: 2021–2025 vs 2026, las 50 ofertas que "
              "más cambiaron.", thumb="comparativa_2026_top15.png"),
    dict(slug="base-sin-p75", title="Quita el cuartil superior: la base es la misma",
         desc="Debajo del p75 histórico la distribución de 2026 coincide con 2021–2025; "
              "el cambio está solo arriba.", thumb="base_sin_p75.png"),
    dict(slug="casi-perfecto", title="Puntajes casi perfectos",
         desc="Proporción con ≥100 y ≥110 aciertos por año: de 0.9% a 5.4% en 2026.",
         thumb="casi_perfecto_2026.png"),
    dict(slug="casi-cero", title="El otro extremo: casi cero",
         desc="Una cola de puntajes ultra-bajos (<20 y <10) que apareció en 2026.",
         thumb="casi_cero_2026.png"),
    dict(slug="brecha", title="¿Subieron parejo? La forma de la distribución",
         desc="Fan de percentiles: en 2026 la distribución no se comprimió, se ensanchó.",
         thumb="brecha_2026.png"),
    dict(slug="minimo", title="Puntaje mínimo de ingreso, 2021–2026",
         desc="La evolución del corte mínimo; top 50 ofertas por incremento 2025→2026.",
         thumb="minimo_ingreso.png"),
    dict(slug="top20", title="Las 20 carreras con mayor mediana",
         desc="Ridgeline de la distribución de aciertos (2026).",
         thumb="top20_aciertos_2026.png"),
]


def build_inners() -> dict[str, str]:
    o_c, s_c = m_comp.load()
    o_m, s_m = m_min.load()
    o_b, gcut_b, fa_b = m_base.load()
    return {
        "comparativa": m_comp.build_inner(o_c, s_c, top_k=50, png=False),
        "base-sin-p75": m_base.build_inner(o_b, gcut_b, fa_b),
        "casi-perfecto": m_cperf.build_inner(m_cperf.load()),
        "casi-cero": m_ccero.build_inner(m_ccero.load()),
        "brecha": m_brecha.build_inner(m_brecha.load()),
        "minimo": m_min.build_inner(o_m, s_m),
        "top20": m_top20.build_inner(m_top20.load_top()),
    }


SITE_CSS = """
:root { --s-plane:#f9f9f7; --s-surface:#fcfcfb; --s-ink:#0b0b0b; --s-ink2:#52514e;
  --s-muted:#898781; --s-border:rgba(11,11,11,.12); --s-accent:#e0342a; }
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
  --s-plane:#0d0d0d; --s-surface:#1a1a19; --s-ink:#fff; --s-ink2:#c3c2b7;
  --s-muted:#898781; --s-border:rgba(255,255,255,.14); --s-accent:#ff5c4f; } }
:root[data-theme="dark"]{ --s-plane:#0d0d0d; --s-surface:#1a1a19; --s-ink:#fff;
  --s-ink2:#c3c2b7; --s-muted:#898781; --s-border:rgba(255,255,255,.14); --s-accent:#ff5c4f; }
html,body{ margin:0; background:var(--s-plane); color:var(--s-ink);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }
.site-bar{ max-width:1160px; margin:0 auto; padding:14px 24px 0; display:flex;
  align-items:center; gap:10px; }
.site-bar a,.site-bar button{ font-size:13px; color:var(--s-ink2); text-decoration:none;
  background:none; border:1px solid var(--s-border); border-radius:7px; padding:5px 11px;
  cursor:pointer; }
.site-bar a:hover,.site-bar button:hover{ border-color:var(--s-accent); color:var(--s-accent); }
.site-bar .sp{ margin-left:auto; }
.hero{ max-width:1160px; margin:0 auto; padding:22px 24px 4px; }
.hero h1{ font-size:30px; margin:0 0 8px; text-wrap:balance; }
.hero p{ font-size:15px; color:var(--s-ink2); line-height:1.55; margin:0 0 6px; max-width:70ch; }
.hero .k{ color:var(--s-accent); font-weight:600; }
.gallery{ max-width:1160px; margin:0 auto; padding:14px 24px 40px;
  display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:18px; }
.card{ display:block; text-decoration:none; color:inherit; background:var(--s-surface);
  border:1px solid var(--s-border); border-radius:12px; overflow:hidden; transition:transform .1s, border-color .1s; }
.card:hover{ transform:translateY(-2px); border-color:var(--s-accent); }
.card .thumb{ width:100%; height:172px; object-fit:cover; object-position:top left;
  display:block; border-bottom:1px solid var(--s-border); background:var(--s-plane); }
.card .body{ padding:12px 14px 14px; }
.card h2{ font-size:16px; margin:0 0 5px; }
.card p{ font-size:13px; color:var(--s-ink2); margin:0; line-height:1.45; }
.card .go{ color:var(--s-accent); font-size:13px; font-weight:600; margin-top:8px; display:inline-block; }
.foot{ max-width:1160px; margin:0 auto; padding:8px 24px 40px; color:var(--s-muted); font-size:12.5px; line-height:1.5; }
"""

THEME_HEAD = ("<script>try{var t=localStorage.getItem('unam-theme');"
              "if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}</script>")
THEME_JS = """
<script>(function(){var r=document.documentElement,K='unam-theme',b=document.getElementById('themeBtn');
if(b)b.addEventListener('click',function(){var c=r.getAttribute('data-theme');
var d=c?c==='dark':matchMedia('(prefers-color-scheme:dark)').matches;var n=d?'light':'dark';
r.setAttribute('data-theme',n);try{localStorage.setItem(K,n)}catch(e){}});})();</script>"""


def _head(title: str, desc: str) -> str:
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{title}</title><meta name="description" content="{desc}">'
            f'<link rel="icon" href="{FAVICON}">{THEME_HEAD}'
            f'<style>{SITE_CSS}</style></head><body>')


def viz_page(title: str, inner: str) -> str:
    bar = (f'<div class="site-bar"><a href="index.html">← Análisis</a>'
           f'<span class="sp"></span>'
           f'<a href="{REPO_URL}" target="_blank" rel="noopener">Repositorio ↗</a>'
           f'<button id="themeBtn" type="button" aria-label="Cambiar tema">◐ Tema</button></div>')
    return (_head(f"{title} · Resultados UNAM", title)
            + bar + inner + THEME_JS + "</body></html>")


def index_page() -> str:
    cards = []
    for p in PAGES:
        cards.append(
            f'<a class="card" href="{p["slug"]}.html">'
            f'<img class="thumb" src="img/{p["slug"]}.png" alt="" loading="lazy">'
            f'<div class="body"><h2>{p["title"]}</h2><p>{p["desc"]}</p>'
            f'<span class="go">Ver interactivo →</span></div></a>')
    bar = (f'<div class="site-bar"><span class="sp"></span>'
           f'<a href="{REPO_URL}" target="_blank" rel="noopener">Repositorio ↗</a>'
           f'<button id="themeBtn" type="button" aria-label="Cambiar tema">◐ Tema</button></div>')
    hero = (
        '<div class="hero"><h1>Resultados de admisión UNAM · 2021–2026</h1>'
        '<p>Análisis de los resultados del concurso de selección a licenciatura '
        '(DGAE), extraídos a datos abiertos. En <span class="k">2026</span>, primer '
        'año con examen en línea, los aciertos <span class="k">saltaron en las 168 '
        'carreras comparables</span> (ninguna bajó): +14.4 puntos de mediana, frente '
        'a ±1.5 entre años previos. Estas visualizaciones muestran ese cambio, de '
        'forma descriptiva.</p></div>')
    foot = ('<div class="foot">Fuente: DGAE-UNAM 2021–2026. Datos agregados; solo '
            'quienes presentaron examen. Análisis descriptivo: muestra corrimientos, '
            f'no causas. Código y método en el <a href="{REPO_URL}" '
            'style="color:var(--s-accent)">repositorio</a>.</div>')
    return (_head("Resultados de admisión UNAM 2021–2026",
                  "Análisis de los resultados del concurso de selección UNAM 2021–2026.")
            + bar + hero + f'<div class="gallery">{"".join(cards)}</div>'
            + foot + THEME_JS + "</body></html>")


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "img").mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    inners = build_inners()
    for p in PAGES:
        (DOCS / f'{p["slug"]}.html').write_text(
            viz_page(p["title"], inners[p["slug"]]), encoding="utf-8")
        src = OUT / p["thumb"]
        if src.exists():
            shutil.copyfile(src, DOCS / "img" / f'{p["slug"]}.png')
        else:
            print("AVISO: falta thumbnail", src)
    (DOCS / "index.html").write_text(index_page(), encoding="utf-8")
    print(f"Sitio generado en {DOCS}: index + {len(PAGES)} páginas")


if __name__ == "__main__":
    main()
