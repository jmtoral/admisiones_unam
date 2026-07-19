"""Configuración central: años, áreas, modalidades, throttle, rutas y cabeceras.

Único punto de verdad para constantes. El resto de los módulos importa de aquí
(`from src import config`). No hardcodees rutas ni parámetros de red en otro lado.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Cobertura del barrido
# --------------------------------------------------------------------------- #

YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
AREAS = [1, 2, 3, 4]

# Segundo dígito del archivo índice -> etiqueta tentativa de modalidad.
# OJO: es solo pista/verificación. La modalidad REAL se lee del <title>/<h2>
# de cada página, nunca se infiere del dígito (ver parsing.modalidad_from_*).
MOD_ESCOLARIZADO = 5
MOD_ABIERTA = 6

# Archivos índice que existen por árbol (primer dígito = área, segundo = mod).
# No existe "16" (no hay modalidad abierta en el área 1).
INDEX_FILES_LICENCIATURA = ["15", "25", "35", "45", "26", "36", "46"]
INDEX_FILES_SUAYED = ["26", "36", "46"]

# Árboles de URL. `tree` es la llave que desambigua los archivos índice que se
# repiten entre árboles (26/36/46 existen en ambos con modalidad distinta).
TREE_LICENCIATURA = "licenciatura"
TREE_SUAYED = "suayed"

BASE_LICENCIATURA = "https://www.dgae.unam.mx/Licenciatura{year}/resultados/"
BASE_SUAYED = "https://www.dgae.unam.mx/Suayed{year}/Licenciatura/resultados/"

BASE_HOST = "https://www.dgae.unam.mx"

# --------------------------------------------------------------------------- #
# Throttle adaptativo (AIMD invertido). Ver README, sección "Throttle adaptativo".
# --------------------------------------------------------------------------- #

DELAY_MIN = 0.25       # piso del delay entre peticiones (s)
DELAY_START = 1.5      # delay inicial (s)
DELAY_MAX = 30.0       # tope del delay (s)
DELAY_DECAY = 0.9      # multiplicador al acumular una racha de éxitos
DELAY_BACKOFF = 3.0    # multiplicador ante una señal de rechazo
SUCCESS_STREAK = 5     # éxitos consecutivos para bajar el delay
JITTER = 0.20          # jitter aleatorio ±20 % sobre el delay
MAX_RETRIES = 5        # reintentos por URL antes de marcarla pendiente

# Timeout de la petición HTTP (connect, read) en segundos.
HTTP_TIMEOUT = (10, 30)

# --------------------------------------------------------------------------- #
# Fallback de navegador (Playwright). El sitio está detrás de Cloudflare con
# reto JavaScript: un cliente HTTP plano recibe 403 ("Un momento…"). Un Chrome
# real atraviesa el reto. Ver README, "Comportamiento de red".
# --------------------------------------------------------------------------- #

# "auto": intenta requests una vez; si hay rechazo/reto, escala a navegador y se
# queda en navegador el resto de la corrida. "always": navegador de entrada.
# "never": solo requests (útil para tests offline con caché).
FETCH_MODE = "auto"

# Canal del navegador: "chrome"/"msedge" usan el navegador REAL instalado (pasa
# Cloudflare mejor que el Chromium de pruebas de Playwright). None = Chromium.
BROWSER_CHANNEL = "chrome"

# headless=False es lo que atraviesa el Managed Challenge de forma fiable; el
# headless se queda atorado en el reto. Con perfil persistente, la cookie
# cf_clearance se reutiliza entre páginas y corridas.
BROWSER_HEADLESS = False

# Segundos máximos a esperar que Cloudflare resuelva el reto por página.
CHALLENGE_TIMEOUT = 90.0

# Marcadores de título de la página de reto de Cloudflare (es y en).
CHALLENGE_TITLE_MARKERS = ("un momento", "just a moment", "momento…", "moment")

# --------------------------------------------------------------------------- #
# Cabeceras de navegador real (el sitio rechaza el UA por defecto de requests)
# --------------------------------------------------------------------------- #

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

# --------------------------------------------------------------------------- #
# Rutas de salida (todas relativas a la raíz del proyecto)
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_HTML_DIR = DATA_DIR / "raw_html"
TABLES_DIR = DATA_DIR / "tables"
CONSOLIDATED_DIR = DATA_DIR / "consolidated"
MANIFEST_PATH = DATA_DIR / "manifest.csv"
RESULTADOS_TODOS_PATH = CONSOLIDATED_DIR / "resultados_todos.csv"
METADATA_CARRERAS_PATH = CONSOLIDATED_DIR / "metadata_carreras.csv"

LOGS_DIR = PROJECT_ROOT / "logs"
LOG_PATH = LOGS_DIR / "scrape.log"

# Perfil persistente del navegador (guarda cookies de clearance de Cloudflare).
# Fuera de raw_html para no mezclarlo con la caché de HTML.
BROWSER_PROFILE_DIR = DATA_DIR / ".browser_profile"

ENCODING = "utf-8"


def base_url(tree: str, year: int) -> str:
    """URL base del árbol de índices para un año."""
    if tree == TREE_LICENCIATURA:
        return BASE_LICENCIATURA.format(year=year)
    if tree == TREE_SUAYED:
        return BASE_SUAYED.format(year=year)
    raise ValueError(f"árbol desconocido: {tree!r}")


def raw_html_path(year: int, tree: str, codigo: str) -> Path:
    """Ruta de caché del HTML crudo de una tabla hoja.

    Se llavea por (año, árbol, codigo). Verificado en vivo (2026): el `codigo` de
    hoja NO es único globalmente — 9 códigos (los de dígito 6) colisionan entre
    `licenciatura/abierta` y `suayed` (misma carrera-campus, modalidad distinta,
    tabla distinta). Sin el árbol en la clave, la caché se pisaría.
    """
    return RAW_HTML_DIR / str(year) / tree / f"{codigo}.html"


def raw_index_path(year: int, tree: str, index_file: str) -> Path:
    """Ruta de caché del HTML crudo de una página índice.

    Se llavea por (año, árbol, archivo) porque 26/36/46 existen en ambos árboles
    con modalidad distinta.
    """
    stem = index_file[:-5] if index_file.endswith(".html") else index_file
    return RAW_HTML_DIR / str(year) / "_index" / tree / f"{stem}.html"
