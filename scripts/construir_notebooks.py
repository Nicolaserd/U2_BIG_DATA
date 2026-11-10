"""Construye los DOS notebooks del proyecto (únicos programas que se suben a Google Drive / Colab).

- notebooks/U2_procesamiento_distribuido.ipynb: notebook único y narrado con todo el procesamiento
  (datos, benchmark de la Actividad 1, PoC en PySpark de la Actividad 2, optimización y pruebas).
- notebooks/U2_informes_y_entregables.ipynb: genera y verifica los informes (xlsx, docx, png, drawio) y organiza
  la carpeta única del proyecto en Drive.

Decisión del usuario (2026-11-10): los programas se usan solo como notebooks y en Drive se sube únicamente lo
necesario. Por eso cada notebook ESCRIBE su propio código de apoyo en el disco del VM (`%%writefile` en
/content/u2lib) antes de usarlo: measure_performance() ejecuta cada repetición en un proceso Python nuevo, y ese
proceso necesita importar el código desde un archivo. Nada de ese código se sube ni queda en Drive.

Este script es herramienta local de desarrollo: toma los módulos de src/, config/ y tests/ (fuente editable del
agente) y los incrusta en los notebooks con su explicación. Uso: .venv/Scripts/python.exe scripts/construir_notebooks.py
"""
from pathlib import Path

import nbformat as nbf

RAIZ = Path(__file__).resolve().parents[1]
LIB = '/content/u2lib'
NB_ANALISIS = 'U2_procesamiento_distribuido.ipynb'
NB_INFORMES = 'U2_informes_y_entregables.ipynb'


def md(texto):
    return nbf.v4.new_markdown_cell(texto.strip())


def code(texto):
    return nbf.v4.new_code_cell(texto.strip())


ANEXO = []   # celdas del Anexo A (código de apoyo), en el orden en que se registran


def modulo(rel, explicacion):
    """Registra en el Anexo A la celda que escribe el archivo `rel` (ruta relativa a la raíz del código) en el VM.

    No devuelve celdas: el relato del notebook no se interrumpe con volcados de código. Lo que importa se muestra
    en pantalla con `ver_codigo()` en las secciones donde se explica.
    """
    contenido = (RAIZ / rel).read_text(encoding='utf-8').replace('\r\n', '\n').rstrip('\n')
    ANEXO.extend([md(explicacion), code(f'%%writefile {LIB}/{rel}\n{contenido}')])
    return []


TITULO_ANEXO = 'Anexo A · Código de apoyo (ejecutar primero)'


def con_anexo(nb):
    """Inserta el Anexo A (plegado en Colab) justo antes de la sección «1. Configuración»."""
    intro = md(f"""
## {TITULO_ANEXO}

Estas celdas **escriben en el disco del VM** (`{LIB}`) el código de apoyo que usa el resto del notebook: la
configuración, las reglas de normalización, las operaciones de cada herramienta, el pipeline, las validaciones y
las pruebas. Cada archivo lleva antes una nota de qué hace. **No hace falta leerlas para seguir el relato**: el
código que importa se muestra en pantalla en las secciones donde se explica. Solo hay que ejecutarlas antes (la
opción *Ejecutar todas* ya lo hace). Nada de esto se sube a Drive.
""")
    i = next(k for k, c in enumerate(nb.cells) if c.source.startswith('## 1. Configuración'))
    nb.cells[i:i] = [intro, *ANEXO]
    nb.metadata['colab']['collapsed_sections'] = [TITULO_ANEXO]
    return nb


def notebook(celdas):
    nb = nbf.v4.new_notebook()
    nb.metadata = {'kernelspec': {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'},
                   'language_info': {'name': 'python'}, 'colab': {'provenance': []}}
    nb.cells = [c for grupo in celdas for c in (grupo if isinstance(grupo, list) else [grupo])]
    return nb


def cabecera(nombre, actividad, objetivos, prerrequisitos, tiempo):
    """Cabecera con el formato de los notebooks de ejemplo del curso."""
    return md('\n'.join([
        '| | |', '|---|---|',
        '| **CURSO** | Herramientas de Big Data |',
        '| **SABER 2** | Procesamiento distribuido |',
        f'| **NOTEBOOK** | {nombre} |',
        f'| **ACTIVIDAD** | {actividad} |',
        '| **DATASET** | Llamadas de urgencias y emergencias de la Línea 123 de Bogotá (Secretaría Distrital de Salud), '
        'julio–septiembre de 2026: 3 CSV, 27 434 registros, ~3 MB |',
        f'| **TIEMPO ESTIMADO** | {tiempo} en Colab (runtime CPU) |',
        '', '**Objetivos de aprendizaje:**', *[f'- {o}' for o in objetivos],
        '', '**Prerrequisitos:**', *[f'- {p}' for p in prerrequisitos],
    ]))


CELDA_ENTORNO = f'''# Entorno: Google Colab + Google Drive (única herramienta del proyecto)
import os, sys
try:
    import google.colab  # noqa: F401
except ImportError as e:
    raise RuntimeError('Este notebook se ejecuta en Google Colab.') from e

if not os.path.ismount('/content/drive'):
    from google.colab import drive
    drive.mount('/content/drive')  # Colab pide autorizar el acceso a Drive

BASE = '/content/drive/MyDrive/BigData_U2'   # carpeta ÚNICA del proyecto en Drive (datos, informes, evidencia)
LIB = '{LIB}'                         # código de apoyo que escribe este notebook (disco del VM; no se sube)
os.makedirs(BASE, exist_ok=True)
for carpeta in ('config', 'src/emergencias123/reportes', 'tests'):
    os.makedirs(f'{{LIB}}/{{carpeta}}', exist_ok=True)
sys.path.insert(0, f'{{LIB}}/src')
os.environ['U2_ENTORNO'] = 'colab'
print('Carpeta del proyecto en Drive:', BASE)'''

CELDA_CARGAR_CONFIG = '''import inspect
from IPython.display import Markdown, display
from emergencias123.config import cargar_config

def ver_codigo(*objetos):
    """Muestra en pantalla el código fuente de funciones o módulos que se están explicando."""
    display(Markdown('```python\\n' + '\\n\\n'.join(inspect.getsource(o) for o in objetos) + '\\n```'))

cfg = cargar_config()
print('Entorno:', cfg.entorno, '| datos:', cfg.dir_datos, '| resultados:', cfg.dir_resultados)'''

CELDA_RECURSOS = '''import json, platform, subprocess, importlib.metadata as md, psutil
from datetime import datetime
entorno = {
    'fecha': datetime.now().isoformat(timespec='seconds'),
    'python': platform.python_version(), 'sistema': platform.platform(),
    'java': subprocess.run(['java', '-version'], capture_output=True, text=True).stderr.splitlines()[0],
    'vcpu': os.cpu_count(), 'ram_gb': round(psutil.virtual_memory().total / 2**30, 2),
    **{p: md.version(p) for p in ('pandas', 'polars', 'pyarrow', 'pyspark', 'psutil', 'numpy')},
}
(cfg.dir_salida('mediciones') / 'entorno_colab.json').write_text(json.dumps(entorno, indent=2, ensure_ascii=False))
entorno'''

MODULOS_CONFIG = [
    ('config/config.yaml', '''
**Configuración (`config/config.yaml`).** Toda ruta y todo parámetro sale de aquí; el código no tiene rutas fijas.
Contiene las rutas de Drive, los 3 archivos con su periodo, su **huella SHA-256** y la URL del portal (respaldo
heredado de la Unidad 1), el esquema observado en la inspección, los parámetros del benchmark y del PoC, la
configuración de Spark y los datos del bloque de título APA de los informes.'''),
    ('src/emergencias123/__init__.py', 'Paquete `emergencias123`, que agrupa el código de apoyo de los notebooks.'),
    ('src/emergencias123/reportes/__init__.py', 'Subpaquete `reportes` (gráficos e informes).'),
    ('src/emergencias123/config.py', '''
**Lectura de la configuración (`config.py`).** Carga el YAML, resuelve las rutas del entorno de Colab y ofrece
utilidades (`rutas_csv`, `dir_salida`). Las variables `U2_DIR_DATOS` y `U2_DIR_RESULTADOS` permiten que el
benchmark trabaje sobre una copia en el disco local del VM sin cambiar el código.'''),
]


def analisis():
    ANEXO.clear()
    return con_anexo(notebook([
        cabecera('Procesamiento distribuido: benchmark y PoC en PySpark',
                 'Actividad 1 (análisis comparativo) y Actividad 2 (arquitectura y PoC en PySpark)',
                 ['Medir de forma automatizada tiempo y memoria de Pandas, Polars y PySpark con measure_performance().',
                  'Construir un pipeline PySpark con ingesta desde Drive, validación de calidad y exportación a Parquet.',
                  'Medir el PoC tres veces y compararlo con una implementación equivalente en Pandas.',
                  'Analizar planes de ejecución, particionamiento, formatos y escalabilidad.'],
                 ['Cuenta de Google con Drive; runtime CPU gratuito de Colab.',
                  'Conocimientos básicos de DataFrames en Pandas y PySpark.'],
                 '~30 minutos'),
        md('''
# Procesamiento distribuido de las emergencias de la Línea 123 de Bogotá

Este notebook reúne **todo lo que se hizo** en la Unidad 2, en el orden en que se hizo, con el código y sus
resultados. Es el único programa de análisis del proyecto; el segundo notebook (`U2_informes_y_entregables.ipynb`)
solo convierte las mediciones que deja este en informes.

**Dónde está cada tarea de la guía.**

| Tarea de la guía | Dónde |
|---|---|
| **1.1** Benchmark Pandas / Polars / PySpark con `measure_performance()` | Sección 3 (3.0 a 3.5) |
| **1.2** Matriz de decisión ponderada | Sección 3.7 y notebook de informes (Excel con fórmulas) |
| **1.3** Selección tecnológica justificada | Sección 3.7 y `analisis_decision_tecnologica.docx` |
| **2.1** Arquitectura y diagrama | Notebook de informes (`arquitectura_tecnica.docx`, `.png`, `.drawio`) |
| **2.2** PoC en PySpark: ingesta desde Drive, validaciones, Parquet y log | Sección 4 |
| **2.4** Métricas de 3 ejecuciones frente a Pandas y escalabilidad | Secciones 4.3, 5 y notebook de informes |

**Recorrido.** Entorno y configuración (0–1) · datos (2) · **Actividad 1**: benchmark (3) · **Actividad 2**: PoC
(4), particionamiento y escalabilidad (5), optimización con los patrones del curso (6) · pruebas (7) · conclusiones (8).

**Cómo leer este notebook.** Las secciones 2 a 8 cuentan el trabajo en el orden de la guía y **muestran en pantalla
el código que importa**: `measure_performance()`, las 5 operaciones de cada herramienta y el pipeline de PySpark. El
**Anexo A** (sección plegada, antes de la 1) escribe en el disco del VM el código de apoyo; hay que ejecutarlo primero
(*Ejecutar todas* lo hace). Está en archivos porque `measure_performance()` ejecuta cada repetición en un
**proceso Python nuevo**, para que ninguna herramienta herede cachés ni una JVM ya caliente, y ese proceso importa el
código desde un archivo.

**Regla de limpieza.** Solo se eliminan las **copias duplicadas exactas** (100 % de sus atributos iguales) y
quedan registradas aparte. Los nulos y demás anomalías **se conservan** y se marcan en `observacion_calidad`.
'''),
        md('## 0. Entorno de ejecución'),
        code(CELDA_ENTORNO),
        md('## 1. Configuración del proyecto\n\nLas rutas y los parámetros salen de `config/config.yaml` (Anexo A).'),
        *[modulo(r, t) for r, t in MODULOS_CONFIG],
        modulo('config/localidades_bogota.csv', '''
**Tabla de localidades (`localidades_bogota.csv`).** División político-administrativa oficial de Bogotá
(códigos 1–20). Sirve para validar que el código y el nombre de localidad de cada registro sean coherentes.'''),
        modulo('config/catalogo_tipos_derivado.csv', '''
**Catálogo de tipos de incidente (`catalogo_tipos_derivado.csv`) — derivado de los datos, NO oficial.** No se
encontró una tabla oficial de códigos entre los insumos, así que el catálogo se derivó de los propios CSV
(23 códigos: 19 con la forma `COD - DESCRIPCIÓN` y 4 sin código). En la parte 2 se vuelve a derivar desde los
datos y se comprueba que coincide con esta tabla.'''),
        code(CELDA_CARGAR_CONFIG),
        md('### Recursos y versiones del runtime'),
        code(CELDA_RECURSOS),

        md('''
## 2. Datos de entrada

Primero se garantiza que los 3 CSV estén en `BigData_U2/datos/` y sean los esperados; después se perfilan con la
biblioteca estándar (sin usar ninguna de las herramientas comparadas) y se deriva el catálogo de tipos.
'''),
        modulo('src/emergencias123/normalizacion.py', '''
**Normalización de texto (`normalizacion.py`).** Reglas compartidas por las tres herramientas: quitar tildes,
colapsar espacios y pasar a mayúsculas (`USAQUÉN` → `USAQUEN`), y separar el código del tipo de incidente de su
descripción. Al definirlas una vez se garantiza que Pandas, Polars y PySpark apliquen la misma lógica.'''),
        modulo('src/emergencias123/adquisicion.py', '''
**Adquisición de los datos (`adquisicion.py`), adaptada de la Unidad 1.** La Unidad 1 leía los CSV de
`MyDrive/BigData_Emergencias_123` y, si Drive no estaba disponible, los descargaba del portal con reintentos.
Al revisar esa lógica se mantuvieron sus dos fuentes y los reintentos, y se corrigieron dos puntos: el fallo del
montaje de Drive ya no se ignora en silencio (aquí Drive es obligatorio, porque los resultados se guardan allí), y
todo archivo se verifica con su **SHA-256** antes de usarse, porque el portal podría reemplazar un recurso.'''),
        code('''
import pandas as pd
from emergencias123.adquisicion import asegurar_datos
origen_datos = asegurar_datos(cfg)
pd.DataFrame([{'archivo': k, 'origen': v['origen'], 'sha256': v['sha256'][:16] + '…'} for k, v in origen_datos.items()])
'''),
        modulo('src/emergencias123/catalogo.py', '''
**Catálogo derivado (`catalogo.py`).** Lee los valores de `TIPO_INCIDENTE`, separa código y descripción y
construye la tabla de códigos únicos. Siempre se rotula como **derivado de los datos, no oficial**.'''),
        modulo('src/emergencias123/inventario.py', '''
**Inventario de datos (`inventario.py`).** Procedencia, tamaño, huella, esquema, nulos, rangos de fechas,
registros fuera del mes de su archivo y duplicados exactos de cada CSV.'''),
        code('''
from emergencias123.inventario import perfilar, a_markdown
from emergencias123.catalogo import derivar_catalogo, leer_catalogo, leer_valores
inv = perfilar(cfg)
inv['origen_datos'] = origen_datos
(cfg.dir_salida('mediciones') / 'inventario_datos.json').write_text(json.dumps(inv, ensure_ascii=False, indent=2))
derivado = derivar_catalogo(leer_valores(cfg.rutas_csv, 'TIPO_INCIDENTE', cfg.datos['separador'], cfg.datos['codificacion']))
versionado = leer_catalogo(cfg.ruta_catalogo_tipos)
assert [(c['codigo_tipo'], c['descripcion_tipo']) for c in derivado] == \\
       [(c['codigo_tipo'], c['descripcion_tipo']) for c in versionado], 'El catálogo no coincide con los datos'
print(f"Catálogo derivado de los datos (no oficial): {len(derivado)} códigos, coincide con la tabla de la parte 1")
_ = (cfg.dir_salida('mediciones') / 'inventario_datos.md').write_text(
    a_markdown(inv, derivado, {'Entorno': 'Google Colab', **{k: entorno[k] for k in ('python', 'pandas', 'polars', 'pyspark', 'vcpu', 'ram_gb')}}),
    encoding='utf-8')
pd.DataFrame([{k: a[k] for k in ('archivo', 'periodo', 'bytes', 'registros', 'fecha_min', 'fecha_max',
                                  'fuera_del_mes_del_archivo', 'duplicados_exactos')} for a in inv['archivos']])
'''),

        md('''
## 3. Actividad 1 — Benchmark Pandas vs Polars vs PySpark

Se comparan las tres herramientas con **los mismos 3 CSV** y **la misma lógica**:

1. **Carga:** leer los 3 CSV y combinarlos (todas las columnas como texto).
2. **Filtrado:** localidades `USAQUEN` y `CHAPINERO` tras normalizar el texto.
3. **Agregación:** conteo de emergencias por `codigo_tipo`.
4. **Join:** LEFT JOIN muchos-a-uno con el catálogo de tipos (derivado, no oficial).
5. **Exportación:** Parquet de los registros filtrados y enriquecidos.

**Medición con `measure_performance()`.**
- Cada repetición corre en un **proceso nuevo**; hay 1 calentamiento descartado y 5 repeticiones medidas por
  herramienta y modo, con el **orden de herramientas rotado** en cada ronda.
- Reloj: `time.perf_counter_ns()` (monotónico; `time.time()` puede saltar con ajustes del reloj del sistema).
- Memoria muestreada cada 20 ms: `psutil.virtual_memory().percent` (% de RAM del sistema, la métrica de la guía)
  y el **RSS del proceso más sus hijos**, que incluye la JVM de Spark.
- **Líneas de código:** líneas no vacías ni de comentario entre los marcadores `# >>> op:` / `# <<< op:`.

**Modos** (Spark y Polars Lazy son perezosos: sin una acción no hay trabajo real).
- `por_operacion`: cada operación se materializa por separado (Spark con `cache()+count()` en cada frontera).
- `extremo_a_extremo`: el pipeline completo con la mínima materialización (Polars `scan_csv` + `collect_all`;
  Spark, un DAG con dos acciones).
- `extremo_a_extremo_caliente` (complementario): segunda pasada en el mismo proceso; separa el coste de una JVM
  recién creada del régimen estable. El arranque de la `SparkSession` se mide aparte como `inicio_sesion`.
'''),
        modulo('src/emergencias123/memoria.py', '''
**Muestreo de memoria (`memoria.py`).** Un hilo registra cada 20 ms el % de memoria del sistema y el RSS del
proceso y sus hijos; el pico es el máximo de las muestras, no una lectura final.'''),
        modulo('src/emergencias123/loc.py', '''
**Líneas de código (`loc.py`).** Cuenta las líneas entre los marcadores de cada operación, con un criterio
explícito y reproducible.'''),
        modulo('src/emergencias123/ops_pandas.py', '**Operaciones en Pandas (`ops_pandas.py`).** Ejecución inmediata: cada llamada ya materializa.'),
        modulo('src/emergencias123/ops_polars.py', '**Operaciones en Polars (`ops_polars.py`).** Modo eager por operación y modo lazy para el extremo a extremo.'),
        modulo('src/emergencias123/spark_session.py', '''
**Sesión de Spark (`spark_session.py`).** Configuración ajustada a los recursos que detecta: `local[*]` según
las vCPU, memoria del driver acotada a la RAM disponible, particiones de shuffle = 2 × vCPU, AQE y Arrow
activados, zona horaria de Bogotá y la interfaz web desactivada. Es Spark local en un único nodo, no un clúster.'''),
        modulo('src/emergencias123/ops_spark.py', '''
**Operaciones en PySpark (`ops_spark.py`).** Evaluación perezosa: nada se ejecuta hasta una acción. Por eso
el modo por operación materializa con `cache()+count()` y libera la caché al terminar.'''),
        modulo('src/emergencias123/benchmark.py', '''
**`measure_performance()` (`benchmark.py`).** Lanza cada repetición en un subproceso, mide cada operación y el
total, y agrega una línea JSON por medición a `benchmark.jsonl` (herramienta, modo, operación, segundos, memoria
base y pico, filas de entrada y salida, LOC, caché y errores).'''),
        modulo('src/emergencias123/equivalencia.py', '''
**Equivalencia (`equivalencia.py`).** Relee los Parquet de cada herramienta y compara filas, esquema lógico,
conteo por tipo y la huella SHA-256 del contenido canónico, fuera del tiempo medido.'''),
        modulo('src/emergencias123/reportes/graficos.py', '''
**Gráficos (`reportes/graficos.py`).** Barras con desviación estándar a 300 dpi; el notebook de informes usa el
mismo módulo para las figuras de los documentos.'''),
        md('''
### 3.0 Cómo se mide: `measure_performance()` y las 5 operaciones

Estas son las piezas centrales de la comparación. `measure_performance()` ejecuta una operación o un pipeline completo
y devuelve el tiempo (`perf_counter_ns`), el pico de memoria muestreado y las filas de entrada y salida;
`MemorySampler` es el hilo que toma las muestras de memoria cada 20 ms.
'''),
        code('''
from emergencias123 import benchmark, memoria
ver_codigo(benchmark.measure_performance, memoria.MemorySampler)
'''),
        md('''
**Las cinco operaciones en cada herramienta** (carga, filtrado, agregación, join y exportación). Las líneas entre los
marcadores `# >>> op:` y `# <<< op:` son las que cuenta la complejidad de código de la sección 3.5.
'''),
        code('''
from emergencias123 import ops_pandas, ops_polars, ops_spark
print('PANDAS')
ver_codigo(ops_pandas.carga, ops_pandas.filtrado, ops_pandas.agregacion, ops_pandas.join, ops_pandas.exportacion)
'''),
        code('''
print('POLARS')
ver_codigo(ops_polars.carga, ops_polars.filtrado, ops_polars.agregacion, ops_polars.join, ops_polars.exportacion)
'''),
        code('''
print('PYSPARK')
ver_codigo(ops_spark.carga, ops_spark.filtrado, ops_spark.agregacion, ops_spark.join, ops_spark.exportacion)
'''),
        md('''
### 3.1 Ejecución del benchmark

Para no medir la latencia variable del sistema de archivos de Drive, el benchmark lee una **copia de los CSV en
el disco local del VM** (`/content/u2_bench`) y escribe allí sus Parquet; las tres herramientas usan los mismos
archivos. Solo las mediciones crudas se guardan en Drive. El PoC (parte 4) sí lee directamente desde Drive,
como pide la guía.
'''),
        code('''
import shutil, time
from pathlib import Path
from emergencias123.benchmark import ejecutar_benchmark, plan_benchmark

LOCAL = Path('/content/u2_bench')
shutil.rmtree(LOCAL, ignore_errors=True)
(LOCAL / 'datos').mkdir(parents=True)
for p in cfg.rutas_csv:
    shutil.copy2(p, LOCAL / 'datos' / p.name)
os.environ['U2_DIR_DATOS'] = str(LOCAL / 'datos')            # lo heredan los subprocesos de medición
os.environ['U2_DIR_RESULTADOS'] = str(LOCAL / 'resultados')
cfg_bench = cargar_config()
salida = LOCAL / 'resultados' / 'mediciones' / 'benchmark.jsonl'
plan = plan_benchmark(cfg_bench)
print(f'{len(plan)} ejecuciones (incluye calentamientos), cada una en un proceso nuevo')

t0 = time.perf_counter()
def progreso(i, n, r):
    marca = 'OK ' if r['codigo_salida'] == 0 else 'ERR'
    print(f"[{i:2d}/{n}] {marca} {r['herramienta']:6s} {r['modo']:26s} e{r['ejecucion']}"
          f"{' (calentamiento)' if r['calentamiento'] else ''} {r['segundos_proceso']:.1f} s", flush=True)
    if r['stderr_final']:
        print(r['stderr_final'])
res = ejecutar_benchmark(cfg_bench, salida, al_avanzar=progreso)
del os.environ['U2_DIR_DATOS'], os.environ['U2_DIR_RESULTADOS']  # el resto del notebook vuelve a Drive
print(f'Duración total: {time.perf_counter() - t0:.0f} s; fallidas: {sum(r["codigo_salida"] != 0 for r in res)}')
shutil.copy2(salida, cfg.dir_salida('mediciones') / 'benchmark.jsonl')
print('Mediciones crudas guardadas en', cfg.dir_salida('mediciones') / 'benchmark.jsonl')
'''),
        md('### 3.2 Resultados por operación (modo `por_operacion`, calentamiento excluido)'),
        code('''
from emergencias123.reportes.graficos import cargar_mediciones
crudo = pd.read_json(salida, lines=True)
print('Registros:', len(crudo), '| errores:', int((crudo['estado'] != 'ok').sum()),
      '| calentamientos excluidos:', int(crudo['calentamiento'].sum()))
med = cargar_mediciones(salida)
ops = ['inicio_sesion', 'carga', 'filtrado', 'agregacion', 'join', 'exportacion', 'total', 'total_con_arranque']
t = (med[med['modo'] == 'por_operacion'].groupby(['herramienta', 'operacion'])
     .agg(seg_media=('segundos', 'mean'), seg_desv=('segundos', 'std'), n=('segundos', 'size'),
          rss_pico_mb=('rss_pico_mb', 'mean'), mem_sis_pico_pct=('mem_sis_pico_pct', 'mean'),
          filas_entrada=('filas_entrada', 'first'), filas_salida=('filas_salida', 'first'), loc=('loc', 'first'))
     .reset_index())
t['operacion'] = pd.Categorical(t['operacion'], ops, ordered=True)
t.sort_values(['herramienta', 'operacion']).round(4)
'''),
        md('### 3.3 Totales de la carga a la exportación y memoria'),
        code('''
tot = (med[med['operacion'].isin(['total', 'total_con_arranque'])]
       .groupby(['modo', 'herramienta', 'operacion'])
       .agg(seg_media=('segundos', 'mean'), seg_desv=('segundos', 'std'), seg_min=('segundos', 'min'),
            seg_max=('segundos', 'max'), mem_sis_base_pct=('mem_sis_base_pct', 'mean'),
            mem_sis_pico_pct=('mem_sis_pico_pct', 'mean'), rss_pico_mb=('rss_pico_mb', 'mean'), n=('segundos', 'size'))
       .reset_index())
es_total = tot['operacion'] == 'total'
tot.loc[es_total, 'veces_vs_mas_rapida'] = (tot.loc[es_total, 'seg_media']
                                           / tot[es_total].groupby('modo')['seg_media'].transform('min'))
tot.round(3)
'''),
        code('''
from IPython.display import Image, display
from emergencias123.reportes.graficos import grafico_operaciones, grafico_totales
GRAF = Path('/content/u2_graficos'); GRAF.mkdir(exist_ok=True)   # vista previa; las figuras finales las genera el notebook de informes
for f in (grafico_operaciones(med, GRAF / 'benchmark_operaciones.png'),
          grafico_totales(med, GRAF / 'benchmark_totales_memoria.png')):
    display(Image(filename=str(f), width=1100))
'''),
        md('''
### 3.4 Equivalencia lógica entre herramientas

Se releen los Parquet de la última repetición de cada herramienta y se comparan filas, esquema lógico, conteo por
`codigo_tipo` y la huella SHA-256 del contenido canónico. También se comprueba que el join no multiplique
registros (filas antes = filas después) y que no queden códigos sin coincidencia en el catálogo.
'''),
        code('''
from emergencias123.equivalencia import comparar
n = cfg_bench.benchmark['repeticiones']
equivalencia = {}
for modo in cfg_bench.benchmark['modos']:
    rutas = {h: cfg_bench.dir_resultados / 'parquet' / 'benchmark' / h / modo / f'e{n}' for h in cfg_bench.benchmark['herramientas']}
    r = comparar(rutas)
    equivalencia[modo] = r
    print(modo, '->', r['criterios'], '| filas:', {h: x['filas'] for h, x in r['resumenes'].items()},
          '| sha256:', {h: x['sha256'][:12] for h, x in r['resumenes'].items()})
join = med[med['operacion'] == 'join']
print('Join sin multiplicar filas:', bool((join['filas_entrada'] == join['filas_salida']).all()),
      '| filas sin coincidencia en el catálogo:', int(join['sin_coincidencia'].max()))
agg = {json.dumps(x, sort_keys=True) for x in med['resultado_agregacion'].dropna()}
print('Agregaciones distintas entre todas las repeticiones y herramientas:', len(agg))
_ = (cfg.dir_salida('mediciones') / 'equivalencia_benchmark.json').write_text(json.dumps(equivalencia, indent=2, ensure_ascii=False))
'''),
        md('### 3.5 Complejidad del código (líneas por operación)'),
        code('''
from emergencias123.loc import loc_por_herramienta
loc_ops = loc_por_herramienta()
_ = (cfg.dir_salida('mediciones') / 'loc_benchmark.json').write_text(json.dumps(loc_ops, indent=2))
loc = pd.DataFrame(loc_ops)
loc.loc['TOTAL'] = loc.sum()
loc
'''),
        md('### 3.6 Síntesis calculada a partir de las mediciones'),
        code('''
e2e = tot[(tot['modo'] == 'extremo_a_extremo') & (tot['operacion'] == 'total')].set_index('herramienta')
mas_rapida = e2e['seg_media'].idxmin(); menor_mem = e2e['rss_pico_mb'].idxmin()
print(f"Más rápida (extremo a extremo): {mas_rapida} ({e2e.loc[mas_rapida, 'seg_media']:.3f} s)")
for h in e2e.index:
    print(f"  {h:6s}: {e2e.loc[h, 'seg_media']:.3f} s  ({e2e.loc[h, 'seg_media'] / e2e.loc[mas_rapida, 'seg_media']:.1f}x)  "
          f"RSS pico {e2e.loc[h, 'rss_pico_mb']:.0f} MB  memoria sistema pico {e2e.loc[h, 'mem_sis_pico_pct']:.1f} %")
arr = med[(med['herramienta'] == 'spark') & (med['operacion'] == 'inicio_sesion')]['segundos']
print(f"Arranque de SparkSession (aparte): {arr.mean():.2f} s de media")
print(f"Menor memoria (RSS proceso+hijos): {menor_mem}")
cal = tot[(tot['modo'] == 'extremo_a_extremo_caliente') & (tot['operacion'] == 'total')].set_index('herramienta')
print('Proceso frío vs caliente (complementario; misma lógica, 2.ª pasada en el mismo proceso):')
for h in cal.index:
    print(f"  {h:6s}: frío {e2e.loc[h, 'seg_media']:.3f} s -> caliente {cal.loc[h, 'seg_media']:.3f} s "
          f"({e2e.loc[h, 'seg_media'] / cal.loc[h, 'seg_media']:.1f}x)")
'''),
        md('''
### 3.7 Limitaciones de la medición y matriz de decisión

- **Volumen pequeño** (~3 MB, 27 434 filas): dominan los costes fijos (arranque de la JVM, planificación y
  serialización de Spark), y el resultado no se puede extrapolar linealmente a volúmenes grandes.
- **Colab es un único nodo** (2 vCPU, ~12.7 GB): Spark corre en modo `local[2]`, no en un clúster.
- El **% de memoria del sistema** incluye el kernel del notebook y los servicios de Colab; el RSS suma páginas
  compartidas y el muestreo cada 20 ms puede perder picos más breves.
- Tras el calentamiento, la caché de páginas del sistema operativo queda igual de caliente para las tres herramientas.

**Matriz de decisión.** Con estas mediciones, el notebook de informes construye la matriz ponderada (rendimiento
30 %, facilidad de uso 25 %, escalabilidad 20 %, recursos 15 %, curva de aprendizaje 10 %) **con fórmulas de
Excel** en `Actividad_1/reporte_comparativo_benchmark.xlsx`, y la justifica en `analisis_decision_tecnologica.docx`.
PySpark es la herramienta principal por exigencia de la actividad y por su escalabilidad horizontal, aunque con
este volumen no sea la más rápida.
'''),

        md('''
## 4. Actividad 2 — PoC en PySpark

Pipeline funcional en PySpark que procesa los **3 meses** leyendo los CSV **desde Google Drive**. Se ejecuta
**3 veces** para obtener métricas promedio y se compara con una implementación en **Pandas de alcance
equivalente** (mismas reglas, mismas salidas).

**Pasos del pipeline.**
1. Comprobar archivos, encabezados requeridos y filas físicas.
2. Ingesta con **esquema explícito** (todo texto y `_corrupt_record`), en modo PERMISSIVE.
3. Procedencia: `archivo_origen` y `periodo` (mes del archivo, desde la configuración).
4. Nulos: `N/A` y vacío pasan a nulo, **sin imputar**.
5. Tipos: fechas con `try_to_timestamp`, enteros con `try_cast` (Spark 4 tiene ANSI activo), edad en años según UNIDAD.
6. Estandarización: localidad (sin tildes, cruzada con la tabla oficial), código de tipo, prioridad y género.
7. **Observaciones de calidad** en `observacion_calidad` (el registro se conserva): registro corrupto, incidente
   nulo, fecha inválida, localidad sin dato o fuera del catálogo, código de localidad inconsistente, tipo nulo y
   edad fuera de 0–120.
8. **Duplicados exactos:** se eliminan solo las copias con el 100 % de los atributos iguales (se conserva la
   primera aparición) y se escriben en `duplicados_eliminados/`. Los incidentes con varios despachos son
   legítimos y solo se informan.
9. **Broadcast join** con el catálogo de tipos (23 filas, derivado, no oficial).
10. Agregados: periodo×localidad×tipo, periodo×prioridad y conteo diario.
11. **Parquet** particionado por `periodo`, ordenado por localidad dentro de cada partición.
12. Relectura de los Parquet con un lector independiente (pyarrow) y log de validación `.txt`.

**Tasas.**
- **Tasa de éxito de validaciones (%)** = controles aprobados / controles evaluados × 100 (evaluados =
  bloqueantes + advertencias; los informativos no entran).
- **Registros conservados (%)** = conservados / leídos × 100; es otra métrica y se reporta aparte.
'''),
        modulo('src/emergencias123/validaciones.py', '''
**Controles de calidad (`validaciones.py`).** Comunes a Spark y Pandas. Cada control tiene severidad
(bloqueante, advertencia o informativo); aquí están también las fórmulas de las tasas y el log `.txt`.'''),
        modulo('src/emergencias123/pipeline_spark.py', '**Pipeline del PoC en PySpark (`pipeline_spark.py`).** Los 12 pasos descritos arriba.'),
        modulo('src/emergencias123/pipeline_pandas.py', '''
**Mismo alcance en Pandas (`pipeline_pandas.py`).** Reproduce las reglas del pipeline de Spark para comparar
en igualdad de condiciones (mismas entradas, mismas salidas en Drive).'''),
        modulo('src/emergencias123/poc.py', '''
**Ejecución y medición del PoC (`poc.py`).** Cada ejecución corre en un subproceso nuevo y registra el tiempo
total de la carga a la exportación (el arranque de la sesión aparte), la memoria, el throughput, las tasas, los
registros procesados y los errores. También genera los datos replicados del experimento de escalabilidad.'''),
        md('''
### Código del pipeline y de los controles de calidad

`procesar()` implementa los 12 pasos; `evaluar()` calcula los controles V01–V20 a partir de los hechos medidos.
'''),
        code('''
from emergencias123 import pipeline_spark, validaciones
ver_codigo(pipeline_spark.procesar, validaciones.evaluar)
'''),
        md('### 4.1 Configuración de Spark ajustada a lo detectado'),
        code('''
from emergencias123.spark_session import configuracion_spark
print('Modo: local en un único nodo de Colab (no es un clúster multinodo)')
configuracion_spark(cfg)
'''),
        md('''
### 4.2 Ejecución: 3 veces Spark y 3 veces Pandas (mismo alcance)

Las herramientas se alternan en cada ronda. Cada ejecución escribe en `resultados/parquet/poc/<herramienta>/e<N>/`
(Drive), agrega sus métricas a `resultados/mediciones/poc.jsonl` y su log a
`resultados/logs/validacion_poc_<herramienta>.txt`.
'''),
        code('''
from emergencias123.poc import ejecutar_poc_completo, ejecutar_subproceso
for ruta in [cfg.dir_salida('mediciones') / 'poc.jsonl', *cfg.dir_salida('logs').glob('validacion_poc_*.txt')]:
    ruta.unlink(missing_ok=True)   # cada ejecución completa del notebook reemplaza la anterior
shutil.rmtree(cfg.dir_resultados / 'parquet', ignore_errors=True)
t0 = time.perf_counter()
def progreso(r):
    print(f"{'OK ' if r['codigo_salida'] == 0 else 'ERR'} {r['herramienta']:6s} e{r['ejecucion']} "
          f"{r['segundos_proceso']:.1f} s -> {r['salida'].strip()[-300:]}", flush=True)
    if r['stderr_final']:
        print(r['stderr_final'])
res = ejecutar_poc_completo(cfg, al_avanzar=progreso)
print('Variante de particionamiento periodo/localidad (1 ejecución, para documentar archivos pequeños):')
progreso(ejecutar_subproceso('spark', 1, particionamiento='periodo_localidad', etiqueta='variante_periodo_localidad'))
print(f'Duración total: {time.perf_counter() - t0:.0f} s')
'''),
        md('### 4.3 Métricas de las 3 ejecuciones y promedios'),
        code('''
poc = pd.read_json(cfg.dir_resultados / 'mediciones' / 'poc.jsonl', lines=True)
principal = poc[poc['etiqueta'].isna() & (poc['estado'] == 'ok')]
cols = ['herramienta', 'ejecucion', 'tiempo_total_s', 'tiempo_inicio_sesion_s', 'mem_sis_base_pct', 'mem_sis_pico_pct',
        'rss_pico_mb', 'throughput_reg_min', 'tasa_validaciones_pct', 'registros_validos_pct',
        'leidos', 'aceptados', 'rechazados', 'errores']
display(principal[cols].rename(columns={'registros_validos_pct': 'registros_conservados_pct', 'aceptados': 'conservados',
                                        'rechazados': 'duplicados_eliminados'}).sort_values(['herramienta', 'ejecucion']))
prom = principal.groupby('herramienta')[cols[2:]].mean().round(3)
prom
'''),
        code('''
s, p = prom.loc['spark'], prom.loc['pandas']
print(f"Tiempo total medio:  Spark {s.tiempo_total_s:.2f} s vs Pandas {p.tiempo_total_s:.2f} s "
      f"-> Spark/Pandas = {s.tiempo_total_s / p.tiempo_total_s:.2f}x")
print(f"Memoria sistema pico: Spark {s.mem_sis_pico_pct:.1f} % vs Pandas {p.mem_sis_pico_pct:.1f} %")
print(f"RSS pico proceso+JVM: Spark {s.rss_pico_mb:.0f} MB vs Pandas {p.rss_pico_mb:.0f} MB "
      f"-> {s.rss_pico_mb / p.rss_pico_mb:.1f}x")
print(f"Throughput: Spark {s.throughput_reg_min:,.0f} vs Pandas {p.throughput_reg_min:,.0f} registros/min")
print(f"Arranque de SparkSession (no incluido en el total): {s.tiempo_inicio_sesion_s:.2f} s")
print(f"Registros: {s.leidos:,.0f} leídos, {s.aceptados:,.0f} conservados, {s.rechazados:,.0f} copias duplicadas exactas eliminadas")
print('Fallos de ejecución:', int((poc['estado'] != 'ok').sum()))
'''),
        md('### 4.4 Log de validación (Spark)'),
        code('''
print((cfg.dir_resultados / 'logs' / 'validacion_poc_spark.txt').read_text(encoding='utf-8'))
'''),
        md('### 4.5 Inspección de los Parquet exportados en Drive (con Spark)'),
        code('''
from emergencias123.spark_session import crear_sesion
from pyspark.sql import functions as F
spark = crear_sesion(cfg)
ult = cfg.dir_resultados / 'parquet' / 'poc' / 'spark' / f"e{cfg.poc['ejecuciones']}"
detalle = spark.read.parquet(str(ult / 'detalle'))
print('Ubicación en Drive:', ult)
detalle.printSchema()
print('Filas:', detalle.count())
detalle.groupBy('periodo').count().orderBy('periodo').show()
detalle.groupBy('observacion_calidad').count().show(truncate=False)
detalle.select('numero_incidente', 'fecha_inicio', 'periodo', 'localidad_norm', 'codigo_tipo', 'descripcion_tipo',
               'prioridad', 'edad_anios', 'observacion_calidad').show(5, truncate=False)
spark.read.parquet(str(ult / 'agregados' / 'periodo_localidad_tipo')).orderBy(F.desc('conteo')).show(8, truncate=False)
print('Copias duplicadas exactas eliminadas (registradas aparte):')
spark.read.parquet(str(ult / 'duplicados_eliminados')).show(5, truncate=False)
'''),
        md('''
## 5. Particionamiento y escalabilidad

### 5.1 `periodo` frente a `periodo/localidad`

Con ~9 100 registros por mes, particionar también por localidad (19–20 valores) produce decenas de archivos de
pocos KB: más metadatos y aperturas de archivo en cada lectura, sin beneficio real de poda.
'''),
        code('''
var = poc[poc['etiqueta'] == 'variante_periodo_localidad']
comp = pd.concat([principal[principal['herramienta'] == 'spark'].tail(1).assign(estrategia='periodo'),
                  var.assign(estrategia='periodo/localidad')])
comp['kb_por_archivo'] = comp['parquet_bytes'] / comp['parquet_archivos'] / 1024
comp[['estrategia', 'parquet_archivos', 'parquet_bytes', 'kb_por_archivo', 'tiempo_total_s']].round(1)
'''),
        md('''
### 5.2 Volumen replicado (datos SINTÉTICOS)

El PoC (Spark y Pandas, 1 ejecución cada uno) se repite con los 3 CSV **replicados 4 y 8 veces** (~110 mil y
~220 mil registros, equivalentes en filas a ~1 y ~2 años). Cada réplica lleva un sufijo `-R<k>` en
`NUMERO_INCIDENTE` para que no sea un duplicado exacto de la original; si lo fuera, la regla de limpieza la
eliminaría y el volumen procesado no crecería. Los datos están en el disco del VM y las métricas se guardan en
`resultados/mediciones/escalabilidad.jsonl`. Estas cifras miden **volumen**, no la variabilidad real de 1–2 años.
'''),
        code('''
from emergencias123.poc import ejecutar_escalabilidad
ruta_esc = cfg.dir_salida('mediciones') / 'escalabilidad.jsonl'
ruta_esc.unlink(missing_ok=True)
def progreso_esc(r):
    print(f"{'OK ' if r['codigo_salida'] == 0 else 'ERR'} x{r['factor']} {r['herramienta']:6s} {r['segundos_proceso']:.1f} s",
          flush=True)
    if r['stderr_final']:
        print(r['stderr_final'])
ejecutar_escalabilidad(cfg, al_avanzar=progreso_esc)
esc = pd.read_json(ruta_esc, lines=True)
base = principal.groupby('herramienta')[['leidos', 'aceptados', 'tiempo_total_s', 'rss_pico_mb', 'mem_sis_pico_pct']].mean().reset_index()
base['factor_replica'] = 1
tabla_esc = pd.concat([base, esc[['herramienta', 'factor_replica', 'leidos', 'aceptados', 'tiempo_total_s', 'rss_pico_mb',
                                  'mem_sis_pico_pct']]]).sort_values(['herramienta', 'factor_replica'])
tabla_esc['throughput_reg_min'] = tabla_esc['leidos'] / (tabla_esc['tiempo_total_s'] / 60)
tabla_esc.round(2)
'''),
        md('''
## 6. Optimización y calidad con los patrones del curso

Se trasladan al caso de la Línea 123 cuatro prácticas de los notebooks de ejemplo del curso:
- **Planes de ejecución (`explain`)** sobre el Parquet exportado: *poda de particiones* (`PartitionFilters` sobre
  `periodo`), *predicado empujado* al lector (`PushedFilters` sobre `localidad_norm`) y *broadcast join*.
- **Formatos CSV, JSON y Parquet:** tamaño y tiempo de lectura más agregación (mediana de 3 ejecuciones).
- **Perfil de nulos** del detalle, con una sola agregación.
- **Atípicos por IQR** en `edad_anios`: solo diagnóstico; no se imputa ni se elimina nada.
'''),
        modulo('src/emergencias123/optimizacion.py', '**Diagnósticos de optimización (`optimizacion.py`).**'),
        code('''
from emergencias123.optimizacion import atipicos_iqr, comparar_formatos, perfil_nulos, planes_ejecucion
planes = planes_ejecucion(spark, ult / 'detalle', cfg.ruta_catalogo_tipos)
print('Poda de particiones:', planes['poda_particiones'], '| Predicado empujado:', planes['predicado_empujado'],
      '| Broadcast join:', planes['broadcast_join'])
print(planes['plan_filtro'][:1800])
print(planes['plan_union'][:1200])
formatos = comparar_formatos(spark, ult / 'detalle', '/content/u2_formatos')
display(pd.DataFrame(formatos['formatos']))
detalle_df = spark.read.parquet(str(ult / 'detalle'))
nulos = pd.DataFrame(perfil_nulos(detalle_df)).query('nulos > 0')
display(nulos)
atipicos = atipicos_iqr(detalle_df, 'edad_anios')
print('Atípicos por IQR en edad_anios (informativo):', atipicos)
optim = {'planes': {k: v for k, v in planes.items() if not k.startswith('plan_')}, 'formatos': formatos,
         'nulos': nulos.to_dict('records'), 'atipicos_edad': atipicos}
(cfg.dir_salida('mediciones') / 'optimizacion_poc.json').write_text(json.dumps(optim, indent=2, ensure_ascii=False))
_ = (cfg.dir_salida('mediciones') / 'planes_ejecucion.txt').write_text(planes['plan_filtro'] + '\\n\\n' + planes['plan_union'])
'''),
        md('### 6.1 Gráfico comparativo frente a Pandas'),
        code('''
from emergencias123.reportes.graficos import grafico_poc
ruta = grafico_poc(principal, GRAF / 'comparativo_poc_vs_pandas.png')
spark.stop()
Image(filename=str(ruta), width=1000)
'''),
        md('''
## 7. Pruebas automáticas (pytest)

Las pruebas verifican la normalización y el catálogo, la adquisición con verificación de huella, la equivalencia
de Pandas, Polars y PySpark, las reglas del pipeline (solo se eliminan duplicados exactos; los nulos se conservan
marcados), la fórmula de las tasas, la relectura de los Parquet y la replicación del experimento de escalabilidad.
Usan un conjunto **sintético** pequeño (cada fila ejercita una regla) y, cuando corresponde, los datos reales.
'''),
        *[modulo(f'tests/{n}', d) for n, d in (
            ('conftest.py', '**Datos sintéticos de prueba y valores esperados (`conftest.py`).**'),
            ('test_normalizacion_catalogo.py', '**Normalización y catálogo.**'),
            ('test_adquisicion.py', '**Adquisición de datos (lógica adaptada de la Unidad 1).**'),
            ('test_benchmark_equivalencia.py', '**Benchmark y equivalencia entre herramientas.**'),
            ('test_pipeline_validaciones.py', '**Reglas del pipeline, tasas y replicación.**'),
            ('test_optimizacion.py', '**Diagnósticos de optimización.**'))],
        code('''
import subprocess, tempfile
r = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q', '-p', 'no:cacheprovider', '--basetemp',
                    tempfile.mkdtemp()], cwd=LIB, capture_output=True, text=True,
                   env={**os.environ, 'PYTHONPATH': f'{LIB}/src'})
print(r.stdout[-2500:] or r.stderr[-2500:])
assert r.returncode == 0, 'Hay pruebas fallidas'
'''),
        md('''
## 8. Conclusiones y próximos pasos

- Todas las cifras de este notebook provienen de su ejecución en Colab (fecha y versiones en la parte 1).
- Con 3 meses de datos, Pandas y Polars son más rápidos y usan menos memoria que Spark: el arranque de la JVM, la
  planificación y la serialización pesan más que el procesamiento. La justificación de PySpark es la escalabilidad
  horizontal, no el rendimiento con este volumen.
- Colab ejecuta Spark en un solo nodo. Un despliegue distribuido (Databricks o un clúster) cambia el balance entre
  los costes fijos y el paralelismo.
- **Siguiente paso (sección 9):** este mismo notebook ejecuta a continuación `U2_informes_y_entregables.ipynb`,
  que genera los informes de las dos actividades a partir de lo que dejó en `BigData_U2/resultados/`, y ordena la
  carpeta `BigData_U2` en Drive.

**Preguntas de reflexión.** ¿Desde qué volumen de datos compensa el coste fijo de Spark? ¿Qué control de calidad
debería detener la publicación de un mes? ¿Cuándo convendría particionar también por localidad?

**Próximos pasos.** Catálogo oficial de códigos; carga incremental mensual; ejecución en Databricks o en un
clúster con al menos un año de datos reales.
'''),
        md('''
## 9. Informes y carpeta de entregables

Con las mediciones ya guardadas, esta sección ejecuta el notebook `U2_informes_y_entregables.ipynb` (debe estar en la
misma carpeta de Drive). Así, **un solo *Ejecutar todas*** deja listo todo dentro de `MyDrive/BigData_U2/`:
`Actividad_1/`, `Actividad_2/`, `Sustentacion/`, `LEEME.md`, `datos/` y `resultados/`. Los informes no vuelven a medir
nada: leen `resultados/mediciones/`.

**Completa estos tres campos** (bloque de título APA de los Word). Si se dejan entre corchetes, los documentos
salen con el marcador `[...]`.
'''),
        code('''
AUTOR = '[Nombre del estudiante o del equipo]'
INSTITUCION = '[Nombre de la institución]'
DOCENTE = '[Nombre del docente]'
'''),
        code('''
import nbformat
ruta_informes = f'{BASE}/U2_informes_y_entregables.ipynb'
assert os.path.exists(ruta_informes), 'Falta U2_informes_y_entregables.ipynb en BigData_U2: súbelo junto a este notebook.'
shell = get_ipython()
for celda in nbformat.read(ruta_informes, as_version=4).cells:
    if celda.cell_type == 'code':
        shell.run_cell(celda.source).raise_error()
'''),
    ]))


MODULOS_INFORMES = [
    ('src/emergencias123/reportes/graficos.py', '**Gráficos (`graficos.py`)**: barras con desviación estándar a 300 dpi.'),
    ('src/emergencias123/reportes/resumen.py', '''
**Cifras de los informes (`resumen.py`).** Todas salen de `resultados/mediciones/`: ningún número de los
documentos se escribe a mano.'''),
    ('src/emergencias123/reportes/diagrama.py', '''
**Diagrama de arquitectura (`diagrama.py`).** Una sola especificación de nodos y flechas produce la fuente
editable `.drawio` y el PNG a 300 dpi.'''),
    ('src/emergencias123/reportes/excel.py', '''
**Libros Excel (`excel.py`).** Promedios, desviaciones, puntajes y la matriz ponderada se calculan con
**fórmulas** (`AVERAGE`, `STDEV`, `SUMPRODUCT`), no con valores pegados.'''),
    ('src/emergencias123/reportes/documentos.py', '''
**Documentos Word en formato APA 7 (`documentos.py`).** Bloque de título, encabezados sin numeración, tablas y
figuras numeradas con nota, citas y referencias con sangría francesa.'''),
    ('src/emergencias123/reportes/sustentacion.py', '''
**Documento de sustentación (`sustentacion.py`).** Explica el proyecto completo a una persona sin
conocimientos técnicos.'''),
    ('src/emergencias123/reportes/verificacion.py', '''
**Verificación con LibreOffice (`verificacion.py`).** Recalcula las fórmulas de los xlsx y busca errores;
exporta los docx a PDF para contar sus páginas.'''),
    ('src/emergencias123/reportes/generador.py', '**Orquestación (`generador.py`)**: genera y verifica todos los informes.'),
    ('src/emergencias123/reportes/entregables.py', '''
**Organización de la carpeta del proyecto (`entregables.py`).** Copia cada informe a la carpeta de su actividad
(sin duplicados), escribe `QUE_SE_PIDE.md` en cada una y `LEEME.md` en la raíz.'''),
]


def informes():
    ANEXO.clear()
    return con_anexo(notebook([
        cabecera('Informes y organización de entregables',
                 'Actividades 1 y 2: documentación, reportes y entregables',
                 ['Generar los informes (xlsx con fórmulas y docx en formato APA 7) a partir de las mediciones.',
                  'Verificar fórmulas y número de páginas con LibreOffice dentro de Colab.',
                  'Dejar en Drive una única carpeta con lo que pide la guía.'],
                 [f'{NB_ANALISIS} ejecutado completo (mediciones en BigData_U2/resultados/).',
                  'Datos de autoría del bloque de título completados en la celda de configuración (sección documentos).'],
                 '~6 minutos'),
        md(f'''
# Informes y entregables — Emergencias 123 Bogotá (U2)

Este notebook **no vuelve a medir nada**: lee lo que dejó `{NB_ANALISIS}` en `BigData_U2/resultados/` y genera
los informes. Después los verifica y organiza la carpeta única del proyecto en Drive:

| Carpeta en `MyDrive/BigData_U2/` | Contenido generado aquí |
|---|---|
| `Actividad_1/` | `reporte_comparativo_benchmark.xlsx` (mediciones, promedios, LOC, reglas y **matriz ponderada con fórmulas**), `analisis_decision_tecnologica.docx`, gráficos del benchmark |
| `Actividad_2/` | `arquitectura_tecnica.docx` (5–8 páginas), `diagrama_arquitectura.png` / `.drawio`, `metricas_poc.xlsx`, `comparativo_poc_vs_pandas.png`, `analisis_escalabilidad.docx` (1 página), `validacion_poc_spark.txt` |
| `Sustentacion/` | `Sustentacion_proyecto_U2.docx`: explicación para no especialistas |
| raíz | `LEEME.md`: qué archivo cumple cada tarea de la guía y cómo ejecutar |

Los informes se generan primero en una carpeta temporal del VM y luego se copian a su actividad; así en Drive no
quedan copias duplicadas ni archivos intermedios.
'''),
        md('## 0. Entorno de ejecución'),
        code(CELDA_ENTORNO),
        md('## 1. Configuración\n\nLas rutas y los parámetros salen de `config/config.yaml` (Anexo A).'),
        *[modulo(r, t) for r, t in MODULOS_CONFIG],
        code(CELDA_CARGAR_CONFIG + f'''
faltan = [n for n in ('benchmark.jsonl', 'poc.jsonl', 'escalabilidad.jsonl', 'loc_benchmark.json', 'entorno_colab.json')
          if not (cfg.dir_resultados / 'mediciones' / n).exists()]
assert not faltan, f'Primero ejecuta {NB_ANALISIS}: faltan las mediciones {{faltan}}\''''),
        md('''
## Datos de autoría (completa estos tres campos antes de ejecutar)

Aparecen en el bloque de título de todos los documentos Word (formato APA 7). Si se dejan entre corchetes, los
documentos salen con el marcador `[...]` para completarlos a mano.
'''),
        code('''
# Si este notebook se ejecuta desde la sección 9 del de procesamiento, esos valores ya vienen definidos allí.
AUTOR = globals().get('AUTOR', '[Nombre del estudiante o del equipo]')
INSTITUCION = globals().get('INSTITUCION', '[Nombre de la institución]')
DOCENTE = globals().get('DOCENTE', '[Nombre del docente]')
datos_doc = {**cfg.documentos, 'autor': AUTOR, 'institucion': INSTITUCION, 'docente': DOCENTE}
'''),
        md('## 2. Herramientas de ofimática en el runtime de Colab (LibreOffice, python-docx, PyMuPDF)'),
        code('''
!apt-get update -qq > /dev/null && apt-get install -y -qq libreoffice-calc libreoffice-writer fonts-liberation > /dev/null
%pip install -q python-docx pymupdf
import shutil, importlib.metadata as md
print('LibreOffice:', shutil.which('soffice'), '| python-docx', md.version('python-docx'), '| pymupdf', md.version('pymupdf'))
'''),
                *[modulo(r, t) for r, t in MODULOS_INFORMES],
        md('## 3. Generación y verificación de los informes'),
        code('''
import pandas as pd
from emergencias123.reportes.generador import generar_todo
shutil.rmtree(cfg.dir_informes, ignore_errors=True)
verif = generar_todo(cfg.dir_resultados, cfg.dir_informes, datos_doc=datos_doc, dir_base=cfg.dir_base)
filas = []
for nombre, v in verif.items():
    if nombre.endswith('.xlsx'):
        filas.append({'archivo': nombre, 'verificación': f"{v['formulas']} fórmulas, {len(v['errores'])} errores, "
                      f"{v['formulas_sin_valor']} sin valor ({v['motor']})"})
    elif nombre.endswith('.docx'):
        filas.append({'archivo': nombre, 'verificación': f"{v['paginas']} página(s) al exportar a PDF"})
assert all(not v['errores'] for k, v in verif.items() if k.endswith('.xlsx')), 'Hay fórmulas con error'
assert 5 <= verif['arquitectura_tecnica.docx']['paginas'] <= 8, 'La arquitectura debe tener 5-8 páginas'
assert verif['analisis_escalabilidad.docx']['paginas'] == 1, 'La escalabilidad debe ocupar 1 página'
print('Matriz ponderada:', {h: round(x, 2) for h, x in verif['matriz']['ponderado'].items()})
pd.DataFrame(filas)
'''),
        md('''
### Matriz de decisión tecnológica (tarea 1.2)

Pesos: rendimiento 30 %, facilidad de uso 25 %, escalabilidad 20 %, recursos 15 %, curva de aprendizaje 10 %. Los
puntajes de rendimiento y recursos salen de una regla fija sobre las mediciones; los demás se justifican en
`analisis_decision_tecnologica.docx`. En el Excel el puntaje ponderado es una fórmula `SUMPRODUCT`.
'''),
        code('''
matriz = verif['matriz']
punt = pd.DataFrame(matriz['puntajes']).T
punt.insert(0, 'peso', pd.Series(matriz['pesos']))
punt.loc['PUNTAJE PONDERADO'] = [None, *[matriz['ponderado'][h] for h in punt.columns[1:]]]
punt.round(2)
'''),
        code('''
from IPython.display import Image, display
for f in ('benchmark_totales_memoria.png', 'comparativo_poc_vs_pandas.png', 'diagrama_arquitectura.png'):
    display(Image(filename=str(cfg.dir_informes / f), width=1000))
'''),
        md('''
## 4. Carpeta única del proyecto en Drive

Cada informe se copia a la carpeta de su actividad. `QUE_SE_PIDE.md` relaciona cada tarea de la guía con sus
archivos (si una tarea usa un archivo de otra carpeta, se indica su ruta en lugar de duplicarlo) y `LEEME.md`
resume el contenido y cómo ejecutar.
'''),
        code('''
from emergencias123.reportes.entregables import construir
estados = construir(cfg.dir_base, cfg.dir_informes)
for carpeta, estado in estados.items():
    print(f'{carpeta}: {estado}')
def arbol(ruta, nivel=0, max_nivel=2):
    for p in sorted(ruta.iterdir()):
        if p.name.startswith('.'):
            continue
        print('    ' * nivel + p.name + ('/' if p.is_dir() else ''))
        if p.is_dir() and nivel < max_nivel and p.name not in ('parquet',):
            arbol(p, nivel + 1, max_nivel)
arbol(cfg.dir_base)
'''),
    ]))


def main():
    destino = RAIZ / 'notebooks'
    destino.mkdir(exist_ok=True)
    for nombre, nb in ((NB_ANALISIS, analisis()), (NB_INFORMES, informes())):
        nbf.validate(nb)
        nbf.write(nb, destino / nombre)
        print('Escrito', destino / nombre, f'({len(nb.cells)} celdas)')


if __name__ == '__main__':
    main()
