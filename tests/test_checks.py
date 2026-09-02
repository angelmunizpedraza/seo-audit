"""Tests de las reglas de auditoría.

Construimos objetos Page a mano con HTML controlado para comprobar
que cada regla detecta lo que debe y no genera falsos positivos.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seo_audit.crawler import Page  # noqa: E402
from seo_audit.checks import (  # noqa: E402
    auditar,
    check_canonical,
    check_datos_estructurados,
    check_encabezados,
    check_enlazado_interno,
    check_estados,
    check_imagenes,
    check_meta_description,
    check_noindex,
    check_titulos,
)


def pagina(url="https://ejemplo.com/", html="", status=200, depth=0, **kw):
    return Page(
        url=url,
        status=status,
        elapsed_ms=100,
        html=html,
        content_type="text/html; charset=utf-8",
        depth=depth,
        **kw,
    )


def envolver(head="", body=""):
    return f"<!DOCTYPE html><html lang='es'><head>{head}</head><body>{body}</body></html>"


def reglas(incidencias):
    return {i.regla for i in incidencias}


# --- estados -----------------------------------------------------------------

def test_detecta_404():
    p = Page(url="https://ejemplo.com/roto", status=404, elapsed_ms=50)
    assert "enlace_roto" in reglas(check_estados([p]))


def test_detecta_error_servidor():
    p = Page(url="https://ejemplo.com/x", status=503, elapsed_ms=50)
    assert "error_servidor" in reglas(check_estados([p]))


def test_detecta_redireccion():
    p = pagina(url="https://ejemplo.com/final", redirected_from="https://ejemplo.com/vieja")
    inc = check_estados([p])
    assert "redireccion_interna" in reglas(inc)
    assert inc[0].url == "https://ejemplo.com/vieja"


def test_pagina_correcta_no_genera_incidencia_de_estado():
    assert check_estados([pagina(html=envolver())]) == []


# --- indexabilidad -----------------------------------------------------------

def test_detecta_noindex():
    html = envolver(head="<meta name='robots' content='noindex, follow'>")
    assert "noindex" in reglas(check_noindex([pagina(html=html)]))


def test_index_follow_no_es_incidencia():
    html = envolver(head="<meta name='robots' content='index, follow'>")
    assert check_noindex([pagina(html=html)]) == []


def test_canonical_presente_no_genera_aviso():
    html = envolver(head="<link rel='canonical' href='https://ejemplo.com/'>")
    assert "sin_canonical" not in reglas(check_canonical([pagina(html=html)]))


def test_canonical_ausente_genera_aviso():
    assert "sin_canonical" in reglas(check_canonical([pagina(html=envolver())]))


def test_canonical_apuntando_a_otra_url():
    html = envolver(head="<link rel='canonical' href='https://ejemplo.com/otra'>")
    assert "canonical_distinta" in reglas(check_canonical([pagina(html=html)]))


# --- contenido ---------------------------------------------------------------

def test_titulo_ausente():
    assert "titulo_ausente" in reglas(check_titulos([pagina(html=envolver())]))


def test_titulo_corto():
    html = envolver(head="<title>Cursos</title>")
    assert "titulo_corto" in reglas(check_titulos([pagina(html=html)]))


def test_titulo_largo():
    html = envolver(head=f"<title>{'palabra ' * 15}</title>")
    assert "titulo_largo" in reglas(check_titulos([pagina(html=html)]))


def test_titulo_de_longitud_correcta_no_avisa():
    html = envolver(head="<title>Cursos de criminalistica online con titulacion</title>")
    assert check_titulos([pagina(html=html)]) == []


def test_titulos_duplicados_entre_paginas():
    html = envolver(head="<title>Cursos de criminalistica online con titulacion</title>")
    paginas = [pagina(url="https://ejemplo.com/a", html=html),
               pagina(url="https://ejemplo.com/b", html=html)]
    inc = check_titulos(paginas)
    assert "titulo_duplicado" in reglas(inc)


def test_meta_description_ausente():
    assert "meta_ausente" in reglas(check_meta_description([pagina(html=envolver())]))


def test_meta_description_correcta():
    desc = "Formacion online especializada en criminalistica con titulacion propia y tutorias."
    html = envolver(head=f"<meta name='description' content='{desc}'>")
    assert check_meta_description([pagina(html=html)]) == []


def test_sin_h1():
    assert "sin_h1" in reglas(check_encabezados([pagina(html=envolver(body="<p>hola</p>"))]))


def test_h1_multiple():
    html = envolver(body="<h1>Uno</h1><h1>Dos</h1>")
    assert "h1_multiple" in reglas(check_encabezados([pagina(html=html)]))


def test_un_solo_h1_es_correcto():
    assert check_encabezados([pagina(html=envolver(body="<h1>Uno</h1>"))]) == []


def test_imagen_sin_alt():
    html = envolver(body="<img src='/a.png'>")
    assert "img_sin_alt" in reglas(check_imagenes([pagina(html=html)]))


def test_imagen_con_alt_vacio_cuenta_como_sin_alt():
    html = envolver(body="<img src='/a.png' alt='   '>")
    assert "img_sin_alt" in reglas(check_imagenes([pagina(html=html)]))


def test_imagen_con_alt_correcto():
    html = envolver(body="<img src='/a.png' alt='Aula de practicas'>")
    assert check_imagenes([pagina(html=html)]) == []


# --- datos estructurados -----------------------------------------------------

def test_jsonld_valido_no_genera_incidencia():
    html = envolver(head='<script type="application/ld+json">{"@type":"Organization"}</script>')
    assert check_datos_estructurados([pagina(html=html)]) == []


def test_jsonld_invalido_es_critico():
    html = envolver(head='<script type="application/ld+json">{roto}</script>')
    inc = check_datos_estructurados([pagina(html=html)])
    assert inc[0].regla == "jsonld_invalido"
    assert inc[0].severidad == "critico"


def test_sin_jsonld_es_informativo():
    inc = check_datos_estructurados([pagina(html=envolver())])
    assert inc[0].severidad == "info"


# --- enlazado ----------------------------------------------------------------

def test_pagina_huerfana():
    inicio = pagina(url="https://ejemplo.com/", html=envolver(), depth=0)
    inicio.links = []
    huerfana = pagina(url="https://ejemplo.com/sola", html=envolver(), depth=1)
    assert "pagina_huerfana" in reglas(check_enlazado_interno([inicio, huerfana]))


def test_pagina_enlazada_no_es_huerfana():
    inicio = pagina(url="https://ejemplo.com/", html=envolver(), depth=0)
    inicio.links = ["https://ejemplo.com/hija"]
    hija = pagina(url="https://ejemplo.com/hija", html=envolver(), depth=1)
    hija.links = ["https://ejemplo.com/"]
    assert "pagina_huerfana" not in reglas(check_enlazado_interno([inicio, hija]))


# --- integración -------------------------------------------------------------

def test_auditar_ordena_criticas_primero():
    rota = Page(url="https://ejemplo.com/404", status=404, elapsed_ms=10)
    sin_h1 = pagina(url="https://ejemplo.com/x", html=envolver(head="<title>Un titulo suficientemente largo aqui</title>"))
    incidencias = auditar([rota, sin_h1])
    assert incidencias[0].severidad == "critico"


def test_paginas_no_html_se_ignoran():
    pdf = Page(url="https://ejemplo.com/a.pdf", status=200, elapsed_ms=10,
               content_type="application/pdf")
    assert check_titulos([pdf]) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
