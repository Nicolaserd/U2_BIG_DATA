"""Catálogo de tipos de incidente DERIVADO de los propios datos (no es un catálogo oficial).

No se encontró una tabla oficial de códigos de emergencia entre los insumos de U2. El catálogo
se construye una sola vez a partir de TIPO_INCIDENTE (`COD - DESCRIPCIÓN`, o solo la descripción
cuando no hay código) y se versiona en config/ como insumo externo del pipeline.
"""
import csv
from collections import defaultdict

from .normalizacion import SEPARADOR_CODIGO, colapsar_espacios, extraer_codigo_tipo, extraer_descripcion_tipo

FUENTE = 'Derivado de TIPO_INCIDENTE de los CSV jul-sep 2026 (no oficial)'
COLUMNAS = ['codigo_tipo', 'descripcion_tipo', 'codigo_explicito', 'fuente']


def leer_valores(rutas, columna, separador, codificacion):
    conteos = defaultdict(int)
    for ruta in rutas:
        with open(ruta, encoding=codificacion, newline='') as f:
            for fila in csv.DictReader(f, delimiter=separador):
                conteos[fila[columna]] += 1
    return dict(conteos)


def derivar_catalogo(valores_tipo):
    """Devuelve las filas del catálogo. Falla si un código queda asociado a dos descripciones."""
    por_codigo = {}
    for valor in sorted(v for v in valores_tipo if colapsar_espacios(v)):
        codigo = extraer_codigo_tipo(valor)
        fila = {
            'codigo_tipo': codigo,
            'descripcion_tipo': extraer_descripcion_tipo(valor),
            'codigo_explicito': SEPARADOR_CODIGO in colapsar_espacios(valor),
            'fuente': FUENTE,
        }
        previa = por_codigo.get(codigo)
        if previa and previa['descripcion_tipo'] != fila['descripcion_tipo']:
            raise ValueError(f'Código ambiguo {codigo}: {previa["descripcion_tipo"]!r} vs {fila["descripcion_tipo"]!r}')
        por_codigo[codigo] = fila
    return [por_codigo[c] for c in sorted(por_codigo)]


def guardar_catalogo(filas, ruta):
    with open(ruta, 'w', encoding='utf-8', newline='') as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)


def leer_catalogo(ruta):
    with open(ruta, encoding='utf-8', newline='') as f:
        filas = list(csv.DictReader(f))
    for fila in filas:
        fila['codigo_explicito'] = fila['codigo_explicito'] == 'True'
    codigos = [f['codigo_tipo'] for f in filas]
    if len(codigos) != len(set(codigos)):
        raise ValueError('La clave codigo_tipo del catálogo no es única')
    return filas
