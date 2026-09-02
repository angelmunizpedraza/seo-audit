"""Auditor de SEO técnico: rastrea un sitio y detecta problemas de indexación,
contenido, rendimiento y datos estructurados."""

__version__ = "1.0.0"

from .crawler import Crawler, Page
from .checks import auditar, Incidencia
from .report import imprimir_consola, guardar_json, guardar_html

__all__ = ["Crawler", "Page", "auditar", "Incidencia",
           "imprimir_consola", "guardar_json", "guardar_html"]
