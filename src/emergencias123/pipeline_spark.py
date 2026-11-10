"""PoC en PySpark: ingesta, tipado, estandarización, validación, enriquecimiento, agregados y Parquet.

Decisiones (ver la skill pipeline-pyspark-u2):
- Esquema explícito, todo texto, y tipado posterior con try_* porque Spark 4 activa ANSI por defecto
  (un cast inválido fallaría en lugar de dar nulo).
- Regla de limpieza (definida por el usuario): SOLO se eliminan los duplicados exactos (filas idénticas en el
  100 % de sus atributos originales; se conserva la primera aparición). Las copias eliminadas se escriben en
  `duplicados_eliminados/`, así que nada se descarta en silencio.
- Los nulos NO se eliminan ni se imputan. Los registros con problemas de calidad (fecha inválida, localidad sin
  dato, código inconsistente, edad fuera de rango…) se CONSERVAN y quedan marcados en `observacion_calidad`.
- El catálogo de tipos (23 filas, derivado y no oficial) se une con broadcast.
- El detalle se particiona por `periodo` (mes del archivo de origen). La variante periodo/localidad
  es configurable, pero genera muchos archivos pequeños con este volumen.
"""
from .catalogo import leer_catalogo
from .normalizacion import CON_TILDE, SIN_TILDE
from .validaciones import COLUMNAS_DETALLE, MOTIVOS, leer_localidades, prevalidar


def procesar(spark, cfg, salida, particionamiento=None):
    """Ejecuta el pipeline de la carga a la exportación y devuelve los hechos medidos."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F
    from pyspark.sql.types import BooleanType, StringType, StructField, StructType

    esq, poc = cfg.esquema, cfg.poc
    hechos = prevalidar(cfg)
    rutas = [str(r) for r in cfg.rutas_csv if r.exists()]

    def norm(c):
        return F.upper(F.trim(F.regexp_replace(F.translate(c, CON_TILDE, SIN_TILDE), r'\s+', ' ')))

    def limpio(nombre):
        t = F.trim(F.col(nombre))
        return F.when(t.isNull() | t.isin(*esq['valores_nulos']), F.lit(None)).otherwise(t).alias(nombre)

    def mapa(d):
        return F.create_map(*[F.lit(x) for par in d.items() for x in par])

    # 1-2. Ingesta con esquema explícito + procedencia
    esquema = StructType([StructField(c, StringType(), True) for c in esq['columnas']]
                         + [StructField('_corrupt_record', StringType(), True)])
    crudo = (spark.read.csv(rutas, schema=esquema, sep=cfg.datos['separador'], header=True, encoding='UTF-8',
                            mode='PERMISSIVE', columnNameOfCorruptRecord='_corrupt_record')
             .withColumn('archivo_origen', F.col('_metadata.file_name')))

    # 3. Nulos explícitos (N/A y vacío -> null, sin imputar)
    df = crudo.select(*[limpio(c) for c in esq['columnas']], '_corrupt_record', 'archivo_origen')
    df = df.withColumn('periodo', mapa(cfg.periodo_por_archivo)[F.col('archivo_origen')])

    # 4-5. Tipos y estandarización
    localidades = leer_localidades(cfg)
    factores = {k: float(v) for k, v in poc['factores_edad'].items()}
    df = df.withColumns({
        'fecha_inicio': F.try_to_timestamp(F.col('FECHA_INICIO_DESPLAZAMIENTO_MOVIL'), F.lit(esq['formato_fecha_spark'])),
        'fecha_recepcion': F.try_to_timestamp(F.col('RECEPCION'), F.lit(esq['formato_fecha_spark'])),
        'codigo_localidad': F.col('CODIGO_LOCALIDAD').try_cast('int'),
        'edad': F.col('EDAD').try_cast('int'),
        'localidad_norm': norm(F.col('LOCALIDAD')),
        'unidad': norm(F.col('UNIDAD')),
        'genero': norm(F.col('GENERO')),
        'prioridad': norm(F.col('PRIORIDAD_FINAL')),
        'codigo_tipo': F.split(norm(F.col('TIPO_INCIDENTE')), ' - ', 2)[0],
    })
    df = df.withColumns({
        'edad_anios': F.col('edad') * mapa(factores)[F.col('unidad')],
        'paciente_completo': F.col('edad').isNotNull() & F.col('unidad').isNotNull() & F.col('genero').isNotNull(),
    })
    inicio_mes = F.to_timestamp(F.concat(F.col('periodo'), F.lit('-01 00:00:00')))
    fin_mes = F.add_months(inicio_mes, 1).cast('timestamp')
    df = df.withColumns({
        'en_mes_archivo': (F.col('fecha_inicio') >= inicio_mes) & (F.col('fecha_inicio') < fin_mes),
        'en_ventana': (F.col('fecha_inicio') >= inicio_mes)
                      & (F.col('fecha_inicio') < F.date_add(fin_mes, poc['tolerancia_dias_fin_mes']).cast('timestamp')),
    })

    # 6. Observaciones de calidad (la primera que aplique): el registro se CONSERVA, solo se marca
    codigo_esperado = mapa(localidades)[F.col('localidad_norm')]
    df = df.withColumn('observacion_calidad', (
        F.when(F.col('_corrupt_record').isNotNull(), 'registro_corrupto')
        .when(F.col('NUMERO_INCIDENTE').isNull(), 'numero_incidente_nulo')
        .when(F.col('fecha_inicio').isNull(), 'fecha_inicio_invalida')
        .when(F.col('localidad_norm').isNull() | (F.col('localidad_norm') == esq['localidad_sin_dato']), 'localidad_sin_dato')
        .when(~F.col('localidad_norm').isin(list(localidades)), 'localidad_fuera_catalogo')
        .when(F.col('codigo_localidad').isNull() | (F.col('codigo_localidad') != codigo_esperado),
              'codigo_localidad_inconsistente')
        .when(F.col('codigo_tipo').isNull(), 'tipo_incidente_nulo')
        .when(F.col('edad_anios').isNotNull() & ((F.col('edad_anios') < poc['edad_min_anios'])
                                                 | (F.col('edad_anios') > poc['edad_max_anios'])), 'edad_fuera_rango')
    ))

    # 7. Duplicados exactos: se ELIMINAN las copias (100 % de atributos iguales) y se conserva la primera aparición
    df = df.withColumn('_fila', F.monotonically_increasing_id())
    df = df.withColumns({
        'es_duplicado_exacto': F.row_number().over(Window.partitionBy(*esq['columnas']).orderBy('_fila')) > 1,
        'incidente_multidespacho': F.count(F.lit(1)).over(Window.partitionBy('NUMERO_INCIDENTE')) > 1,
    }).cache()

    unicos = ~F.col('es_duplicado_exacto')
    r = df.agg(  # una sola acción para todos los conteos de calidad de la entrada
        F.count(F.lit(1)).alias('leidos'),
        F.sum(unicos.cast('int')).alias('aceptados'),
        F.sum((F.col('FECHA_INICIO_DESPLAZAMIENTO_MOVIL').isNotNull() & F.col('fecha_inicio').isNull()).cast('int'))
        .alias('fechas_invalidas'),
        F.sum(F.col('es_duplicado_exacto').cast('int')).alias('duplicados_exactos'),
        F.sum((unicos & F.col('incidente_multidespacho')).cast('int')).alias('filas_incidente_repetido'),
        *[F.sum((unicos & (F.col('observacion_calidad') == m)).cast('int')).alias(f'motivo__{m}') for m in MOTIVOS],
    ).first().asDict()
    hechos['observaciones_por_motivo'] = {k.split('__', 1)[1]: int(v) for k, v in r.items()
                                          if k.startswith('motivo__') and v}
    hechos.update({k: int(v or 0) for k, v in r.items() if not k.startswith('motivo__')})
    hechos['rechazados'] = hechos['leidos'] - hechos['aceptados']  # = copias duplicadas exactas eliminadas
    hechos['rechazos_por_motivo'] = {'duplicado_exacto': hechos['rechazados']} if hechos['rechazados'] else {}
    hechos['inconsistencias_localidad'] = hechos['observaciones_por_motivo'].get('codigo_localidad_inconsistente', 0)

    # 8. Enriquecimiento con el catálogo derivado (broadcast; 23 filas)
    filas_cat = leer_catalogo(cfg.ruta_catalogo_tipos)
    catalogo = spark.createDataFrame(
        [(f['codigo_tipo'], f['descripcion_tipo'], f['codigo_explicito']) for f in filas_cat],
        StructType([StructField('codigo_tipo', StringType()), StructField('descripcion_tipo', StringType()),
                    StructField('codigo_explicito', BooleanType())]))
    hechos['catalogo_clave_unica'] = len(filas_cat) == len({f['codigo_tipo'] for f in filas_cat})
    aceptados = df.filter(unicos)
    hechos['filas_antes_join'] = hechos['aceptados']
    enriquecido = (aceptados.join(F.broadcast(catalogo), on='codigo_tipo', how='left')
                   .withColumn('codigo_reconocido', F.col('descripcion_tipo').isNotNull()))
    detalle = enriquecido.select(
        F.col('NUMERO_INCIDENTE').alias('numero_incidente'), 'fecha_inicio', 'fecha_recepcion', 'periodo',
        'archivo_origen', 'en_mes_archivo', 'codigo_localidad', 'localidad_norm', F.col('LOCALIDAD').alias('localidad'),
        'edad', 'unidad', 'edad_anios', 'genero', 'paciente_completo', F.col('TIPO_INCIDENTE').alias('tipo_incidente'),
        'codigo_tipo', 'descripcion_tipo', 'codigo_explicito', 'codigo_reconocido', 'prioridad',
        'observacion_calidad', 'incidente_multidespacho', 'en_ventana',
    ).cache()
    criticos = ['numero_incidente', 'fecha_inicio', 'codigo_localidad', 'localidad_norm', 'codigo_tipo']
    r = detalle.agg(
        F.count(F.lit(1)).alias('filas_despues_join'),
        F.sum((~F.col('codigo_reconocido')).cast('int')).alias('codigos_no_reconocidos'),
        F.sum((~F.col('en_ventana')).cast('int')).alias('fuera_ventana_aceptados'),
        F.sum((~F.col('en_mes_archivo')).cast('int')).alias('fuera_mes_aceptados'),
        F.sum(F.greatest(*[F.col(c).isNull().cast('int') for c in criticos])).alias('nulos_criticos_aceptados'),
        F.sum((F.greatest(*[F.col(c).isNull() for c in criticos]) & F.col('observacion_calidad').isNull()).cast('int'))
        .alias('nulos_criticos_sin_observacion'),
        F.sum((F.col('edad_anios').isNotNull() & ((F.col('edad_anios') < poc['edad_min_anios'])
                                                  | (F.col('edad_anios') > poc['edad_max_anios']))).cast('int'))
        .alias('edades_fuera_rango_aceptados'),
    ).first()
    hechos.update({k: int(r[k] or 0) for k in r.asDict()})
    detalle = detalle.drop('en_ventana')

    # 9. Agregados
    agregados = {  # el principal se guarda en caché: se suma (V12) y se escribe sin recomputarse
        'periodo_localidad_tipo': detalle.groupBy('periodo', 'localidad_norm', 'codigo_tipo', 'descripcion_tipo')
        .agg(F.count(F.lit(1)).alias('conteo')).cache(),
        'periodo_prioridad': detalle.groupBy('periodo', 'prioridad').agg(F.count(F.lit(1)).alias('conteo')),
        'diario': detalle.groupBy(F.to_date('fecha_inicio').alias('fecha')).agg(F.count(F.lit(1)).alias('conteo')),
    }
    hechos['suma_agregado_principal'] = int(agregados['periodo_localidad_tipo'].agg(F.sum('conteo')).first()[0] or 0)

    # 10. Exportación Parquet
    modo = particionamiento or poc['particionamiento']
    columnas_particion = ['periodo', 'localidad_norm'] if modo == 'periodo_localidad' else ['periodo']
    (detalle.repartition(*columnas_particion).sortWithinPartitions('localidad_norm', 'fecha_inicio')
     .write.mode('overwrite').partitionBy(*columnas_particion).parquet(str(salida / 'detalle')))
    for nombre, agg in agregados.items():
        agg.coalesce(1).write.mode('overwrite').parquet(str(salida / 'agregados' / nombre))
    (df.filter(F.col('es_duplicado_exacto'))
     .select(*esq['columnas'], 'archivo_origen', 'periodo')
     .coalesce(1).write.mode('overwrite').parquet(str(salida / 'duplicados_eliminados')))

    hechos['particionamiento'] = modo
    agregados['periodo_localidad_tipo'].unpersist()
    detalle.unpersist()
    df.unpersist()
    assert sorted(detalle.columns) == sorted(COLUMNAS_DETALLE), 'Esquema de detalle inesperado'
    return hechos
