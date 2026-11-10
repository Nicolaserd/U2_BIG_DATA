"""Controles de calidad del PoC, comunes a Spark y Pandas, y fórmulas de las tasas.

Los pipelines producen un diccionario de `hechos` medidos y aquí se evalúan los controles.
- Tasa de éxito de validaciones (%) = controles aprobados / controles evaluados x 100, donde
  evaluados = bloqueantes + advertencias. Los informativos se reportan pero no entran en la tasa.
- Registros válidos (%) = aceptados / leídos x 100. Es otra métrica y no se mezcla con la anterior.

Regla de limpieza (decisión del usuario, 2026-11-10): solo se ELIMINAN las copias duplicadas exactas (100 % de los
atributos iguales). En los hechos, `aceptados` = registros conservados y `rechazados` = copias eliminadas. Los nulos
y demás anomalías se conservan y quedan marcados en `observacion_calidad` (ver MOTIVOS).
"""
import csv
from pathlib import Path

import pyarrow.dataset as ds

COLUMNAS_DETALLE = [
    'numero_incidente', 'fecha_inicio', 'fecha_recepcion', 'periodo', 'archivo_origen', 'en_mes_archivo',
    'codigo_localidad', 'localidad_norm', 'localidad', 'edad', 'unidad', 'edad_anios', 'genero',
    'paciente_completo', 'tipo_incidente', 'codigo_tipo', 'descripcion_tipo', 'codigo_explicito',
    'codigo_reconocido', 'prioridad', 'observacion_calidad', 'incidente_multidespacho',
]
MOTIVOS = ['registro_corrupto', 'numero_incidente_nulo', 'fecha_inicio_invalida', 'localidad_sin_dato',
           'localidad_fuera_catalogo', 'codigo_localidad_inconsistente', 'tipo_incidente_nulo', 'edad_fuera_rango']


def prevalidar(cfg):
    """Controles sobre los archivos antes de procesar: presencia, encabezados y filas físicas."""
    esperadas = cfg.esquema['columnas']
    presentes, faltantes, filas = 0, {}, {}
    for ruta in cfg.rutas_csv:
        if not ruta.exists():
            continue
        presentes += 1
        with open(ruta, encoding=cfg.datos['codificacion']) as f:
            encabezado = f.readline().strip().split(cfg.datos['separador'])
            filas[ruta.name] = sum(1 for linea in f if linea.strip())
        faltan = [c for c in esperadas if c not in encabezado]
        if faltan:
            faltantes[ruta.name] = faltan
    return {'archivos_esperados': len(cfg.rutas_csv), 'archivos_presentes': presentes,
            'columnas_faltantes': faltantes, 'filas_fisicas_por_archivo': filas,
            'filas_fisicas': sum(filas.values())}


def leer_localidades(cfg):
    with open(cfg.ruta_localidades, encoding='utf-8', newline='') as f:
        return {r['localidad_norm']: int(r['codigo_localidad']) for r in csv.DictReader(f)}


def _archivos_parquet(ruta):
    return sorted(p for p in Path(ruta).rglob('*.parquet'))


def verificar_salidas(salida):
    """Relee los Parquet exportados con pyarrow (lector independiente de la herramienta que los escribió)."""
    detalle = salida / 'detalle'
    archivos = _archivos_parquet(detalle)
    tabla = ds.dataset(str(detalle), format='parquet', partitioning='hive').to_table()
    rechazados = _archivos_parquet(salida / 'duplicados_eliminados')
    n_rech = ds.dataset([str(p) for p in rechazados], format='parquet').count_rows() if rechazados else 0
    return {
        'parquet_conteo': tabla.num_rows,
        'parquet_columnas': sorted(tabla.column_names),
        'parquet_archivos': len(archivos),
        'parquet_bytes': sum(p.stat().st_size for p in archivos),
        'parquet_particiones': sorted({p.parent.name for p in archivos}),
        'parquet_rechazados_conteo': n_rech,
        'parquet_suma_agregado_releido': sum(
            ds.dataset(str(salida / 'agregados' / 'periodo_localidad_tipo'), format='parquet')
            .to_table(columns=['conteo']).column('conteo').to_pylist()),
    }


def _control(id_, descripcion, severidad, valor, esperado, aprobado):
    return {'id': id_, 'descripcion': descripcion, 'severidad': severidad,
            'valor': valor, 'esperado': esperado, 'aprobado': bool(aprobado)}


def evaluar(h):
    """Lista de controles a partir de los hechos medidos (pipeline + verificación de salidas)."""
    c = [
        _control('V01', 'Archivos de entrada presentes', 'bloqueante',
                 h['archivos_presentes'], h['archivos_esperados'], h['archivos_presentes'] == h['archivos_esperados']),
        _control('V02', 'Columnas requeridas presentes en cada archivo', 'bloqueante',
                 h['columnas_faltantes'] or 'ninguna faltante', 'ninguna faltante', not h['columnas_faltantes']),
        _control('V03', 'Registros leídos = filas físicas de datos de los CSV', 'bloqueante',
                 h['leidos'], h['filas_fisicas'], h['leidos'] == h['filas_fisicas']),
        _control('V04', 'Leídos = conservados + duplicados exactos eliminados', 'bloqueante',
                 h['aceptados'] + h['rechazados'], h['leidos'], h['aceptados'] + h['rechazados'] == h['leidos']),
        _control('V05', 'Fechas de inicio no parseables', 'advertencia',
                 h['fechas_invalidas'], 0, h['fechas_invalidas'] == 0),
        _control('V06', 'Conservados fuera de la ventana [mes del archivo, fin de mes + tolerancia]', 'advertencia',
                 h['fuera_ventana_aceptados'], 0, h['fuera_ventana_aceptados'] == 0),
        _control('V07', 'Nulos en campos críticos sin observación de calidad (nulo silencioso)', 'bloqueante',
                 h['nulos_criticos_sin_observacion'], 0, h['nulos_criticos_sin_observacion'] == 0),
        _control('V08', 'Códigos de tipo no reconocidos por el catálogo derivado', 'advertencia',
                 h['codigos_no_reconocidos'], 0, h['codigos_no_reconocidos'] == 0),
        _control('V09', 'Clave del catálogo única y join sin multiplicar filas', 'bloqueante',
                 f"clave_unica={h['catalogo_clave_unica']}; {h['filas_antes_join']}->{h['filas_despues_join']}",
                 'clave_unica=True; filas iguales',
                 h['catalogo_clave_unica'] and h['filas_antes_join'] == h['filas_despues_join']),
        _control('V10', 'Inconsistencias código↔nombre de localidad', 'advertencia',
                 h['inconsistencias_localidad'], 0, h['inconsistencias_localidad'] == 0),
        _control('V11', 'Edades fuera de rango (conservadas y marcadas)', 'advertencia',
                 h['edades_fuera_rango_aceptados'], 0, h['edades_fuera_rango_aceptados'] == 0),
        _control('V12', 'Suma del agregado periodo×localidad×tipo = conservados', 'bloqueante',
                 h['suma_agregado_principal'], h['aceptados'], h['suma_agregado_principal'] == h['aceptados']),
        _control('V13', 'Parquet releído: filas = conservados', 'bloqueante',
                 h['parquet_conteo'], h['aceptados'], h['parquet_conteo'] == h['aceptados']),
        _control('V14', 'Parquet releído: columnas esperadas', 'bloqueante',
                 len(h['parquet_columnas']), len(COLUMNAS_DETALLE),
                 sorted(h['parquet_columnas']) == sorted(COLUMNAS_DETALLE)),
        _control('V15', 'Parquet de duplicados eliminados releído = duplicados eliminados', 'bloqueante',
                 h['parquet_rechazados_conteo'], h['rechazados'], h['parquet_rechazados_conteo'] == h['rechazados']),
        _control('V16', 'Agregado releído desde Parquet = conservados', 'bloqueante',
                 h['parquet_suma_agregado_releido'], h['aceptados'], h['parquet_suma_agregado_releido'] == h['aceptados']),
        _control('V17', 'Copias duplicadas exactas eliminadas (100 % de atributos iguales)', 'informativo',
                 h['duplicados_exactos'], 'se reporta', True),
        _control('V18', 'Filas de incidentes con varios despachos', 'informativo',
                 h['filas_incidente_repetido'], 'se reporta', True),
        _control('V19', 'Registros conservados con observación de calidad, por motivo', 'informativo',
                 h['observaciones_por_motivo'] or 'ninguno', 'se reporta', True),
        _control('V20', 'Registros conservados con algún nulo en campos críticos', 'informativo',
                 h['nulos_criticos_aceptados'], 'se reporta', True),
    ]
    return c


def tasas(controles, h):
    evaluados = [c for c in controles if c['severidad'] != 'informativo']
    aprobados = sum(c['aprobado'] for c in evaluados)
    return {
        'controles_evaluados': len(evaluados),
        'controles_aprobados': aprobados,
        'controles_fallidos': [c['id'] for c in evaluados if not c['aprobado']],
        'tasa_validaciones_pct': round(100 * aprobados / len(evaluados), 2),
        'registros_validos_pct': round(100 * h['aceptados'] / h['leidos'], 4) if h['leidos'] else 0.0,
    }


def escribir_log(ruta, metricas, controles, hechos):
    """Agrega al log .txt el bloque de una ejecución (registros, errores, tiempos y controles)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    m = metricas
    lineas = [
        '=' * 78,
        f"PoC {m['herramienta'].upper()} — ejecución {m['ejecucion']} — {m['ts_inicio']} — entorno: {m['entorno']}",
        '=' * 78,
        f"Registros leídos:     {m['leidos']:,}",
        f"Registros conservados: {m['aceptados']:,}  ({m['registros_validos_pct']} % de los leídos)",
        f"Duplicados exactos eliminados (100 % de atributos iguales): {m['rechazados']:,}",
        f"Conservados con observación de calidad: {hechos['observaciones_por_motivo'] or 'ninguno'}",
        f"Conservados con nulos en campos críticos: {hechos['nulos_criticos_aceptados']}",
        f"Filas de incidentes con varios despachos: {hechos['filas_incidente_repetido']}",
        f"Errores de ejecución: {m['errores_ejecucion'] or 'ninguno'}",
        f"Tiempo total carga→exportación: {m['tiempo_total_s']:.3f} s   "
        f"(arranque de sesión aparte: {m['tiempo_inicio_sesion_s']:.3f} s; verificación de salidas: "
        f"{m['tiempo_verificacion_s']:.3f} s)",
        f"Throughput: {m['throughput_reg_min']:,.0f} registros/minuto",
        f"Memoria del sistema: base {m['mem_sis_base_pct']} % · pico muestreado {m['mem_sis_pico_pct']} %   "
        f"RSS proceso+hijos: base {m['rss_base_mb']} MB · pico {m['rss_pico_mb']} MB",
        f"Parquet detalle: {hechos['parquet_archivos']} archivos, {hechos['parquet_bytes']:,} bytes, "
        f"particiones {hechos['parquet_particiones']}",
        f"Tasa de éxito de validaciones: {m['tasa_validaciones_pct']} % "
        f"({m['controles_aprobados']}/{m['controles_evaluados']} controles bloqueantes+advertencia aprobados)",
        '', 'Controles:',
    ]
    for c in controles:
        estado = 'OK   ' if c['aprobado'] else 'FALLA'
        lineas.append(f"  [{estado}] {c['id']} ({c['severidad']}) {c['descripcion']}: valor={c['valor']} esperado={c['esperado']}")
    lineas.append('')
    with open(ruta, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lineas) + '\n')
