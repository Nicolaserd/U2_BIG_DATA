---
name: pipeline-pyspark-u2
description: Reglas del PoC de PySpark del proyecto U2 - esquema explícito, nulos, rechazos con motivo, normalización, catálogo derivado y broadcast join, validaciones con fórmulas de tasas, particionamiento, configuración de Spark y log de validación. Usar al tocar src/emergencias123/{pipeline_spark,pipeline_pandas,validaciones,spark_session}.py o notebooks/02_poc_pyspark.ipynb.
---

# PoC PySpark U2

## Pasos (`pipeline_spark.py`, configurable con `config/config.yaml`, argumentos `--run-id` y `--salida`)
1. **Archivos:** comprobar que existan los 3 CSV de `config.datos.archivos` (cada uno con su `periodo`).
2. **Esquema explícito:** `StructType` con las 10 columnas como `StringType`; los tipos se convierten
   después y se validan (EDAD trae `N/A`). `header=true`, `sep=;`, `encoding=UTF-8` y `mode=PERMISSIVE`
   con columna `_corrupt_record`.
3. **Procedencia:** `archivo_origen` (nombre de archivo) y `periodo` (`AAAA-MM` del archivo, según config).
4. **Nulos:** `N/A` o vacío → null. **Sin imputación.** RECEPCION null es legítima (sin recepción
   registrada). EDAD/UNIDAD/GENERO null quedan como datos de paciente incompletos (bandera
   `paciente_completo`).
5. **Tipos:** `fecha_inicio = to_timestamp(..., 'yyyy-MM-dd HH:mm:ss')`, `fecha_recepcion` igual,
   `codigo_localidad` int, `edad` int, `edad_anios` = edad según UNIDAD (Años ×1, Meses /12,
   Dias /365.25, Horas /8766).
6. **Estandarización:** `localidad_norm` (sin tildes, mayúsculas), cruzada con
   `config/localidades_bogota.csv` (código ↔ nombre); `codigo_tipo` y `descripcion_tipo`;
   `prioridad` y `genero` en mayúsculas sin tildes.
7. **Observaciones de calidad** (columna `observacion_calidad`, la primera que aplique; el registro SE CONSERVA):
   `registro_corrupto`, `numero_incidente_nulo`, `fecha_inicio_invalida`, `localidad_sin_dato`
   (`SIN_D`), `localidad_fuera_catalogo`, `codigo_localidad_inconsistente`, `tipo_incidente_nulo`,
   `edad_fuera_rango` (fuera de 0–120 años). Nunca se elimina ni se imputa nada por estas razones.
8. **Duplicados:** se ELIMINAN solo las copias con el 100 % de los atributos originales iguales (44 en los datos;
   se conserva la primera aparición) y se escriben en `parquet/duplicados_eliminados/`. Se informan las filas con
   NUMERO_INCIDENTE repetido (varios despachos legítimos, se conservan).
9. **Enriquecimiento:** `broadcast(catalogo)` LEFT JOIN por `codigo_tipo` (catálogo de 23 filas,
   **derivado, no oficial**). Se comprueba que la clave sea única y que las filas después sean
   iguales a las filas antes. Los códigos no reconocidos quedan con `codigo_reconocido=false`
   (advertencia, no rechazo).
10. **Agregados:** periodo×localidad×tipo, periodo×prioridad y conteo diario → `parquet/agregados/<nombre>`.
11. **Exportación:** el detalle aceptado se escribe en `parquet/detalle/`, particionado por
    `periodo`, con `repartition("periodo").sortWithinPartitions("localidad_norm", "fecha_inicio")`.
    Sale ~1 archivo por mes; las estadísticas de los row groups por localidad permiten predicate
    pushdown. `config.particionamiento.modo = periodo_localidad` activa la variante
    `partitionBy("periodo", "localidad_norm")` (≈57 archivos de ≈480 filas → riesgo de archivos
    pequeños). Se mide una vez para documentarlo.
12. **Log** `.txt` + `metricas.json`.

## Validaciones (`validaciones.py`)
Cada control es `{id, descripcion, severidad, valor, esperado, aprobado}`, con severidad
`bloqueante | advertencia | informativo`.
V01 archivos presentes · V02 columnas requeridas · V03 leídos = filas físicas de los CSV ·
V04 leídos = conservados + duplicados eliminados · V05 fechas parseables · V06 fechas dentro de
[inicio del mes, fin del mes + 1 día] · V07 ningún nulo crítico SIN observación de calidad · V08 0 códigos no
reconocidos · V09 clave del catálogo única y filas tras el join = filas antes · V10 consistencia
código↔localidad · V11 edades en rango (advertencia) · V12 suma de agregados = conservados · V13 Parquet releído:
conteo = conservados · V14 esquema esperado · V15 Parquet de duplicados eliminados releído · V16 agregado releído ·
V17 duplicados eliminados · V18 incidentes con varios despachos · V19 observaciones por motivo · V20 nulos críticos
conservados (V17–V20 informativos).
- **Tasa de éxito de validaciones (%)** = aprobados / evaluados × 100, donde evaluados =
  bloqueantes + advertencias (los informativos no cuentan).
- **Registros conservados (%)** = conservados / leídos × 100 (`registros_validos_pct` en los JSON). **Nunca se
  mezclan las dos tasas.**

## Configuración de Spark (`spark_session.py`)
Base de la guía: AQE, coalescePartitions, skewJoin, Arrow, `advisoryPartitionSizeInBytes=64MB`,
`maxResultSize=2g`. Se ajusta a lo detectado en el VM: `master=local[N]` con N = vCPU,
`driver.memory=min(4g, 50 % de la RAM)`, `sql.shuffle.partitions=2×vCPU`,
`session.timeZone=America/Bogota`, `ui.enabled=false`. La configuración efectiva se guarda en las
métricas. **Colab = un solo nodo en modo local, no un clúster.** El documento de arquitectura
distingue lo implementado de un despliegue distribuido (Databricks o clúster).

## Métricas del PoC (3 ejecuciones, cada una en un subproceso nuevo)
`tiempo_total_s` (de la carga a la exportación, sin el arranque de la sesión; el arranque se
reporta aparte), `mem_sis_pico_pct`, `rss_pico_mb` (proceso + JVM), `throughput_reg_min` =
leídos / (tiempo_total_s / 60), `tasa_validaciones_pct`, `registros_validos_pct`, leídos,
aceptados, rechazados, errores. `pipeline_pandas.py` cubre el mismo alcance y produce las mismas
métricas para la comparación.
