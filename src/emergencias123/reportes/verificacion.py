"""Verificación de entregables en Colab: recálculo de fórmulas xlsx y conteo de páginas de docx.

Usa LibreOffice en modo headless, instalado en el runtime de Colab (notebook de informes:
`apt-get install libreoffice-calc libreoffice-writer`). Las celdas que escribe openpyxl no traen valor en caché:
LibreOffice las calcula al convertir el libro y así se detectan errores de fórmula. Los docx se exportan a PDF
para contar las páginas tal como se renderizan.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from openpyxl import load_workbook

ERRORES = ('#DIV/0!', '#REF!', '#NAME?', '#VALUE!', '#N/A', '#NUM!', '#NULL!', 'Err:502', 'Err:504')


def _soffice(*args, salida):
    binario = shutil.which('soffice') or shutil.which('libreoffice')
    if not binario:
        raise RuntimeError('Falta LibreOffice en el runtime: ejecute la celda de instalación del notebook de informes.')
    perfil = Path(tempfile.mkdtemp(prefix='lo_perfil_'))  # perfil aislado: evita bloqueos entre ejecuciones
    subprocess.run([binario, f'-env:UserInstallation=file://{perfil}', '--headless', '--norestore', *args,
                    '--outdir', str(salida)], check=True, capture_output=True, timeout=300)


def libro_calculado(ruta):
    """Copia del libro con los valores calculados por LibreOffice (para leer resultados; no se entrega)."""
    ruta = Path(ruta).resolve()
    tmp = Path(tempfile.mkdtemp(prefix='recalc_'))
    _soffice('--convert-to', 'xlsx:Calc MS Excel 2007 XML', str(ruta), salida=tmp)
    return tmp / ruta.name


def recalcular_excel(ruta):
    """Recalcula con LibreOffice y cuenta fórmulas, errores y fórmulas sin resultado.

    El libro entregado conserva sus fórmulas; Excel, LibreOffice o Google Sheets las recalculan al abrirlo.
    """
    ruta = Path(ruta).resolve()
    calculado = libro_calculado(ruta)
    original, valores = load_workbook(ruta), load_workbook(calculado, data_only=True)
    formulas, errores, vacias = 0, [], 0
    for ws in original.worksheets:
        for fila in ws.iter_rows():
            for c in fila:
                if isinstance(c.value, str) and c.value.startswith('='):
                    formulas += 1
                    v = valores[ws.title][c.coordinate].value
                    if isinstance(v, str) and v in ERRORES:
                        errores.append(f'{ws.title}!{c.coordinate}={v}')
                    elif v is None:
                        vacias += 1
    shutil.rmtree(calculado.parent, ignore_errors=True)
    return {'archivo': ruta.name, 'formulas': formulas, 'errores': errores, 'formulas_sin_valor': vacias,
            'motor': 'LibreOffice (Colab)'}


def docx_a_pdf(ruta_docx, ruta_pdf):
    """Exporta a PDF con LibreOffice y devuelve el número de páginas renderizadas."""
    import pymupdf

    ruta_docx, ruta_pdf = Path(ruta_docx).resolve(), Path(ruta_pdf).resolve()
    ruta_pdf.parent.mkdir(parents=True, exist_ok=True)
    _soffice('--convert-to', 'pdf', str(ruta_docx), salida=ruta_pdf.parent)
    generado = ruta_pdf.parent / (ruta_docx.stem + '.pdf')
    if generado != ruta_pdf:
        generado.replace(ruta_pdf)
    with pymupdf.open(ruta_pdf) as pdf:
        return pdf.page_count
