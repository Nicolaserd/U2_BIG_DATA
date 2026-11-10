# Proyecto U2: Benchmark y PoC PySpark (Emergencias 123 Bogotá)

Implementa la **Guía de actividades U2: Procesamiento distribuido** y se ejecuta por completo en **Google Colab**
con los datos y los resultados en **Google Drive**. Los programas son **solo dos notebooks**:

| Notebook | Qué hace |
|---|---|
| `U2_procesamiento_distribuido.ipynb` | Todo el procesamiento, narrado en el orden de la guía: datos, **Actividad 1** (benchmark de Pandas, Polars y PySpark con `measure_performance()` y matriz de decisión), **Actividad 2** (PoC en PySpark con validaciones y Parquet, métricas de 3 ejecuciones frente a Pandas, escalabilidad, optimización) y pruebas |
| `U2_informes_y_entregables.ipynb` | Genera y verifica los informes (xlsx, docx en formato APA 7, PNG, `.drawio`), la sustentación y ordena la carpeta del proyecto |

Quedan fuera del alcance el video, las diapositivas, el guion del mini-pitch y las capturas manuales.

## Cómo ejecutarlo (solo con Google Colab)

1. Sube los dos `.ipynb` a `Mi unidad/BigData_U2/` en Google Drive y ábrelos con Colab (runtime CPU).
2. Abre `U2_procesamiento_distribuido.ipynb` y elige *Entorno de ejecución → Ejecutar todas* (~30 min). Colab pide
   autorizar Drive. Los CSV se toman de `MyDrive/BigData_Emergencias_123` (carpeta de la Unidad 1; se reconocen por
   su SHA-256, aunque el nombre cambie) o, si no están, se descargan del portal Datos Abiertos Bogotá y se
   verifica el SHA-256. El notebook **escribe él mismo** el código de apoyo en el disco del VM (Anexo A, sección
   plegada): no hay que subir código.
3. Completa autor, institución y docente en la celda de la sección 9. Esa sección ejecuta a continuación
   `U2_informes_y_entregables.ipynb` (~6 min), que instala LibreOffice en el runtime para verificar las fórmulas y
   contar las páginas. Con un solo *Ejecutar todas* queda todo dentro de `MyDrive/BigData_U2/`.

## Qué queda en Drive (`MyDrive/BigData_U2/`)

| Ruta | Contenido |
|---|---|
| `LEEME.md` | Qué archivo cumple cada tarea de la guía |
| `Guia de actividades_U2 (6) (1).pdf` | La guía de la unidad (se sube una vez junto a los notebooks) |
| los 2 notebooks | Guardados con sus salidas de Colab |
| `datos/` | Los 3 CSV (julio, agosto y septiembre de 2026), con SHA-256 verificado |
| `Actividad_1/` | `reporte_comparativo_benchmark.xlsx`, `analisis_decision_tecnologica.docx`, gráficos del benchmark, `QUE_SE_PIDE.md` |
| `Actividad_2/` | `arquitectura_tecnica.docx`, `diagrama_arquitectura.png`/`.drawio`, `metricas_poc.xlsx`, `comparativo_poc_vs_pandas.png`, `analisis_escalabilidad.docx`, `validacion_poc_spark.txt`, `QUE_SE_PIDE.md` |
| `Sustentacion/` | `Sustentacion_proyecto_U2.docx` (explicación para no especialistas) y `Hoja_de_sustentacion_5min.md` |
| `resultados/` | Evidencia: `mediciones/` (JSONL/JSON), `logs/` y `parquet/poc/spark/e1..e3/` |

Todas las cifras están en esos archivos (`metricas_poc.xlsx`, `reporte_comparativo_benchmark.xlsx`,
`resultados/mediciones/`); este README no las repite para no desactualizarse.

## Regla de limpieza de datos

Solo se **eliminan las copias duplicadas exactas** (100 % de los atributos iguales; se conserva la primera
aparición) y se guardan aparte en `duplicados_eliminados/`. Los nulos y las demás anomalías **se conservan** y se
marcan en la columna `observacion_calidad`. No se imputa ningún valor. El catálogo de tipos de incidente es
**derivado de los datos, no oficial**.

## Datos

Conjunto «Llamadas de urgencias y emergencias que ingresan a través de la línea 123» (Secretaría Distrital de Salud,
portal Datos Abiertos Bogotá, licencia CC BY 4.0). Reutiliza los mismos 3 archivos de la Unidad 1.

## Limitaciones

- Con ~27 mil registros dominan los costes fijos de Spark; los resultados no se extrapolan linealmente.
- Colab es un único nodo: Spark corre en modo local, no en un clúster. No se probó Databricks.
- Las proyecciones a 1–2 años son estimaciones sobre datos replicados (sintéticos), no mediciones.

## Desarrollo (solo para quien modifique el proyecto)

Los notebooks se generan con `scripts/construir_notebooks.py` a partir de `src/`, `config/` y `tests/`
(fuente del código de apoyo). Las pruebas se ejecutan en el `.venv` local (`pytest tests`) y dentro del notebook
en Colab (incluidas las de Spark). La documentación de trabajo está en `.claude/` y `docs/TRAZABILIDAD.md`.
