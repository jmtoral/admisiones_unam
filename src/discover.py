"""Fase 1 — Descubrimiento: construye `data/manifest.csv`.

Recorre las páginas índice de cada (año, árbol, archivo), lee la modalidad del
`<title>`, parsea los botones carrera-campus-tabla e inyecta el contexto. Emite
una fila por tabla.

Uso:
    python -m src.discover                 # todos los años de config.YEARS
    python -m src.discover --year 2026     # solo un año
    python -m src.discover --tree suayed   # solo un árbol

Reanudable: el HTML de cada índice se cachea. Reejecutar reconstruye el
manifiesto para los años pedidos y preserva las filas de los demás años.
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd

from src import config, parsing
from src.http_client import FetchError, HttpClient
from src.runlog import setup_logging

logger = logging.getLogger("unam-scraper.discover")

MANIFEST_COLUMNS = [
    "year", "tree", "modalidad", "area",
    "carrera", "campus", "codigo", "url", "index_page",
]

TREE_INDEX_FILES = {
    config.TREE_LICENCIATURA: config.INDEX_FILES_LICENCIATURA,
    config.TREE_SUAYED: config.INDEX_FILES_SUAYED,
}

# Modalidad esperada por el segundo dígito del archivo (solo verificación; la
# fuente de verdad es el <title>).
_DIGIT_EXPECTED = {
    (config.TREE_LICENCIATURA, "5"): "escolarizado",
    (config.TREE_LICENCIATURA, "6"): "abierta",
    (config.TREE_SUAYED, "6"): "suayed",
}


def _verify_modalidad_digit(tree: str, index_file: str, modalidad: str) -> None:
    """Loguea si la modalidad leída del título no cuadra con el dígito."""
    digit = index_file[1] if len(index_file) >= 2 else ""
    expected = _DIGIT_EXPECTED.get((tree, digit))
    if expected and modalidad and modalidad != expected:
        logger.warning(
            "modalidad '%s' del <title> difiere de la esperada por el dígito "
            "'%s' (%s) en %s/%s. Se respeta el título.",
            modalidad, digit, expected, tree, index_file,
        )


def discover_index(
    client: HttpClient, year: int, tree: str, index_file: str
) -> list[dict]:
    """Descubre las tablas de una página índice. Devuelve filas de manifiesto.

    Un índice inexistente o inaccesible se loguea y devuelve []: no aborta.
    """
    is_suayed = tree == config.TREE_SUAYED
    area = int(index_file[0])
    base = config.base_url(tree, year)
    url = base + f"{index_file}.html"
    cache = config.raw_index_path(year, tree, index_file)

    try:
        html = client.fetch(url, cache, referer=base)
    except FetchError as exc:
        logger.warning("índice %s/%s/%s.html no accesible: %s",
                       year, tree, index_file, exc)
        return []

    modalidad = parsing.modalidad_from_title(html, is_suayed=is_suayed)
    _verify_modalidad_digit(tree, index_file, modalidad)

    entries = parsing.parse_index(html, base_url=url)
    if not entries:
        logger.warning("índice %s/%s/%s.html: 0 botones (¿no existe o cambió el "
                       "DOM?). Se continúa.", year, tree, index_file)
        return []

    index_page = f"{index_file}.html"
    rows = [
        {
            "year": year,
            "tree": tree,
            "modalidad": modalidad,
            "area": area,
            "carrera": e.carrera,
            "campus": e.campus,
            "codigo": e.codigo,
            "url": e.url,
            "index_page": index_page,
        }
        for e in entries
    ]
    logger.info("índice %s/%s/%s.html: %d botones, %d carreras, modalidad=%s",
                year, tree, index_file, len(entries),
                len({e.carrera for e in entries}), modalidad)
    return rows


def run(years: list[int], trees: list[str]) -> pd.DataFrame:
    """Descubre todos los índices de los años/árboles pedidos y escribe el
    manifiesto (preservando las filas de años no tocados)."""
    rows: list[dict] = []
    with HttpClient() as client:
        client.check_robots()
        for year in years:
            for tree in trees:
                for index_file in TREE_INDEX_FILES[tree]:
                    rows.extend(discover_index(client, year, tree, index_file))

    df_new = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    df_out = _merge_manifest(df_new, discovered_years=years)

    config.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(config.MANIFEST_PATH, index=False, encoding=config.ENCODING)
    logger.info("manifiesto escrito: %s (%d filas; %d de esta corrida)",
                config.MANIFEST_PATH, len(df_out), len(df_new))
    return df_out


def _merge_manifest(df_new: pd.DataFrame, discovered_years: list[int]) -> pd.DataFrame:
    """Combina las filas nuevas con el manifiesto existente, reemplazando solo
    las de los años (re)descubiertos y preservando los demás."""
    if not config.MANIFEST_PATH.exists():
        return df_new
    try:
        df_old = pd.read_csv(config.MANIFEST_PATH, encoding=config.ENCODING,
                             dtype={"codigo": str, "index_page": str})
    except (pd.errors.EmptyDataError, FileNotFoundError):
        return df_new
    df_keep = df_old[~df_old["year"].isin(discovered_years)]
    combined = pd.concat([df_keep, df_new], ignore_index=True)
    return combined.sort_values(
        ["year", "tree", "area", "carrera", "campus"]
    ).reset_index(drop=True)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fase 1: construye manifest.csv")
    p.add_argument("--year", type=int, default=None,
                   help="Limitar a un año (default: todos los de config.YEARS)")
    p.add_argument("--tree", choices=[config.TREE_LICENCIATURA, config.TREE_SUAYED],
                   default=None, help="Limitar a un árbol (default: ambos)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = _parse_args(argv)
    years = [args.year] if args.year else list(config.YEARS)
    trees = [args.tree] if args.tree else [config.TREE_LICENCIATURA, config.TREE_SUAYED]
    logger.info("discover: años=%s árboles=%s", years, trees)
    df = run(years, trees)
    # Resumen a consola para revisión rápida.
    if not df.empty:
        summary = (df.groupby(["year", "tree", "modalidad"])
                     .size().reset_index(name="tablas"))
        logger.info("resumen por año/árbol/modalidad:\n%s",
                    summary.to_string(index=False))


if __name__ == "__main__":
    main()
