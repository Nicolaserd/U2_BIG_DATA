"""Ejecución y medición del PoC (Spark) y de su equivalente en Pandas.

Cada ejecución corre en un subproceso nuevo (`python -m emergencias123.poc ...`) y registra:
tiempo total de la carga a la exportación (sin el arranque de la SparkSession, que se informa
aparte), memoria del sistema y RSS del proceso más sus hijos (JVM) muestreadas, throughput,
tasas de validación, registros procesados y errores. Las métricas se agregan a
`mediciones/poc.jsonl` y los controles al log `logs/validacion_poc_<herramienta>.txt`.
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from .config import cargar_config
from .memoria import MemorySampler, medir
from .validaciones import escribir_log, evaluar, tasas, verificar_salidas

log = logging.getLogger(__name__)


def ejecutar_poc(herramienta, ejecucion, cfg, particionamiento=None, etiqueta=None):
    sufijo = f'_{etiqueta}' if etiqueta else ''
    salida = cfg.dir_salida('parquet', 'poc', herramienta, f'e{ejecucion}{sufijo}')
    metricas = {'herramienta': herramienta, 'ejecucion': ejecucion, 'etiqueta': etiqueta, 'entorno': cfg.entorno,
                'ts_inicio': datetime.now().isoformat(timespec='seconds'), 'ruta_salida': str(salida),
                'particionamiento': particionamiento or cfg.poc['particionamiento'], 'errores_ejecucion': []}
    hechos, spark = {}, None
    with MemorySampler(cfg.benchmark['intervalo_muestreo_s']) as s:
        try:
            if herramienta == 'spark':
                from .pipeline_spark import procesar
                from .spark_session import configuracion_spark, crear_sesion
                spark, t_ini, m_ini = medir(s, crear_sesion, cfg)
                metricas['config_spark'] = configuracion_spark(cfg)
                hechos, t_total, m_total = medir(s, procesar, spark, cfg, salida, particionamiento)
            else:
                from .pipeline_pandas import procesar
                t_ini, m_ini = 0.0, None
                hechos, t_total, m_total = medir(s, procesar, cfg, salida, particionamiento)
            verif, t_verif, _ = medir(s, verificar_salidas, salida)
            hechos.update(verif)
        except Exception as error:  # se registra y se reporta, no se oculta
            metricas['errores_ejecucion'].append(f'{type(error).__name__}: {error}')
            metricas['traza'] = traceback.format_exc()[-3000:]
        finally:
            if spark is not None:
                from .spark_session import detener_sesion
                detener_sesion(spark)
    if metricas['errores_ejecucion']:
        metricas['estado'] = 'error'
        return metricas, hechos, []
    controles = evaluar(hechos)
    metricas.update({
        'estado': 'ok',
        'tiempo_inicio_sesion_s': round(t_ini, 4),
        'tiempo_total_s': round(t_total, 4),
        'tiempo_verificacion_s': round(t_verif, 4),
        'tiempo_total_con_verificacion_s': round(t_total + t_verif, 4),
        **m_total,
        'leidos': hechos['leidos'], 'aceptados': hechos['aceptados'], 'rechazados': hechos['rechazados'],
        'throughput_reg_min': round(hechos['leidos'] / (t_total / 60), 1),
        **tasas(controles, hechos),
        'parquet_archivos': hechos['parquet_archivos'], 'parquet_bytes': hechos['parquet_bytes'],
        'rechazos_por_motivo': hechos['rechazos_por_motivo'],  # solo copias duplicadas exactas eliminadas
        'observaciones_por_motivo': hechos['observaciones_por_motivo'],  # conservados con anomalía marcada
        'nulos_criticos_aceptados': hechos['nulos_criticos_aceptados'],
        'duplicados_exactos': hechos['duplicados_exactos'],
        'filas_incidente_repetido': hechos['filas_incidente_repetido'],
        'fuera_mes_aceptados': hechos['fuera_mes_aceptados'],
    })
    metricas['errores'] = len(metricas['controles_fallidos'])
    return metricas, hechos, controles


def ejecutar_subproceso(herramienta, ejecucion, particionamiento=None, etiqueta=None, timeout=3600, entorno_extra=None):
    src = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ, PYTHONPATH=src + os.pathsep + os.environ.get('PYTHONPATH', ''), **(entorno_extra or {}))
    cmd = [sys.executable, '-m', 'emergencias123.poc', '--herramienta', herramienta, '--ejecucion', str(ejecucion)]
    if particionamiento:
        cmd += ['--particionamiento', particionamiento]
    if etiqueta:
        cmd += ['--etiqueta', etiqueta]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    return {'herramienta': herramienta, 'ejecucion': ejecucion, 'etiqueta': etiqueta, 'codigo_salida': r.returncode,
            'segundos_proceso': round(time.perf_counter() - t0, 2), 'salida': r.stdout[-800:],
            'stderr_final': r.stderr[-2000:] if r.returncode else ''}


def ejecutar_poc_completo(cfg, herramientas=('spark', 'pandas'), ejecuciones=None, al_avanzar=None):
    """N ejecuciones por herramienta, alternando el orden en cada ronda."""
    ejecuciones = ejecuciones or cfg.poc['ejecuciones']
    resultados = []
    for e in range(1, ejecuciones + 1):
        orden = list(herramientas) if e % 2 else list(reversed(herramientas))
        for h in orden:
            res = ejecutar_subproceso(h, e)
            resultados.append(res)
            if al_avanzar:
                al_avanzar(res)
    return resultados


def replicar_datos(cfg, factor, destino):
    """Crea CSV con el contenido de cada mes repetido `factor` veces (DATOS SINTÉTICOS por replicación).

    Sirve para medir cómo crecen tiempo y memoria con el volumen (x4 ≈ 1 año, x8 ≈ 2 años de filas).
    La réplica k (k ≥ 1) agrega el sufijo `-R<k>` a NUMERO_INCIDENTE (primera columna): así las réplicas NO son
    duplicados exactos de la original (si lo fueran, la regla de limpieza las eliminaría y el volumen procesado
    no crecería). Los duplicados exactos propios de los datos se repiten dentro de cada réplica.
    """
    destino.mkdir(parents=True, exist_ok=True)
    for ruta in cfg.rutas_csv:
        crudo = ruta.read_bytes()
        bom = b'\xef\xbb\xbf' if crudo.startswith(b'\xef\xbb\xbf') else b''
        encabezado, _, cuerpo = crudo[len(bom):].partition(b'\n')
        lineas = [ln for ln in cuerpo.split(b'\n') if ln.strip()]
        partes = [bom + encabezado + b'\n']
        for k in range(factor):
            if k == 0:
                partes.extend(ln + b'\n' for ln in lineas)
            else:
                sufijo = f'-R{k}'.encode()
                for ln in lineas:
                    clave, sep, resto = ln.partition(b';')
                    partes.append(clave + sufijo + sep + resto + b'\n')
        (destino / ruta.name).write_bytes(b''.join(partes))
    return destino


def ejecutar_escalabilidad(cfg, factores=(4, 8), base=Path('/content/u2_escala'), herramientas=('spark', 'pandas'),
                           al_avanzar=None):
    """Mide el PoC con volumen replicado; las métricas se agregan a mediciones/escalabilidad.jsonl de cfg."""
    import shutil
    resultados = []
    for factor in factores:
        datos = replicar_datos(cfg, factor, base / f'datos_x{factor}')
        salida = base / f'resultados_x{factor}'
        shutil.rmtree(salida, ignore_errors=True)
        for h in herramientas:
            res = ejecutar_subproceso(h, 1, etiqueta=f'replica_x{factor}',
                                      entorno_extra={'U2_DIR_DATOS': str(datos), 'U2_DIR_RESULTADOS': str(salida)})
            res['factor'] = factor
            resultados.append(res)
            if al_avanzar:
                al_avanzar(res)
        jsonl = salida / 'mediciones' / 'poc.jsonl'
        if jsonl.exists():
            with open(cfg.dir_salida('mediciones') / 'escalabilidad.jsonl', 'a', encoding='utf-8') as f:
                for linea in jsonl.read_text(encoding='utf-8').splitlines():
                    registro = json.loads(linea)
                    registro.update(factor_replica=factor, datos='sinteticos_replicados')
                    f.write(json.dumps(registro, ensure_ascii=False) + '\n')
    return resultados


def main():
    p = argparse.ArgumentParser(description='Una ejecución medida del PoC en este proceso.')
    p.add_argument('--herramienta', required=True, choices=['spark', 'pandas'])
    p.add_argument('--ejecucion', type=int, required=True)
    p.add_argument('--particionamiento', choices=['periodo', 'periodo_localidad'])
    p.add_argument('--etiqueta')
    a = p.parse_args()
    logging.basicConfig(level=logging.WARNING)
    cfg = cargar_config()
    metricas, hechos, controles = ejecutar_poc(a.herramienta, a.ejecucion, cfg, a.particionamiento, a.etiqueta)
    metricas['controles'] = controles
    ruta = cfg.dir_salida('mediciones') / 'poc.jsonl'
    with open(ruta, 'a', encoding='utf-8') as f:
        f.write(json.dumps(metricas, ensure_ascii=False, default=str) + '\n')
    if metricas['estado'] == 'ok':
        nombre = f'validacion_poc_{a.herramienta}{"_" + a.etiqueta if a.etiqueta else ""}.txt'
        escribir_log(cfg.dir_salida('logs') / nombre, metricas, controles, hechos)
        print(json.dumps({k: metricas[k] for k in ('herramienta', 'ejecucion', 'tiempo_total_s', 'mem_sis_pico_pct',
                                                   'rss_pico_mb', 'throughput_reg_min', 'tasa_validaciones_pct',
                                                   'registros_validos_pct', 'aceptados', 'rechazados')}, ensure_ascii=False))
    else:
        print(metricas.get('traza', ''), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
