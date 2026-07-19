"""Cliente HTTP: sesión con cabeceras de navegador, throttle adaptativo
(AIMD invertido), backoff, caché de HTML crudo y logging.

Todo el conocimiento de red vive aquí. El parseo vive en `parsing.py`.

Diseño (ver README, "Throttle adaptativo" y "Comportamiento de red"):
- Peticiones ESTRICTAMENTE secuenciales. Nunca concurrencia contra el host.
- Un único estado de `delay` por corrida (mismo host).
- Caché obligatoria: cada página se baja una sola vez.
- Un fallo agotados los reintentos no aborta la corrida: se registra y se sigue.
"""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from src import config

logger = logging.getLogger("unam-scraper.http")


# --------------------------------------------------------------------------- #
# Excepciones y señales
# --------------------------------------------------------------------------- #


class FetchError(Exception):
    """Se agotaron los reintentos de una URL. Quien llama la marca pendiente."""


class _RejectionSignal(Exception):
    """Señal interna de rechazo del servidor; dispara backoff y reintento."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


# Heurística de "reto anti-bot" en el cuerpo de una respuesta 200. El sitio real
# devuelve páginas con <h2>/<table> o índices con botones; una respuesta 200 sin
# nada de eso y con marcadores de challenge indica un muro anti-bot (JS/captcha).
_CHALLENGE_MARKERS = (
    "captcha",
    "are you human",
    "verificación de seguridad",
    "cf-challenge",
    "cf_chl",
    "just a moment",
    "un momento",          # reto de Cloudflare en español
    "enable javascript",
    "attention required",
    "checking your browser",
    "ddos",
)

# Marcadores de que la respuesta SÍ es contenido real del sitio (whitelist).
# Si aparece alguno, no la tratamos como reto aunque contenga alguna palabra
# ambigua.
_CONTENT_MARKERS = (
    "<table",
    "waves-light",
    "concurso",
    "resultados",
    "aspirantes",
)


def looks_like_challenge(html: str) -> bool:
    """Heurística: ¿esta respuesta 200 es en realidad un muro anti-bot?

    Regla: si el cuerpo trae marcadores de contenido real -> no es reto. Si no,
    y además trae un marcador de challenge (o es sospechosamente corto sin
    estructura), lo tratamos como rechazo.
    """
    low = html.lower()
    if any(m in low for m in _CONTENT_MARKERS):
        return False
    if any(m in low for m in _CHALLENGE_MARKERS):
        return True
    # 200 sin estructura reconocible y muy corto: sospechoso.
    if len(html) < 512 and "<html" in low:
        return True
    return False


# --------------------------------------------------------------------------- #
# Throttle adaptativo (AIMD invertido)
# --------------------------------------------------------------------------- #


class AdaptiveThrottle:
    """Estado del delay adaptativo. Único por corrida.

    - Éxito: acumula racha; a los SUCCESS_STREAK éxitos limpios, delay *= DECAY
      (piso DELAY_MIN) y reinicia la racha.
    - Rechazo: delay *= BACKOFF (tope DELAY_MAX), reinicia la racha.
    - `wait()` duerme el delay actual con jitter ±JITTER.
    """

    def __init__(self) -> None:
        self.delay = config.DELAY_START
        self.streak = 0

    def wait(self) -> None:
        jitter = 1.0 + random.uniform(-config.JITTER, config.JITTER)
        time.sleep(max(0.0, self.delay * jitter))

    def on_success(self) -> None:
        self.streak += 1
        if self.streak >= config.SUCCESS_STREAK:
            new = max(config.DELAY_MIN, self.delay * config.DELAY_DECAY)
            if new != self.delay:
                logger.info("throttle: éxito x%d -> delay %.3f→%.3f s",
                            config.SUCCESS_STREAK, self.delay, new)
            self.delay = new
            self.streak = 0

    def on_rejection(self, retry_after: float | None = None) -> None:
        new = min(config.DELAY_MAX, self.delay * config.DELAY_BACKOFF)
        logger.warning("throttle: rechazo -> delay %.3f→%.3f s", self.delay, new)
        self.delay = new
        self.streak = 0
        if retry_after is not None and retry_after > 0:
            # Retry-After es piso de espera adicional antes del próximo intento.
            logger.warning("throttle: Retry-After=%.1f s (piso)", retry_after)
            time.sleep(retry_after)


# --------------------------------------------------------------------------- #
# Fallback de navegador (Playwright) para atravesar el reto de Cloudflare
# --------------------------------------------------------------------------- #


class BrowserFetcher:
    """Navegador real persistente (Chrome) que atraviesa el reto de Cloudflare.

    Mantiene UN contexto abierto por corrida: así la cookie `cf_clearance` se
    reutiliza entre páginas (solo el primer hit paga el reto). El throttle se
    aplica igual que en requests. La caché de HTML vive en HttpClient; aquí solo
    se navega y se devuelve el HTML renderizado.

    Playwright se importa perezosamente para no exigirlo si FETCH_MODE="never".
    """

    def __init__(self, throttle: "AdaptiveThrottle") -> None:
        self.throttle = throttle
        self._pw = None
        self._ctx = None
        self._page = None

    def start(self) -> None:
        if self._ctx is not None:
            return
        from playwright.sync_api import sync_playwright

        config.BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        launch_kwargs = dict(
            user_data_dir=str(config.BROWSER_PROFILE_DIR),
            headless=config.BROWSER_HEADLESS,
            locale="es-MX",
            viewport={"width": 1280, "height": 800},
            user_agent=config.HEADERS["User-Agent"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        if config.BROWSER_CHANNEL:
            launch_kwargs["channel"] = config.BROWSER_CHANNEL
        self._ctx = self._pw.chromium.launch_persistent_context(**launch_kwargs)
        # Oculta señales de automatización que Cloudflare inspecciona.
        self._ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        logger.info("navegador iniciado (channel=%s headless=%s)",
                    config.BROWSER_CHANNEL, config.BROWSER_HEADLESS)

    def _in_challenge(self, title: str) -> bool:
        low = (title or "").lower()
        return any(m in low for m in config.CHALLENGE_TITLE_MARKERS)

    def fetch(self, url: str, *, referer: str | None = None) -> str:
        """Navega a `url` con throttle y devuelve el HTML tras pasar el reto.

        Lanza _RejectionSignal si el reto no se resuelve dentro de
        CHALLENGE_TIMEOUT (quien llama aplica backoff / reintento).
        """
        self.start()
        self.throttle.wait()

        if referer:
            self._page.set_extra_http_headers({"Referer": referer})
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:  # noqa: BLE001 - navegación puede fallar de varias formas
            raise _RejectionSignal(f"navegación falló: {exc}") from exc

        # Espera activa a que Cloudflare resuelva el reto (el título deja de ser
        # "Un momento…"). No dependemos de un selector de contenido concreto para
        # no acoplar el cliente al DOM; eso lo valida parsing.py.
        deadline = time.time() + config.CHALLENGE_TIMEOUT
        while time.time() < deadline:
            title = self._page.title()
            if not self._in_challenge(title):
                return self._page.content()
            time.sleep(1.5)

        raise _RejectionSignal(
            f"reto de Cloudflare sin resolver en {config.CHALLENGE_TIMEOUT:.0f}s: {url}"
        )

    def close(self) -> None:
        try:
            if self._ctx is not None:
                self._ctx.close()
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # noqa: BLE001 - cierre best-effort
            pass
        finally:
            self._ctx = self._page = self._pw = None


# --------------------------------------------------------------------------- #
# Cliente
# --------------------------------------------------------------------------- #


class HttpClient:
    """Sesión + throttle + caché + fallback de navegador.

    Reutiliza una instancia por corrida. Úsala como context manager para cerrar
    el navegador al final:

        with HttpClient() as client:
            html = client.fetch(url, cache_path)
    """

    def __init__(
        self,
        throttle: AdaptiveThrottle | None = None,
        *,
        fetch_mode: str | None = None,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        self.throttle = throttle or AdaptiveThrottle()
        self.fetch_mode = fetch_mode or config.FETCH_MODE
        self._robots_checked = False
        self._browser: BrowserFetcher | None = None
        # En modo "auto", una vez que requests es rechazado escalamos a navegador
        # y nos quedamos ahí el resto de la corrida (todo el sitio está tras CF).
        self._force_browser = self.fetch_mode == "always"

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    # -- robots.txt (informativo; no gobierna el throttle) ------------------ #

    def check_robots(self) -> None:
        """Lee robots.txt una vez y lo registra en el log de forma informativa.

        El Crawl-delay NO gobierna el throttle. Un Disallow sobre rutas de
        resultados se reporta para que sea una decisión consciente.
        """
        if self._robots_checked:
            return
        self._robots_checked = True
        robots_url = f"{config.BASE_HOST}/robots.txt"
        try:
            resp = self.session.get(robots_url, timeout=config.HTTP_TIMEOUT)
        except requests.RequestException as exc:
            logger.info("robots.txt no accesible (%s); se continúa.", exc)
            return
        if resp.status_code != 200:
            logger.info("robots.txt devolvió %d; se continúa.", resp.status_code)
            return

        rp = RobotFileParser()
        rp.parse(resp.text.splitlines())
        cd = rp.crawl_delay(config.HEADERS["User-Agent"]) or rp.crawl_delay("*")
        if cd:
            logger.info("robots.txt Crawl-delay=%s (informativo; no gobierna el "
                        "throttle).", cd)
        # Reporta Disallow que toque rutas de resultados.
        for line in resp.text.splitlines():
            s = line.strip().lower()
            if s.startswith("disallow") and ("resultado" in s or s.endswith(": /")):
                logger.warning("robots.txt Disallow relevante: %s", line.strip())

    # -- caché --------------------------------------------------------------- #

    @staticmethod
    def _read_cache(path: Path) -> str | None:
        if path.exists():
            return path.read_text(encoding=config.ENCODING)
        return None

    @staticmethod
    def _write_cache(path: Path, html: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding=config.ENCODING)

    # -- fetch con throttle, backoff y caché -------------------------------- #

    def fetch(
        self,
        url: str,
        cache_path: Path | None = None,
        *,
        referer: str | None = None,
    ) -> str:
        """Devuelve el HTML de `url`, usando caché si existe.

        - Si `cache_path` existe, lo lee y NO toca la red.
        - Si no, descarga con throttle adaptativo y backoff, y cachea el crudo.
        - Agotados los reintentos, lanza FetchError (quien llama la marca
          pendiente y sigue; un fallo no aborta la corrida).
        """
        if cache_path is not None:
            cached = self._read_cache(cache_path)
            if cached is not None:
                logger.debug("caché HIT %s", cache_path)
                return cached

        html = self._get(url, referer=referer)

        if cache_path is not None:
            self._write_cache(cache_path, html)
        return html

    # -- orquestación requests <-> navegador -------------------------------- #

    def _ensure_browser(self) -> BrowserFetcher:
        if self._browser is None:
            self._browser = BrowserFetcher(self.throttle)
        return self._browser

    def _get(self, url: str, *, referer: str | None) -> str:
        """Elige el mecanismo de descarga según el modo y el estado de escalado.

        - Ya escalados (o modo "always"): navegador con reintentos.
        - Modo "auto" sin escalar aún: una sonda con requests; si hay rechazo,
          escala a navegador para esta URL y para el resto de la corrida.
        - Modo "never": solo requests con reintentos.
        """
        if self._force_browser:
            return self._browser_with_retries(url, referer=referer)

        if self.fetch_mode == "never":
            return self._requests_with_retries(url, referer=referer)

        # Modo "auto": sondear requests una vez. Como todo el sitio está tras
        # Cloudflare, un rechazo aquí significa que hay que escalar ya, sin gastar
        # los 5 reintentos de requests contra un muro que no cede.
        try:
            return self._requests_once(url, referer=referer)
        except _RejectionSignal as sig:
            logger.warning("requests rechazado (%s); escalando a navegador para "
                           "el resto de la corrida.", sig)
            self.throttle.on_rejection(sig.retry_after)
            self._force_browser = True
            return self._browser_with_retries(url, referer=referer)

    def _requests_once(self, url: str, *, referer: str | None) -> str:
        """Un solo intento con requests. Lanza _RejectionSignal si es rechazado."""
        headers = {"Referer": referer} if referer else None
        self.throttle.wait()
        try:
            resp = self.session.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
            self._raise_if_rejected(resp)
        except requests.Timeout as exc:
            raise _RejectionSignal("timeout") from exc
        except requests.RequestException as exc:
            raise _RejectionSignal(f"error de red: {exc}") from exc
        self.throttle.on_success()
        return resp.text

    def _requests_with_retries(self, url: str, *, referer: str | None) -> str:
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                return self._requests_once(url, referer=referer)
            except _RejectionSignal as sig:
                logger.warning("rechazo en %s (intento %d/%d): %s",
                               url, attempt, config.MAX_RETRIES, sig)
                self.throttle.on_rejection(sig.retry_after)
        raise FetchError(f"agotados {config.MAX_RETRIES} reintentos: {url}")

    def _browser_with_retries(self, url: str, *, referer: str | None) -> str:
        browser = self._ensure_browser()
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                html = browser.fetch(url, referer=referer)
            except _RejectionSignal as sig:
                logger.warning("navegador rechazado en %s (intento %d/%d): %s",
                               url, attempt, config.MAX_RETRIES, sig)
                self.throttle.on_rejection(sig.retry_after)
                continue
            self.throttle.on_success()
            return html
        raise FetchError(f"agotados {config.MAX_RETRIES} reintentos (navegador): {url}")

    @staticmethod
    def _raise_if_rejected(resp: requests.Response) -> None:
        """Traduce status y cuerpo en señal de rechazo si aplica."""
        if resp.status_code in (429, 503, 403):
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            raise _RejectionSignal(f"HTTP {resp.status_code}", retry_after)
        # 200 con reto anti-bot en el cuerpo (heurística).
        if resp.status_code == 200 and looks_like_challenge(resp.text):
            raise _RejectionSignal("reto anti-bot en el cuerpo (200)")
        # Otros errores server-side también valen backoff.
        if resp.status_code >= 500:
            raise _RejectionSignal(f"HTTP {resp.status_code}")
        # 404 y otros 4xx no se reintentan como rechazo: son "no existe".
        resp.raise_for_status()


def _parse_retry_after(value: str | None) -> float | None:
    """Parsea la cabecera Retry-After (solo el formato de segundos enteros)."""
    if not value:
        return None
    try:
        return float(value.strip())
    except ValueError:
        # Formato de fecha HTTP: no lo soportamos como piso preciso; ignoramos.
        return None
