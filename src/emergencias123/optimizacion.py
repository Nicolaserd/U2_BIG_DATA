"""Diagnósticos de optimización y calidad del PoC, trasladados de los notebooks de ejemplo del curso (Formatos/).

- Planes de ejecución (explain): evidencia de poda de particiones, predicados empujados al Parquet y broadcast join.
- Comparación de formatos CSV, JSON y Parquet con los datos del PoC: tamaño en disco y tiempo de lectura.
- Perfil de nulos por columna (en una sola agregación, no una acción por columna como en el ejemplo).
- Valores atípicos por rango intercuartílico (IQR), solo informativo: no se imputa ni se elimina nada.
Se ejecuta en Colab desde el notebook 02.
"""
import shutil
import statistics
import time
from pathlib import Path


def _plan(df):
    """Texto del plan físico: se captura la salida de la API pública df.explain(mode='formatted')."""
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        df.explain(mode='formatted')
    return buffer.getvalue()


def planes_ejecucion(spark, ruta_detalle, ruta_catalogo):
    """Dos consultas representativas y lo que su plan físico demuestra."""
    from pyspark.sql import functions as F

    detalle = spark.read.parquet(str(ruta_detalle))
    consulta = (detalle.filter((F.col('periodo') == '2026-08') & (F.col('localidad_norm') == 'USAQUEN'))
                .groupBy('codigo_tipo').count())
    plan_filtro = _plan(consulta)
    catalogo = spark.read.csv(str(ruta_catalogo), header=True).select('codigo_tipo', F.col('descripcion_tipo').alias('desc_cat'))
    union = detalle.join(F.broadcast(catalogo), on='codigo_tipo', how='left').groupBy('desc_cat').count()
    plan_union = _plan(union)
    return {
        'plan_filtro': plan_filtro,
        'plan_union': plan_union,
        'poda_particiones': 'PartitionFilters' in plan_filtro and 'periodo' in plan_filtro.split('PartitionFilters')[1][:200],
        'predicado_empujado': 'PushedFilters' in plan_filtro and 'localidad_norm' in plan_filtro.split('PushedFilters')[1][:300],
        'broadcast_join': 'BroadcastHashJoin' in plan_union,
    }


def _tamano_mb(ruta):
    ruta = Path(ruta)
    archivos = [ruta] if ruta.is_file() else [p for p in ruta.rglob('*') if p.is_file() and not p.name.startswith(('.', '_'))]
    return sum(p.stat().st_size for p in archivos) / 2 ** 20


def comparar_formatos(spark, ruta_detalle, directorio_tmp, repeticiones=3):
    """Escribe el mismo detalle en CSV, JSON y Parquet y mide tamaño y lectura + agregación (mediana de N)."""
    from pyspark.sql import functions as F

    tmp = Path(directorio_tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    detalle = spark.read.parquet(str(ruta_detalle)).cache()
    n = detalle.count()
    rutas = {'CSV': tmp / 'csv', 'JSON': tmp / 'json', 'Parquet': tmp / 'parquet'}
    detalle.coalesce(1).write.mode('overwrite').option('header', True).csv(str(rutas['CSV']))
    detalle.coalesce(1).write.mode('overwrite').json(str(rutas['JSON']))
    detalle.coalesce(1).write.mode('overwrite').parquet(str(rutas['Parquet']))
    detalle.unpersist()
    lectores = {
        'CSV': lambda: spark.read.option('header', True).option('inferSchema', True).csv(str(rutas['CSV'])),
        'JSON': lambda: spark.read.json(str(rutas['JSON'])),
        'Parquet': lambda: spark.read.parquet(str(rutas['Parquet'])),
    }
    resultados = []
    for formato, leer in lectores.items():
        tiempos = []
        for _ in range(repeticiones):
            t0 = time.perf_counter_ns()
            filas = leer().groupBy('codigo_tipo').agg(F.count(F.lit(1)).alias('n')).agg(F.sum('n')).first()[0]
            tiempos.append((time.perf_counter_ns() - t0) / 1e9)
        resultados.append({'formato': formato, 'mb': round(_tamano_mb(rutas[formato]), 3),
                           'lectura_agregacion_s': round(statistics.median(tiempos), 3), 'filas': int(filas)})
    base = next(r for r in resultados if r['formato'] == 'CSV')
    for r in resultados:
        r['tamano_vs_csv'] = round(r['mb'] / base['mb'], 3)
    shutil.rmtree(tmp, ignore_errors=True)
    return {'registros': n, 'repeticiones': repeticiones, 'formatos': resultados}


def perfil_nulos(df):
    """Nulos por columna con UNA sola agregación (el ejemplo del curso lanza una acción por columna)."""
    from pyspark.sql import functions as F

    fila = df.agg(F.count(F.lit(1)).alias('__total'),
                  *[F.sum(F.col(c).isNull().cast('int')).alias(c) for c in df.columns]).first().asDict()
    total = fila.pop('__total')
    return [{'columna': c, 'nulos': int(v or 0), 'porcentaje': round(100 * (v or 0) / total, 2)}
            for c, v in fila.items()]


def atipicos_iqr(df, columna, error_relativo=0.01):
    """Límites IQR (1.5 × IQR) con approxQuantile y conteo de valores fuera de ellos; no modifica los datos."""
    from pyspark.sql import functions as F

    q1, q3 = df.filter(F.col(columna).isNotNull()).approxQuantile(columna, [0.25, 0.75], error_relativo)
    iqr = q3 - q1
    inferior, superior = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    fuera = df.filter((F.col(columna) < inferior) | (F.col(columna) > superior)).count()
    return {'columna': columna, 'q1': q1, 'q3': q3, 'iqr': iqr, 'limite_inferior': inferior,
            'limite_superior': superior, 'atipicos': int(fuera)}
