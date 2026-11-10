"""Inventario de los CSV de entrada: procedencia, tamaño, huella, esquema, nulos y rangos.

Usa solo la biblioteca estándar para que el perfil no dependa de ninguna de las herramientas
que se comparan en el benchmark.
"""
import csv
import hashlib
from collections import Counter
from datetime import datetime, timedelta

from .normalizacion import normalizar_texto


def _sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def _fin_de_mes(periodo):
    anio, mes = map(int, periodo.split('-'))
    return datetime(anio + (mes == 12), mes % 12 + 1, 1)


def perfilar_archivo(ruta, periodo, cfg):
    esq = cfg.esquema
    nulos_marcados = set(esq['valores_nulos'])
    with open(ruta, 'rb') as f:
        crudo = f.read()
    lineas_fisicas = crudo.count(b'\n') + (0 if crudo.endswith(b'\n') else 1)
    with open(ruta, encoding=cfg.datos['codificacion'], newline='') as f:
        lector = csv.DictReader(f, delimiter=cfg.datos['separador'])
        columnas = lector.fieldnames
        filas = list(lector)
    nulos = {c: sum(1 for r in filas if (r[c] or '').strip() in nulos_marcados) for c in columnas}
    fechas, invalidas = [], 0
    for r in filas:
        try:
            fechas.append(datetime.strptime(r['FECHA_INICIO_DESPLAZAMIENTO_MOVIL'], esq['formato_fecha']))
        except (ValueError, TypeError):
            invalidas += 1
    inicio = datetime.strptime(periodo + '-01', '%Y-%m-%d')
    fin = _fin_de_mes(periodo)
    fuera_mes = sum(1 for d in fechas if not inicio <= d < fin)
    fuera_ventana = sum(1 for d in fechas if not inicio <= d < fin + timedelta(days=cfg.poc['tolerancia_dias_fin_mes']))
    claves = [tuple(r[c] for c in columnas) for r in filas]
    return {
        'archivo': ruta.name,
        'periodo': periodo,
        'bytes': len(crudo),
        'sha256': _sha256(ruta),
        'bom_utf8': crudo.startswith(b'\xef\xbb\xbf'),
        'fin_de_linea': 'CRLF' if b'\r\n' in crudo[:4096] else 'LF',
        'lineas_fisicas': lineas_fisicas,
        'registros': len(filas),
        'columnas': columnas,
        'nulos_o_na': nulos,
        'fechas_invalidas': invalidas,
        'fecha_min': min(fechas).isoformat(sep=' ') if fechas else None,
        'fecha_max': max(fechas).isoformat(sep=' ') if fechas else None,
        'fuera_del_mes_del_archivo': fuera_mes,
        'fuera_de_ventana_con_tolerancia': fuera_ventana,
        'duplicados_exactos': len(claves) - len(set(claves)),
        'localidades': dict(Counter(r['LOCALIDAD'] for r in filas).most_common()),
        'tipos_incidente': dict(Counter(r['TIPO_INCIDENTE'] for r in filas).most_common()),
    }


def perfilar(cfg):
    archivos = [perfilar_archivo(cfg.ruta_csv(a['nombre']), a['periodo'], cfg) for a in cfg.datos['archivos']]
    todas = []
    for a in cfg.datos['archivos']:
        with open(cfg.ruta_csv(a['nombre']), encoding=cfg.datos['codificacion'], newline='') as f:
            todas.extend(csv.DictReader(f, delimiter=cfg.datos['separador']))
    ids = Counter(r['NUMERO_INCIDENTE'] for r in todas)
    claves = [tuple(r.values()) for r in todas]
    pares = Counter((r['CODIGO_LOCALIDAD'], normalizar_texto(r['LOCALIDAD'])) for r in todas)
    return {
        'archivos': archivos,
        'total_registros': len(todas),
        'duplicados_exactos_global': len(claves) - len(set(claves)),
        'filas_con_incidente_repetido': sum(n for n in ids.values() if n > 1),
        'incidentes_unicos': len(ids),
        'pares_codigo_localidad': {f'{c}|{n}': k for (c, n), k in sorted(pares.items())},
    }


def a_markdown(inv, catalogo, entorno_local):
    """Documento docs/inventario_datos.md a partir del inventario medido."""
    a0 = inv['archivos'][0]
    l = ['# Inventario de datos — Emergencias 123 Bogotá (U2)', '',
         'Generado en Google Colab por el notebook de procesamiento (`emergencias123.inventario`) a partir de los CSV en Drive, sin modificarlos.', '',
         '## Procedencia', '',
         '- Conjunto «Llamadas de urgencias y emergencias que ingresan a través de la línea 123», publicado por la',
         '  Secretaría Distrital de Salud en el portal Datos Abiertos Bogotá (licencia CC BY 4.0); un archivo por mes.',
         '- Los archivos se toman de la carpeta de Drive de la Unidad 1 o se descargan del portal; la integridad se fija',
         '  con la huella SHA-256 de cada archivo (idénticos a los del portal, verificado el 2026-11-10).',
         '- Meses seleccionados: julio, agosto y septiembre de 2026.', '',
         '## Archivos', '',
         '| Archivo | Periodo | Bytes | Registros | Líneas físicas | Fecha mín. | Fecha máx. | Fuera del mes | Dup. exactos | SHA-256 |',
         '|---|---|---:|---:|---:|---|---|---:|---:|---|']
    for a in inv['archivos']:
        l.append(f"| {a['archivo']} | {a['periodo']} | {a['bytes']:,} | {a['registros']:,} | {a['lineas_fisicas']:,} | "
                 f"{a['fecha_min']} | {a['fecha_max']} | {a['fuera_del_mes_del_archivo']} | {a['duplicados_exactos']} | "
                 f"`{a['sha256'][:16]}…` |")
    l += ['', f"**Total:** {inv['total_registros']:,} registros · {inv['incidentes_unicos']:,} incidentes únicos · "
              f"{inv['filas_con_incidente_repetido']:,} filas con NUMERO_INCIDENTE repetido · "
              f"{inv['duplicados_exactos_global']} copias duplicadas exactas.", '',
          '## Formato y esquema', '',
          f"- Codificación UTF-8 con BOM: {a0['bom_utf8']}; fin de línea {a0['fin_de_linea']}; separador `;`; encabezado en la primera línea.",
          '- Columnas (todas se leen como texto y se tipan después):', '']
    l += [f'  {i + 1}. `{c}` — nulos/`N/A`: {sum(a["nulos_o_na"][c] for a in inv["archivos"]):,}'
          for i, c in enumerate(a0['columnas'])]
    l += ['', '## Hallazgos que condicionan el diseño', '',
          '- `EDAD`, `UNIDAD` y `GENERO` usan `N/A` como marcador de ausencia: se convierte a nulo y no se imputa.',
          '- `RECEPCION` vacía significa que no hay recepción registrada: es un nulo legítimo, no un error.',
          '- Cada archivo incluye registros de la madrugada del día 1 del mes siguiente '
          f"({', '.join(str(a['fuera_del_mes_del_archivo']) for a in inv['archivos'])} registros). "
          'Se conservan con el periodo de su archivo y se valida una ventana de 1 día de tolerancia.',
          '- Las localidades vienen con tilde (`USAQUÉN`) y se normalizan a `USAQUEN`. Hay 1 fila con `SIN_D` '
          '(localidad sin dato), que el PoC conserva marcada en `observacion_calidad`.',
          '- `NUMERO_INCIDENTE` se repite cuando un incidente tiene varios despachos: no es un duplicado.',
          '- Las copias duplicadas exactas (100 % de los atributos iguales) se eliminan en el PoC y se guardan aparte; '
          'los nulos no se eliminan ni se imputan.', '',
          '## Catálogo de tipos de incidente (derivado, NO oficial)', '',
          'No se encontró una tabla oficial de códigos de emergencia entre los insumos. '
          '`config/catalogo_tipos_derivado.csv` se derivó de `TIPO_INCIDENTE` '
          f"({len(catalogo)} códigos; {sum(c['codigo_explicito'] for c in catalogo)} con código explícito "
          f"`COD - DESCRIPCIÓN` y {sum(not c['codigo_explicito'] for c in catalogo)} sin código, en los que "
          'el texto normalizado actúa como código). Para usar un catálogo oficial basta con reemplazar ese archivo '
          'conservando sus columnas.', '',
          '## Pares código ↔ localidad observados', '',
          '| Código | Localidad normalizada | Registros |', '|---|---|---:|']
    l += [f'| {k.split("|")[0]} | {k.split("|")[1]} | {v:,} |' for k, v in inv['pares_codigo_localidad'].items()]
    l += ['', '## Entorno de ejecución', '', *[f'- {k}: {v}' for k, v in entorno_local.items()], '']
    return '\n'.join(l)
