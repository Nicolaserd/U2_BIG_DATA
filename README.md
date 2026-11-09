# Proyecto U2: Benchmark y PoC PySpark (Emergencias 123 Bogotá)

Este proyecto implementa la **Guía de actividades U2: Procesamiento distribuido** y se ejecuta por completo
en **Google Colab**, con el código y los datos en **Google Drive**:

- **Actividad 1:** benchmark de Pandas, Polars y PySpark con `measure_performance()`, matriz de decisión
  ponderada y selección tecnológica.
- **Actividad 2:** documento de arquitectura y prueba de concepto (PoC) en PySpark, con métricas de tres
  ejecuciones y un análisis de escalabilidad.

Quedan fuera del alcance el video, las diapositivas, el guion del mini-pitch y las capturas manuales.

## Cómo ejecutarlo (solo con Google Colab)

1. **Subir el proyecto a Drive (una sola vez).** Sube `BigData_U2_drive.zip` a tu `Mi unidad` (MyDrive)
   desde el navegador. También puedes subirlo al panel *Archivos* de una sesión de Colab.
2. **Abrir y ejecutar los notebooks en orden** (Entorno de ejecución → *Ejecutar todas*):
   1. `01_benchmark.ipynb`: benchmark de las tres herramientas (~13 min).
   2. `02_poc_pyspark.ipynb`: PoC en PySpark, 3 ejecuciones frente a Pandas y escalabilidad ×4/×8 (~8 min).
   3. `03_informes.ipynb`: pruebas automáticas, informes verificados y carpeta `ENTREGABLES` (~5 min).

   La primera celda de cada notebook monta Drive (Colab pide autorizar el acceso). Si el proyecto no está
   instalado todavía, la misma celda descomprime el zip en `MyDrive/BigData_U2/`. Tras la instalación, abre los
   notebooks desde `MyDrive/BigData_U2/notebooks/`: así quedan guardados en Drive con sus resultados.
3. **Datos de autoría (APA).** Antes de generar los informes, completa en
   `MyDrive/BigData_U2/codigo/config/config.yaml`, sección `documentos`, los campos autor, institución,
   docente y fuente de los datos. Después vuelve a ejecutar el notebook 03.

No hay que instalar nada a mano. pandas, Polars, PySpark, Java y psutil vienen en el runtime de Colab (las
versiones verificadas están en `requirements-colab.txt`). El notebook 03 instala en el runtime LibreOffice,
python-docx y PyMuPDF para generar y verificar los informes.

## Qué queda en Drive (`MyDrive/BigData_U2/`)

| Carpeta | Contenido |
|---|---|
| `datos/` | Los 3 CSV originales (julio, agosto y septiembre de 2026; 27 434 registros) |
| `codigo/` | Paquete `emergencias123`, `config/`, `scripts/`, `tests/`, notebooks fuente y este README |
| `notebooks/` | Los notebooks que se abren en Colab, guardados con sus resultados |
| `resultados/mediciones/` | `benchmark.jsonl`, `poc.jsonl`, `escalabilidad.jsonl`, `entorno_colab.json`, `inventario_datos.json`, `equivalencia_benchmark.json`, `verificacion_informes.json` |
| `resultados/parquet/poc/spark/e1..e3/` | Parquet del PoC: `detalle/` particionado por periodo, `agregados/` y `rechazados/` |
| `resultados/logs/` | `validacion_poc_spark.txt` (log de validación) |
| `informes/` | xlsx, docx (formato APA 7), gráficos PNG y diagrama `.png`/`.drawio` |
| `ENTREGABLES/` | Una carpeta por actividad, cada una con un `QUE_SE_PIDE.md` que relaciona cada tarea con sus archivos |

## Resultados principales (ejecución en Google Colab)

Entorno: Python 3.13, pandas 2.2.3, Polars 1.35.2, PySpark 4.0.5, OpenJDK 21, 2 vCPU y 12.7 GB de RAM.
Spark corre en **modo local en un único nodo**, no en un clúster.

| Benchmark (27 434 registros, 5 repeticiones) | Pandas | Polars | PySpark |
|---|---:|---:|---:|
| Tiempo de la carga a la exportación (s) | 0.430 | **0.123** | 19.611 (+12.4 s de arranque) |
| Memoria residente (RSS) pico del proceso y la JVM (MB) | 133 | 76 | 1 065 |
| Puntaje de la matriz ponderada (1–5) | 3.65 | **4.50** | 2.65 |

| PoC (3 ejecuciones, mismo alcance) | PySpark | Pandas |
|---|---:|---:|
| Tiempo de la carga a la exportación (s) | 42.66 | 1.62 |
| Memoria del sistema, pico (%) | 22.0 | 12.7 |
| RSS pico del proceso y la JVM (MB) | 1 804 | 194 |
| Tasa de éxito de validaciones (%) | 100.0 | 100.0 |

Con unos 3 MB de datos, **PySpark no mejora a Pandas** y así lo reportan los informes. Se mantiene como
herramienta principal porque la actividad lo exige y porque escala horizontalmente a un clúster sin cambiar
el código. Las tres herramientas producen salidas equivalentes: mismas filas, mismo esquema, mismos conteos y
la misma huella SHA-256. El catálogo de tipos de incidente **se derivó de los datos y no es oficial**, porque
entre los insumos no había una tabla oficial de códigos.

## Metodología (resumen)

- **`measure_performance()`** (`codigo/src/emergencias123/benchmark.py`):
  - Cada repetición corre en un proceso nuevo; hay 1 calentamiento descartado y 5 repeticiones medidas, con el
    orden de las herramientas rotado.
  - Reloj `perf_counter_ns`.
  - Memoria muestreada cada 20 ms: % del sistema (psutil) y RSS del proceso con sus hijos (incluye la JVM).
- **Materialización:**
  - Modo `por_operacion`: Spark aplica `cache()+count()` en cada frontera.
  - Modo `extremo_a_extremo`: Polars usa `collect_all` y Spark ejecuta dos acciones con el filtrado en caché.
  - Modo `extremo_a_extremo_caliente` (complementario): segunda pasada dentro del mismo proceso.
- **Validaciones V01–V19:**
  - Tasa de éxito = controles aprobados / evaluados (bloqueantes + advertencias).
  - Registros válidos = aceptados / leídos.
  - Ningún registro se elimina en silencio: los rechazos llevan su motivo y los duplicados se marcan.
- **Particionamiento** por periodo. La variante periodo/localidad se midió y genera 57 archivos de ~20 KB
  (archivos pequeños).

## Limitaciones

- El volumen es pequeño: dominan los costes fijos y la extrapolación lineal no garantiza el rendimiento.
- El análisis de escalabilidad separa lo medido (×1 real; ×4/×8 con datos replicados sintéticos) de lo teórico.
- Colab es un único nodo de 2 vCPU, así que no se midió Spark distribuido.
- El % de memoria del sistema incluye otros procesos de Colab, y el RSS cuenta páginas compartidas.
- Montar Drive requiere que el usuario autorice el acceso en cada sesión nueva.
