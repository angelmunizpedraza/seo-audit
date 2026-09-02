"""Rastreador ligero para auditoría SEO técnica.

Recorre un dominio respetando robots.txt y un límite de páginas,
y devuelve el HTML de cada URL junto con datos de la respuesta.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "seo-audit/1.0 (+https://github.com/angelmunizpedraza/seo-audit)"


@dataclass
class Page:
    """Una página rastreada y todo lo que necesitamos para auditarla."""

    url: str
    status: int
    elapsed_ms: int
    html: str = ""
    content_type: str = ""
    depth: int = 0
    redirected_from: str | None = None
    error: str | None = None
    links: list[str] = field(default_factory=list)

    @property
    def is_html(self) -> bool:
        return "text/html" in self.content_type

    @property
    def soup(self) -> BeautifulSoup | None:
        if not self.is_html or not self.html:
            return None
        # cacheamos para no re-parsear en cada check
        if not hasattr(self, "_soup"):
            self._soup = BeautifulSoup(self.html, "html.parser")
        return self._soup


class Crawler:
    def __init__(
        self,
        start_url: str,
        max_pages: int = 100,
        max_depth: int = 3,
        delay: float = 0.3,
        respect_robots: bool = True,
        timeout: int = 15,
    ):
        self.start_url = self._normalize(start_url)
        self.domain = urlparse(self.start_url).netloc
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

        self.robots = self._load_robots() if respect_robots else None
        self.pages: list[Page] = []
        self.seen: set[str] = set()

    # --- utilidades internas -------------------------------------------------

    @staticmethod
    def _normalize(url: str) -> str:
        """Quita el fragmento (#seccion) y la barra final duplicada.

        Sin esto el rastreo entra en bucle: /precios y /precios#planes
        son la misma página para Google pero URLs distintas para Python.
        """
        url, _ = urldefrag(url.strip())
        parsed = urlparse(url)
        path = parsed.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        return f"{parsed.scheme}://{parsed.netloc}{path}" + (
            f"?{parsed.query}" if parsed.query else ""
        )

    def _load_robots(self) -> RobotFileParser | None:
        parsed = urlparse(self.start_url)
        rp = RobotFileParser()
        rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
        try:
            rp.read()
            return rp
        except Exception:
            # sin robots.txt accesible, rastreamos igual pero lo anotamos
            return None

    def _allowed(self, url: str) -> bool:
        if self.robots is None:
            return True
        return self.robots.can_fetch(USER_AGENT, url)

    def _same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == self.domain

    def _extract_links(self, page: Page) -> list[str]:
        soup = page.soup
        if soup is None:
            return []
        found = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            absolute = self._normalize(urljoin(page.url, href))
            if self._same_domain(absolute):
                found.append(absolute)
        return found

    # --- rastreo -------------------------------------------------------------

    def fetch(self, url: str, depth: int = 0) -> Page:
        started = time.perf_counter()
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            elapsed = int((time.perf_counter() - started) * 1000)

            # Si el servidor no declara charset, requests asume ISO-8859-1 y
            # rompe los acentos. Dejamos que detecte el real por contenido.
            if "charset" not in resp.headers.get("Content-Type", "").lower():
                resp.encoding = resp.apparent_encoding or "utf-8"

            redirected = resp.history[0].url if resp.history else None
            return Page(
                url=resp.url,
                status=resp.status_code,
                elapsed_ms=elapsed,
                html=resp.text if "text/html" in resp.headers.get("Content-Type", "") else "",
                content_type=resp.headers.get("Content-Type", ""),
                depth=depth,
                redirected_from=redirected,
            )
        except requests.RequestException as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            return Page(url=url, status=0, elapsed_ms=elapsed, depth=depth, error=str(exc))

    def crawl(self, verbose: bool = True) -> list[Page]:
        queue: deque[tuple[str, int]] = deque([(self.start_url, 0)])
        self.seen.add(self.start_url)

        while queue and len(self.pages) < self.max_pages:
            url, depth = queue.popleft()

            if not self._allowed(url):
                if verbose:
                    print(f"  robots.txt bloquea: {url}")
                continue

            page = self.fetch(url, depth)
            page.links = self._extract_links(page)
            self.pages.append(page)

            if verbose:
                marca = "OK " if 200 <= page.status < 300 else f"{page.status or 'ERR'}"
                print(f"[{len(self.pages):>3}/{self.max_pages}] {marca} {page.url}")

            if depth < self.max_depth:
                for link in page.links:
                    if link not in self.seen and len(self.seen) < self.max_pages * 3:
                        self.seen.add(link)
                        queue.append((link, depth + 1))

            time.sleep(self.delay)

        return self.pages
