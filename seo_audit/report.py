"""Salida del informe: consola, JSON y HTML."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime

from .checks import Incidencia
from .crawler import Page

ETIQUETAS = {"critico": "CRÍTICO", "aviso": "AVISO", "info": "INFO"}

EXPLICACIONES = {
    "noindex": "Google no indexará esta página. Revisa si es intencionado.",
    "titulo_duplicado": "Compiten entre sí por la misma búsqueda (canibalización).",
    "enlace_roto": "Desperdicia presupuesto de rastreo y empeora la experiencia.",
    "jsonld_invalido": "Google descarta el bloque entero: pierdes resultados enriquecidos.",
    "pagina_huerfana": "No recibe autoridad interna; Google puede tardar en encontrarla.",
    "titulo_largo": "Se corta en resultados y pierdes el mensaje del final.",
    "redireccion_interna": "Cada salto pierde algo de autoridad y ralentiza el rastreo.",
}


def resumen(pages: list[Page], incidencias: list[Incidencia]) -> dict:
    por_severidad = Counter(i.severidad for i in incidencias)
    return {
        "paginas_rastreadas": len(pages),
        "paginas_ok": sum(1 for p in pages if 200 <= p.status < 300),
        "incidencias_total": len(incidencias),
        "criticas": por_severidad.get("critico", 0),
        "avisos": por_severidad.get("aviso", 0),
        "info": por_severidad.get("info", 0),
        "tiempo_medio_ms": round(
            sum(p.elapsed_ms for p in pages) / len(pages)
        ) if pages else 0,
    }


def imprimir_consola(pages: list[Page], incidencias: list[Incidencia]) -> None:
    r = resumen(pages, incidencias)
    print("\n" + "=" * 70)
    print("INFORME DE AUDITORÍA SEO TÉCNICA")
    print("=" * 70)
    print(f"Páginas rastreadas : {r['paginas_rastreadas']}  (respuesta media {r['tiempo_medio_ms']} ms)")
    print(f"Incidencias        : {r['criticas']} críticas · {r['avisos']} avisos · {r['info']} informativas")

    if not incidencias:
        print("\nSin incidencias detectadas.")
        return

    agrupadas: dict[str, list[Incidencia]] = defaultdict(list)
    for i in incidencias:
        agrupadas[i.regla].append(i)

    orden = {"critico": 0, "aviso": 1, "info": 2}
    reglas = sorted(agrupadas.items(), key=lambda kv: (orden[kv[1][0].severidad], -len(kv[1])))

    for regla, grupo in reglas:
        sev = ETIQUETAS[grupo[0].severidad]
        print(f"\n[{sev}] {regla} — {len(grupo)} página(s)")
        if regla in EXPLICACIONES:
            print(f"  → {EXPLICACIONES[regla]}")
        for inc in grupo[:5]:
            print(f"  · {inc.url}")
            print(f"    {inc.detalle}")
        if len(grupo) > 5:
            print(f"  · ... y {len(grupo) - 5} más")
    print()


def guardar_json(ruta: str, pages: list[Page], incidencias: list[Incidencia]) -> None:
    datos = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "resumen": resumen(pages, incidencias),
        "incidencias": [i.as_dict() for i in incidencias],
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def guardar_html(ruta: str, pages: list[Page], incidencias: list[Incidencia]) -> None:
    r = resumen(pages, incidencias)
    colores = {"critico": "#c0392b", "aviso": "#e67e22", "info": "#7f8c8d"}

    filas = "\n".join(
        f'<tr><td><span class="sev" style="background:{colores[i.severidad]}">'
        f'{ETIQUETAS[i.severidad]}</span></td>'
        f"<td><code>{i.regla}</code></td>"
        f'<td><a href="{i.url}" target="_blank" rel="noopener">{i.url}</a></td>'
        f"<td>{i.detalle}</td></tr>"
        for i in incidencias
    )

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Auditoría SEO técnica</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#f5f6f8;color:#1a2b3c}}
 .wrap{{max-width:1100px;margin:0 auto;padding:32px 20px}}
 h1{{margin:0 0 4px}}
 .fecha{{color:#7f8c8d;font-size:14px;margin-bottom:24px}}
 .cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px}}
 .card{{background:#fff;border-radius:10px;padding:16px 20px;flex:1;min-width:150px;
        box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 .card .n{{font-size:30px;font-weight:700}}
 .card .l{{color:#7f8c8d;font-size:13px;text-transform:uppercase;letter-spacing:.4px}}
 table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;
        box-shadow:0 1px 3px rgba(0,0,0,.08);font-size:14px}}
 th{{text-align:left;background:#1a2b3c;color:#fff;padding:11px 14px;font-weight:600}}
 td{{padding:11px 14px;border-top:1px solid #edf0f2;vertical-align:top}}
 td a{{color:#0e7c7b;text-decoration:none;word-break:break-all}}
 code{{background:#eef1f3;padding:2px 6px;border-radius:4px;font-size:12px}}
 .sev{{color:#fff;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:700;
       white-space:nowrap}}
</style></head><body><div class="wrap">
<h1>Auditoría SEO técnica</h1>
<div class="fecha">Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}</div>
<div class="cards">
 <div class="card"><div class="n">{r['paginas_rastreadas']}</div><div class="l">Páginas</div></div>
 <div class="card"><div class="n" style="color:{colores['critico']}">{r['criticas']}</div><div class="l">Críticas</div></div>
 <div class="card"><div class="n" style="color:{colores['aviso']}">{r['avisos']}</div><div class="l">Avisos</div></div>
 <div class="card"><div class="n">{r['tiempo_medio_ms']} ms</div><div class="l">Respuesta media</div></div>
</div>
<table><thead><tr><th>Severidad</th><th>Regla</th><th>URL</th><th>Detalle</th></tr></thead>
<tbody>
{filas}
</tbody></table></div></body></html>"""

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
