"""Operaciones del benchmark en PySpark (evaluación perezosa: nada se ejecuta hasta una acción).

La materialización la decide el orquestador (benchmark.py): en el modo por_operacion se aplica
cache()+count() en cada frontera; en el extremo_a_extremo solo actúan las acciones finales.
"""
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

from .normalizacion import CON_TILDE, SIN_TILDE


def _normalizar(columna):
    return F.upper(F.trim(F.regexp_replace(F.translate(F.col(columna), CON_TILDE, SIN_TILDE), r'\s+', ' ')))


def esquema_texto(columnas):
    return StructType([StructField(c, StringType(), True) for c in columnas])


def carga(spark, rutas, columnas, separador=';'):
    # >>> op:carga
    df = spark.read.csv([str(r) for r in rutas], schema=esquema_texto(columnas), sep=separador,
                        header=True, encoding='UTF-8')
    # <<< op:carga
    return df


def filtrado(df, localidades):
    # >>> op:filtrado
    df = df.withColumns({'localidad_norm': _normalizar('LOCALIDAD'),
                         'codigo_tipo': F.split(_normalizar('TIPO_INCIDENTE'), ' - ', 2)[0]})
    df = df.filter(F.col('localidad_norm').isin(localidades))
    # <<< op:filtrado
    return df


def agregacion(df):
    # >>> op:agregacion
    conteo = df.groupBy('codigo_tipo').agg(F.count(F.lit(1)).alias('conteo'))
    conteo = conteo.orderBy(F.desc('conteo'), F.asc('codigo_tipo'))
    # <<< op:agregacion
    return conteo


def join(df, ruta_catalogo, spark):
    # >>> op:join
    catalogo = spark.read.csv(str(ruta_catalogo), header=True, encoding='UTF-8')
    catalogo = catalogo.select('codigo_tipo', 'descripcion_tipo',
                               (F.col('codigo_explicito') == 'True').alias('codigo_explicito'))
    enriquecido = df.join(F.broadcast(catalogo), on='codigo_tipo', how='left')
    # <<< op:join
    return enriquecido


def exportacion(df, ruta_salida):
    # >>> op:exportacion
    df.write.mode('overwrite').parquet(str(ruta_salida))
    # <<< op:exportacion


def filas(df):
    return df.count()


def a_dict_conteo(conteo):
    return {r['codigo_tipo']: int(r['conteo']) for r in conteo.collect()}


def sin_coincidencia(df):
    return df.filter(F.col('descripcion_tipo').isNull()).count()


def claves_catalogo_unicas(spark, ruta_catalogo):
    catalogo = spark.read.csv(str(ruta_catalogo), header=True)
    return catalogo.count() == catalogo.select('codigo_tipo').distinct().count()
