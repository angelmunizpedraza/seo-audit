# seo-audit

[![CI](https://github.com/angelmunizpedraza/seo-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/angelmunizpedraza/seo-audit/actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Auditoría SEO técnica desde línea de comandos. Rastrea un sitio y devuelve las
incidencias que afectan a indexación, contenido, rendimiento y datos estructurados,
ordenadas por gravedad.

Lo escribí porque en las auditorías que hago repetía siempre las mismas
comprobaciones a mano. Ahora lanzo un comando antes de tocar nada y sé por dónde
empezar.

## Instalación

```bash
pip install "seo-audit @ git+https://github.com/angelmunizpedraza/seo-audit"
```

O para trabajar sobre el código:

```bash
git clone https://github.com/angelmunizpedraza/seo-audit
cd seo-audit
pip install -e ".[dev]"
```

## Uso

```bash
seo-audit https://ejemplo.com
```

(`python -m seo_audit` sigue funcionando igual.)

### Como GitHub Action

Rastrea el sitio ya desplegado y tumba el build si el despliegue ha metido una
incidencia crítica (un `noindex` accidental, un 5xx, un canonical roto):

```yaml
- uses: angelmunizpedraza/seo-audit@main
  with:
    url: https://ejemplo.com
    max-pages: "100"
    fail-on-critical: "true"
```

Entradas: `url`, `max-pages` (50), `max-depth` (3), `delay` (0.3),
`fail-on-critical` (true), `json` (seo-audit.json), `html`, `python-version` (3.12)
y `ref`. La CI de este repositorio ejecuta la propia action contra un sitio real en
cada push.

Con informe en HTML y más páginas:

```bash
python -m seo_audit https://ejemplo.com -n 200 --html informe.html
```

### Opciones

| Opción | Descripción |
|---|---|
| `-n, --max-pages` | Máximo de páginas a rastrear (por defecto 50) |
| `-d, --max-depth` | Profundidad máxima desde la URL inicial (por defecto 3) |
| `--delay` | Segundos entre peticiones (por defecto 0.3) |
| `--json RUTA` | Guarda el informe en JSON |
| `--html RUTA` | Guarda el informe en HTML |
| `--ignorar-robots` | Ignora robots.txt (solo para sitios propios) |
| `--fallar-si-criticas` | Devuelve código 1 si hay críticas, para usar en CI |

## Qué comprueba

**Indexabilidad**
- `noindex` en meta robots — la causa más común de caídas de tráfico inexplicables
- Enlaces internos rotos (404) y errores de servidor (5xx)
- Redirecciones internas que deberían apuntar ya al destino final
- Canonical ausente o apuntando a otra URL

**Contenido**
- Títulos ausentes, cortos, largos o duplicados entre páginas (canibalización)
- Meta descriptions ausentes, fuera de longitud o repetidas
- Páginas sin H1 o con varios
- Imágenes sin atributo `alt`

**Rendimiento**
- Tiempo de respuesta por encima de 1,5 s
- HTML por encima de 500 KB

**Datos estructurados**
- Bloques JSON-LD con sintaxis inválida, que Google descarta enteros
- Páginas sin datos estructurados

**Enlazado interno**
- Páginas huérfanas: existen pero no reciben ningún enlace interno
- Páginas con un solo enlace entrante a profundidad 2 o mayor

## Ejemplo de salida

```
======================================================================
INFORME DE AUDITORÍA SEO TÉCNICA
======================================================================
Páginas rastreadas : 48  (respuesta media 412 ms)
Incidencias        : 4 críticas · 11 avisos · 3 informativas

[CRÍTICO] titulo_duplicado — 6 página(s)
  → Compiten entre sí por la misma búsqueda (canibalización).
  · https://ejemplo.com/cursos/perito
    'Curso de perito judicial' se repite en 6 páginas
```

## Uso en integración continua

Con `--fallar-si-criticas` el comando devuelve código 1, así que se puede usar
como puerta de calidad antes de desplegar:

```yaml
- name: Auditoría SEO
  run: python -m seo_audit https://staging.ejemplo.com --fallar-si-criticas
```

## Decisiones de diseño

**Un `Page` con el HTML dentro y el `BeautifulSoup` cacheado.** Cada regla necesita
el árbol parseado; parsearlo diez veces por página multiplicaba el tiempo sin
motivo.

**Normalización de URLs antes de encolar.** Sin quitar el fragmento (`#seccion`) y
la barra final, el rastreador visita la misma página varias veces y se queda
dando vueltas en lugar de avanzar.

**El charset se detecta por contenido cuando el servidor no lo declara.** `requests`
asume ISO-8859-1 en ese caso y los acentos llegan rotos, lo que hacía que dos
títulos idénticos no se detectaran como duplicados.

**Las reglas son funciones independientes** que reciben la lista de páginas y
devuelven incidencias. Añadir una comprobación nueva es escribir una función y
meterla en `TODOS_LOS_CHECKS`.

**Severidad en tres niveles.** Un `noindex` accidental y una meta description
larga no son el mismo problema, y un informe que no prioriza no sirve para
decidir por dónde empezar.

## Tests

```bash
pytest tests/ -v
```

29 tests que cubren cada regla con casos positivos y negativos, porque un
auditor que da falsos positivos deja de usarse a la semana.

## Limitaciones conocidas

- No ejecuta JavaScript: en sitios renderizados en cliente verá el HTML inicial.
  Para esos casos hace falta un navegador headless.
- No mide Core Web Vitals reales (LCP, CLS, INP); el tiempo de respuesta es
  orientativo, no sustituye a datos de campo.
- No consulta la API de Search Console, así que no sabe qué está indexado de verdad.

## Licencia

MIT

## Related tools

Part of a set of nine open-source tools I use on client work — all Python, MIT, deterministic, no API keys:

[geo-check](https://github.com/angelmunizpedraza/geo-check) · [render-gap](https://github.com/angelmunizpedraza/render-gap) · [llms-txt-generator](https://github.com/angelmunizpedraza/llms-txt-generator) · [citeable](https://github.com/angelmunizpedraza/citeable) · [serp-to-ai-diff](https://github.com/angelmunizpedraza/serp-to-ai-diff) · [ai-visibility-tracker](https://github.com/angelmunizpedraza/ai-visibility-tracker) · [linkjuice](https://github.com/angelmunizpedraza/linkjuice) · [ga4-report](https://github.com/angelmunizpedraza/ga4-report)

`geo-check` asks whether the AI crawlers are allowed in. `render-gap` asks whether anything was there when they arrived. `citeable` asks whether it was worth quoting.
