# Trazabilidad: requisito → evidencia

Estados: **Cumplido** · **Parcial** (con el motivo) · **Excluido** (fuera del alcance pedido).
Las rutas son relativas a la raíz de U2. «Drive» = `MyDrive/BigData_U2/`.

## 1. Inspección y preparación

| Requisito | Evidencia | Estado |
|---|---|---|
| Localizar los 3 CSV, la tabla de códigos y la guía | `docs/inventario_datos.md`; guía `Guia de actividades_U2 (6) (1).pdf` | Cumplido |
| Tabla de códigos: buscarla e informar si falta; la derivada se identifica como tal | No existe en los insumos. `config/catalogo_tipos_derivado.csv` (columna `fuente` = no oficial) y aviso en todos los informes | Cumplido |
| Esquema real: columnas, separador, codificación, fechas, nulos, códigos, localidades | `docs/inventario_datos.md`, `resultados/mediciones/inventario_datos.json` | Cumplido |
| Meses, procedencia, tamaños, registros, versiones del entorno | `docs/inventario_datos.md`, `resultados/mediciones/entorno_colab.json` | Cumplido |
| Carpetas organizadas; originales intactos; sin datos ni credenciales en git | Estructura del README, `.gitignore`, hook `.claude/hooks/guardia.py` (bloquea la escritura sobre los CSV) | Cumplido |

## 2. Benchmark Pandas / Polars / PySpark

| Requisito | Evidencia | Estado |
|---|---|---|
| Mismas 5 operaciones con las 3 herramientas | `src/emergencias123/ops_{pandas,polars,spark}.py` | Cumplido |
| Normalización de USAQUÉN/CHAPINERO | `normalizacion.py` y las funciones `_normalizar` de `ops_*`; prueba `test_vectorizado_*` | Cumplido |
| Claves, cardinalidad y tipo de unión; el join no multiplica filas | LEFT m:1 por `codigo_tipo`; celda 6 de `notebooks/01_benchmark_output.ipynb` («Join sin multiplicar filas: True») | Cumplido |
| `measure_performance()` con herramienta, ejecución, operación, tiempos, memoria base/pico, filas, estado, error y LOC | `src/emergencias123/benchmark.py`; `resultados/mediciones/benchmark.jsonl` | Cumplido |
| Criterio de conteo de LOC documentado | `src/emergencias123/loc.py`; hoja LOC del xlsx | Cumplido |
| ≥3 repeticiones; calentamiento separado | 5 repeticiones + 1 calentamiento por herramienta y modo (`plan_benchmark`) | Cumplido |
| Sin reutilizar cachés entre repeticiones; materialización explicada; sin sumar recomputaciones; uso de caché registrado | Subproceso nuevo por repetición; campos `usa_cache` y `accion_materializacion`; markdown del notebook 01 | Cumplido |
| Reloj monotónico de alta resolución | `time.perf_counter_ns()` (`memoria.medir`) | Cumplido |
| Equivalencia de conteos, agregación, esquema y contenido | `equivalencia.py`; `resultados/mediciones/equivalencia_benchmark.json` (SHA-256 idéntico en los 3 modos) | Cumplido |
| % de memoria del sistema + memoria del proceso y la JVM; pico por muestreo; limitaciones | `memoria.py` (MemorySampler, 20 ms); limitaciones en el notebook 01 y en el README | Cumplido |

## 3. Matriz de decisión

| Requisito | Evidencia | Estado |
|---|---|---|
| Puntajes 1–5, pesos 30/25/20/15/10 y fórmulas en Excel | `informes/reporte_comparativo_benchmark.xlsx`, hojas Matriz y Reglas (SUMPRODUCT, 0 errores tras recalcular) | Cumplido |
| Reglas explícitas; cuantitativas sustentadas en resultados; cualitativas justificadas | Hoja Reglas; columna Fundamento de la hoja Matriz | Cumplido |
| Si gana otra herramienta, mostrarlo y explicar por qué se exige PySpark | Polars 4.50 > Pandas 3.35 > PySpark 2.65. `informes/analisis_decision_tecnologica.docx`, secciones «Resumen ejecutivo» y «Conveniencia para el volumen probado frente a la elección exigida» | Cumplido |
| Recomendaciones por volumen, herramientas complementarias, limitaciones y plan por fases | `analisis_decision_tecnologica.docx`, secciones «Recomendaciones por volumen», «Herramientas complementarias», «Plan de implementación por fases» y «Limitaciones» | Cumplido |

## 4. Pipeline PySpark (PoC)

| Requisito | Evidencia | Estado |
|---|---|---|
| Carga de los 3 CSV desde Drive | `notebooks/02_poc_pyspark_output.ipynb` (Drive montado; `cfg.dir_datos` = Drive) | Cumplido |
| Esquema explícito; procedencia; nulos; fechas y tipos; estandarización | `src/emergencias123/pipeline_spark.py` pasos 1–5 | Cumplido |
| Enriquecimiento con broadcast; agregaciones; Parquet; logs y métricas | `pipeline_spark.py` pasos 8–10; `resultados/logs/validacion_poc_spark.txt`; `poc.jsonl` | Cumplido |
| Sin eliminación ni imputación silenciosa; rechazos con motivo; duplicados evaluados y no eliminados | `motivo_rechazo`, `parquet/.../rechazados/`, `es_duplicado_exacto` (44 marcados); prueba `test_pipeline_spark_reglas` | Cumplido |
| Validaciones V01–V19 (archivos, columnas, conteos, fechas y meses, nulos críticos, códigos, cardinalidad, coherencia, relectura de Parquet) | `src/emergencias123/validaciones.py`; log de validación | Cumplido |
| Fórmula inequívoca de la tasa; distinguirla de los registros válidos | `validaciones.tasas`; xlsx de métricas, hoja Validaciones | Cumplido |
| Particionamiento justificado (mes/localidad, archivos pequeños) | `arquitectura_tecnica.docx`, sección «Estrategia de particionamiento»; hoja Particionamiento (3 archivos frente a 57 medidos) | Cumplido |
| Configuración de Spark según los recursos; local frente a clúster | `spark_session.py`; `arquitectura_tecnica.docx`, sección «Configuración de PySpark» | Cumplido |

## 5. Medición del PoC

| Requisito | Evidencia | Estado |
|---|---|---|
| 3 ejecuciones: tiempo, memoria del sistema (%), proceso+JVM, throughput, tasa, procesados y errores | `resultados/mediciones/poc.jsonl`; `informes/metricas_poc.xlsx` | Cumplido |
| Promedios y comparación con Pandas en alcance equivalente | `pipeline_pandas.py`; hoja Promedios del xlsx; `informes/comparativo_poc_vs_pandas.png` | Cumplido |
| No inventar una mejora | PySpark fue ~32 veces más lento y usó ~10 veces más RSS que Pandas (media de 3 ejecuciones); reportado así en todos los informes | Cumplido |

## 6. Arquitectura y escalabilidad

| Requisito | Evidencia | Estado |
|---|---|---|
| Arquitectura implementada (ingesta, procesamiento, almacenamiento, salidas, configuración, particionamiento, recursos, KPIs, riesgos) | `informes/arquitectura_tecnica.docx` (5–8 páginas, verificado en Colab al exportar a PDF con LibreOffice) | Cumplido |
| Diagrama PNG de alta resolución y fuente editable | `informes/diagrama_arquitectura.png` (300 dpi), `informes/diagrama_arquitectura.drawio` | Cumplido |
| Proyección a 1 y 2 años con supuestos; lo medido separado de lo teórico | `informes/analisis_escalabilidad.docx` (1 página): puntos medidos ×1 (real) y ×4/×8 (replicados, sintéticos) más el ajuste lineal | Cumplido |

## 7. Entregables y su carpeta en `ENTREGABLES/`

A1 = `Actividad_1_Analisis_comparativo_de_herramientas`, A2 = `Actividad_2_Arquitectura_y_PoC_PySpark`. Cada
actividad tiene una sola carpeta. Su `QUE_SE_PIDE.md` relaciona cada tarea con los archivos que la cumplen.

| Entregable | Archivo de trabajo | Carpeta | Tareas que cumple | Estado |
|---|---|---|---|---|
| Código, configuración, dependencias, README, inventario y esta lista | `src/`, `config/`, `scripts/`, `tests/`, `requirements*.txt`, `README.md`, `docs/` | A1 y A2 (copiado en ambas) | Todas | Cumplido |
| Notebook de benchmark con resultados | `notebooks/01_benchmark_output.ipynb` (ejecutado en Colab) | A1 | 1.1 | Cumplido |
| Reporte comparativo .xlsx (mediciones + matriz) | `informes/reporte_comparativo_benchmark.xlsx` | A1 (y A2 como referencia de Pandas) | 1.1, 1.2, 1.3, 2.4 | Cumplido |
| Análisis de decisión .docx | `informes/analisis_decision_tecnologica.docx` | A1 | 1.2, 1.3 | Cumplido |
| Arquitectura .docx (5–8 páginas) + diagrama .png/.drawio | `informes/arquitectura_tecnica.docx`, `informes/diagrama_arquitectura.*` | A2 | 2.1 (y 2.4: recursos/KPIs) | Cumplido |
| Notebook del PoC + Parquet en Drive + log .txt | `notebooks/02_poc_pyspark_output.ipynb`; Drive `resultados/parquet/poc/spark/e1..e3/`; `resultados/logs/validacion_poc_spark.txt` | A2 | 2.2 | Cumplido |
| Mini-pitch (video, slides) | — | A2 (solo descripción en QUE_SE_PIDE.md) | 2.3 | Excluido por el encargo |
| Métricas del PoC .xlsx + gráfico vs Pandas .png + escalabilidad .docx (1 página) | `informes/metricas_poc.xlsx`, `comparativo_poc_vs_pandas.png`, `analisis_escalabilidad.docx` | A2 | 2.4 | Cumplido |

## 8. Verificación

| Requisito | Evidencia | Estado |
|---|---|---|
| Pruebas de transformaciones, equivalencia, validaciones y exportaciones | `tests/`: batería completa ejecutada en Colab por el notebook 03 (incluye las pruebas de Spark) | Cumplido |
| Notebooks ejecutables en orden desde un entorno limpio | Ejecutados en orden (01 → 02 → 03) en una VM nueva de Colab; la primera celda instala el proyecto desde `BigData_U2_drive.zip` | Cumplido |
| Sin credenciales ni rutas privadas en los entregables | Búsqueda de rutas de usuario, correos y tokens en notebooks, informes y mediciones: 0 coincidencias | Cumplido |
| Documentos y hojas verificados | `resultados/mediciones/verificacion_informes.json` (xlsx: 0 errores; docx: 3, 5 y 1 páginas) | Cumplido |
| Evidencia real de Colab (nada simulado) | Notebooks ejecutados en Colab y guardados en Drive con sus salidas; las cifras salen de los JSONL en `MyDrive/BigData_U2/resultados/mediciones/` | Cumplido |

## 9. Alineación con los notebooks de ejemplo del curso (`Formatos/`)

| Patrón del ejemplo | Dónde se aplica | Estado |
|---|---|---|
| Cabecera (curso, saber, objetivos, prerrequisitos, tiempo, dataset) y cierre de reflexión | Notebooks 01, 02 y 03 | Cumplido |
| SparkSession optimizada para Colab | `spark_session.py` (config de la guía, ajustada a vCPU/RAM); diferencias con el ejemplo (70 % de RAM, Kryo) justificadas en la arquitectura | Cumplido |
| Planes de ejecución con `explain()` | `optimizacion.planes_ejecucion`; notebook 02, sección 8; `mediciones/planes_ejecucion.txt` | Cumplido |
| Nulos (`analyze_nulls`) y atípicos IQR (`detect_outliers_iqr`) | `optimizacion.perfil_nulos` (una sola agregación) y `atipicos_iqr` (solo informativo, sin imputar ni eliminar) | Cumplido |
| Comparación de formatos CSV/JSON/Parquet | `optimizacion.comparar_formatos`; tabla en la arquitectura | Cumplido |
| `measure_operation` | `benchmark.measure_performance` (proceso nuevo por repetición, memoria muestreada) | Cumplido |
