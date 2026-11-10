"""Conteo de líneas de código por operación del benchmark.

Criterio: se cuentan las líneas físicas entre `# >>> op:<nombre>` y `# <<< op:<nombre>` que no
estén vacías ni sean solo comentario. Una sentencia partida en varias líneas cuenta cada línea.
Las firmas `def` y los marcadores no se cuentan (quedan fuera del bloque).
"""
import re
from pathlib import Path

INICIO = re.compile(r'#\s*>>>\s*op:(\w+)')
FIN = re.compile(r'#\s*<<<\s*op:(\w+)')


def contar_loc(ruta_modulo):
    conteos, actual = {}, None
    for linea in Path(ruta_modulo).read_text(encoding='utf-8').splitlines():
        texto = linea.strip()
        if m := INICIO.search(texto):
            actual = m.group(1)
            conteos.setdefault(actual, 0)
            continue
        if FIN.search(texto):
            actual = None
            continue
        if actual and texto and not texto.startswith('#'):
            conteos[actual] += 1
    return conteos


def loc_por_herramienta():
    base = Path(__file__).resolve().parent
    return {h: contar_loc(base / f'ops_{h}.py') for h in ('pandas', 'polars', 'spark')}
