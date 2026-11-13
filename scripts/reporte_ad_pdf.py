"""PDF del reporte ejecutivo de Analítica de Datos: analitica/Reporte_ejecutivo_Salome.md -> .pdf"""
import asyncio
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

RAIZ = Path(__file__).resolve().parents[1]
AD = RAIZ / "analitica"
CSS = (RAIZ / "docs" / "estilo_pdf.css").read_text() + """
body { font-size: 9.6pt; line-height: 1.42; }
h1 { font-size: 17pt; margin-bottom: 8pt; }
h2 { font-size: 12pt; margin-top: 12pt; }
table:first-of-type td:first-child { width: 16%; color: #7a4a2e; font-weight: 600; }
table:first-of-type thead { display: none; }
table { font-size: 8.2pt; page-break-inside: avoid; }
img { width: 100%; max-height: none; margin: 8pt auto 4pt; }
"""


async def main():
    md = AD / "Reporte_ejecutivo_Salome.md"
    cuerpo = subprocess.run(["pandoc", str(md), "-f", "gfm", "-t", "html", "--wrap=none"],
                            capture_output=True, text=True, check=True).stdout
    pagina = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><base href="{AD.as_uri()}/">
<style>{CSS}</style><title>Reporte ejecutivo · Salomé</title></head><body>{cuerpo}</body></html>"""
    tmp = AD / ".reporte.html"
    tmp.write_text(pagina, encoding="utf-8")
    async with async_playwright() as p:
        nav = await p.chromium.launch()
        pg = await nav.new_page()
        await pg.goto(tmp.as_uri())
        await pg.wait_for_timeout(400)
        await pg.pdf(path=str(AD / "Reporte_ejecutivo_Salome.pdf"), format="Letter", print_background=True,
                     display_header_footer=True, header_template="<span></span>",
                     footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#888">'
                                     'Salomé · Reporte ejecutivo · <span class="pageNumber"></span> de <span class="totalPages"></span></div>',
                     margin={"top": "1.6cm", "bottom": "1.6cm", "left": "1.9cm", "right": "1.9cm"})
        await nav.close()
    tmp.unlink()
    print("Reporte_ejecutivo_Salome.pdf")


asyncio.run(main())
