"""Examen de control presencial (2026): descubre, extrae y consolida.

Fuente nueva y separada de la principal: `resultados_control/` (Licenciatura)
y `resultados_control/` (Suayed), año 2026 únicamente. DOM verificado en vivo
y DISTINTO del examen regular (ver docstring de `parsing.parse_table_control`):
- Botones del índice: `a.btn.btn-primary` (no `btn-link waves-effect waves-light`).
- Metadata por `<span id="stat-*">` en vez de `<h5>Oferta=...`.
- Sin `<table>`: cada aspirante es una tarjeta `.btn-number` en
  `#buttons-container`.

Cada tarjeta enlaza a un portal externo con usuario/contraseña
(primeringreso1.dgae.unam.mx) para el diagnóstico personal — es el
equivalente al viejo "Diagnóstico": se descarta sin seguirlo ni guardarlo.
Mismo alcance de campos que siempre: numero_comprobante, aciertos,
acreditado, detalles (texto inline, no el link).

Caché y salidas EN NAMESPACE APARTE (nunca toca `data/raw_html/` ni
`data/consolidated/resultados_todos.csv`): el `codigo` de una tabla de
control puede coincidir con el de la tabla regular de la misma oferta, y
mezclarlas corrompería `resultados_todos.csv` (dos exámenes distintos bajo
el mismo year+carrera+campus+modalidad).

Reutiliza HttpClient (throttle adaptativo, caché, backoff, navegador real) y
las funciones de parsing.py — solo cambia la URL base, el selector de botón y
el parser de tabla.

Uso:  python -m src.scrape_control
Salidas:
  data/manifest_control_2026.csv
  data/raw_html_control/2026/{tree}/_index/{archivo}.html
  data/raw_html_control/2026/{tree}/{codigo}.html
  data/consolidated/resultados_control_2026.csv
  data/consolidated/metadata_control_2026.csv
"""

from __future__ import annotations

import logging

import pandas as pd

from src import config, parsing
from src.http_client import FetchError, HttpClient
from src.runlog import setup_logging

logger = logging.getLogger("unam-scraper.control")

YEAR = 2026
DATA_DIR = config.DATA_DIR
RAW_DIR = DATA_DIR / "raw_html_control"
MANIFEST_PATH = DATA_DIR / f"manifest_control_{YEAR}.csv"
RESULTADOS_PATH = config.CONSOLIDATED_DIR / f"resultados_control_{YEAR}.csv"
METADATA_PATH = config.CONSOLIDATED_DIR / f"metadata_control_{YEAR}.csv"

BASE_LICENCIATURA = f"https://www.dgae.unam.mx/Licenciatura{YEAR}/resultados_control/"
BASE_SUAYED = f"https://www.dgae.unam.mx/Suayed{YEAR}/Licenciatura/resultados_control/"

# Verificado en vivo: los mismos 10 índices que la fuente regular de 2026.
INDEX_LICENCIATURA = ["15", "25", "35", "45", "26", "36", "46"]
INDEX_SUAYED = ["26", "36", "46"]

_BTN_CLASSES = {"btn", "btn-primary"}

MANIFEST_COLUMNS = ["tree", "modalidad", "area", "carrera", "campus", "codigo",
                    "url", "index_page"]
RESULTADOS_COLUMNS = ["year", "fase", "modalidad", "area", "carrera", "campus",
                      "codigo", "numero_comprobante", "aciertos", "acreditado",
                      "detalles"]
METADATA_COLUMNS = ["year", "fase", "tree", "modalidad", "area", "carrera",
                    "campus", "codigo", "oferta", "aspirantes",
                    "presentaron_examen", "aciertos_minimos", "seleccionados"]


def _index_path(tree: str, index_file: str) -> "config.Path":
    return RAW_DIR / str(YEAR) / "_index" / tree / f"{index_file}.html"


def _table_path(tree: str, codigo: str) -> "config.Path":
    return RAW_DIR / str(YEAR) / tree / f"{codigo}.html"


def discover(client: HttpClient) -> pd.DataFrame:
    """Descubre las tablas de los 10 índices del examen de control 2026."""
    rows: list[dict] = []
    plan = ([(config.TREE_LICENCIATURA, BASE_LICENCIATURA, f) for f in INDEX_LICENCIATURA]
            + [(config.TREE_SUAYED, BASE_SUAYED, f) for f in INDEX_SUAYED])

    for tree, base, index_file in plan:
        is_suayed = tree == config.TREE_SUAYED
        area = int(index_file[0])
        url = base + f"{index_file}.html"
        cache = _index_path(tree, index_file)
        try:
            html = client.fetch(url, cache, referer=base)
        except FetchError as exc:
            logger.warning("índice control %s/%s no accesible: %s", tree, index_file, exc)
            continue

        modalidad = parsing.modalidad_from_title(html, is_suayed=is_suayed)
        entries = parsing.parse_index(html, base_url=url, btn_classes=_BTN_CLASSES)
        if not entries:
            logger.warning("índice control %s/%s: 0 botones.", tree, index_file)
            continue

        for e in entries:
            rows.append({
                "tree": tree, "modalidad": modalidad, "area": area,
                "carrera": e.carrera, "campus": e.campus, "codigo": e.codigo,
                "url": e.url, "index_page": f"{index_file}.html",
            })
        logger.info("índice control %s/%s: %d ofertas (modalidad=%s)",
                    tree, index_file, len(entries), modalidad)

    df = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(MANIFEST_PATH, index=False, encoding=config.ENCODING)
    logger.info("manifest_control: %d ofertas -> %s", len(df), MANIFEST_PATH)
    return df


def fetch_tables(client: HttpClient, manifest: pd.DataFrame) -> dict[str, int]:
    """Descarga (con caché) el HTML de cada tabla del manifiesto de control."""
    counts = {"ok": 0, "skip": 0, "fail": 0}
    total = len(manifest)
    for i, (_, row) in enumerate(manifest.iterrows(), 1):
        cache = _table_path(row["tree"], row["codigo"])
        if cache.exists():
            counts["skip"] += 1
        else:
            referer = (BASE_SUAYED if row["tree"] == config.TREE_SUAYED
                       else BASE_LICENCIATURA) + str(row["index_page"])
            try:
                client.fetch(row["url"], cache, referer=referer)
                counts["ok"] += 1
            except FetchError as exc:
                logger.warning("PENDIENTE control %s: %s", row["codigo"], exc)
                counts["fail"] += 1
        if i % 25 == 0 or i == total:
            logger.info("fetch control %d/%d ok=%d skip=%d fail=%d",
                        i, total, counts["ok"], counts["skip"], counts["fail"])
    return counts


def build_consolidated(manifest: pd.DataFrame) -> tuple[int, int]:
    """Parsea el HTML cacheado de cada tabla y escribe los CSV maestros de
    control (separados de resultados_todos.csv / metadata_carreras.csv)."""
    res_rows: list[dict] = []
    meta_rows: list[dict] = []
    faltantes = 0

    for _, row in manifest.iterrows():
        tree = row["tree"]
        cache = _table_path(tree, row["codigo"])
        if not cache.exists():
            faltantes += 1
            continue
        html = cache.read_text(encoding=config.ENCODING)
        is_suayed = tree == config.TREE_SUAYED
        parsed = parsing.parse_table_control(html, is_suayed=is_suayed)

        meta_rows.append({
            "year": YEAR, "fase": "control", "tree": tree,
            "modalidad": row["modalidad"], "area": int(row["area"]),
            "carrera": row["carrera"], "campus": row["campus"],
            "codigo": row["codigo"], "oferta": parsed.meta.oferta,
            "aspirantes": parsed.meta.aspirantes,
            "presentaron_examen": parsed.meta.presentaron_examen,
            "aciertos_minimos": parsed.meta.aciertos_minimos,
            "seleccionados": parsed.meta.seleccionados,
        })
        for r in parsed.rows:
            res_rows.append({
                "year": YEAR, "fase": "control", "modalidad": row["modalidad"],
                "area": int(row["area"]), "carrera": row["carrera"],
                "campus": row["campus"], "codigo": row["codigo"],
                "numero_comprobante": r.numero_comprobante,
                "aciertos": r.aciertos, "acreditado": r.acreditado,
                "detalles": r.detalles,
            })

    if faltantes:
        logger.warning("build control: %d tablas sin HTML cacheado (no scrapeadas aún)",
                       faltantes)

    config.CONSOLIDATED_DIR.mkdir(parents=True, exist_ok=True)

    df_res = pd.DataFrame(res_rows, columns=RESULTADOS_COLUMNS)
    df_res = df_res.sort_values(
        ["carrera", "campus", "codigo", "numero_comprobante"]).reset_index(drop=True)
    df_res.to_csv(RESULTADOS_PATH, index=False, encoding=config.ENCODING)

    df_meta = pd.DataFrame(meta_rows, columns=METADATA_COLUMNS)
    df_meta = df_meta.sort_values(["tree", "area", "carrera", "campus"]).reset_index(drop=True)
    df_meta.to_csv(METADATA_PATH, index=False, encoding=config.ENCODING)

    logger.info("resultados_control: %d filas -> %s", len(df_res), RESULTADOS_PATH)
    logger.info("metadata_control: %d ofertas -> %s", len(df_meta), METADATA_PATH)
    return len(df_res), len(df_meta)


def main() -> None:
    setup_logging()
    with HttpClient() as client:
        client.check_robots()
        manifest = discover(client)
        if manifest.empty:
            logger.error("manifest_control vacío; no se puede continuar.")
            return
        counts = fetch_tables(client, manifest)
        logger.info("fetch FIN: ok=%d skip=%d fail=%d",
                    counts["ok"], counts["skip"], counts["fail"])

    n_res, n_meta = build_consolidated(manifest)
    logger.info("FIN control: resultados=%d filas, metadata=%d ofertas", n_res, n_meta)


if __name__ == "__main__":
    main()
