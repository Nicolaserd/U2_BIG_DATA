# Bitácora de progreso — U2

Leer al retomar. Actualizar al cerrar cada bloque. Formato: estado · hecho · decisiones · cifras · pendientes.

## Decisiones del usuario (2026-11-07)
- Catálogo de tipos: **derivado de los datos**, etiquetado "no oficial".
- Drive: **el usuario ejecuta** `colab drivemount -s u2bd` cuando se le pida. Layout en Drive:
  `MyDrive/BigData_U2/{datos,codigo,resultados}`.
- Git: `git init` + `.gitignore`, **sin commits** salvo que lo pida.
- U1 y U2 son independientes.

## Bloque 0 — `.claude` del proyecto
- Estado: COMPLETADO
- Hecho: `.claude/CLAUDE.md` (movido dentro de `.claude/` a pedido del usuario), este archivo, `rules/`
  (datos-y-evidencia, codigo-python, notebooks, informes), las skills `colab-u2`, `benchmark-u2`,
  `pipeline-pyspark-u2` y `entregables-u2`, y los hooks en `settings.json`.
- Hooks (stdlib, `python -I`):
  - `guardia.py` (PreToolUse): bloquea CSV crudos, U1, pip global, Colab de pago o interactivo y
    `exec` sin `--timeout`; pide confirmación para git commit/push. 17/17 pruebas OK y verificado en vivo.
  - `compilar_py.py` (PostToolUse): compila cada `.py` editado.
  - `contexto_inicio.py` (SessionStart): inyecta este archivo.
  - `recordatorio_colab.py` (Stop): avisa si `u2bd` sigue activa.
- Nota: un hook GLOBAL del usuario bloquea cualquier comando cuyo texto contenga `python -m pip install`.
  Para instalar se usa `.venv/Scripts/python.exe -m pip install` (permitido).

## Bloque 1 — Preparación
- Estado: COMPLETADO
- Colab (verificado con sesión breve, ya detenida): Python 3.13.18, pandas 2.2.3, polars 1.35.2,
  pyarrow 23.0.1, pyspark 4.0.5, psutil 5.9.5, OpenJDK 21, 2 vCPU, 12.67 GB RAM.
  Implicaciones: Spark 4 tiene ANSI activado por defecto (usar `try_to_timestamp` / `try_cast`) y
  Polars 1.x (`infer_schema=False`).
- `.venv` local alineado con Colab (pandas 2.2.3, polars 1.35.2, pyarrow 23.0.1, pyspark 4.0.5) y
  kernel `big-data-u2`. `requirements.txt` (local) y `requirements-colab.txt` listos.
- `git init` (sin commits) y `.gitignore`.
- `config/config.yaml`, `config/localidades_bogota.csv` (oficial 1–20) y
  `config/catalogo_tipos_derivado.csv` (23 códigos, NO oficial).
- `src/emergencias123/{config,normalizacion,catalogo,inventario}.py`,
  `scripts/preparar_insumos.py`, `docs/inventario_datos.md` y
  `resultados/mediciones/inventario_datos.json`.
- Cifras: 27 434 registros; 25 366 incidentes únicos; 44 copias duplicadas exactas; 15 registros
  fuera del mes del archivo (0 fuera de la ventana de +1 día); 1 fila `SIN_D`.

## Bloque 2 — Librería y pruebas locales
- Estado: COMPLETADO (Spark pendiente de probar en Colab)
- Módulos: memoria (MemorySampler), loc, ops_{pandas,polars,spark}, benchmark
  (`measure_performance` + subproceso por repetición + `plan_benchmark` con rotación),
  equivalencia (huella SHA-256), spark_session, validaciones (V01–V19 y tasas), pipeline_spark,
  pipeline_pandas y poc (ejecución + log + poc.jsonl).
- Pruebas: 21 pasan en local y 4 de Spark se omiten en Windows (se corren en Colab).
- Prueba local (`scratchpad/res_local`, NO es evidencia): Pandas y Polars equivalentes (hash
  idéntico, 1 762 filas filtradas). El PoC de Pandas da 27 433 aceptados, 1 rechazado (SIN_D) y
  una tasa de validaciones del 100 %.
- El fixture de pruebas provoca 4 rechazos y 3 advertencias (V05, V08, V10) a propósito.

## Bloque 3 — Conexión a Colab
- Estado: COMPLETADO. Drive montado el 2026-11-08 con `.claude/scripts/montar_drive.py` (el usuario
  aceptó los permisos en su navegador; el script envió Enter cuando lo confirmó). El primer intento
  manual falló con 400 porque se pulsó Enter antes de tiempo.
- Drive: `MyDrive/BigData_U2/datos` (3 CSV, SHA-256 verificados), `codigo/` y `resultados/`.
- Sesión `u2bd` (CPU) activa. Código en `/content/u2` y CSV en `/content/u2_datos` (SHA-256
  idénticos a los locales). Se suben con `scripts/empaquetar_codigo.py` + `colab upload`
  (`MSYS_NO_PATHCONV=1`).
- **27/27 pruebas pasan en Colab** (Spark incluido: equivalencia de las 3 herramientas en los 3
  modos, reglas del PoC y Spark = Pandas con datos reales).
- Ensayo en `/content` (1 repetición, NO es evidencia): Spark frío ~17–21 s de pipeline y ~10–11 s
  de arranque; Pandas ~0.4 s; Polars ~0.09 s. PoC: Spark ~39 s vs Pandas ~1.1 s, ambos con tasa
  100 %. La variante periodo/localidad genera 57 archivos (1.19 MB) frente a 3 (0.75 MB).
- Cambios tras el ensayo: nuevo modo complementario `extremo_a_extremo_caliente` (segunda pasada en
  el mismo proceso) y PoC de Spark con menos acciones (motivos dentro de la misma agregación y
  agregado principal en caché).
- Notebooks fuente generados con `scripts/construir_notebooks.py` → `notebooks/01_benchmark.ipynb`
  y `notebooks/02_poc_pyspark.ipynb`.
- Siguiente paso, cuando Drive esté montado: crear `MyDrive/BigData_U2/{datos,codigo}`, copiar los
  CSV y el código, restart-kernel, `colab exec -f notebooks/01_benchmark.ipynb --timeout 3600`, y
  luego el 02.

## Bloques 4–7 — COMPLETADOS (2026-11-08)
- Benchmark oficial: 54/54 OK (716 s), 0 celdas con error. Extremo a extremo: Pandas 0.430 s, Polars 0.123 s,
  PySpark 19.611 s (+12.4 s de arranque). En caliente: 0.385 / 0.085 / 3.536 s. RSS: 133 / 76 / 1 065 MB.
  Equivalencia con SHA-256 idéntico en los 3 modos.
- Matriz ponderada: Polars 4.50 > Pandas 3.65 > PySpark 2.65. La elección obligatoria de PySpark se explica en el docx.
- PoC oficial: 3 + 3 ejecuciones, variante de particionamiento y escalabilidad ×4/×8, todo OK.
  Spark 42.66 s vs Pandas 1.62 s; RSS 1 804 vs 194 MB; tasa de validaciones 100 %; registros válidos 99.996 %.
  Particionamiento: 3 archivos (periodo) frente a 57 (periodo/localidad).
- Informes generados y verificados: xlsx con 0 errores (332 + 56 fórmulas); docx de 3, 5 y 1 páginas.
- Pruebas finales: 27/27 en Colab y 22 en local + 5 de Spark omitidas. Sin rutas privadas ni tokens en
  los entregables.
- `ENTREGABLES/` 01–15 completos. `README.md` y `docs/TRAZABILIDAD.md` escritos.
- Sesión de Colab `u2bd` DETENIDA. Sin commits de git.
- Para regenerar los informes: `scripts/generar_informes.py`, luego `scripts/organizar_entregables.py`.

## ENTREGABLES/ (pedido del usuario; estructura final del 2026-11-09)
- UNA carpeta por actividad (`Actividad_1_…`, `Actividad_2_…`), SIN carpeta común y SIN subcarpetas por tarea.
  Las tareas de una misma actividad comparten archivos; el `QUE_SE_PIDE.md` de cada actividad relaciona
  cada tarea (1.1–1.3 / 2.1–2.4) con sus archivos. La duplicación ENTRE actividades es aceptable para el
  usuario (código, dependencias y README van en ambas; el xlsx del benchmark también está en A2).
- `scripts/organizar_entregables.py` reconstruye la carpeta desde cero. Ejecutarlo tras regenerar informes.

## Código de informes
- `reportes/{graficos,excel,verificacion,diagrama,resumen,documentos}.py` y `scripts/generar_informes.py`.
  Flujo: xlsx → recálculo con Excel COM → lectura de la Matriz → docx → PDF con Word COM → páginas.
- El PoC (notebook 02) incluye un experimento de escalabilidad con datos replicados ×4/×8 (sintéticos) →
  `mediciones/escalabilidad.jsonl`.

## Migración a flujo SOLO-COLAB + APA 7 (2026-11-09, /loop de 3 rondas)
- Ronda 1 HECHA (cambios de código, aún NO ejecutados en Colab):
  - Notebooks 01/02/03: la primera celda monta Drive e instala desde `BigData_U2_drive.zip` si hace falta.
    El 01 deriva y comprueba el catálogo y guarda el inventario en Drive. El 03 instala LibreOffice,
    python-docx y PyMuPDF, corre pytest, genera y verifica los informes y arma ENTREGABLES en Drive.
  - `reportes/{generador,entregables,verificacion}.py`: verificación solo con LibreOffice (se quitó Excel/Word
    COM). `config.yaml` tiene rutas `base`/`informes` por entorno y la sección `documentos` (autoría APA,
    con marcadores `[...]`).
  - APA 7 en los docx: bloque de título, encabezados sin número, Tabla/Figura N con *Nota.*, tablas sin líneas
    verticales, citas y Referencias (Zaharia et al. 2016; McKinney 2010; Spark, Parquet, pandas, Polars,
    psutil, Colab, guía y datos). Revisión visual: decisión 5 páginas, arquitectura 7 y escalabilidad 1.
  - README reescrito en modo solo-Colab; reglas de `.claude` actualizadas.
- Pendiente (ronda 2): ejecutar 01→02→03 en Colab desde una VM nueva con instalación por zip (requiere
  el "listo" del usuario para Drive; el script de montaje quedó esperando). Mejorar la Figura 1 de la
  decisión (gráfico muy apaisado). Actualizar TRAZABILIDAD (LibreOffice, pytest en el notebook 03, VM nueva).
- Plan de Drive: renombrar `MyDrive/BigData_U2` → `BigData_U2_anterior_20261109` (no borrar) y subir el zip a MyDrive.

- Ronda 2 HECHA (2026-11-09): VM nueva; `MyDrive/BigData_U2` renombrada a `BigData_U2_anterior_20261109`;
  instalación desde el zip OK. 01, 02 y 03 se ejecutaron en Colab sin errores (pytest 27/27; xlsx con 0 errores;
  docx de 5, 8 y 1 páginas; ENTREGABLES en Drive). Benchmark e2e: Pandas 0.387, Polars 0.089, Spark 17.058 s.
  PoC: Spark 38.36 s vs Pandas 1.20 s; RSS 2 016 vs 194 MB. Matriz: Polars 4.50 > Pandas 3.35 > PySpark 2.65.
  Los notebooks `_output` se subieron a `MyDrive/BigData_U2/notebooks/`.
- Patrones de `Formatos/` (pedido del usuario): cabeceras del curso en los 3 notebooks; módulo
  `optimizacion.py` (explain con poda, pushdown y broadcast; CSV/JSON/Parquet; nulos en una agregación;
  IQR informativo); sección 8 del notebook 02; sección «Evidencia de optimización» en la arquitectura;
  test_optimizacion (Spark). AÚN NO ejecutado en Colab: la VM se liberó por inactividad.
- SIGUIENTE: montar Drive (helper esperando), subir el zip y reemplazar `MyDrive/BigData_U2/codigo` con el
  zip nuevo, conservando datos/ y resultados/. Correr 01 → 02 → 03, subir los `_output` a Drive, actualizar
  las cifras de README/TRAZABILIDAD desde las mediciones finales y cerrar la ronda 3 del /loop.

- Sustentación (pedido del usuario, 2026-11-09): `reportes/sustentacion.py` genera
  `Sustentacion/Sustentacion_proyecto_U2.docx`, una explicación para no especialistas (APA, ~9 páginas, cifras de
  las mediciones). La genera el notebook 03 en `MyDrive/BigData_U2/Sustentacion/`; hay que copiarla también a
  `U2/Sustentacion/` en local.
- `Formatos/` NO se sube nunca (pedido del usuario): está en `.gitignore` y `empaquetar_codigo` la excluye. El
  usuario rechazó escribir esa regla en CLAUDE.md, así que no hay que reintentarlo.
- Corrida en curso: el 01 terminó a las 15:06 (benchmark nuevo en Drive). El 02 se interrumpió dos veces
  (cierre de sesión y luego KeyboardInterrupt por un restart-kernel que se solapó). Ahora corren 02 → 03 con
  restart + espera.

## Pendientes conocidos (no bloquean)
- No se probaron los notebooks en un VM nuevo: se ejecutaron tras reiniciar el kernel, y un VM nuevo exige
  volver a autorizar Drive.
- Catálogo de tipos oficial: si se consigue, reemplazar `config/catalogo_tipos_derivado.csv` y regenerar.

## Rediseño 2026-11-10 — notebooks guiados por los del curso (carpeta Formatos)
- Estado: notebooks COMPLETADOS y ejecutados en Colab; informes PENDIENTES (hay que reescribirlos para el formato nuevo).
- Pedido del usuario: los notebooks siguen los del curso (Formatos/02 SparkSession, 03 sintaxis/optimización,
  04 formatos/ETL), solo muestran el proceso (todo el código a la vista, sin anexos ni subprocesos) y NO generan
  Word/Excel. Los informes los prepara el agente aparte desde las mediciones.
- 4 notebooks (`scripts/construir_notebooks.py`; respaldo del diseño anterior en `archivo_anterior/`):
  01 benchmark (`measure_performance` = `measure_operation` del curso + pico con psutil), 02 matriz, 03 PoC
  (`PipelineEmergencias` = `RobustPipeline` en PySpark), 04 métricas (3 ejecuciones vs `pipeline_pandas`) y escalabilidad (x1/x4/x8).
- Error corregido: Spark no distingue mayúsculas en nombres de columna (`withColumn('edad')` pisaba `EDAD`):
  columnas nuevas `edad_num`, `cod_localidad`, `genero_norm`.
- Cifras (Colab, 2026-11-10 16:44, 2 vCPU, 12.67 GB, PySpark 4.0.5): benchmark total Polars 0.13 s, Pandas ~0.44 s,
  Spark 3.99 s (+10.1 s arranque JVM); resultados idénticos (1 762 filas USAQUÉN+CHAPINERO, 21 tipos); LOC 10/10/10.
  Matriz: Polars 4.50, Pandas 3.80, PySpark 3.25. PoC: 27 434 leídos, 27 390 aceptados, 44 duplicados exactos,
  11/11 controles (100 %). Métricas 3 ejecuciones: Spark 62.7 s (90/51/47), Pandas 1.29 s; memoria pico ~23 %.
  Escalabilidad: Spark 40.5/49.2/59.3 s y Pandas 1.6/3.3/9.3 s para x1/x4/x8 (pico Spark x8: 85.2 %).
- Mediciones descargadas en `resultados_colab/descarga/resultados/` (CSV/JSON, logs, Parquet).
- Pendiente: reescribir `src/emergencias123/reportes/` (excel, documentos, sustentacion, graficos, resumen) para los
  CSV nuevos y generar los entregables con `scripts/preparar_entregables.py`; README/TRAZABILIDAD; ENTREGABLES/.


## Mejoras del PoC (2026-11-11)
- `scripts/construir_notebooks.py` (notebooks 03 y 04 regenerados; los `_output` ya no se borran al regenerar):
  1. Parquet particionado por mes/localidad: `partitionBy('periodo', 'cod_localidad')` (Spark y Pandas).
  2. `edad_anios` según UNIDAD (Años/Meses/Dias/Horas); V09 usa `edad_anios`.
  3. `min_desplazamiento_a_recepcion` con su nombre literal (no es tiempo de respuesta: mediana ~197 min) +
     observación `recepcion_antes_de_desplazamiento` + control V12 → 12 controles.
  4. Configuración de Spark de la guía: maxResultSize 2g, skewJoin, advisoryPartitionSize 64MB; driver ≥ 1 GB.
  - Textos de particionamiento actualizados en reportes/{diagrama,documentos,sustentacion}.py.
- EJECUTADO en Colab el 2026-11-11:
  - 03: 0 errores · 12/12 controles · 27 390 aceptados · 58 particiones mes/localidad · PartitionFilters
    periodo + cod_localidad · PoC 91.32 s.
  - 04: Spark 51.35/41.92/37.18 s (media 43.48) vs Pandas 1.31/1.36/1.06 s (media 1.24); memoria 26.3 vs 26.0 %;
    100 % en ambos. Escalabilidad x1/x4/x8: Spark 38.1/55.0/58.8 s, Pandas 1.06/6.66/7.98 s.
- SIGUIENTE: reescribir reportes/ con las mediciones nuevas y generar entregables con `scripts/preparar_entregables.py`.
