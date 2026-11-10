---
name: benchmark-u2
description: Reglas para implementar y ejecutar el benchmark Pandas vs Polars vs PySpark del proyecto U2 con measure_performance() - operaciones, materialización, memoria muestreada, conteo de LOC, repeticiones, caché y equivalencia entre herramientas. Usar al tocar src/emergencias123/{benchmark,ops_*,memoria,loc,equivalencia}.py o notebooks/01_benchmark.ipynb.
---

# Benchmark U2

## Operaciones (la misma lógica en las 3 herramientas, en `ops_pandas.py`, `ops_polars.py` y `ops_spark.py`)
1. `carga`: leer los 3 CSV (todas las columnas como texto, `;`, UTF-8 con BOM) y concatenarlos.
2. `filtrado`: `localidad_norm = normalizar_texto(LOCALIDAD)` ∈ {`USAQUEN`, `CHAPINERO`}.
3. `agregacion`: conteo por `codigo_tipo` sobre el filtrado.
4. `join`: LEFT JOIN muchos-a-uno filtrado ⟕ catálogo derivado por `codigo_tipo`. Se comprueba que
   la clave del catálogo sea única, que las filas después sean iguales a las filas antes y se
   cuentan las filas sin coincidencia.
5. `exportacion`: Parquet del filtrado enriquecido (en Spark, un directorio de part-files).

`normalizar_texto`: trim → colapso de espacios → mayúsculas → sin tildes (NFKD). `codigo_tipo`:
el texto antes del primer `-` rodeado de espacios, normalizado; si no hay código, el texto completo
normalizado. La referencia es `normalizacion.py`; las versiones vectorizadas de Polars y Spark
deben dar el mismo resultado (hay pruebas que lo comprueban).

## Conteo de LOC
Cada operación va delimitada con `# >>> op:<nombre>` y `# <<< op:<nombre>`. `loc.py` cuenta las
líneas lógicas entre los marcadores, sin contar las vacías, las de comentario ni las propias
marcas. Una sentencia partida en varias líneas cuenta cada línea física no vacía. El criterio se
documenta en los informes.

## measure_performance()
- Interfaz pública: `measure_performance(herramienta, ejecucion, modo, calentamiento, config)`.
  Devuelve una lista de registros (uno por operación + `total`) y los guarda en
  `resultados/mediciones/benchmark.jsonl`.
- Campos: `herramienta, modo, ejecucion, calentamiento, operacion, segundos, mem_sis_base_pct,
  mem_sis_pico_pct, rss_base_mb, rss_pico_mb, filas_entrada, filas_salida, estado, error, loc,
  usa_cache, accion_materializacion, n_muestras, ts_inicio`.
- Reloj: `time.perf_counter_ns()` (monotónico, alta resolución). La guía sugiere `time.time()`;
  se explica por qué se usa perf_counter.
- Memoria: el hilo `MemorySampler` muestrea cada 20 ms `psutil.virtual_memory().percent` (% del
  sistema, lo que pide la guía) y la suma de RSS del proceso + `children(recursive=True)` (incluye
  la JVM de Spark). El pico es el **máximo de las muestras**, nunca una lectura final.
  Limitaciones: el % del sistema incluye otros procesos de Colab, RSS cuenta páginas compartidas y
  el muestreo puede perder picos de menos de 20 ms.

## Validez de la comparación
- **Un subproceso Python nuevo por (herramienta, modo, ejecución)**, lanzado desde el
  notebook/script orquestador: no se reutiliza estado, caché ni JVM entre repeticiones.
- Por cada herramienta y modo: 1 calentamiento (`calentamiento=True`, excluido de los promedios)
  y luego N medidas (config `benchmark.repeticiones`, 5 por defecto, mínimo 3).
- El orden de las herramientas rota en cada ronda para no sesgar por deriva térmica o de caché del SO.
- Caché de páginas del SO: queda caliente por igual para las tres tras el calentamiento; se documenta.
- Modos:
  - `por_operacion`: tiempo de cada operación materializada. Pandas es eager. Polars usa la API
    eager (DataFrame). Spark aplica `df.cache(); df.count()` en cada frontera (`usa_cache=True`) para
    que la operación siguiente no recompute la anterior, y `unpersist()` al final. Los tiempos se
    suman sin recomputaciones. El arranque de SparkSession se mide aparte como `inicio_sesion`.
  - `extremo_a_extremo`: el pipeline completo con mínima materialización. Polars: `scan_csv` lazy
    → `collect()` de la agregación + `sink_parquet`/`write_parquet`. Spark: DAG único, acciones solo
    en `collect()` de la agregación y `write.parquet`. Se documenta que en Spark esas dos acciones
    recorren el plan dos veces si no hay caché (se registra la decisión tomada).
- `total` = de carga a exportación. Para Spark también `total_con_arranque`.
- Archivo de salida distinto por ejecución (`parquet/benchmark/<herramienta>/<modo>/<ejecucion>`),
  que se borra antes de escribir.

## Equivalencia (fuera de la medición)
`equivalencia.py` lee de vuelta los Parquet de las 3 herramientas y compara: número de filas, el
diccionario `{codigo_tipo: conteo}`, los nombres de columna y sus tipos lógicos, y el SHA-256 del
contenido canónico (columnas en orden fijo, valores como texto, filas ordenadas). Si algo difiere,
se informa y se corrige antes de reportar.
