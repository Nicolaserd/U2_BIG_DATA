"""Comprobación de equivalencia lógica entre las salidas Parquet de las tres herramientas.

Se ejecuta fuera de la medición. Compara: número de filas, conjunto de columnas, tipos lógicos,
agregación por codigo_tipo y SHA-256 del contenido canónico (valores como texto, columnas en
orden fijo, filas ordenadas). Los Parquet de Spark (directorio de part-files) y de Pandas/Polars
(un archivo) se leen igual, con pyarrow.
"""
import hashlib
import json

import pyarrow.dataset as ds
import pyarrow.types as pat


def tipo_logico(tipo):
    if pat.is_string(tipo) or pat.is_large_string(tipo) or pat.is_string_view(tipo):
        return 'texto'
    if pat.is_boolean(tipo):
        return 'booleano'
    if pat.is_integer(tipo):
        return 'entero'
    if pat.is_floating(tipo):
        return 'decimal'
    if pat.is_timestamp(tipo):
        return 'fecha_hora'
    return str(tipo)


def leer_tabla(ruta):
    archivos = [p for p in ruta.rglob('*.parquet')] if ruta.is_dir() else [ruta]
    return ds.dataset([str(p) for p in archivos], format='parquet').to_table()


def huella(tabla):
    columnas = sorted(tabla.column_names)
    datos = tabla.select(columnas).to_pydict()
    filas = sorted('\x1f'.join('' if datos[c][i] is None else str(datos[c][i]) for c in columnas)
                   for i in range(tabla.num_rows))
    h = hashlib.sha256()
    for f in filas:
        h.update(f.encode('utf-8') + b'\n')
    return h.hexdigest()


def resumen_salida(ruta):
    tabla = leer_tabla(ruta)
    conteo = {}
    for codigo in tabla.column('codigo_tipo').to_pylist():
        conteo[codigo] = conteo.get(codigo, 0) + 1
    return {
        'filas': tabla.num_rows,
        'esquema': {c: tipo_logico(tabla.schema.field(c).type) for c in sorted(tabla.column_names)},
        'agregacion': dict(sorted(conteo.items())),
        'sha256': huella(tabla),
    }


def comparar(rutas_por_herramienta):
    """{'pandas': Path, ...} -> dict con resúmenes y veredicto por criterio."""
    resumenes = {h: resumen_salida(r) for h, r in rutas_por_herramienta.items()}
    criterios = {}
    for clave in ('filas', 'esquema', 'agregacion', 'sha256'):
        valores = {json.dumps(r[clave], sort_keys=True) for r in resumenes.values()}
        criterios[clave] = len(valores) == 1
    return {'resumenes': resumenes, 'criterios': criterios, 'equivalentes': all(criterios.values())}
