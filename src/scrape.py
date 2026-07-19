"""Fase 2 — Extracción: baja y parsea cada tabla del manifiesto a un CSV.

Lee `data/manifest.csv`, y por cada tabla: baja el HTML (con caché + navegador),
lo parsea, inyecta el contexto (carrera/campus/modalidad/…) y escribe un CSV por
tabla en `data/tables/{año}/{modalidad}/{codigo}_{slug}.csv`.

Uso:
    python -m src.scrape --solo 10100035   # una sola tabla (prueba)
    python -m src.scrape --year 2026        # acotar por año
    python -m src.scrape                     # todo el manifiesto

Reglas:
- Idempotente: si el CSV destino existe, se salta la tabla.
- Caché: si el HTML crudo existe, no se re-descarga.
- Un fallo agotados los reintentos se registra como pendiente y NO aborta la
  corrida; re-ejecutar reintenta solo las que no tienen CSV.
"""

from __future__ import annotations

import argparse
import logging
import re
import unicodedata

import pandas as pd

from src import config, parsing
from src.http_client import FetchError, HttpClient
from src.runlog import setup_logging

logger = logging.getLogger("unam-scraper.scrape")

# Columnas del CSV por tabla (contexto inyectado + datos por aspirante).
TABLE_CSV_COLUMNS = [
    "year", "modalidad", "area", "carrera", "campus", "codigo",
    "numero_comprobante", "aciertos", "acreditado", "detalles",
]


def slugify(text: str, maxlen: int = 40) -> str:
    """Texto -> slug ASCII apto para nombre de archivo (sin acentos)."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^A-Za-z0-9]+", "_", norm).strip("_").lower()
    return norm[:maxlen].strip("_")


def table_csv_path(row: pd.Series):
    """Ruta del CSV destino de una tabla, foldereado por año/modalidad."""
    slug = slugify(f"{row['carrera']}_{row['campus']}")
    folder = config.TABLES_DIR / str(row["year"]) / str(row["modalidad"])
    return folder / f"{row['codigo']}_{slug}.csv"


def scrape_row(client: HttpClient, row: pd.Series) -> str:
    """Procesa una fila del manifiesto. Devuelve un estado:
    'skip' (ya existía), 'ok' (escrita), 'empty' (0 filas), 'fail' (pendiente)."""
    out_path = table_csv_path(row)
    if out_path.exists():
        logger.debug("skip (ya existe): %s", out_path.name)
        return "skip"

    tree = row["tree"]
    year = int(row["year"])
    is_suayed = tree == config.TREE_SUAYED
    cache_path = config.raw_html_path(year, tree, row["codigo"])
    referer = config.base_url(tree, year) + str(row["index_page"])

    try:
        html = client.fetch(row["url"], cache_path, referer=referer)
    except FetchError as exc:
        logger.warning("PENDIENTE %s (%s): %s", row["codigo"], row["url"], exc)
        return "fail"

    parsed = parsing.parse_table(html, is_suayed=is_suayed)
    out_rows = [
        {
            "year": year,
            "modalidad": row["modalidad"],
            "area": int(row["area"]),
            "carrera": row["carrera"],
            "campus": row["campus"],
            "codigo": row["codigo"],
            "numero_comprobante": r.numero_comprobante,
            "aciertos": r.aciertos,
            "acreditado": r.acreditado,
            "detalles": r.detalles,
        }
        for r in parsed.rows
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(out_rows, columns=TABLE_CSV_COLUMNS)
    df.to_csv(out_path, index=False, encoding=config.ENCODING)

    if not out_rows:
        logger.warning("tabla %s escrita con 0 filas (¿solo placeholder o DOM "
                       "distinto?): %s", row["codigo"], out_path.name)
        return "empty"
    logger.info("%s -> %s (%d filas)", row["codigo"], out_path.name, len(out_rows))
    return "ok"


def run(manifest: pd.DataFrame) -> dict[str, int]:
    counts = {"ok": 0, "skip": 0, "empty": 0, "fail": 0}
    pendientes: list[str] = []
    total = len(manifest)
    with HttpClient() as client:
        client.check_robots()
        for i, (_, row) in enumerate(manifest.iterrows(), 1):
            status = scrape_row(client, row)
            counts[status] += 1
            if status == "fail":
                pendientes.append(f"{row['codigo']} {row['url']}")
            if i % 25 == 0 or i == total:
                logger.info("progreso %d/%d  ok=%d skip=%d empty=%d fail=%d",
                            i, total, counts["ok"], counts["skip"],
                            counts["empty"], counts["fail"])

    if pendientes:
        logger.warning("%d tablas pendientes (re-ejecuta para reintentar):\n  %s",
                       len(pendientes), "\n  ".join(pendientes))
    return counts


def _load_manifest() -> pd.DataFrame:
    if not config.MANIFEST_PATH.exists():
        raise SystemExit(
            f"No existe {config.MANIFEST_PATH}. Corre primero: python -m src.discover"
        )
    return pd.read_csv(config.MANIFEST_PATH, encoding=config.ENCODING,
                       dtype={"codigo": str, "index_page": str})


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fase 2: baja y parsea las tablas")
    p.add_argument("--solo", type=str, default=None,
                   help="Procesar solo la tabla de este codigo (prueba puntual)")
    p.add_argument("--year", type=int, default=None, help="Acotar a un año")
    p.add_argument("--tree", choices=[config.TREE_LICENCIATURA, config.TREE_SUAYED],
                   default=None, help="Acotar a un árbol")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = _parse_args(argv)
    manifest = _load_manifest()

    if args.solo:
        manifest = manifest[manifest["codigo"] == args.solo]
        if manifest.empty:
            raise SystemExit(f"codigo {args.solo} no está en el manifiesto.")
    if args.year:
        manifest = manifest[manifest["year"] == args.year]
    if args.tree:
        manifest = manifest[manifest["tree"] == args.tree]

    logger.info("scrape: %d tablas a procesar", len(manifest))
    counts = run(manifest)
    logger.info("FIN: ok=%d skip=%d empty=%d fail=%d",
                counts["ok"], counts["skip"], counts["empty"], counts["fail"])


if __name__ == "__main__":
    main()
