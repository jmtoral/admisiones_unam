"""Contrapunto de comparativa_2026: las ofertas que MENOS cambiaron.

Misma viz que comparativa_2026 (distribuciones de aciertos 2021-2025 vs 2026,
KDE, tooltip interactivo), pero muestra las 15 carreras-campus con MENOR distancia
de Wasserstein (W1) 2026 vs 2025 — las más estables. Reusa toda la maquinaria de
comparativa_2026 (load, facets, CSS/JS) vía import; solo cambia la selección de
paneles y los textos. Análisis descriptivo.

Hallazgo: incluso las más estables (casi todas de humanidades) subieron; es el
extremo suave del mismo corrimiento general.

Uso:  python analysis/comparativa_estables.py
Salidas en analysis/output/: comparativa_estables.html + previews (interactivo y png)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ANALYSIS = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))
import comparativa_2026 as cmp  # noqa: E402

OUT_DIR = ANALYSIS / "output"
TOP_K = 15


def build_inner(offers, summary, top_k=TOP_K, png=False):
    order = sorted(offers, key=lambda o: o["w1"])   # más estables primero
    panels = order[:top_k]
    shift = float(np.mean([o["med"][2026] - o["med"][2025] for o in panels]))
    n_flat = sum(1 for o in panels if o["med"][2026] == o["med"][2025])
    n_down = sum(1 for o in panels if o["med"][2026] < o["med"][2025])
    baja = ("ninguna bajó" if n_down == 0 else f"{n_down} bajó")
    igual = (f" y solo {n_flat} quedó igual" if n_flat else "")

    title = "Las que MENOS cambiaron: aciertos por carrera-campus · UNAM"
    method = (
        f'<b>Cómo se eligen los paneles:</b> de las {summary["n_offers"]} ofertas '
        f'comparables (una carrera-campus con ≥{cmp.MIN_N} sustentantes en 2025 y '
        f'2026), estas son las <b>{top_k}</b> con <b>menor</b> distancia de Wasserstein '
        f'(W1) 2026 vs 2025 — las más <b>estables</b>. Es el contrapunto de «las que '
        f'más cambiaron».')
    headline = (
        f'Aun las ofertas <b>más estables</b> —casi todas de <b>humanidades</b> '
        f'(Historia, Filosofía, Letras)— subieron. En estos {top_k} paneles la mediana '
        f'creció en promedio <b>+{shift:.1f} puntos</b> de 2025 a 2026; {baja}{igual}. '
        f'Es el extremo suave del mismo movimiento: en las {summary["n_offers"]} '
        f'ofertas comparables el alza media fue de <b>+{summary["shift_2526"]:.1f}</b>.')

    return cmp.build_inner(offers, summary, top_k=top_k, png=png,
                           panels=panels, table_offers=order,
                           title=title, method=method, headline=headline)


def load():
    return cmp.load()


def _standalone(inner: str) -> str:
    return ("<!doctype html><html lang=es><head><meta charset=utf-8>"
            "<title>Las que menos cambiaron</title></head>"
            "<body style='margin:0'>" + inner + "</body></html>")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    offers, summary = cmp.load()
    order = sorted(offers, key=lambda o: o["w1"])[:TOP_K]
    print(f"ofertas comparables: {summary['n_offers']} | "
          f"W1 de los paneles: {order[0]['w1']:.2f}..{order[-1]['w1']:.2f}")
    print("más estables:", [f"{o['carrera'][:20]} ({o['campus'][:12]})" for o in order[:5]])

    inner = build_inner(offers, summary, png=False)
    (OUT_DIR / "comparativa_estables.html").write_text(inner, encoding="utf-8")
    (OUT_DIR / "_comparativa_estables_preview.html").write_text(
        _standalone(inner), encoding="utf-8")
    inner_png = build_inner(offers, summary, png=True)
    (OUT_DIR / "_comparativa_estables_png.html").write_text(
        _standalone(inner_png), encoding="utf-8")
    print("HTML generado en", OUT_DIR)


if __name__ == "__main__":
    main()
