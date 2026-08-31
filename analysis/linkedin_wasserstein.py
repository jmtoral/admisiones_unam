"""Imagen para LinkedIn: cuadrícula 8x8 con las 64 ofertas (carrera-campus)
cuya distribución de aciertos cambió MÁS de 2025 a 2026 (distancia de
Wasserstein, W1) — reusa `comparativa_2026.py` (mismos datos, mismo
`facet_svg`), solo cambia el layout a 8 columnas y quita lo interactivo.

No es una página del sitio: genera un HTML standalone que se recorta a PNG
con Playwright, pensado para compartirse como imagen fija.

Uso:  python analysis/linkedin_wasserstein.py
Salida: analysis/output/linkedin_wasserstein.html (+ _preview.html)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS_DIR))
import comparativa_2026 as m2026  # noqa: E402

OUT_DIR = ROOT / "analysis" / "output"
N_GRID = 64


def build() -> tuple[str, list[dict]]:
    offers, summary = m2026.load()
    top = offers[:N_GRID]

    title = f"Las {N_GRID} carreras-campus que MÁS cambiaron: 2025 → 2026 (UNAM)"
    method = (
        f'De las {summary["n_offers"]} ofertas comparables (carrera-campus con '
        f'≥{m2026.MIN_N} sustentantes en 2025 y 2026), estas son las <b>{N_GRID} '
        f'con mayor distancia de Wasserstein (W1)</b> entre su distribución de '
        f'aciertos 2026 y 2025 — el cambio de FORMA más grande, no solo de mediana.')
    headline = (
        f'En las {summary["n_offers"]} ofertas comparables la mediana subió '
        f'en <b>todas — ninguna bajó</b> — con un alza media de '
        f'<b>+{summary["shift_2526"]:.1f} puntos</b> de 2025 a 2026, frente a '
        f'variaciones de apenas ±1 a ±2 puntos entre años previos.')

    inner = m2026.build_inner(
        offers, summary, panels=top, png=True,
        title=title, method=method, headline=headline,
    )
    # cuadrícula 8x8 (en vez del layout de 3 columnas del sitio) y contenedor
    # más ancho para que 8 columnas quepan con paneles legibles.
    inner = inner.replace("grid-template-columns:repeat(3,1fr)",
                           "grid-template-columns:repeat(8,1fr)")
    inner = inner.replace("max-width:1080px", "max-width:2040px")
    # sin la tabla colapsable de todas las ofertas: es una imagen, no una página
    inner = re.sub(r"<details>.*?</details>", "", inner, flags=re.S)
    # pie con atribución para la imagen (reemplaza el <p class=note> genérico)
    inner = re.sub(
        r'<p class="note">.*?</p>',
        '<p class="note">Fuente: resultados DGAE-UNAM 2021–2026. Solo aspirantes '
        'que presentaron examen. Ordenado por distancia de Wasserstein (W1), '
        '2026 vs 2025 — mide cuánto cambió la FORMA de la distribución, no solo '
        'su mediana. Análisis descriptivo: muestra corrimientos, no causas. '
        'jmtoral.github.io/admisiones_unam</p>',
        inner, count=1, flags=re.S)
    return inner, top


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inner, top = build()
    print(f"{len(top)} ofertas en la cuadrícula; W1 de {top[0]['w1']:.1f} (máx) "
          f"a {top[-1]['w1']:.1f} (mín, posición {N_GRID})")
    (OUT_DIR / "linkedin_wasserstein.html").write_text(inner, encoding="utf-8")
    preview = ("<!doctype html><html lang=es><head><meta charset=utf-8>"
               "<title>LinkedIn: mayor cambio 2025-2026</title></head>"
               "<body style='margin:0'>" + inner + "</body></html>")
    (OUT_DIR / "_linkedin_wasserstein_preview.html").write_text(preview, encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
