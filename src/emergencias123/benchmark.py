"""Benchmark Pandas vs Polars vs PySpark con measure_performance().

Cada (herramienta, modo, ejecución) corre en un subproceso Python NUEVO (`python -m
emergencias123.benchmark ...`): no se reutilizan DataFrames, cachés ni JVM entre repeticiones.
El orquestador (`ejecutar_benchmark`) hace 1 calentamiento descartado por herramienta y modo,
y luego N repeticiones con el orden de herramientas rotado en cada ronda.

Modos:
- por_operacion: cada operación se materializa y se mide por separado. En Spark se aplica
  cache()+count() en cada frontera para que la operación siguiente no recompute las anteriores.
- extremo_a_extremo: el pipeline completo con la mínima materialización (Polars perezoso con
  collect_all; Spark con un DAG único y solo las acciones finales, con caché del filtrado porque
  lo consumen dos acciones: la agregación y la exportación).
- extremo_a_extremo_caliente (complementario): igual que el anterior, pero se mide la SEGUNDA
  pasada dentro del mismo proceso, tras limpiar la caché de datos. Separa el coste de arranque en
  frío (JVM recién creada) del coste en régimen estable. No sustituye a los modos principales.
"""
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import cargar_config
from .loc import loc_por_herramienta
from .memoria import MemorySampler, medir

OPERACIONES = ['carga', 'filtrado', 'agregacion', 'join', 'exportacion']
log = logging.getLogger(__name__)


def _filas_fisicas(cfg):
    """Registros de datos de los CSV (líneas no vacías menos el encabezado), para los modos sin conteo intermedio."""
    total = 0
    for ruta in cfg.rutas_csv:
        with open(ruta, 'rb') as f:
            total += sum(1 for linea in f if linea.strip()) - 1
    return total


class _Registro:
    def __init__(self, base):
        self.base, self.filas = base, []

    def agregar(self, operacion, segundos, memoria, entrada, salida, accion, cache=False, **extra):
        self.filas.append({**self.base, 'operacion': operacion, 'segundos': round(segundos, 6), **memoria,
                           'filas_entrada': entrada, 'filas_salida': salida, 'estado': 'ok', 'error': None,
                           'accion_materializacion': accion, 'usa_cache': cache, **extra})


# ---------- Pandas y Polars: modo por_operacion (eager) ----------
def _por_operacion_eager(ops, s, cfg, ruta, reg, **kw_carga):
    locs, cat = cfg.benchmark['localidades_filtro'], cfg.ruta_catalogo_tipos
    df, t, m = medir(s, ops.carga, cfg.rutas_csv, cfg.datos['separador'], **kw_carga)
    reg.agregar('carga', t, m, None, ops.filas(df), 'eager')
    dff, t, m = medir(s, ops.filtrado, df, locs)
    reg.agregar('filtrado', t, m, ops.filas(df), ops.filas(dff), 'eager')
    conteo, t, m = medir(s, ops.agregacion, dff)
    reg.agregar('agregacion', t, m, ops.filas(dff), ops.filas(conteo), 'eager',
                resultado_agregacion=ops.a_dict_conteo(conteo))
    enr, t, m = medir(s, ops.join, dff, cat)
    reg.agregar('join', t, m, ops.filas(dff), ops.filas(enr), 'eager', sin_coincidencia=ops.sin_coincidencia(enr))
    _, t, m = medir(s, ops.exportacion, enr, ruta)
    reg.agregar('exportacion', t, m, ops.filas(enr), ops.filas(enr), 'escritura parquet')


def _pandas_por_operacion(s, cfg, ruta, reg):
    from . import ops_pandas
    _por_operacion_eager(ops_pandas, s, cfg, ruta, reg, codificacion=cfg.datos['codificacion'])


def _polars_por_operacion(s, cfg, ruta, reg):
    from . import ops_polars
    _por_operacion_eager(ops_polars, s, cfg, ruta, reg)


# ---------- Pandas y Polars: modo extremo_a_extremo ----------
def _pandas_extremo(s, cfg, ruta, reg):
    from . import ops_pandas as ops

    def pipeline():
        dff = ops.filtrado(ops.carga(cfg.rutas_csv, cfg.datos['separador'], cfg.datos['codificacion']),
                           cfg.benchmark['localidades_filtro'])
        conteo = ops.agregacion(dff)
        enr = ops.join(dff, cfg.ruta_catalogo_tipos)
        ops.exportacion(enr, ruta)
        return ops.a_dict_conteo(conteo), ops.filas(enr), ops.sin_coincidencia(enr)

    (conteo, n, sin), t, m = medir(s, pipeline)
    reg.agregar('extremo_a_extremo', t, m, _filas_fisicas(cfg), n, 'eager + escritura parquet',
                resultado_agregacion=conteo, sin_coincidencia=sin)


def _polars_extremo(s, cfg, ruta, reg):
    import polars as pl

    from . import ops_polars as ops

    def pipeline():
        lff = ops.filtrado(ops.carga(cfg.rutas_csv, cfg.datos['separador'], perezoso=True),
                           cfg.benchmark['localidades_filtro'])
        conteo, enr = pl.collect_all([ops.agregacion(lff), ops.join(lff, cfg.ruta_catalogo_tipos)])
        ops.exportacion(enr, ruta)
        return ops.a_dict_conteo(conteo), ops.filas(enr), ops.sin_coincidencia(enr)

    (conteo, n, sin), t, m = medir(s, pipeline)
    reg.agregar('extremo_a_extremo', t, m, _filas_fisicas(cfg), n, 'collect_all (subplan común) + write_parquet',
                resultado_agregacion=conteo, sin_coincidencia=sin)


# ---------- Spark ----------
def _materializar(df):
    df = df.cache()
    return df, df.count()


def _spark_por_operacion(s, cfg, ruta, reg, spark):
    from . import ops_spark as ops
    cols, locs = cfg.esquema['columnas'], cfg.benchmark['localidades_filtro']
    (df, n0), t, m = medir(s, lambda: _materializar(ops.carga(spark, cfg.rutas_csv, cols, cfg.datos['separador'])))
    reg.agregar('carga', t, m, None, n0, 'cache()+count()', cache=True)
    (dff, n1), t, m = medir(s, lambda: _materializar(ops.filtrado(df, locs)))
    reg.agregar('filtrado', t, m, n0, n1, 'cache()+count()', cache=True)
    df.unpersist(blocking=True)
    conteo, t, m = medir(s, lambda: ops.a_dict_conteo(ops.agregacion(dff)))
    reg.agregar('agregacion', t, m, n1, len(conteo), 'collect()', cache=True, resultado_agregacion=conteo)
    (enr, n2), t, m = medir(s, lambda: _materializar(ops.join(dff, cfg.ruta_catalogo_tipos, spark)))
    reg.agregar('join', t, m, n1, n2, 'cache()+count()', cache=True, sin_coincidencia=ops.sin_coincidencia(enr))
    _, t, m = medir(s, ops.exportacion, enr, ruta)
    reg.agregar('exportacion', t, m, n2, n2, 'write.parquet()', cache=True)
    enr.unpersist(blocking=True)
    dff.unpersist(blocking=True)


def _spark_extremo(s, cfg, ruta, reg, spark):
    from . import ops_spark as ops
    cols, locs = cfg.esquema['columnas'], cfg.benchmark['localidades_filtro']
    estado = {}

    def pipeline():
        dff = ops.filtrado(ops.carga(spark, cfg.rutas_csv, cols, cfg.datos['separador']), locs).cache()
        conteo = ops.a_dict_conteo(ops.agregacion(dff))
        enr = ops.join(dff, cfg.ruta_catalogo_tipos, spark)
        ops.exportacion(enr, ruta)
        estado.update(dff=dff, enr=enr)
        return conteo

    conteo, t, m = medir(s, pipeline)
    n = estado['enr'].count()
    reg.agregar('extremo_a_extremo', t, m, _filas_fisicas(cfg), n,
                'collect() de la agregación + write.parquet(); filtrado en caché (lo usan ambas acciones)',
                cache=True, resultado_agregacion=conteo, sin_coincidencia=ops.sin_coincidencia(estado['enr']))
    estado['dff'].unpersist(blocking=True)


def _caliente(ejecutor):
    """Modo complementario: una pasada previa sin medir en el MISMO proceso (JIT, clases y codegen de la
    JVM ya cargados; imports y pools de hilos ya creados), limpieza de la caché de datos y luego la
    pasada medida. Aísla el coste de arranque en frío del coste en régimen estable."""
    def ejecutar(s, cfg, ruta, reg, *spark):
        previa = ruta.with_name(ruta.name + '_previa')
        shutil.rmtree(previa, ignore_errors=True)
        if not spark:
            previa.mkdir(parents=True, exist_ok=True)
        ejecutor(s, cfg, previa, _Registro({}), *spark)
        if spark:
            spark[0].catalog.clearCache()
        ejecutor(s, cfg, ruta, reg, *spark)
    return ejecutar


EJECUTORES = {
    ('pandas', 'por_operacion'): _pandas_por_operacion,
    ('pandas', 'extremo_a_extremo'): _pandas_extremo,
    ('pandas', 'extremo_a_extremo_caliente'): _caliente(_pandas_extremo),
    ('polars', 'por_operacion'): _polars_por_operacion,
    ('polars', 'extremo_a_extremo'): _polars_extremo,
    ('polars', 'extremo_a_extremo_caliente'): _caliente(_polars_extremo),
    ('spark', 'por_operacion'): _spark_por_operacion,
    ('spark', 'extremo_a_extremo'): _spark_extremo,
    ('spark', 'extremo_a_extremo_caliente'): _caliente(_spark_extremo),
}


def _registro_total(filas, loc_total, operacion='total', extra_segundos=0.0):
    medidas = [f for f in filas if f['operacion'] in OPERACIONES + ['extremo_a_extremo']]
    if not medidas:
        return None
    total = dict(medidas[0])
    total.update(operacion=operacion, segundos=round(sum(f['segundos'] for f in medidas) + extra_segundos, 6),
                 mem_sis_pico_pct=max(f['mem_sis_pico_pct'] for f in medidas),
                 rss_pico_mb=max(f['rss_pico_mb'] for f in medidas),
                 n_muestras=sum(f['n_muestras'] for f in medidas),
                 filas_salida=medidas[-1]['filas_salida'], loc=loc_total,
                 accion_materializacion='suma de las operaciones medidas', resultado_agregacion=None)
    return total


def measure_performance(herramienta, ejecucion, modo, calentamiento, cfg):
    """Ejecuta y mide una repetición completa del benchmark en el proceso actual.

    Devuelve una lista de registros: uno por operación (o uno de extremo a extremo), más `total`
    (de la carga a la exportación) y, en Spark, `inicio_sesion` y `total_con_arranque`.
    """
    loc = loc_por_herramienta()[herramienta]
    loc_total = sum(loc[o] for o in OPERACIONES)
    ruta = cfg.dir_resultados / 'parquet' / 'benchmark' / herramienta / modo / f'e{ejecucion}{"_cal" if calentamiento else ""}'
    shutil.rmtree(ruta, ignore_errors=True)
    if herramienta != 'spark':
        ruta.mkdir(parents=True, exist_ok=True)
    base = {'herramienta': herramienta, 'modo': modo, 'ejecucion': ejecucion, 'calentamiento': calentamiento,
            'entorno': cfg.entorno, 'ts_inicio': datetime.now().isoformat(timespec='seconds'),
            'ruta_salida': str(ruta)}
    reg = _Registro(base)
    spark, arranque = None, 0.0
    with MemorySampler(cfg.benchmark['intervalo_muestreo_s']) as s:
        try:
            if herramienta == 'spark':
                from .spark_session import crear_sesion
                spark, arranque, m = medir(s, crear_sesion, cfg)
                reg.agregar('inicio_sesion', arranque, m, None, None, 'creación de SparkSession (JVM)')
                EJECUTORES[(herramienta, modo)](s, cfg, ruta, reg, spark)
            else:
                EJECUTORES[(herramienta, modo)](s, cfg, ruta, reg)
        except Exception as error:  # se registra como medición fallida, no se oculta
            log.exception('Fallo en %s/%s/%s', herramienta, modo, ejecucion)
            reg.filas.append({**base, 'operacion': 'error', 'segundos': None, 'estado': 'error',
                              'error': f'{type(error).__name__}: {error}'})
        finally:
            if spark is not None:
                from .spark_session import detener_sesion
                detener_sesion(spark)
    for fila in reg.filas:
        fila.setdefault('loc', loc.get(fila['operacion'], loc_total if fila['operacion'] == 'extremo_a_extremo' else None))
    if not any(f['estado'] == 'error' for f in reg.filas):
        reg.filas.append(_registro_total(reg.filas, loc_total))
        if herramienta == 'spark':
            reg.filas.append(_registro_total(reg.filas[:-1], loc_total, 'total_con_arranque', arranque))
    return reg.filas


def guardar_jsonl(registros, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, 'a', encoding='utf-8') as f:
        for r in registros:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def ejecutar_subproceso(herramienta, modo, ejecucion, calentamiento, salida, timeout=1800):
    src = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ, PYTHONPATH=src + os.pathsep + os.environ.get('PYTHONPATH', ''))
    cmd = [sys.executable, '-m', 'emergencias123.benchmark', '--herramienta', herramienta, '--modo', modo,
           '--ejecucion', str(ejecucion), '--salida', str(salida)] + (['--calentamiento'] if calentamiento else [])
    t0 = time.perf_counter()
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    return {'herramienta': herramienta, 'modo': modo, 'ejecucion': ejecucion, 'calentamiento': calentamiento,
            'codigo_salida': r.returncode, 'segundos_proceso': round(time.perf_counter() - t0, 2),
            'stderr_final': r.stderr[-1500:] if r.returncode else ''}


def plan_benchmark(cfg, herramientas=None, modos=None, repeticiones=None):
    """Orden de ejecución: calentamientos y luego rondas con rotación del orden de herramientas."""
    herramientas = herramientas or cfg.benchmark['herramientas']
    modos = modos or cfg.benchmark['modos']
    repeticiones = repeticiones or cfg.benchmark['repeticiones']
    plan = []
    for modo in modos:
        for h in herramientas:
            plan += [(h, modo, c + 1, True) for c in range(cfg.benchmark['calentamientos'])]
        for r in range(repeticiones):
            k = r % len(herramientas)
            plan += [(h, modo, r + 1, False) for h in herramientas[k:] + herramientas[:k]]
    return plan


def ejecutar_benchmark(cfg, salida, herramientas=None, modos=None, repeticiones=None, al_avanzar=None):
    resultados = []
    plan = plan_benchmark(cfg, herramientas, modos, repeticiones)
    for i, paso in enumerate(plan, 1):
        res = ejecutar_subproceso(*paso, salida=salida)
        resultados.append(res)
        if al_avanzar:
            al_avanzar(i, len(plan), res)
    return resultados


def main():
    p = argparse.ArgumentParser(description='Una repetición medida del benchmark (en este proceso).')
    p.add_argument('--herramienta', required=True, choices=['pandas', 'polars', 'spark'])
    p.add_argument('--modo', required=True, choices=['por_operacion', 'extremo_a_extremo', 'extremo_a_extremo_caliente'])
    p.add_argument('--ejecucion', type=int, required=True)
    p.add_argument('--calentamiento', action='store_true')
    p.add_argument('--salida', required=True, type=Path)
    a = p.parse_args()
    logging.basicConfig(level=logging.WARNING)
    cfg = cargar_config()
    registros = measure_performance(a.herramienta, a.ejecucion, a.modo, a.calentamiento, cfg)
    guardar_jsonl(registros, a.salida)
    sys.exit(1 if any(r['estado'] == 'error' for r in registros) else 0)


if __name__ == '__main__':
    main()
