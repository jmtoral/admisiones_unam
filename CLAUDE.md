# CLAUDE.md

Guía para el agente que construye y mantiene este proyecto. Léela completa antes
de escribir código. El `README.md` tiene el detalle; este archivo fija las reglas
que no debes romper.

## Contexto

Scraper en Python que extrae a CSV los resultados del Concurso de Selección de
Ingreso a Licenciatura de la UNAM (DGAE), para 2021 a 2026, con el fin de hacer
comparativas entre años. La fuente son páginas HTML estáticas y públicas.

## Objetivo

Tres fases independientes y reanudables:

1. `discover.py`: construye `data/manifest.csv` a partir de las páginas índice.
2. `scrape.py`: baja y parsea cada tabla del manifiesto a un CSV por tabla.
3. `consolidate.py`: genera los CSV maestros.

## Entorno

**Ambiente conda local. No Colab, no notebooks.** La carga es I/O-bound: GPU y
TPU no aportan nada, y una IP de datacenter empeora el bloqueo anti-bot.

Entrega un `environment.yml` con `python=3.11`, `requests`, `beautifulsoup4`,
`lxml`, `pandas` desde `conda-forge`. `playwright` solo por `pip` y solo si se
requiere el fallback.

El código son módulos `.py` ejecutables con `python -m src.<modulo>`. No
entregues `.ipynb`.

## Reglas duras (no negociables)

1. **Throttle adaptativo, no delay fijo.** Implementa el algoritmo de la sección
   "Throttle adaptativo" del README tal cual. El objetivo es ir tan rápido como
   el servidor tolere y desacelerar solo ante señales de rechazo.
2. **Peticiones secuenciales.** Nunca concurrencia contra el host: dispara los
   filtros anti-bot y rompe el throttle adaptativo.
3. **Cachea el HTML crudo** en `data/raw_html/{año}/{codigo}.html`. Antes de
   descargar, revisa la caché. Cada página se baja una sola vez.
4. **Idempotencia.** Si el CSV destino de una tabla ya existe, salta esa tabla.
   El scraper debe cortarse y reanudarse sin re-trabajo.
5. **UTF-8 siempre**, en lectura y escritura.
6. **No inventes URLs ni datos.** Si una página no existe o cambia de
   estructura, regístralo en el log y continúa. No rellenes con valores
   supuestos.
7. **Un fallo no aborta la corrida.** Agotados los reintentos de una URL,
   regístrala como pendiente y sigue con la siguiente.
8. **Separa las fases en módulos.** Red en `http_client.py`, parseo en
   `parsing.py`. Nada de scripts monolíticos.
9. **Valida antes de escalar.** No implementes un año nuevo asumiendo el DOM de
   2026. Prueba una página índice y una tabla de ese año primero.

## Estructura del sitio de origen

Fuente de verdad detallada en el `README.md`. Resumen operativo:

- `https://www.dgae.unam.mx/Licenciatura{año}/resultados/{area}{mod}.html`
  (escolarizado y abierta).
- `https://www.dgae.unam.mx/Suayed{año}/Licenciatura/resultados/{area}{mod}.html`
  (SUAYED a distancia).

`{area}{mod}.html`: primer dígito = área (1-4), segundo = modalidad (`5`
escolarizado, `6` abierta/SUAYED). No existe `16`. El mismo `{area}{mod}` aparece
en ambos árboles con significado distinto: llavea por `(año, árbol, archivo)`.

En cada índice, cada carrera es un `<h3>` seguido de botones
`a.btn.btn-link.waves-effect.waves-light` cuya leyenda es el campus y cuyo `href`
(ya absoluto) apunta a la tabla.

La página de tabla trae `<h2>` (código corto, carrera, campus, modalidad), `<h5>`
de metadata (`Oferta=… Aspirantes=… Presentaron Examen=… Aciertos Minimos=…
Seleccionados=…`), `<h5>` de leyenda, y una `<table>` con columnas `Número de
comprobante | Aciertos | Acreditado | Detalles | Diagnóstico`.

## Gotchas del sitio (obligatorio manejarlos)

- Descarta la fila placeholder `no se encontraron resultados para la búsqueda`.
- Elimina la columna `Diagnóstico` (link `javascript:` sin valor por fila).
- Conserva `Detalles`.
- `Aciertos` puede venir vacío; `Acreditado` es `S` / `N` / `C` / vacío.
- La modalidad se lee del `<title>` o `<h2>`, no se infiere del dígito.
- Los `href` de los botones ya son absolutos; no los reconstruyas.

## Comportamiento de red obligatorio

El sitio tiene detección de bots. Un cliente HTTP con User-Agent por defecto es
rechazado; un navegador entra. Por eso:

- `requests.Session` con cabeceras de navegador real (User-Agent de Chrome
  actual, `Accept`, `Accept-Language: es-MX,es;q=0.9`). Snippet en el README.
- `Referer` con la URL del índice de origen al pedir una tabla.
- Backoff según el throttle adaptativo; respeta `Retry-After` como piso.
- `robots.txt`: léelo una vez y regístralo en el log de forma informativa. El
  `Crawl-delay` no gobierna el throttle. Reporta cualquier `Disallow` sobre las
  rutas de resultados en el log.
- Fallback con Playwright (Chromium headless) solo si un User-Agent de navegador
  sigue bloqueado, lo que indicaría reto por JavaScript. Manteniendo throttle y
  caché. No lo implementes de entrada.

## Convenciones de datos

- Clave de almacenamiento por tabla: `{year}_{codigo}` (el `codigo` se repite
  entre años).
- CSV por tabla: filas por aspirante con contexto inyectado
  (`year, modalidad, area, carrera, campus, codigo` + `numero_comprobante,
  aciertos, acreditado, detalles`).
- `metadata_carreras.csv`: una fila por carrera-campus-año con los campos del
  `<h5>`.
- `resultados_todos.csv`: concatenación de los CSV por tabla.
- Esquemas completos en el README. No cambies nombres de columna sin actualizar
  el README.

## Flujo de trabajo

1. Implementa `http_client.py` (sesión, throttle adaptativo, backoff, caché) y
   `parsing.py` (índice, `<h2>`, `<h5>`, tabla).
2. Implementa `discover.py`; corre y revisa `manifest.csv` a mano.
3. Implementa `scrape.py`; pruébalo con `--solo 10100035` antes de correr todo.
4. Corre acotado a `--year 2026`; valida los CSV.
5. Valida el DOM de cada año anterior con una página índice y una tabla antes de
   incluirlo.
6. Implementa `consolidate.py` al final.

## Comandos

```bash
conda env create -f environment.yml
conda activate unam-scraper

python -m src.discover
python -m src.scrape --solo 10100035     # prueba puntual
python -m src.scrape --year 2026         # acotar por año
python -m src.scrape                     # todo
python -m src.consolidate
```

## Qué NO hacer

- No uses delay fijo ni ventanas horarias. El ritmo lo decide el throttle
  adaptativo.
- No paralelices peticiones al sitio.
- No propongas Colab, notebooks ni GPU para este proyecto.
- No re-descargues páginas ya cacheadas.
- No infieras la modalidad del dígito del archivo.
- No asumas que el DOM de años anteriores es igual al de 2026.
- No guardes la columna `Diagnóstico` ni la fila placeholder.
- No difundas datos a nivel de aspirante individual fuera del uso agregado.
- No inventes atribuciones ni valores faltantes.
