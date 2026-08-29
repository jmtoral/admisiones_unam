"""Parseo del DOM del sitio de la DGAE.

Todo el conocimiento de la estructura HTML vive aquí. La red vive en
`http_client.py`. Estas funciones reciben HTML crudo (str) y devuelven datos
estructurados; no descargan nada.

Estructura verificada para 2026 (ver README, "Estructura del sitio de origen").
Antes de escalar a un año anterior hay que validar su DOM y, si difiere,
ramificar aquí.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# --------------------------------------------------------------------------- #
# Modelos de datos
# --------------------------------------------------------------------------- #


@dataclass
class IndexEntry:
    """Un botón de campus dentro de una página índice: apunta a una tabla."""

    carrera: str      # texto del <h3> que agrupa a este botón
    campus: str       # leyenda del botón
    url: str          # href absoluto a la tabla
    codigo: str       # nombre del archivo hoja, p. ej. "10100035"


@dataclass
class TableMeta:
    """Metadata de la cabecera de una página de tabla (<h2> y <h5>)."""

    codigo_corto: str = ""   # p. ej. "101" (el de paréntesis en el <h2>)
    carrera: str = ""
    campus: str = ""
    modalidad: str = ""      # leída del <h2>/<title>, NO inferida del dígito
    oferta: str = ""
    aspirantes: str = ""
    presentaron_examen: str = ""
    aciertos_minimos: str = ""
    seleccionados: str = ""


@dataclass
class TableRow:
    """Una fila de aspirante de la tabla de resultados."""

    numero_comprobante: str = ""
    aciertos: str = ""
    acreditado: str = ""       # S / N / C / vacío
    detalles: str = ""


@dataclass
class ParsedTable:
    meta: TableMeta
    rows: list[TableRow] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

_PLACEHOLDER = "no se encontraron resultados para la búsqueda"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean(text: str | None) -> str:
    """Colapsa espacios y recorta. Devuelve '' si es None."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _codigo_from_url(url: str) -> str:
    """Extrae el nombre del archivo hoja de una URL de tabla.

    `.../resultados/1/10100035.html` -> `10100035`.
    """
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return tail[:-5] if tail.endswith(".html") else tail


# --------------------------------------------------------------------------- #
# Modalidad (leída del texto, nunca del dígito)
# --------------------------------------------------------------------------- #

# El sitio escribe la modalidad literal en <title>/<h2>. Normalizamos a las tres
# etiquetas del esquema: escolarizado / abierta / suayed. El árbol (suayed vs.
# licenciatura) lo aporta quien llama, porque "abierta" y "a distancia" comparten
# el dígito 6 pero viven en árboles distintos.


def normalize_modalidad(raw: str, *, is_suayed: bool = False) -> str:
    """Normaliza la etiqueta de modalidad del texto del sitio.

    `is_suayed` desambigua el árbol SUAYED, cuya leyenda suele decir "Abierta"
    o "A Distancia" pero corresponde a la modalidad `suayed` en el esquema.
    """
    low = raw.lower()
    if is_suayed:
        return "suayed"
    if "escolar" in low:
        return "escolarizado"
    if "abiert" in low or "distancia" in low:
        return "abierta"
    return _clean(raw).lower()


def modalidad_from_title(html: str, *, is_suayed: bool = False) -> str:
    """Modalidad tentativa leída del <title> de una página índice.

    Ej. `ResultadosAREA 2 ABIERTO` / `ResultadosAREA 1 ESCOLARIZADO`.
    """
    soup = _soup(html)
    title = _clean(soup.title.string if soup.title else "")
    return normalize_modalidad(title, is_suayed=is_suayed)


# --------------------------------------------------------------------------- #
# Página índice
# --------------------------------------------------------------------------- #

_BTN_SELECTOR = "a.btn.btn-link.waves-effect.waves-light"
_BTN_CLASSES = {"btn", "btn-link", "waves-effect", "waves-light"}


def parse_index(
    html: str, base_url: str, *, btn_classes: set[str] | None = None
) -> list[IndexEntry]:
    """Extrae los botones (carrera-campus-tabla) de una página índice.

    Cada carrera es un <h3>; los botones que le siguen (hasta el próximo <h3>)
    son sus campus. El href puede ser absoluto (resultados/) o relativo
    (resultados_control/, verificado en vivo 2026); siempre se pasa por
    urljoin con `base_url`.

    `btn_classes` permite reconocer variantes de botón (p. ej. el examen de
    control usa `btn btn-primary` en vez de `btn btn-link waves-effect
    waves-light`). Default: la variante original de `resultados/`.
    """
    soup = _soup(html)
    entries: list[IndexEntry] = []
    wanted = btn_classes or _BTN_CLASSES

    # Recorremos el documento en orden; llevamos la carrera <h3> vigente y la
    # asignamos a cada botón que aparezca después.
    carrera_actual = ""
    for el in soup.find_all(["h3", "a"]):
        if el.name == "h3":
            carrera_actual = _clean(el.get_text())
            continue

        # Es un <a>: ¿es uno de los botones de campus?
        classes = set(el.get("class") or [])
        if not wanted.issubset(classes):
            continue

        href = el.get("href")
        if not href:
            continue

        url = urljoin(base_url, href)
        campus = _clean(el.get_text())
        entries.append(
            IndexEntry(
                carrera=carrera_actual,
                campus=campus,
                url=url,
                codigo=_codigo_from_url(url),
            )
        )

    return entries


# --------------------------------------------------------------------------- #
# Página de tabla: cabecera (<h2>, <h5>)
# --------------------------------------------------------------------------- #

# <h2>: `Concurso Licenciatura 2026 : (101) ACTUARIA - FACULTAD DE CIENCIAS - Escolarizado`
_H2_RE = re.compile(
    r":\s*\((?P<codigo>[^)]*)\)\s*(?P<resto>.+)$",
    re.DOTALL,
)

# <h5> metadata: `Oferta=70 Aspirantes=1614 Presentaron Examen=1395 Aciertos Minimos=113 Seleccionados=86`
# Capturamos cada campo por su etiqueta; los valores son números (o vacío).
_META_FIELDS = {
    "oferta": r"Oferta",
    "aspirantes": r"Aspirantes",
    "presentaron_examen": r"Presentaron\s+Examen",
    "aciertos_minimos": r"Aciertos\s+M[ií]nimos",
    "seleccionados": r"Seleccionados",
}


def _parse_h2(text: str, *, is_suayed: bool) -> tuple[str, str, str, str]:
    """Devuelve (codigo_corto, carrera, campus, modalidad) del <h2>."""
    text = _clean(text)
    m = _H2_RE.search(text)
    if not m:
        return "", "", "", ("suayed" if is_suayed else "")

    codigo_corto = _clean(m.group("codigo"))
    resto = _clean(m.group("resto"))

    # `CARRERA - CAMPUS - Modalidad`. La modalidad es el último segmento; el
    # campus el penúltimo; el resto es la carrera (puede traer guiones internos).
    parts = [p.strip() for p in resto.split(" - ")]
    modalidad_raw = parts[-1] if len(parts) >= 1 else ""
    campus = parts[-2] if len(parts) >= 2 else ""
    carrera = " - ".join(parts[:-2]) if len(parts) >= 3 else (
        parts[0] if parts else ""
    )
    modalidad = normalize_modalidad(modalidad_raw, is_suayed=is_suayed)
    return codigo_corto, carrera, campus, modalidad


def _parse_meta_h5(text: str) -> dict[str, str]:
    """Extrae los campos numéricos del <h5> de metadata."""
    text = _clean(text)
    out: dict[str, str] = {}
    for key, label in _META_FIELDS.items():
        # `Etiqueta=valor` hasta el próximo `Etiqueta=` o fin de cadena.
        m = re.search(rf"{label}\s*=\s*(?P<val>[^=]*?)(?=\s+\w[\w ]*=|$)", text)
        out[key] = _clean(m.group("val")) if m else ""
    return out


def parse_table_meta(html: str, *, is_suayed: bool = False) -> TableMeta:
    """Parsea <h2> + <h5> de metadata de una página de tabla."""
    soup = _soup(html)

    h2 = soup.find("h2")
    codigo_corto, carrera, campus, modalidad = _parse_h2(
        h2.get_text() if h2 else "", is_suayed=is_suayed
    )

    # El <h5> de metadata es el que contiene "Oferta". Hay otro <h5> de leyenda
    # (S=Seleccionado ...) que debemos ignorar.
    meta_fields: dict[str, str] = {k: "" for k in _META_FIELDS}
    for h5 in soup.find_all("h5"):
        txt = h5.get_text()
        if "Oferta" in txt and "Aspirantes" in txt:
            meta_fields = _parse_meta_h5(txt)
            break

    return TableMeta(
        codigo_corto=codigo_corto,
        carrera=carrera,
        campus=campus,
        modalidad=modalidad,
        **meta_fields,
    )


# --------------------------------------------------------------------------- #
# Página de tabla del EXAMEN DE CONTROL (2026): DOM distinto, verificado en vivo.
#
# No hay <table>: cada aspirante es una tarjeta `.btn-number` dentro de
# `#buttons-container`. La metadata usa `<span id="stat-*">` en vez del <h5>
# `Oferta=... Aspirantes=...`. El `<h2>` es solo `(codigo) CARRERA` (sin el
# prefijo "Concurso Licenciatura AAAA :" ni el sufijo "- Campus - Modalidad");
# campus y modalidad viven en el <h4 class="text-muted"> siguiente, separados
# por " — ". El botón de cada tarjeta enlaza a un portal externo con
# usuario/contraseña (primeringreso1.dgae.unam.mx/.../ingresar.html) — es el
# equivalente al viejo "Diagnóstico": se descarta sin seguirlo ni guardarlo.
# --------------------------------------------------------------------------- #


def parse_table_meta_control(html: str, *, is_suayed: bool = False) -> TableMeta:
    """Parsea la cabecera (<h1>/<h2>/<h4> + `#stat-*`) de una tabla de control."""
    soup = _soup(html)

    h2 = soup.find("h2")
    h2_text = _clean(h2.get_text()) if h2 else ""
    m = re.match(r"^\((?P<codigo>[^)]*)\)\s*(?P<carrera>.+)$", h2_text)
    codigo_corto = _clean(m.group("codigo")) if m else ""
    carrera = _clean(m.group("carrera")) if m else ""

    campus, modalidad = "", ("suayed" if is_suayed else "")
    h4 = soup.find("h4", class_="text-muted")
    if h4:
        parts = _clean(h4.get_text()).split("—")
        campus = _clean(parts[0]) if parts else ""
        if len(parts) >= 2:
            modalidad = normalize_modalidad(parts[-1], is_suayed=is_suayed)

    def stat(id_: str) -> str:
        el = soup.find(id=id_)
        return _clean(el.get_text()) if el else ""

    return TableMeta(
        codigo_corto=codigo_corto,
        carrera=carrera,
        campus=campus,
        modalidad=modalidad,
        oferta=stat("stat-oferta"),
        aspirantes=stat("stat-aspirantes"),
        presentaron_examen=stat("stat-presentaron"),
        aciertos_minimos=stat("stat-aciertos"),
        seleccionados=stat("stat-seleccionados"),
    )


# Guiones usados por el sitio para "no seleccionado" (vacío en nuestro esquema).
_DASH_CHARS = {"—", "-", "–", ""}


def parse_table_rows_control(html: str) -> list[TableRow]:
    """Extrae las tarjetas de aspirante de `#buttons-container` (examen de
    control). Sin placeholder que descartar: la tarjeta "No se encontraron
    resultados" vive fuera de `#buttons-container` (o el contenedor está
    vacío), nunca se confunde con una tarjeta real."""
    soup = _soup(html)
    container = soup.find(id="buttons-container")
    if container is None:
        return []

    rows: list[TableRow] = []
    for card in container.select("a.btn-number"):
        numero = _clean(card.select_one(".numero").get_text()) if card.select_one(".numero") else ""
        badges = card.select(".meta .badge")

        aciertos = ""
        acreditado = ""
        for b in badges:
            txt = _clean(b.get_text())
            if "badge-aciertos" in (b.get("class") or []):
                aciertos = txt.replace("aciertos", "").strip()
            else:
                acreditado = "" if txt in _DASH_CHARS else txt

        detalle_el = card.select_one(".detalle")
        detalles = _clean(detalle_el.get_text()) if detalle_el else ""
        # BeautifulSoup vuelve "&nbsp;" en '\xa0'; _clean ya lo colapsa a "".

        if not any([numero, aciertos, acreditado, detalles]):
            continue
        rows.append(TableRow(numero_comprobante=numero, aciertos=aciertos,
                              acreditado=acreditado, detalles=detalles))

    return rows


def parse_table_control(html: str, *, is_suayed: bool = False) -> ParsedTable:
    """Parsea una página de tabla completa del examen de control."""
    return ParsedTable(
        meta=parse_table_meta_control(html, is_suayed=is_suayed),
        rows=parse_table_rows_control(html),
    )


# --------------------------------------------------------------------------- #
# Página de tabla: cuerpo (<table>)
# --------------------------------------------------------------------------- #

# Índice de columnas esperado. La columna Diagnóstico se descarta.
_COL_ORDER = ["numero_comprobante", "aciertos", "acreditado", "detalles", "diagnostico"]


def _header_map(table) -> dict[str, int] | None:
    """Mapea nombre de columna -> índice, leyendo el <thead>/primera fila.

    Devuelve None si no reconoce la cabecera (para caer al orden posicional).
    """
    head_cells = []
    thead = table.find("thead")
    if thead:
        tr = thead.find("tr")
        if tr:
            head_cells = tr.find_all(["th", "td"])
    if not head_cells:
        first = table.find("tr")
        if first:
            head_cells = first.find_all(["th", "td"])
    if not head_cells:
        return None

    labels = [_clean(c.get_text()).lower() for c in head_cells]
    mapping: dict[str, int] = {}
    for i, lab in enumerate(labels):
        if "comprobante" in lab:
            mapping["numero_comprobante"] = i
        elif "acierto" in lab:
            mapping["aciertos"] = i
        elif "acreditad" in lab:
            mapping["acreditado"] = i
        elif "detalle" in lab:
            mapping["detalles"] = i
        elif "diagn" in lab:
            mapping["diagnostico"] = i
    # Debe reconocer al menos comprobante y acreditado para fiarnos del header.
    if "numero_comprobante" in mapping and "acreditado" in mapping:
        return mapping
    return None


def _cell_text(cell) -> str:
    """Texto de una celda. Si trae un <a> de "Detalles", conserva el href."""
    a = cell.find("a")
    if a is not None:
        href = a.get("href", "")
        # Los links javascript: (Diagnóstico) no tienen valor; para Detalles
        # preferimos el href si es una URL real, si no el texto.
        if href and not href.strip().lower().startswith("javascript:"):
            return _clean(href)
    return _clean(cell.get_text())


def parse_table_rows(html: str) -> list[TableRow]:
    """Extrae las filas de aspirantes de la <table>, descartando placeholder y
    la columna Diagnóstico."""
    soup = _soup(html)
    table = soup.find("table")
    if table is None:
        return []

    colmap = _header_map(table)

    body = table.find("tbody") or table
    rows: list[TableRow] = []
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue  # fila de cabecera (th) u vacía

        row_text = _clean(tr.get_text()).lower()
        if _PLACEHOLDER in row_text:
            continue  # fila placeholder

        if colmap:
            def get(name: str) -> str:
                idx = colmap.get(name)
                if idx is None or idx >= len(cells):
                    return ""
                return _cell_text(cells[idx])

            row = TableRow(
                numero_comprobante=get("numero_comprobante"),
                aciertos=get("aciertos"),
                acreditado=get("acreditado"),
                detalles=get("detalles"),
            )
        else:
            # Orden posicional: comprobante, aciertos, acreditado, detalles, [diag]
            vals = [_cell_text(c) for c in cells]
            row = TableRow(
                numero_comprobante=vals[0] if len(vals) > 0 else "",
                aciertos=vals[1] if len(vals) > 1 else "",
                acreditado=vals[2] if len(vals) > 2 else "",
                detalles=vals[3] if len(vals) > 3 else "",
            )

        # Descarta filas totalmente vacías (residuo de maquetado).
        if not any([row.numero_comprobante, row.aciertos, row.acreditado, row.detalles]):
            continue
        rows.append(row)

    return rows


def parse_table(html: str, *, is_suayed: bool = False) -> ParsedTable:
    """Parsea una página de tabla completa: metadata + filas."""
    return ParsedTable(
        meta=parse_table_meta(html, is_suayed=is_suayed),
        rows=parse_table_rows(html),
    )
