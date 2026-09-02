"""Reglas de auditoría SEO técnica.

Cada check recibe la lista de páginas rastreadas y devuelve incidencias.
La severidad marca el orden de trabajo: primero 'critico', luego 'aviso'.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlparse

from .crawler import Page

# Umbrales. Los de título y meta son los que usa Google para truncar en SERP.
TITULO_MIN, TITULO_MAX = 30, 60
META_MIN, META_MAX = 70, 160
TTFB_LENTO_MS = 1500
HTML_PESADO_KB = 500


@dataclass
class Incidencia:
    regla: str
    severidad: str  # critico | aviso | info
    url: str
    detalle: str

    def as_dict(self) -> dict:
        return {
            "regla": self.regla,
            "severidad": self.severidad,
            "url": self.url,
            "detalle": self.detalle,
        }


def _html_paginas(pages: list[Page]) -> list[Page]:
    return [p for p in pages if p.is_html and 200 <= p.status < 300]


# --- indexabilidad -----------------------------------------------------------

def check_estados(pages: list[Page]) -> list[Incidencia]:
    out = []
    for p in pages:
        if p.error:
            out.append(Incidencia("error_conexion", "critico", p.url, f"No responde: {p.error}"))
        elif p.status >= 500:
            out.append(Incidencia("error_servidor", "critico", p.url, f"HTTP {p.status}"))
        elif p.status == 404:
            out.append(Incidencia("enlace_roto", "critico", p.url, "HTTP 404 enlazada internamente"))
        elif 300 <= p.status < 400 or p.redirected_from:
            origen = p.redirected_from or p.url
            out.append(Incidencia("redireccion_interna", "aviso", origen,
                                  f"Redirige a {p.url}. Actualiza el enlace al destino final."))
    return out


def check_noindex(pages: list[Page]) -> list[Incidencia]:
    """Un noindex accidental es la causa nº1 de caídas de tráfico inexplicables."""
    out = []
    for p in _html_paginas(pages):
        soup = p.soup
        if soup is None:
            continue
        for tag in soup.find_all("meta", attrs={"name": lambda v: v and v.lower() == "robots"}):
            contenido = (tag.get("content") or "").lower()
            if "noindex" in contenido:
                out.append(Incidencia("noindex", "critico", p.url,
                                      f'meta robots="{contenido}" impide la indexación'))
            if "nofollow" in contenido:
                out.append(Incidencia("nofollow_global", "aviso", p.url,
                                      "meta robots nofollow corta el reparto de autoridad"))
    return out


def _buscar_canonical(soup) -> str | None:
    """bs4 entrega rel como lista, así que filtramos a mano en vez de con lambda."""
    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        if isinstance(rel, str):
            rel = [rel]
        if any(r.lower() == "canonical" for r in rel):
            return (link.get("href") or "").strip() or None
    return None


def check_canonical(pages: list[Page]) -> list[Incidencia]:
    out = []
    for p in _html_paginas(pages):
        soup = p.soup
        if soup is None:
            continue
        destino = _buscar_canonical(soup)
        if not destino:
            out.append(Incidencia("sin_canonical", "aviso", p.url, "Falta la etiqueta canonical"))
            continue
        destino_norm = destino.rstrip("/")
        actual = p.url.rstrip("/")
        if destino_norm and destino_norm != actual and urlparse(destino_norm).netloc == urlparse(actual).netloc:
            out.append(Incidencia("canonical_distinta", "info", p.url,
                                  f"Canonical apunta a {destino}"))
    return out


# --- contenido ---------------------------------------------------------------

def check_titulos(pages: list[Page]) -> list[Incidencia]:
    out = []
    vistos: dict[str, list[str]] = defaultdict(list)

    for p in _html_paginas(pages):
        soup = p.soup
        if soup is None:
            continue
        tag = soup.find("title")
        texto = tag.get_text(strip=True) if tag else ""

        if not texto:
            out.append(Incidencia("titulo_ausente", "critico", p.url, "La página no tiene <title>"))
            continue

        vistos[texto].append(p.url)
        n = len(texto)
        if n < TITULO_MIN:
            out.append(Incidencia("titulo_corto", "aviso", p.url,
                                  f"{n} caracteres (mínimo recomendado {TITULO_MIN}): '{texto}'"))
        elif n > TITULO_MAX:
            out.append(Incidencia("titulo_largo", "aviso", p.url,
                                  f"{n} caracteres, se truncará en resultados (máx. {TITULO_MAX})"))

    for texto, urls in vistos.items():
        if len(urls) > 1:
            out.append(Incidencia("titulo_duplicado", "critico", urls[0],
                                  f"'{texto}' se repite en {len(urls)} páginas: "
                                  + ", ".join(urls[1:4])))
    return out


def check_meta_description(pages: list[Page]) -> list[Incidencia]:
    out = []
    vistas: dict[str, list[str]] = defaultdict(list)

    for p in _html_paginas(pages):
        soup = p.soup
        if soup is None:
            continue
        tag = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
        texto = (tag.get("content") or "").strip() if tag else ""

        if not texto:
            out.append(Incidencia("meta_ausente", "aviso", p.url, "Sin meta description"))
            continue

        vistas[texto].append(p.url)
        n = len(texto)
        if n > META_MAX:
            out.append(Incidencia("meta_larga", "info", p.url, f"{n} caracteres (máx. {META_MAX})"))
        elif n < META_MIN:
            out.append(Incidencia("meta_corta", "info", p.url, f"{n} caracteres (mín. {META_MIN})"))

    for texto, urls in vistas.items():
        if len(urls) > 1:
            out.append(Incidencia("meta_duplicada", "aviso", urls[0],
                                  f"Meta description repetida en {len(urls)} páginas"))
    return out


def check_encabezados(pages: list[Page]) -> list[Incidencia]:
    out = []
    for p in _html_paginas(pages):
        soup = p.soup
        if soup is None:
            continue
        h1 = soup.find_all("h1")
        if not h1:
            out.append(Incidencia("sin_h1", "aviso", p.url, "La página no tiene H1"))
        elif len(h1) > 1:
            out.append(Incidencia("h1_multiple", "info", p.url, f"{len(h1)} etiquetas H1"))
    return out


def check_imagenes(pages: list[Page]) -> list[Incidencia]:
    out = []
    for p in _html_paginas(pages):
        soup = p.soup
        if soup is None:
            continue
        sin_alt = [img for img in soup.find_all("img") if not (img.get("alt") or "").strip()]
        if sin_alt:
            muestras = [img.get("src", "?")[:60] for img in sin_alt[:3]]
            out.append(Incidencia("img_sin_alt", "aviso", p.url,
                                  f"{len(sin_alt)} imágenes sin alt: " + ", ".join(muestras)))
    return out


# --- rendimiento y datos estructurados ---------------------------------------

def check_rendimiento(pages: list[Page]) -> list[Incidencia]:
    out = []
    for p in _html_paginas(pages):
        if p.elapsed_ms > TTFB_LENTO_MS:
            out.append(Incidencia("respuesta_lenta", "aviso", p.url,
                                  f"{p.elapsed_ms} ms de respuesta (umbral {TTFB_LENTO_MS} ms)"))
        peso_kb = len(p.html.encode("utf-8")) / 1024
        if peso_kb > HTML_PESADO_KB:
            out.append(Incidencia("html_pesado", "info", p.url, f"HTML de {peso_kb:.0f} KB"))
    return out


def check_datos_estructurados(pages: list[Page]) -> list[Incidencia]:
    """Sin JSON-LD válido no hay resultados enriquecidos ni buena lectura por IAs."""
    out = []
    for p in _html_paginas(pages):
        soup = p.soup
        if soup is None:
            continue
        bloques = soup.find_all("script", attrs={"type": "application/ld+json"})
        if not bloques:
            out.append(Incidencia("sin_jsonld", "info", p.url, "Sin datos estructurados JSON-LD"))
            continue
        for bloque in bloques:
            try:
                json.loads(bloque.string or "")
            except (json.JSONDecodeError, TypeError):
                out.append(Incidencia("jsonld_invalido", "critico", p.url,
                                      "Bloque JSON-LD con sintaxis inválida: Google lo descarta"))
    return out


def check_enlazado_interno(pages: list[Page]) -> list[Incidencia]:
    """Páginas huérfanas: existen pero nadie las enlaza, así que no reciben autoridad."""
    out = []
    entrantes: dict[str, int] = defaultdict(int)
    rastreadas = {p.url for p in pages}

    for p in pages:
        for link in p.links:
            if link != p.url:
                entrantes[link] += 1

    for p in _html_paginas(pages):
        if p.depth > 0 and entrantes.get(p.url, 0) == 0:
            out.append(Incidencia("pagina_huerfana", "aviso", p.url,
                                  "Sin enlaces internos entrantes"))
        elif entrantes.get(p.url, 0) == 1 and p.depth >= 2:
            out.append(Incidencia("enlazado_debil", "info", p.url,
                                  "Solo 1 enlace interno entrante"))
    return out


TODOS_LOS_CHECKS = [
    check_estados,
    check_noindex,
    check_canonical,
    check_titulos,
    check_meta_description,
    check_encabezados,
    check_imagenes,
    check_rendimiento,
    check_datos_estructurados,
    check_enlazado_interno,
]


def auditar(pages: list[Page]) -> list[Incidencia]:
    incidencias: list[Incidencia] = []
    for check in TODOS_LOS_CHECKS:
        incidencias.extend(check(pages))
    orden = {"critico": 0, "aviso": 1, "info": 2}
    return sorted(incidencias, key=lambda i: (orden[i.severidad], i.regla, i.url))
