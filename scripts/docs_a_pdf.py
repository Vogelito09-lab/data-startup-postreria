"""Convierte docs/E*.md en PDF con portada (pandoc + Chromium de Playwright).

    python scripts/docs_a_pdf.py            # los cuatro documentos
    python scripts/docs_a_pdf.py E2         # solo uno

Las imágenes de docs/img/evidencia/ se acomodan de dos en dos. Si una captura todavía no existe,
en su lugar sale un recuadro "Captura pendiente" con el nombre del archivo que falta.
"""
import asyncio
import html
import re
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
FECHA = "12 de noviembre de 2026"
FECHAS = {"E2-cimientos": "13 de noviembre de 2026", "E3-produccion": "19 de noviembre de 2026"}  # fecha de la versión entregada
DOCUMENTOS = [
    ("E0-propuesta", "E0 · Propuesta", "DulceDato Analytics para Salomé"),
    ("E1-dashboard", "E1 · Dashboard empresarial", "Salomé, postrería por pedido"),
    ("E2-cimientos", "E2 · Cimientos en la nube", "Los pedidos viajan solos"),
    ("E3-produccion", "E3 · Inteligencia en producción", "El modelo vive en la nube"),
]
IMG = re.compile(r'<p><img src="(img/evidencia/[^"]+)"\s+alt="Evidencia: ([^"]*)"\s*/?></p>')


def evidencias(cuerpo: str) -> tuple[str, list[str]]:
    faltan = []

    def bloque(m):
        ruta, texto = m.group(1), html.unescape(m.group(2))
        if (DOCS / ruta).exists():
            return f'<figure class="evidencia"><img src="{ruta}"><figcaption>{html.escape(texto)}</figcaption></figure>'
        faltan.append(ruta)
        return (f'<div class="pendiente"><div class="rotulo">CAPTURA PENDIENTE</div>'
                f'<div class="texto">{html.escape(texto)}</div><code>docs/{ruta}</code></div>')

    cuerpo = IMG.sub(bloque, cuerpo)
    return agrupar(cuerpo), faltan  # capturas seguidas, de dos en dos


def agrupar(cuerpo: str) -> str:
    lineas, salida, grupo = cuerpo.split("\n"), [], []
    for l in lineas:
        if l.startswith('<figure class="evidencia">') or l.startswith('<div class="pendiente">'):
            grupo.append(l)
            continue
        if grupo and l.strip() == "":
            continue
        if grupo:
            salida.append('<div class="evidencias">' + "".join(grupo) + "</div>")
            grupo = []
        salida.append(l)
    if grupo:
        salida.append('<div class="evidencias">' + "".join(grupo) + "</div>")
    return "\n".join(salida)


async def main(filtro: str | None):
    async with async_playwright() as p:
        navegador = await p.chromium.launch()
        for nombre, titulo, sub in DOCUMENTOS:
            if filtro and not nombre.startswith(filtro):
                continue
            cuerpo = subprocess.run(["pandoc", str(DOCS / f"{nombre}.md"), "-f", "gfm", "-t", "html", "--wrap=none"],
                                    capture_output=True, text=True, check=True).stdout
            cuerpo, faltan = evidencias(cuerpo)
            portada = f"""<div class="portada"><div class="inst">Instituto Tecnológico de Colima</div>
<div class="carrera">Ingeniería en Inteligencia Artificial</div>
<div class="materias">Cómputo en la Nube (IAD-2408) · Analítica de Datos (IAD-2403)<br>Proyecto integrador DATA STARTUP</div>
<div class="titulo">{titulo}</div><div class="sub">{sub}</div>
<div class="equipo">Carlos Antonio Vogel Romero<br>Jarom Cortes Pérez</div>
<div class="fecha">Villa de Álvarez, Colima · {FECHAS.get(nombre, FECHA)}</div></div>"""
            pagina = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><base href="{DOCS.as_uri()}/">
<link rel="stylesheet" href="estilo_pdf.css"><title>{titulo}</title></head><body>{portada}{cuerpo}</body></html>"""
            temporal = DOCS / f".{nombre}.html"
            temporal.write_text(pagina, encoding="utf-8")
            pg = await navegador.new_page()
            await pg.goto(temporal.as_uri())
            await pg.wait_for_timeout(500)
            await pg.pdf(path=str(DOCS / f"{nombre}.pdf"), format="Letter", print_background=True,
                         display_header_footer=True, header_template="<span></span>",
                         footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#888"><span class="pageNumber"></span></div>',
                         margin={"top": "1.8cm", "bottom": "1.8cm", "left": "1.9cm", "right": "1.9cm"})
            await pg.close()
            temporal.unlink()
            print(f"{nombre}.pdf" + (f"  ({len(faltan)} capturas pendientes)" if faltan else ""))
        await navegador.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
