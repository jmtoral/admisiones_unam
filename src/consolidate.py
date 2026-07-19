"""Fase 3 — Consolidación: genera los CSV maestros.

Produce:
  1. data/consolidated/resultados_todos.csv  — concatenación de los CSV por tabla.
  2. data/consolidated/metadata_carreras.csv — una fila por carrera-campus-año con
     los campos del <h5>, re-parseados desde el HTML crudo cacheado.

Uso:
    python -m src.consolidate                # todo lo que haya en data/tables
    python -m src.consolidate --year 2026    # acotar por año

No toca la red: lee los CSV por tabla y el HTML crudo ya cacheado.
"""

from __future__ import annotations

import argparse
import logging
import unicodedata
from collections import Counter

import pandas as pd

from src import config, parsing
from src.runlog import setup_logging

logger = logging.getLogger("unam-scraper.consolidate")

METADATA_COLUMNS = [
    "year", "tree", "modalidad", "area", "carrera", "campus", "codigo",
    "oferta", "aspirantes", "presentaron_examen", "aciertos_minimos",
    "seleccionados",
]

# Lectura fiel de los CSV por tabla: todo como texto, sin convertir "" en NaN ni
# perder ceros a la izquierda (numero_comprobante, codigo).
_READ_KW = dict(dtype=str, keep_default_na=False, na_filter=False,
                encoding=config.ENCODING)

_ACCENTED = set("ÁÉÍÓÚÑÜáéíóúñü")


def _fold(s: str) -> str:
    """Clave insensible a acentos/mayúsculas/espacios para agrupar variantes."""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_ = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_.upper().split())


def build_canonical_map(values) -> dict[str, str]:
    """Mapa variante -> forma canónica para nombres que la fuente escribe de
    forma inconsistente (mismo campus con y sin acento entre años).

    Para cada grupo insensible a acentos, la forma canónica es la variante con
    MÁS caracteres acentuados (la ortografía correcta, que ya existe en la
    fuente); desempate por frecuencia y luego alfabético. No inventa nombres: solo
    elige entre las variantes realmente observadas.
    """
    groups: dict[str, list[str]] = {}
    for v in values:
        groups.setdefault(_fold(v), []).append(v)

    cmap: dict[str, str] = {}
    for variants in groups.values():
        counts = Counter(variants)
        canonical = max(
            counts,
            key=lambda x: (sum(c in _ACCENTED for c in x), counts[x], x),
        )
        for variant in counts:
            cmap[variant] = canonical
    return cmap


def _load_canonical_maps() -> dict[str, dict[str, str]]:
    """Construye los mapas canónicos de carrera y campus desde el manifiesto
    (contiene toda combinación carrera-campus que existe)."""
    if not config.MANIFEST_PATH.exists():
        return {"carrera": {}, "campus": {}}
    man = pd.read_csv(config.MANIFEST_PATH, dtype=str, keep_default_na=False,
                      na_filter=False, encoding=config.ENCODING)
    maps = {col: build_canonical_map(man[col].tolist())
            for col in ("carrera", "campus")}
    for col in ("carrera", "campus"):
        n_fixed = sum(1 for k, v in maps[col].items() if k != v)
        if n_fixed:
            logger.info("canonicalización %s: %d variantes normalizadas",
                        col, n_fixed)
    return maps


def _apply_canonical(df: pd.DataFrame, maps: dict[str, dict[str, str]]) -> pd.DataFrame:
    for col in ("carrera", "campus"):
        if col in df.columns and maps.get(col):
            df[col] = df[col].map(lambda v: maps[col].get(v, v))
    return df


def _table_csvs(year: int | None) -> list:
    root = config.TABLES_DIR
    if not root.exists():
        return []
    pattern = f"{year}/*/*.csv" if year else "*/*/*.csv"
    return sorted(root.glob(pattern))


def build_resultados_todos(year: int | None, canon: dict[str, dict[str, str]]) -> int:
    """Concatena todos los CSV por tabla en un maestro. Devuelve nº de filas.

    Canonicaliza carrera/campus (los CSV por tabla quedan fieles al origen; el
    maestro queda consistente para análisis)."""
    files = _table_csvs(year)
    if not files:
        logger.warning("no hay CSV por tabla en %s (¿corriste scrape?)",
                       config.TABLES_DIR)
        return 0

    frames = (pd.read_csv(f, **_READ_KW) for f in files)
    df = pd.concat(frames, ignore_index=True)
    df = _apply_canonical(df, canon)
    df = df.sort_values(
        ["year", "modalidad", "area", "carrera", "campus", "codigo",
         "numero_comprobante"]
    ).reset_index(drop=True)

    config.CONSOLIDATED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.RESULTADOS_TODOS_PATH, index=False, encoding=config.ENCODING)
    logger.info("resultados_todos.csv: %d filas de %d tablas -> %s",
                len(df), len(files), config.RESULTADOS_TODOS_PATH)
    return len(df)


def build_metadata_carreras(year: int | None, canon: dict[str, dict[str, str]]) -> int:
    """Una fila por carrera-campus-año con el <h5>, re-parseado desde caché."""
    if not config.MANIFEST_PATH.exists():
        logger.warning("no existe el manifiesto; se omite metadata_carreras.")
        return 0

    manifest = pd.read_csv(config.MANIFEST_PATH,
                           dtype={"codigo": str, "index_page": str},
                           encoding=config.ENCODING)
    if year:
        manifest = manifest[manifest["year"] == year]

    rows: list[dict] = []
    faltantes = 0
    for _, m in manifest.iterrows():
        yr, tree = int(m["year"]), m["tree"]
        cache = config.raw_html_path(yr, tree, m["codigo"])
        if not cache.exists():
            faltantes += 1
            logger.warning("HTML crudo ausente (no scrapeada aún): %s/%s/%s",
                           yr, tree, m["codigo"])
            continue
        html = cache.read_text(encoding=config.ENCODING)
        meta = parsing.parse_table_meta(html, is_suayed=(tree == config.TREE_SUAYED))
        rows.append({
            "year": yr,
            "tree": tree,
            "modalidad": m["modalidad"],
            "area": int(m["area"]),
            "carrera": m["carrera"],
            "campus": m["campus"],
            "codigo": m["codigo"],
            "oferta": meta.oferta,
            "aspirantes": meta.aspirantes,
            "presentaron_examen": meta.presentaron_examen,
            "aciertos_minimos": meta.aciertos_minimos,
            "seleccionados": meta.seleccionados,
        })

    if not rows:
        logger.warning("metadata_carreras: 0 filas (¿faltan HTML cacheados?).")
        return 0

    df = pd.DataFrame(rows, columns=METADATA_COLUMNS)
    df = _apply_canonical(df, canon)
    df = df.sort_values(["year", "tree", "area", "carrera", "campus"]).reset_index(
        drop=True)
    config.CONSOLIDATED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.METADATA_CARRERAS_PATH, index=False, encoding=config.ENCODING)
    logger.info("metadata_carreras.csv: %d filas (%d sin HTML) -> %s",
                len(df), faltantes, config.METADATA_CARRERAS_PATH)
    return len(df)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fase 3: genera los CSV maestros")
    p.add_argument("--year", type=int, default=None, help="Acotar a un año")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = _parse_args(argv)
    logger.info("consolidate: year=%s", args.year or "todos")
    canon = _load_canonical_maps()
    n_res = build_resultados_todos(args.year, canon)
    n_meta = build_metadata_carreras(args.year, canon)
    logger.info("FIN: resultados=%d filas, metadata=%d carreras", n_res, n_meta)


if __name__ == "__main__":
    main()
