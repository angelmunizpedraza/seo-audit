"""Punto de entrada CLI: python -m seo_audit https://ejemplo.com"""

import argparse
import sys

from .crawler import Crawler
from .checks import auditar
from .report import imprimir_consola, guardar_json, guardar_html, resumen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="seo-audit",
        description="Auditoría SEO técnica de un sitio web.",
    )
    parser.add_argument("url", help="URL inicial, por ejemplo https://ejemplo.com")
    parser.add_argument("-n", "--max-pages", type=int, default=50,
                        help="máximo de páginas a rastrear (por defecto 50)")
    parser.add_argument("-d", "--max-depth", type=int, default=3,
                        help="profundidad máxima de rastreo (por defecto 3)")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="segundos de espera entre peticiones (por defecto 0.3)")
    parser.add_argument("--ignorar-robots", action="store_true",
                        help="no respetar robots.txt (solo en sitios propios)")
    parser.add_argument("--json", metavar="RUTA", help="guardar informe en JSON")
    parser.add_argument("--html", metavar="RUTA", help="guardar informe en HTML")
    parser.add_argument("-q", "--quiet", action="store_true", help="sin progreso de rastreo")
    parser.add_argument("--fallar-si-criticas", action="store_true",
                        help="salir con código 1 si hay incidencias críticas (útil en CI)")

    args = parser.parse_args(argv)

    if not args.url.startswith(("http://", "https://")):
        args.url = "https://" + args.url

    print(f"Rastreando {args.url} (máx. {args.max_pages} páginas)...\n")

    crawler = Crawler(
        args.url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay=args.delay,
        respect_robots=not args.ignorar_robots,
    )
    pages = crawler.crawl(verbose=not args.quiet)

    if not pages:
        print("No se pudo rastrear ninguna página. Revisa la URL o la conexión.")
        return 1

    incidencias = auditar(pages)
    imprimir_consola(pages, incidencias)

    if args.json:
        guardar_json(args.json, pages, incidencias)
        print(f"JSON guardado en {args.json}")
    if args.html:
        guardar_html(args.html, pages, incidencias)
        print(f"HTML guardado en {args.html}")

    if args.fallar_si_criticas and resumen(pages, incidencias)["criticas"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
