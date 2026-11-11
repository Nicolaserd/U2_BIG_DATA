"""Construye los 4 notebooks del proyecto U2 (uno por tarea práctica de la guía).

Decisión del usuario (2026-11-10): los notebooks se guían por los del curso (carpeta Formatos: 02 SparkSession,
03 sintaxis y optimización, 04 formatos y ETL) y solo muestran el proceso, con todo el código a la vista. No generan
Word, Excel ni reportes: eso se prepara aparte (scripts/preparar_entregables.py) desde las mediciones que dejan en Drive.

    01_T1.1_Benchmark.ipynb                 measure_performance() sobre Pandas, Polars y PySpark
    02_T1.2_Matriz_de_decision.ipynb        matriz ponderada 30/25/20/15/10 desde el benchmark
    03_T2.2_PoC_PySpark.ipynb               pipeline robusto en PySpark (Drive -> validación -> Parquet + log)
    04_T2.4_Metricas_y_escalabilidad.ipynb  3 ejecuciones del PoC vs Pandas y escalabilidad

Uso: .venv/Scripts/python.exe scripts/construir_notebooks.py
"""
from pathlib import Path

import nbformat as nbf

RAIZ = Path(__file__).resolve().parents[1]
NB = {
    '1.1': '01_T1.1_Benchmark.ipynb',
    '1.2': '02_T1.2_Matriz_de_decision.ipynb',
    '2.2': '03_T2.2_PoC_PySpark.ipynb',
    '2.4': '04_T2.4_Metricas_y_escalabilidad.ipynb',
}


def md(texto):
    return nbf.v4.new_markdown_cell(texto.strip('\n'))


def code(texto):
    return nbf.v4.new_code_cell(texto.strip('\n'))


def notebook(celdas):
    nb = nbf.v4.new_notebook()
    nb.cells = celdas
    nb.metadata = {'kernelspec': {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'},
                   'language_info': {'name': 'python'}, 'colab': {'provenance': []}}
    return nb


def cabecera(tarea, titulo, actividad, objetivos, prerrequisitos, tiempo):
    obj = '\n'.join(f'- {o}' for o in objetivos)
    pre = '\n'.join(f'- {p}' for p in prerrequisitos)
    return md(f'''
# Tarea {tarea} · {titulo}

**Curso:** Herramientas de Big Data · Saber 2: Procesamiento distribuido
**Proyecto:** Emergencias de la Línea 123 de Bogotá (julio, agosto y septiembre de 2026)
**Actividad:** {actividad}

**Objetivos**
{obj}

**Prerrequisitos**
{pre}

**Tiempo estimado de ejecución:** {tiempo} (Colab gratuito, solo CPU)

**Dataset:** «Llamadas de urgencias y emergencias que ingresan a través de la línea 123», Secretaría Distrital de
Salud, portal Datos Abiertos Bogotá (CC BY 4.0). Tres CSV mensuales (27 434 registros, separador `;`).
''')


# ============================================================================ código común a los notebooks
ENTORNO = r'''
# 1.1 Conexión con Google Drive (los datos y los resultados viven en MyDrive/BigData_U2)
import os
from google.colab import drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')

# 1.2 Librerías
import time, json, inspect, threading, platform, gc, shutil
import numpy as np
import pandas as pd
import polars as pl
import psutil
import matplotlib.pyplot as plt
import pyspark
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType
import warnings
warnings.filterwarnings('ignore')
pd.set_option('display.max_columns', None)
pd.set_option('display.float_format', '{:.3f}'.format)

os.environ['TZ'] = 'America/Bogota'   # hora local en los logs
time.tzset()

# 1.3 Rutas de trabajo (una sola carpeta del proyecto en Drive)
BASE = '/content/drive/MyDrive/BigData_U2'
DATOS = f'{BASE}/datos'
RESULTADOS = f'{BASE}/resultados'
MEDICIONES = f'{RESULTADOS}/mediciones'
for ruta in (RESULTADOS, MEDICIONES, f'{RESULTADOS}/logs', f'{RESULTADOS}/parquet'):
    os.makedirs(ruta, exist_ok=True)

ARCHIVOS = ['llamadas123_julio_2026.csv', 'llamadaslinea123agosto2026.csv', 'llamadaslinea123Septiembre.csv']
RUTAS = [f'{DATOS}/{a}' for a in ARCHIVOS]
COLUMNAS = ['NUMERO_INCIDENTE', 'FECHA_INICIO_DESPLAZAMIENTO_MOVIL', 'CODIGO_LOCALIDAD', 'LOCALIDAD', 'EDAD',
            'UNIDAD', 'GENERO', 'TIPO_INCIDENTE', 'PRIORIDAD_FINAL', 'RECEPCION']
faltan = [a for a in ARCHIVOS if not os.path.exists(f'{DATOS}/{a}')]
assert not faltan, f'Sube a {DATOS} los archivos: {faltan}'

print('✓ Drive montado y librerías importadas')
print(f'   Python {platform.python_version()} · pandas {pd.__version__} · polars {pl.__version__} · '
      f'PySpark {pyspark.__version__}')
'''

MEDICION = r'''
# 1.4 Funciones de monitoreo (notebook 02 del curso: get_memory_info / print_memory_status)
def get_memory_info():
    """Obtiene información sobre el uso de memoria del sistema."""
    memory = psutil.virtual_memory()
    return {'total_gb': round(memory.total / 1024**3, 2), 'disponible_gb': round(memory.available / 1024**3, 2),
            'usado_gb': round(memory.used / 1024**3, 2), 'porcentaje': memory.percent}


def print_memory_status(titulo='Estado de memoria'):
    mem = get_memory_info()
    print(f"\n📊 {titulo}: {mem['usado_gb']} de {mem['total_gb']} GB usados ({mem['porcentaje']:.1f} %), "
          f"{mem['disponible_gb']} GB disponibles")


class MonitorMemoria:
    """Muestrea psutil.virtual_memory().percent cada 50 ms para capturar el PICO de memoria durante una operación."""

    def __init__(self, intervalo=0.05):
        self.intervalo, self.pico, self._activo = intervalo, 0.0, False

    def _muestrear(self):
        while self._activo:
            self.pico = max(self.pico, psutil.virtual_memory().percent)
            time.sleep(self.intervalo)

    def __enter__(self):
        self.pico, self._activo = psutil.virtual_memory().percent, True
        self._hilo = threading.Thread(target=self._muestrear, daemon=True)
        self._hilo.start()
        return self

    def __exit__(self, *exc):
        self._activo = False
        self._hilo.join()


def measure_performance(func, *args, **kwargs):
    """Mide tiempo y memoria de una operación (adaptación de measure_operation, notebook 04 del curso).

    - Tiempo: time.time() antes y después.
    - Memoria: psutil.virtual_memory() (porcentaje del sistema antes y pico durante la operación) y el cambio de
      RSS del proceso Python. El % del sistema incluye la JVM de Spark, que corre en otro proceso.
    """
    proceso = psutil.Process()
    rss_antes = proceso.memory_info().rss / 1024**2
    mem_antes = psutil.virtual_memory().percent
    with MonitorMemoria() as monitor:
        inicio = time.time()
        resultado = func(*args, **kwargs)
        fin = time.time()
    return {'result': resultado, 'time_seconds': fin - inicio, 'mem_pct_antes': mem_antes,
            'mem_pct_pico': monitor.pico, 'memory_delta_mb': proceso.memory_info().rss / 1024**2 - rss_antes}


print('✓ Funciones de medición configuradas')
print_memory_status('Memoria inicial')
'''

SPARK = r'''
# Helper del notebook 02 del curso (create_optimized_spark_session), con la zona horaria de Bogotá
def create_optimized_spark_session(app_name='Emergencias123', memory_fraction=0.7):
    """Crea una SparkSession optimizada para Google Colab."""
    num_cores = os.cpu_count()
    driver_memory = f"{max(1, int(get_memory_info()['disponible_gb'] * memory_fraction))}g"   # mínimo 1 GB
    return (SparkSession.builder
            .appName(app_name)
            .master(f'local[{num_cores}]')
            .config('spark.driver.memory', driver_memory)
            .config('spark.driver.maxResultSize', '2g')                           # configuración de la guía
            .config('spark.sql.adaptive.enabled', 'true')
            .config('spark.sql.adaptive.coalescePartitions.enabled', 'true')
            .config('spark.sql.adaptive.skewJoin.enabled', 'true')                # configuración de la guía
            .config('spark.sql.adaptive.advisoryPartitionSizeInBytes', '64MB')   # configuración de la guía
            .config('spark.serializer', 'org.apache.spark.serializer.KryoSerializer')
            .config('spark.sql.execution.arrow.pyspark.enabled', 'true')
            .config('spark.sql.session.timeZone', 'America/Bogota')
            .config('spark.ui.showConsoleProgress', 'false')
            .getOrCreate())


m = measure_performance(create_optimized_spark_session)
spark = m['result']
TIEMPO_INICIO_SPARK = m['time_seconds']
print(f"✅ SparkSession creada en {TIEMPO_INICIO_SPARK:.2f} s")
print(f"   - Master: {spark.sparkContext.master}")
print(f"   - Paralelismo por defecto: {spark.sparkContext.defaultParallelism}")
print(f"   - Driver memory: {spark.conf.get('spark.driver.memory')}")
print(f"   - AQE: {spark.conf.get('spark.sql.adaptive.enabled')} · skewJoin: "
      f"{spark.conf.get('spark.sql.adaptive.skewJoin.enabled')} · Serializador: Kryo · Arrow: activado")
print('\n💡 En Colab, Spark corre en modo local: driver y ejecutores comparten una JVM en un solo nodo (no es un clúster).')
'''

NORMALIZACION = r'''
# Normalización común a las tres herramientas: mayúsculas, sin tildes y con espacios simples.
# Necesaria porque los datos traen «USAQUÉN» con tilde y un tipo con doble espacio («AMESUI  - ...»).
CON_TILDE, SIN_TILDE = 'ÁÉÍÓÚÜÑ', 'AEIOUUN'
TABLA_TILDES = str.maketrans(CON_TILDE, SIN_TILDE)
LOCALIDADES = ['USAQUEN', 'CHAPINERO']
'''

CATALOGO = r'''
# Tabla de códigos de tipo de incidente: no existe una tabla oficial publicada, así que se DERIVA de los datos.
# Código = texto antes de « - » (normalizado); si el tipo no trae código, el texto completo hace de código.
tipos = pd.concat([pd.read_csv(r, sep=';', dtype=str, encoding='utf-8-sig', usecols=['TIPO_INCIDENTE'])
                   for r in RUTAS])['TIPO_INCIDENTE'].dropna().unique()
filas = []
for texto in sorted(tipos):
    norm = ' '.join(texto.upper().translate(TABLA_TILDES).split())
    codigo, _, descripcion = norm.partition(' - ')
    filas.append({'codigo_tipo': codigo.strip(), 'descripcion_tipo': (descripcion or codigo).strip(),
                  'codigo_explicito': bool(descripcion), 'fuente': 'derivado de los datos, no oficial'})
catalogo = pd.DataFrame(filas).drop_duplicates('codigo_tipo').reset_index(drop=True)
assert catalogo['codigo_tipo'].is_unique
RUTA_CATALOGO = f'{RESULTADOS}/catalogo_tipos_derivado.csv'
catalogo.to_csv(RUTA_CATALOGO, index=False)
print(f'Catálogo derivado (NO oficial): {len(catalogo)} códigos, '
      f"{int(catalogo['codigo_explicito'].sum())} con código explícito → {RUTA_CATALOGO}")
catalogo
'''

# ------------------------------------------------------------------------- pipeline del PoC (notebooks 03 y 04)
PIPELINE = r'''
ESQUEMA = StructType([StructField(c, StringType(), True) for c in COLUMNAS])   # esquema explícito: nada se infiere
MESES = {'julio': '2026-07', 'agosto': '2026-08', 'septiembre': '2026-09'}
OBSERVACIONES = ['fecha_invalida', 'fecha_fuera_de_mes', 'localidad_sin_dato', 'edad_nula', 'genero_nulo', 'recepcion_nula',
                 'recepcion_antes_de_desplazamiento']
# Edad homologada a años según UNIDAD (valores reales en los datos: Años, Meses, Dias, Horas; «N/A» ya es nulo)
FACTOR_EDAD = {'ANOS': 1.0, 'MESES': 1 / 12, 'DIAS': 1 / 365, 'HORAS': 1 / 8760}


def periodo_de(nombre_archivo):
    """Periodo (mes) del archivo de origen, tomado de su nombre."""
    nombre = nombre_archivo.lower()
    return next(p for mes, p in MESES.items() if mes in nombre)


def evaluar_controles(s):
    """Controles de calidad comunes a PySpark y Pandas a partir de los conteos `s` del pipeline.

    Devuelve la tabla de controles y la tasa de éxito = aprobados / evaluados × 100.
    """
    controles = [
        ('V01', 'Se leyeron los 3 archivos', s['archivos'] == 3, s['archivos']),
        ('V02', 'Columnas requeridas presentes', s['columnas_ok'], s['columnas_ok']),
        ('V03', 'Leídos = aceptados + duplicados exactos apartados', s['leidos'] == s['aceptados'] + s['duplicados'],
         f"{s['leidos']} = {s['aceptados']} + {s['duplicados']}"),
        ('V04', 'Fechas de desplazamiento válidas (0 sin convertir)', s['fechas_invalidas'] == 0, s['fechas_invalidas']),
        ('V05', 'Fechas dentro del mes del archivo (+1 día de tolerancia)', s['fuera_ventana'] == 0, s['fuera_ventana']),
        ('V06', 'Todos los códigos de tipo están en el catálogo', s['sin_catalogo'] == 0, s['sin_catalogo']),
        ('V07', 'El join no cambia el número de filas', s['filas_antes_join'] == s['filas_despues_join'],
         f"{s['filas_antes_join']} → {s['filas_despues_join']}"),
        ('V08', 'Cada localidad tiene un único código', s['localidades_inconsistentes'] == 0, s['localidades_inconsistentes']),
        ('V09', 'Edades dentro de 0–120', s['edades_fuera_rango'] == 0, s['edades_fuera_rango']),
        ('V10', 'Sin duplicados exactos remanentes', s['duplicados_remanentes'] == 0, s['duplicados_remanentes']),
        ('V11', 'El Parquet releído tiene las filas aceptadas', s['parquet_filas'] == s['aceptados'], s['parquet_filas']),
        ('V12', 'RECEPCION nunca es anterior al inicio del desplazamiento', s['recepcion_antes'] == 0, s['recepcion_antes']),
    ]
    tabla = pd.DataFrame(controles, columns=['control', 'descripcion', 'aprobado', 'valor'])
    return tabla, round(tabla['aprobado'].mean() * 100, 1)


class PipelineEmergencias:
    """Pipeline robusto en PySpark (adaptación de RobustPipeline del notebook 04 del curso).

    extract → transform → validate → load, con log en archivo .txt y métricas de cada etapa.
    Regla de limpieza del proyecto: solo se apartan los duplicados EXACTOS (100 % de los atributos iguales) y se
    guardan aparte. Los nulos y demás anomalías se conservan y se marcan en `observacion_calidad`. Nunca se imputa.
    """

    def __init__(self, spark, nombre, destino, log_file):
        self.spark, self.nombre, self.destino, self.log_file = spark, nombre, destino, log_file
        self.metrics = {}
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        open(log_file, 'w', encoding='utf-8').close()

    def log(self, mensaje, nivel='INFO', mostrar=True):
        entrada = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{nivel}] {mensaje}"
        if mostrar:
            print('   ' + entrada)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(entrada + '\n')

    def extract(self, rutas):
        inicio = time.time()
        df = (self.spark.read.csv(rutas, schema=ESQUEMA, sep=';', header=True, encoding='UTF-8')
              .withColumn('archivo_origen', F.col('_metadata.file_name')))
        periodo = F.lit(None).cast('string')
        for mes, p in MESES.items():
            periodo = F.when(F.lower(F.col('archivo_origen')).contains(mes), p).otherwise(periodo)
        df = df.withColumn('periodo', periodo).cache()
        self.metrics['leidos'] = df.count()
        self.metrics['archivos'] = df.select('archivo_origen').distinct().count()
        self.metrics['extract_s'] = time.time() - inicio
        self.log(f"Extract: {self.metrics['leidos']:,} registros de {self.metrics['archivos']} archivos")
        return df

    def transform(self, df, catalogo):
        inicio = time.time()
        # 1) Duplicados exactos (todas las columnas originales iguales): se conserva la primera copia
        ventana = Window.partitionBy(*COLUMNAS).orderBy('archivo_origen')
        df = df.withColumn('_n', F.row_number().over(ventana))
        duplicados = df.filter('_n > 1').drop('_n').cache()
        df = df.filter('_n = 1').drop('_n')
        # 2) Nulos: «N/A» es un valor faltante; se convierte en null (sin imputar)
        for c in ('EDAD', 'UNIDAD', 'GENERO'):
            df = df.withColumn(c, F.when(F.trim(F.col(c)) == 'N/A', None).otherwise(F.col(c)))
        # 3) Tipos y 4) estandarización de textos y códigos
        norm = lambda c: F.trim(F.regexp_replace(F.translate(F.upper(F.col(c)), CON_TILDE, SIN_TILDE), r'\s+', ' '))
        fmt = F.lit('yyyy-MM-dd HH:mm:ss')
        df = (df
              .withColumn('fecha_inicio', F.try_to_timestamp(F.col('FECHA_INICIO_DESPLAZAMIENTO_MOVIL'), fmt))
              .withColumn('fecha_recepcion', F.try_to_timestamp(F.col('RECEPCION'), fmt))
              .withColumn('cod_localidad', F.expr('try_cast(CODIGO_LOCALIDAD AS INT)'))
              .withColumn('edad_num', F.expr('try_cast(EDAD AS INT)'))
              .withColumn('localidad_norm', norm('LOCALIDAD'))
              .withColumn('codigo_tipo', F.trim(F.split(norm('TIPO_INCIDENTE'), ' - ').getItem(0)))
              .withColumn('prioridad', norm('PRIORIDAD_FINAL'))
              .withColumn('genero_norm', norm('GENERO')))
        # 4b) Edad en años según la unidad (meses, días y horas se convierten; una unidad desconocida queda nula)
        factor = F.lit(None).cast('double')
        for unidad, valor in FACTOR_EDAD.items():
            factor = F.when(norm('UNIDAD') == unidad, F.lit(valor)).otherwise(factor)
        # 4c) Minutos entre el inicio del desplazamiento y RECEPCION. No es el «tiempo de respuesta»: en los datos
        #     RECEPCION siempre es posterior al despacho (mediana ~3 h), así que se reporta con su nombre literal.
        df = (df
              .withColumn('edad_anios', F.round(F.col('edad_num') * factor, 2))
              .withColumn('min_desplazamiento_a_recepcion',
                          F.round((F.col('fecha_recepcion').cast('long') - F.col('fecha_inicio').cast('long')) / 60, 1)))
        # 5) Observaciones de calidad: se marcan, no se borran
        inicio_mes = F.to_timestamp(F.concat(F.col('periodo'), F.lit('-01')))
        fin_ventana = F.date_add(F.add_months(inicio_mes, 1), 1)
        condiciones = {
            'fecha_invalida': F.col('fecha_inicio').isNull(),
            'fecha_fuera_de_mes': (F.col('fecha_inicio') < inicio_mes) | (F.col('fecha_inicio') >= fin_ventana),
            'localidad_sin_dato': F.col('cod_localidad').isNull(),
            'edad_nula': F.col('edad_num').isNull(),
            'genero_nulo': F.col('genero_norm').isNull(),
            'recepcion_nula': F.col('fecha_recepcion').isNull(),
            'recepcion_antes_de_desplazamiento': F.col('min_desplazamiento_a_recepcion') < 0}
        obs = F.concat_ws('; ', *[F.when(condiciones[n], F.lit(n)) for n in OBSERVACIONES])
        df = df.withColumn('observacion_calidad', F.when(obs == '', 'OK').otherwise(obs))
        # 6) Enriquecimiento: broadcast join con la tabla de códigos (23 filas)
        self.metrics['filas_antes_join'] = df.count()
        df = df.join(F.broadcast(catalogo), on='codigo_tipo', how='left').cache()
        self.metrics['filas_despues_join'] = df.count()
        self.metrics['transform_s'] = time.time() - inicio
        self.log(f"Transform: {self.metrics['filas_despues_join']:,} aceptados; duplicados exactos apartados: "
                 f"{duplicados.count():,}")
        return df, duplicados

    def validate(self, df, duplicados):
        inicio = time.time()
        s = {k: self.metrics[k] for k in ('archivos', 'leidos', 'filas_antes_join', 'filas_despues_join')}
        s['aceptados'], s['duplicados'] = df.count(), duplicados.count()
        s['columnas_ok'] = all(c in df.columns for c in COLUMNAS)
        fila = df.agg(
            F.sum(F.col('fecha_inicio').isNull().cast('int')).alias('fechas_invalidas'),
            F.sum(F.col('observacion_calidad').contains('fecha_fuera_de_mes').cast('int')).alias('fuera_ventana'),
            F.sum(F.col('descripcion_tipo').isNull().cast('int')).alias('sin_catalogo'),
            F.sum(((F.col('edad_anios') < 0) | (F.col('edad_anios') > 120)).cast('int')).alias('edades_fuera_rango'),
            F.sum((F.col('min_desplazamiento_a_recepcion') < 0).cast('int')).alias('recepcion_antes'),
        ).first().asDict()
        s.update({k: int(v or 0) for k, v in fila.items()})
        s['localidades_inconsistentes'] = (df.groupBy('localidad_norm').agg(F.countDistinct('cod_localidad').alias('n'))
                                           .filter('n > 1').count())
        s['duplicados_remanentes'] = s['aceptados'] - df.select(*COLUMNAS).distinct().count()
        self.stats = s
        self.metrics['validate_s'] = time.time() - inicio
        self.log(f"Validate: controles calculados sobre {s['aceptados']:,} registros")
        return s

    def load(self, df, duplicados):
        inicio = time.time()
        # Particionamiento mes/localidad que pide la guía: periodo (mes del archivo) y código de localidad.
        # repartition por las mismas columnas → un archivo por carpeta (sin archivos sueltos de más).
        (df.repartition('periodo', 'cod_localidad')
           .write.mode('overwrite').partitionBy('periodo', 'cod_localidad').parquet(f'{self.destino}/detalle'))
        duplicados.write.mode('overwrite').parquet(f'{self.destino}/duplicados_eliminados')
        (df.groupBy('periodo', 'localidad_norm', 'codigo_tipo', 'descripcion_tipo').count()
           .write.mode('overwrite').parquet(f'{self.destino}/agregados'))
        self.stats['parquet_filas'] = self.spark.read.parquet(f'{self.destino}/detalle').count()
        self.metrics['load_s'] = time.time() - inicio
        self.log(f"Load: Parquet particionado por periodo/cod_localidad en {self.destino}")

    def run(self, rutas, catalogo):
        self.log('=' * 60)
        self.log(f'INICIANDO PIPELINE: {self.nombre}')
        inicio = time.time()
        try:
            df = self.extract(rutas)
            limpio, duplicados = self.transform(df, catalogo)
            self.validate(limpio, duplicados)
            self.load(limpio, duplicados)
            errores = 0
        except Exception as e:
            self.log(f'Error en el pipeline: {e}', 'ERROR')
            raise
        self.metrics['tiempo_total_s'] = time.time() - inicio
        controles, tasa = evaluar_controles(self.stats)
        self.metrics.update(aceptados=self.stats['aceptados'], duplicados=self.stats['duplicados'],
                            tasa_validaciones_pct=tasa, errores=errores,
                            controles_fallidos=int((~controles['aprobado']).sum()))
        self.log('-' * 60)
        self.log('REPORTE DE VALIDACIÓN')
        for _, c in controles.iterrows():
            self.log(f"{c['control']} {'OK   ' if c['aprobado'] else 'FALLA'} {c['descripcion']} (valor: {c['valor']})",
                     'INFO' if c['aprobado'] else 'WARNING', mostrar=False)
        self.log(f"Registros procesados: {self.metrics['leidos']:,} leídos · {self.metrics['aceptados']:,} aceptados · "
                 f"{self.metrics['duplicados']:,} duplicados exactos apartados")
        self.log(f"Errores de ejecución: {errores} · Tasa de éxito de validaciones: {tasa} % "
                 f"({len(controles) - self.metrics['controles_fallidos']}/{len(controles)} controles)")
        self.log(f"Tiempo de ejecución: {self.metrics['tiempo_total_s']:.2f} s "
                 f"(extract {self.metrics['extract_s']:.2f} · transform {self.metrics['transform_s']:.2f} · "
                 f"validate {self.metrics['validate_s']:.2f} · load {self.metrics['load_s']:.2f})")
        self.spark.catalog.clearCache()
        return controles


def leer_catalogo_spark(spark):
    return (spark.read.csv(f'{RESULTADOS}/catalogo_tipos_derivado.csv', header=True)
            .select('codigo_tipo', 'descripcion_tipo'))


print('✓ PipelineEmergencias definido')
'''

PIPELINE_PANDAS = r'''
def pipeline_pandas(rutas, destino, catalogo_pd):
    """El MISMO alcance del PoC en Pandas (mismas reglas, controles y salidas) para comparar en igualdad."""
    inicio = time.time()
    partes = []
    for r in rutas:
        d = pd.read_csv(r, sep=';', dtype=str, encoding='utf-8-sig', keep_default_na=False, na_values=[''])
        d['archivo_origen'] = os.path.basename(r)
        partes.append(d)
    df = pd.concat(partes, ignore_index=True)
    df['periodo'] = df['archivo_origen'].map(periodo_de)
    s = {'archivos': df['archivo_origen'].nunique(), 'leidos': len(df)}
    es_dup = df.duplicated(subset=COLUMNAS, keep='first')
    duplicados, df = df[es_dup], df[~es_dup].copy()
    for c in ('EDAD', 'UNIDAD', 'GENERO'):
        df[c] = df[c].where(df[c].str.strip() != 'N/A')
    norm = lambda serie: serie.str.upper().str.translate(TABLA_TILDES).str.replace(r'\s+', ' ', regex=True).str.strip()
    df['fecha_inicio'] = pd.to_datetime(df['FECHA_INICIO_DESPLAZAMIENTO_MOVIL'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['fecha_recepcion'] = pd.to_datetime(df['RECEPCION'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['cod_localidad'] = pd.to_numeric(df['CODIGO_LOCALIDAD'], errors='coerce').astype('Int64')
    df['edad_num'] = pd.to_numeric(df['EDAD'], errors='coerce').astype('Int64')
    df['localidad_norm'] = norm(df['LOCALIDAD'])
    df['codigo_tipo'] = norm(df['TIPO_INCIDENTE']).str.split(' - ', n=1).str[0].str.strip()
    df['prioridad'] = norm(df['PRIORIDAD_FINAL'])
    df['genero_norm'] = norm(df['GENERO'])
    df['edad_anios'] = (df['edad_num'].astype('float') * norm(df['UNIDAD']).map(FACTOR_EDAD)).round(2)
    df['min_desplazamiento_a_recepcion'] = ((df['fecha_recepcion'] - df['fecha_inicio']).dt.total_seconds() / 60).round(1)
    inicio_mes = pd.to_datetime(df['periodo'] + '-01')
    fin_ventana = inicio_mes + pd.DateOffset(months=1) + pd.Timedelta(days=1)
    condiciones = {
        'fecha_invalida': df['fecha_inicio'].isna(),
        'fecha_fuera_de_mes': (df['fecha_inicio'] < inicio_mes) | (df['fecha_inicio'] >= fin_ventana),
        'localidad_sin_dato': df['cod_localidad'].isna(),
        'edad_nula': df['edad_num'].isna(),
        'genero_nulo': df['genero_norm'].isna(),
        'recepcion_nula': df['fecha_recepcion'].isna(),
        'recepcion_antes_de_desplazamiento': df['min_desplazamiento_a_recepcion'] < 0}
    obs = pd.Series('', index=df.index)
    for n in OBSERVACIONES:
        obs = obs + np.where(condiciones[n], n + '; ', '')
    obs = obs.str.rstrip('; ')
    df['observacion_calidad'] = obs.where(obs != '', 'OK')
    s['filas_antes_join'] = len(df)
    df = df.merge(catalogo_pd, on='codigo_tipo', how='left', validate='m:1')
    s['filas_despues_join'] = len(df)
    s['aceptados'], s['duplicados'] = len(df), len(duplicados)
    s['columnas_ok'] = all(c in df.columns for c in COLUMNAS)
    s['fechas_invalidas'] = int(df['fecha_inicio'].isna().sum())
    s['fuera_ventana'] = int(df['observacion_calidad'].str.contains('fecha_fuera_de_mes').sum())
    s['sin_catalogo'] = int(df['descripcion_tipo'].isna().sum())
    s['edades_fuera_rango'] = int(((df['edad_anios'] < 0) | (df['edad_anios'] > 120)).fillna(False).sum())
    s['recepcion_antes'] = int((df['min_desplazamiento_a_recepcion'] < 0).sum())
    s['localidades_inconsistentes'] = int((df.groupby('localidad_norm')['cod_localidad'].nunique() > 1).sum())
    s['duplicados_remanentes'] = int(df.duplicated(subset=COLUMNAS).sum())
    shutil.rmtree(destino, ignore_errors=True)
    os.makedirs(destino, exist_ok=True)
    # La clave de partición va como texto: pyarrow no relee una partición Int64 con nulos (la fila SIN_D)
    (df.assign(cod_localidad=df['cod_localidad'].astype('string'))
       .to_parquet(f'{destino}/detalle', partition_cols=['periodo', 'cod_localidad'], index=False))
    duplicados.to_parquet(f'{destino}/duplicados_eliminados.parquet', index=False)
    (df.groupby(['periodo', 'localidad_norm', 'codigo_tipo', 'descripcion_tipo'], dropna=False).size()
       .reset_index(name='count').to_parquet(f'{destino}/agregados.parquet', index=False))
    s['parquet_filas'] = len(pd.read_parquet(f'{destino}/detalle', columns=['NUMERO_INCIDENTE']))
    controles, tasa = evaluar_controles(s)
    return {'leidos': s['leidos'], 'aceptados': s['aceptados'], 'duplicados': s['duplicados'],
            'tiempo_total_s': time.time() - inicio, 'tasa_validaciones_pct': tasa, 'errores': 0,
            'controles_fallidos': int((~controles['aprobado']).sum())}


catalogo_pd = pd.read_csv(f'{RESULTADOS}/catalogo_tipos_derivado.csv', dtype=str)[['codigo_tipo', 'descripcion_tipo']]
print('✓ pipeline_pandas definido (mismo alcance que el PoC)')
'''


# ============================================================================ 01 · tarea 1.1
def nb_11():
    return notebook([
        cabecera('1.1', 'Benchmark comparativo: Pandas vs Polars vs PySpark', 'Actividad 1 · Fase 1 · Investigación',
                 ['Medir con `measure_performance()` el tiempo y la memoria (`psutil.virtual_memory()`) de Pandas, '
                  'Polars y PySpark sobre los mismos 3 archivos mensuales.',
                  'Comparar cinco operaciones: carga y combinación de los 3 CSV, filtrado de USAQUÉN y CHAPINERO, '
                  'agregación por tipo de incidente, join con la tabla de códigos y exportación a Parquet.',
                  'Documentar la complejidad del código (líneas por operación) y comprobar que las tres herramientas '
                  'llegan al mismo resultado.'],
                 ['Los 3 CSV en `MyDrive/BigData_U2/datos/`.',
                  'Notebooks del curso 02 (SparkSession), 03 (sintaxis) y 04 (formatos y `measure_operation`).'],
                 '~6 minutos'),
        md('''
## 1. Configuración del entorno

Igual que en los notebooks del curso: se monta Drive, se importan las librerías y se definen las funciones de
monitoreo. `measure_performance()` es la adaptación de `measure_operation()` (notebook 04 del curso) que pide la guía:
mide el tiempo con `time.time()` y la memoria con `psutil.virtual_memory()`; además registra el **pico** de memoria
con un muestreo cada 50 ms, porque Spark usa la memoria en otro proceso (la JVM) y solo se ve en el % del sistema.
'''),
        code(ENTORNO),
        code(MEDICION),
        md('''
## 2. Datos de entrada

Tres meses consecutivos de llamadas a la Línea 123. Todos los campos se leen como texto, para que las tres
herramientas partan exactamente de lo mismo.
'''),
        code(r'''
resumen_archivos = pd.DataFrame([
    {'archivo': a, 'tamaño_MB': round(os.path.getsize(r) / 1024**2, 2),
     'registros': len(pd.read_csv(r, sep=';', dtype=str, encoding='utf-8-sig', usecols=['NUMERO_INCIDENTE']))}
    for a, r in zip(ARCHIVOS, RUTAS)])
print(f"Total: {resumen_archivos['registros'].sum():,} registros en {resumen_archivos['tamaño_MB'].sum():.2f} MB")
resumen_archivos
'''),
        md('''
## 3. SparkSession optimizada para Colab

Se usa el helper `create_optimized_spark_session()` del notebook 02 del curso: todos los núcleos (`local[*]`), 70 % de
la memoria disponible para el driver, ejecución adaptativa (AQE), serializador Kryo y Arrow. El tiempo de arranque de
la JVM se mide aparte, porque es un costo fijo de PySpark que Pandas y Polars no tienen.
'''),
        code(SPARK),
        md('''
## 4. Tabla de códigos de tipo de incidente

La operación de join necesita una tabla de códigos. Como no hay una tabla oficial publicada, se **deriva de los datos**
y se rotula como **no oficial**. Se guarda en Drive para reutilizarla en el PoC.
'''),
        code(NORMALIZACION + CATALOGO),
        md('''
## 5. Las cinco operaciones en cada herramienta

La misma lógica en las tres. En el filtrado se crean dos columnas: `localidad_norm` (sin tildes, para encontrar
«USAQUÉN») y `codigo_tipo` (el código antes de « - »), que usan la agregación y el join.

**Evaluación perezosa (notebook 02 del curso).** PySpark solo define un plan hasta que llega una *acción*. Para medir
cada operación por separado, después de cada transformación se ejecuta `cache()` + `count()` (función
`materializar`); sin eso, el filtrado «tardaría» 0 s y todo el costo aparecería en la exportación.
'''),
        code(r'''
# ---------------- PANDAS
def pandas_carga(rutas):
    return pd.concat([pd.read_csv(r, sep=';', dtype=str, encoding='utf-8-sig', keep_default_na=False, na_values=[''])
                      for r in rutas], ignore_index=True)


def pandas_filtrado(df):
    norm = lambda s: s.str.upper().str.translate(TABLA_TILDES).str.replace(r'\s+', ' ', regex=True).str.strip()
    df = df.assign(localidad_norm=norm(df['LOCALIDAD']),
                   codigo_tipo=norm(df['TIPO_INCIDENTE']).str.split(' - ', n=1).str[0].str.strip())
    return df[df['localidad_norm'].isin(LOCALIDADES)]


def pandas_agregacion(df):
    conteo = df.groupby('codigo_tipo').size().reset_index(name='conteo')
    return conteo.sort_values(['conteo', 'codigo_tipo'], ascending=[False, True])


def pandas_join(df, catalogo):
    return df.merge(catalogo, on='codigo_tipo', how='left', validate='m:1')


def pandas_exportacion(df, ruta):
    df.to_parquet(ruta, index=False)


# ---------------- POLARS
def polars_carga(rutas):
    return pl.concat([pl.read_csv(r, separator=';', infer_schema=False) for r in rutas])


def polars_filtrado(df):
    norm = lambda c: (pl.col(c).str.to_uppercase().str.replace_many(list(CON_TILDE), list(SIN_TILDE))
                      .str.replace_all(r'\s+', ' ').str.strip_chars())
    df = df.with_columns(norm('LOCALIDAD').alias('localidad_norm'),
                         norm('TIPO_INCIDENTE').str.split(' - ').list.first().str.strip_chars().alias('codigo_tipo'))
    return df.filter(pl.col('localidad_norm').is_in(LOCALIDADES))


def polars_agregacion(df):
    conteo = df.group_by('codigo_tipo').agg(pl.len().alias('conteo'))
    return conteo.sort(['conteo', 'codigo_tipo'], descending=[True, False])


def polars_join(df, catalogo):
    return df.join(catalogo, on='codigo_tipo', how='left')


def polars_exportacion(df, ruta):
    df.write_parquet(ruta)


# ---------------- PYSPARK
def spark_carga(rutas):
    return spark.read.csv(rutas, schema=StructType([StructField(c, StringType(), True) for c in COLUMNAS]),
                          sep=';', header=True, encoding='UTF-8')


def spark_filtrado(df):
    norm = lambda c: F.trim(F.regexp_replace(F.translate(F.upper(F.col(c)), CON_TILDE, SIN_TILDE), r'\s+', ' '))
    df = (df.withColumn('localidad_norm', norm('LOCALIDAD'))
            .withColumn('codigo_tipo', F.trim(F.split(norm('TIPO_INCIDENTE'), ' - ').getItem(0))))
    return df.filter(F.col('localidad_norm').isin(LOCALIDADES))


def spark_agregacion(df):
    conteo = df.groupBy('codigo_tipo').agg(F.count('*').alias('conteo'))
    return conteo.orderBy(F.desc('conteo'), F.asc('codigo_tipo'))


def spark_join(df, catalogo):
    return df.join(F.broadcast(catalogo), on='codigo_tipo', how='left')


def spark_exportacion(df, ruta):
    df.write.mode('overwrite').parquet(ruta)


def materializar(df):
    """Acción que obliga a Spark a ejecutar el plan (cache + count) para poder medir la operación."""
    df = df.cache()
    df.count()
    return df


# Tabla de códigos en el formato de cada herramienta (se prepara antes de medir)
cat_pd = catalogo[['codigo_tipo', 'descripcion_tipo']]
cat_pl = pl.from_pandas(cat_pd)
cat_sp = spark.createDataFrame(cat_pd)
print('✓ Operaciones definidas para Pandas, Polars y PySpark')
'''),
        md('''
## 6. Ejecución del benchmark con `measure_performance()`

- **1 ronda de calentamiento** (se descarta: carga librerías y calienta la JVM) y **3 rondas medidas**.
- El **orden de las herramientas rota** en cada ronda, para que ninguna se beneficie siempre de ir primero o último.
- Entre herramientas se liberan los DataFrames (`gc.collect()`, `clearCache()`), para no sumar memoria ajena.
- La exportación escribe en el disco local del VM (`/content`), para que la latencia de Drive no distorsione la medición.
'''),
        code(r'''
SALIDA = '/content/benchmark_parquet'
os.makedirs(SALIDA, exist_ok=True)
OPERACIONES = {
    'pandas': {'carga': pandas_carga, 'filtrado': pandas_filtrado, 'agregacion': pandas_agregacion,
               'join': lambda d: pandas_join(d, cat_pd), 'exportacion': pandas_exportacion},
    'polars': {'carga': polars_carga, 'filtrado': polars_filtrado, 'agregacion': polars_agregacion,
               'join': lambda d: polars_join(d, cat_pl), 'exportacion': polars_exportacion},
    'spark': {'carga': lambda r: materializar(spark_carga(r)), 'filtrado': lambda d: materializar(spark_filtrado(d)),
              'agregacion': lambda d: materializar(spark_agregacion(d)),
              'join': lambda d: materializar(spark_join(d, cat_sp)), 'exportacion': spark_exportacion},
}
REPETICIONES = 3
mediciones, resultados = [], {}


def correr(herramienta, ronda):
    f = OPERACIONES[herramienta]

    def medir(operacion, funcion, *args):
        m = measure_performance(funcion, *args)
        mediciones.append({'herramienta': herramienta, 'ronda': ronda, 'operacion': operacion,
                           'segundos': m['time_seconds'], 'mem_pct_antes': m['mem_pct_antes'],
                           'mem_pct_pico': m['mem_pct_pico'], 'memoria_delta_mb': m['memory_delta_mb']})
        return m['result']

    df = medir('carga', f['carga'], RUTAS)
    filtrado = medir('filtrado', f['filtrado'], df)
    conteo = medir('agregacion', f['agregacion'], filtrado)
    unido = medir('join', f['join'], filtrado)
    medir('exportacion', f['exportacion'], unido, f'{SALIDA}/{herramienta}.parquet')
    return conteo, unido


HERRAMIENTAS = ['pandas', 'polars', 'spark']
for ronda in range(REPETICIONES + 1):
    orden = HERRAMIENTAS[ronda % 3:] + HERRAMIENTAS[:ronda % 3]
    etiqueta = 'calentamiento' if ronda == 0 else f'ronda {ronda}'
    for h in orden:
        conteo, unido = correr(h, ronda)
        if ronda == REPETICIONES:   # el resultado de la última ronda se usa para comprobar la equivalencia
            resultados[h] = (conteo, unido)
        del conteo, unido
        gc.collect()
        if ronda < REPETICIONES:
            spark.catalog.clearCache()
    print(f'✓ {etiqueta}: ' + ' → '.join(orden))

bench = pd.DataFrame(mediciones)
medidas = bench[bench['ronda'] > 0]
print(f'\n{len(medidas)} mediciones válidas ({REPETICIONES} rondas × 3 herramientas × 5 operaciones)')
'''),
        md('## 7. Resultados\n\n### 7.1 Tiempo por operación (media de las 3 rondas, en segundos)'),
        code(r'''
por_operacion = medidas.pivot_table(index='operacion', columns='herramienta', values='segundos', aggfunc='mean')
por_operacion = por_operacion.loc[['carga', 'filtrado', 'agregacion', 'join', 'exportacion'], HERRAMIENTAS]
por_operacion.loc['TOTAL'] = por_operacion.sum()
por_operacion
'''),
        md('### 7.2 Tiempo total y memoria por herramienta'),
        code(r'''
por_ronda = medidas.groupby(['herramienta', 'ronda']).agg(
    tiempo_total_s=('segundos', 'sum'), mem_pct_pico=('mem_pct_pico', 'max'), mem_pct_inicio=('mem_pct_antes', 'first'))
por_ronda['mem_incremento_pp'] = por_ronda['mem_pct_pico'] - por_ronda['mem_pct_inicio']
totales = por_ronda.groupby('herramienta').agg(
    tiempo_total_s=('tiempo_total_s', 'mean'), tiempo_desv_s=('tiempo_total_s', 'std'),
    mem_pct_pico=('mem_pct_pico', 'mean'), mem_incremento_pp=('mem_incremento_pp', 'mean')).loc[HERRAMIENTAS]
totales['veces_vs_mas_rapida'] = totales['tiempo_total_s'] / totales['tiempo_total_s'].min()
print(f'Arranque de la SparkSession (costo fijo, no incluido en los totales): {TIEMPO_INICIO_SPARK:.2f} s')
totales
'''),
        md('### 7.3 Visualización'),
        code(r'''
colores = {'pandas': '#4C78A8', 'polars': '#54A24B', 'spark': '#F58518'}
fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(17, 4.8))
x = np.arange(5)
for i, h in enumerate(HERRAMIENTAS):
    ax1.bar(x + (i - 1) * 0.27, por_operacion[h].iloc[:5], 0.27, label=h.capitalize(), color=colores[h])
ax1.set_xticks(x)
ax1.set_xticklabels(por_operacion.index[:5])
ax1.set_ylabel('Tiempo (s)')
ax1.set_title('Tiempo por operación')
ax1.legend()
ax2.bar(HERRAMIENTAS, totales['tiempo_total_s'], yerr=totales['tiempo_desv_s'], capsize=5,
        color=[colores[h] for h in HERRAMIENTAS])
ax2.set_ylabel('Tiempo (s)')
ax2.set_title('Tiempo total (media ± desv. estándar)')
ax3.bar(HERRAMIENTAS, totales['mem_incremento_pp'], color=[colores[h] for h in HERRAMIENTAS])
ax3.set_ylabel('Puntos porcentuales')
ax3.set_title('Incremento pico de memoria del sistema')
for ax in (ax1, ax2, ax3):
    ax.grid(True, alpha=0.3)
plt.suptitle('Benchmark Pandas vs Polars vs PySpark · Emergencias 123 (jul–sep 2026)', fontweight='bold')
plt.tight_layout()
plt.show()
'''),
        md('''
## 8. ¿Las tres herramientas producen el mismo resultado?

Un benchmark solo es válido si las herramientas hacen lo mismo. Se compara el conteo por tipo de incidente, el
número de filas después del join y las filas sin descripción (deben ser 0).
'''),
        code(r'''
def a_pandas(obj):
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, pl.DataFrame):
        return obj.to_pandas()
    return obj.toPandas()


equivalencia = {}
for h, (conteo, unido) in resultados.items():
    c, u = a_pandas(conteo), a_pandas(unido)
    equivalencia[h] = {'filas_filtradas': int(len(u)),
                       'conteo_por_tipo': {k: int(v) for k, v in zip(c['codigo_tipo'], c['conteo'])},
                       'sin_descripcion': int(u['descripcion_tipo'].isna().sum())}
iguales = all(equivalencia[h]['conteo_por_tipo'] == equivalencia['pandas']['conteo_por_tipo'] and
              equivalencia[h]['filas_filtradas'] == equivalencia['pandas']['filas_filtradas'] for h in HERRAMIENTAS)
display(pd.DataFrame({h: {'filas USAQUÉN + CHAPINERO': v['filas_filtradas'], 'tipos distintos': len(v['conteo_por_tipo']),
                          'filas sin descripción': v['sin_descripcion']} for h, v in equivalencia.items()}))
print('✅ Las tres herramientas producen el mismo resultado' if iguales else '❌ Los resultados difieren')
print('\nTipos de incidente más frecuentes en USAQUÉN y CHAPINERO (PySpark):')
display(a_pandas(resultados['spark'][0]).head(10))
spark.catalog.clearCache()
'''),
        md('''
## 9. Complejidad del código: líneas por operación

Se cuentan las líneas de código de cada función (sin la línea `def`, sin líneas vacías ni comentarios). Es un
indicador aproximado de facilidad de uso, que alimenta la matriz de decisión (tarea 1.2).
'''),
        code(r'''
def contar_lineas(funcion):
    lineas = inspect.getsource(funcion).splitlines()[1:]
    return sum(1 for l in lineas if l.strip() and not l.strip().startswith('#'))


FUNCIONES = {'pandas': [pandas_carga, pandas_filtrado, pandas_agregacion, pandas_join, pandas_exportacion],
             'polars': [polars_carga, polars_filtrado, polars_agregacion, polars_join, polars_exportacion],
             'spark': [spark_carga, spark_filtrado, spark_agregacion, spark_join, spark_exportacion]}
loc = pd.DataFrame({h: [contar_lineas(f) for f in fs] for h, fs in FUNCIONES.items()},
                   index=['carga', 'filtrado', 'agregacion', 'join', 'exportacion'])
loc.loc['TOTAL'] = loc.sum()
print('Nota: en PySpark, materializar() solo sirve para poder medir y no se cuenta.')
loc
'''),
        md('## 10. Guardar las mediciones en Drive\n\nSon la fuente de la matriz de decisión (tarea 1.2) y de los informes.'),
        code(r'''
bench.to_csv(f'{MEDICIONES}/benchmark.csv', index=False)
loc.to_csv(f'{MEDICIONES}/loc_benchmark.csv')
with open(f'{MEDICIONES}/equivalencia_benchmark.json', 'w', encoding='utf-8') as f:
    json.dump({'iguales': iguales, **equivalencia}, f, indent=2, ensure_ascii=False)
entorno = {'python': platform.python_version(), 'pandas': pd.__version__, 'polars': pl.__version__,
           'pyspark': pyspark.__version__, 'vcpu': os.cpu_count(), 'ram_gb': get_memory_info()['total_gb'],
           'spark_driver_memory': spark.conf.get('spark.driver.memory'), 'inicio_spark_s': TIEMPO_INICIO_SPARK,
           'repeticiones': REPETICIONES, 'registros': int(resumen_archivos['registros'].sum()),
           'fecha': time.strftime('%Y-%m-%d %H:%M')}
with open(f'{MEDICIONES}/entorno_colab.json', 'w', encoding='utf-8') as f:
    json.dump(entorno, f, indent=2)
print('✓ Guardado en', MEDICIONES, '→', sorted(os.listdir(MEDICIONES)))
'''),
        md('## 11. Hallazgos'),
        code(r'''
rapida = totales['tiempo_total_s'].idxmin()
lenta = totales['tiempo_total_s'].idxmax()
print(f"• Con {resumen_archivos['registros'].sum():,} registros (~{resumen_archivos['tamaño_MB'].sum():.0f} MB), la más "
      f"rápida fue {rapida.capitalize()} ({totales.loc[rapida, 'tiempo_total_s']:.2f} s) y la más lenta "
      f"{lenta.capitalize()} ({totales.loc[lenta, 'tiempo_total_s']:.2f} s, "
      f"{totales.loc[lenta, 'veces_vs_mas_rapida']:.1f} veces más).")
print(f"• PySpark además paga {TIEMPO_INICIO_SPARK:.1f} s de arranque de la JVM, un costo fijo que con pocos datos pesa mucho.")
op_lenta = por_operacion.drop('TOTAL')['spark'].idxmax()
print(f"• La operación más costosa en PySpark fue «{op_lenta}» ({por_operacion.loc[op_lenta, 'spark']:.2f} s).")
print('• Líneas de código totales: ' + ', '.join(f"{h.capitalize()} {loc.loc['TOTAL', h]}" for h in HERRAMIENTAS) + '.')
print('• Los resultados de las tres herramientas son ' + ('idénticos.' if iguales else 'DISTINTOS: revisar.'))
'''),
        md('''
**Interpretación.** Con un volumen pequeño dominan los costos fijos de PySpark (JVM, planificación, serialización
entre Python y Java), así que Pandas y Polars ganan en tiempo, y así se reporta. La razón para usar PySpark es que
escala horizontalmente a un clúster cuando los datos dejan de caber en una sola máquina (ver la tarea 2.4).

**Limitaciones.** Colab es un único nodo (2 vCPU), así que Spark corre en modo local y no como clúster. El % de
memoria del sistema incluye otros procesos de Colab, y el muestreo cada 50 ms puede perder picos muy breves. Además,
las tres herramientas comparten el mismo proceso de Python: se liberan los objetos entre mediciones, pero la memoria
que el sistema operativo aún no recupera puede sumarse a la siguiente.
'''),
        code("spark.stop()\nprint('✓ SparkSession detenida')"),
    ])


# ============================================================================ 02 · tarea 1.2
def nb_12():
    return notebook([
        cabecera('1.2', 'Matriz de decisión tecnológica', 'Actividad 1 · Fase 1 · Investigación',
                 ['Definir criterios y pesos: rendimiento 30 %, facilidad de uso 25 %, escalabilidad 20 %, '
                  'recursos 15 %, curva de aprendizaje 10 %.',
                  'Puntuar de 1 a 5 cada herramienta a partir de las mediciones del benchmark (tarea 1.1).',
                  'Calcular el puntaje ponderado Σ(criterio × peso) y validarlo con el caso de uso.'],
                 ['`01_T1.1_Benchmark.ipynb` ejecutado (mediciones en `BigData_U2/resultados/mediciones/`).'],
                 '~1 minuto'),
        md('''
## 1. Lectura de las mediciones del benchmark

Solo se leen las mediciones guardadas por el notebook 01; aquí no se vuelve a medir.
'''),
        code(r'''
import os, json
import pandas as pd
import matplotlib.pyplot as plt
from google.colab import drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')

MEDICIONES = '/content/drive/MyDrive/BigData_U2/resultados/mediciones'
bench = pd.read_csv(f'{MEDICIONES}/benchmark.csv')
loc = pd.read_csv(f'{MEDICIONES}/loc_benchmark.csv', index_col=0)
medidas = bench[bench['ronda'] > 0]
por_ronda = medidas.groupby(['herramienta', 'ronda']).agg(
    tiempo_total_s=('segundos', 'sum'), mem_pct_pico=('mem_pct_pico', 'max'), mem_pct_inicio=('mem_pct_antes', 'first'))
por_ronda['mem_incremento_pp'] = por_ronda['mem_pct_pico'] - por_ronda['mem_pct_inicio']
HERRAMIENTAS = ['pandas', 'polars', 'spark']
insumos = por_ronda.groupby('herramienta')[['tiempo_total_s', 'mem_incremento_pp']].mean().loc[HERRAMIENTAS]
insumos['lineas_codigo'] = loc.loc['TOTAL', HERRAMIENTAS].astype(int)
insumos.round(3)
'''),
        md('''
## 2. Reglas de puntuación (1 = peor, 5 = mejor)

| Criterio | Peso | Cómo se puntúa |
|---|---:|---|
| Rendimiento | 30 % | Cuantitativo: tiempo total del benchmark. |
| Facilidad de uso | 25 % | Cuantitativo (líneas de código) con un ajuste cualitativo de −1 a +1. |
| Escalabilidad | 20 % | Cualitativo: 5 = multinodo nativo; 3 = un nodo multihilo; 2 = un nodo en memoria. |
| Recursos | 15 % | Cuantitativo: incremento pico de memoria del sistema (puntos porcentuales). |
| Curva de aprendizaje | 10 % | Cualitativo: 5 = API conocida; 4 = API nueva similar; 2 = conceptos de motor distribuido. |

Para los criterios cuantitativos se calcula `r = valor / mejor valor` y se asigna: `r ≤ 1,25 → 5`, `r ≤ 2 → 4`,
`r ≤ 4 → 3`, `r ≤ 8 → 2` y `r > 8 → 1`. En memoria, los incrementos menores de 0,1 puntos se toman como 0,1 para que
el cociente tenga sentido.
'''),
        code(r'''
def puntaje(valores):
    r = valores / valores.min()
    return r.apply(lambda x: 5 if x <= 1.25 else 4 if x <= 2 else 3 if x <= 4 else 2 if x <= 8 else 1)


AJUSTE_FACILIDAD = pd.Series({'pandas': 0, 'polars': 0, 'spark': -1})   # PySpark: SparkSession, JVM, evaluación perezosa
ESCALABILIDAD = pd.Series({'pandas': 2, 'polars': 3, 'spark': 5})
CURVA = pd.Series({'pandas': 5, 'polars': 4, 'spark': 2})
PESOS = pd.Series({'Rendimiento': 0.30, 'Facilidad de uso': 0.25, 'Escalabilidad': 0.20, 'Recursos': 0.15,
                   'Curva de aprendizaje': 0.10})

matriz = pd.DataFrame({
    'Rendimiento': puntaje(insumos['tiempo_total_s']),
    'Facilidad de uso': (puntaje(insumos['lineas_codigo']) + AJUSTE_FACILIDAD).clip(1, 5),
    'Escalabilidad': ESCALABILIDAD,
    'Recursos': puntaje(insumos['mem_incremento_pp'].clip(lower=0.1)),
    'Curva de aprendizaje': CURVA,
}).T[HERRAMIENTAS]
matriz.insert(0, 'Peso', PESOS)
matriz
'''),
        md('## 3. Puntaje ponderado'),
        code(r'''
ponderado = matriz[HERRAMIENTAS].mul(matriz['Peso'], axis=0).sum().round(2)
resultado = pd.DataFrame({'Puntaje ponderado': ponderado,
                          'Posición': ponderado.rank(ascending=False, method='min').astype(int)})
print(f"Suma de pesos: {matriz['Peso'].sum():.0%}")
display(resultado.sort_values('Posición'))

fig, ax = plt.subplots(figsize=(7, 3.5))
ax.barh([h.capitalize() for h in HERRAMIENTAS], ponderado[HERRAMIENTAS], color=['#4C78A8', '#54A24B', '#F58518'])
for i, v in enumerate(ponderado[HERRAMIENTAS]):
    ax.text(v + 0.03, i, f'{v:.2f}', va='center')
ax.set_xlim(0, 5)
ax.set_xlabel('Puntaje ponderado (1–5)')
ax.set_title('Matriz de decisión: puntaje ponderado')
ax.grid(True, axis='x', alpha=0.3)
plt.tight_layout()
plt.show()
'''),
        md('''
## 4. Validación con el caso de uso y restricciones de Colab

- **Caso de uso:** consolidar y validar mes a mes las llamadas de la Línea 123 (≈9 000 registros por mes) y dejar
  datos limpios en Parquet para análisis por localidad y tipo de incidente.
- **Restricciones de Colab gratuito:** ≈12 GB de RAM, 2 vCPU y sesiones de hasta 12 h. Con este volumen cualquier
  herramienta cabe en memoria; la diferencia aparece cuando el histórico crece (tarea 2.4).
- **Decisión:** la matriz muestra qué herramienta conviene con **este** volumen. PySpark es la herramienta
  **obligatoria** de la actividad y se justifica por su escalabilidad horizontal; si otra gana aquí, se reporta tal cual.
'''),
        code(r'''
matriz_json = {'pesos': PESOS.to_dict(),
               'puntajes': {c: {h: int(matriz.loc[c, h]) for h in HERRAMIENTAS} for c in PESOS.index},
               'ponderado': ponderado.to_dict(), 'insumos': insumos.round(4).to_dict()}
with open(f'{MEDICIONES}/matriz_decision.json', 'w', encoding='utf-8') as f:
    json.dump(matriz_json, f, indent=2, ensure_ascii=False)
mejor = ponderado.idxmax()
print(f"Mayor puntaje con este volumen: {mejor.capitalize()} ({ponderado[mejor]:.2f}). "
      f"PySpark: {ponderado['spark']:.2f}. Matriz guardada en {MEDICIONES}/matriz_decision.json")
'''),
    ])


# ============================================================================ 03 · tarea 2.2
def nb_22():
    return notebook([
        cabecera('2.2', 'Proof of Concept funcional en PySpark', 'Actividad 2 · Diseño de arquitectura y PoC (evaluativa)',
                 ['Configurar PySpark en Colab e ingerir los 3 CSV directamente desde Google Drive.',
                  'Limpiar nulos, convertir tipos y estandarizar códigos, sin borrar ni imputar registros (solo se '
                  'apartan los duplicados exactos).',
                  'Validar la calidad (conteos, rangos de fechas, consistencia de códigos), exportar a Parquet en Drive '
                  'y dejar un log de validación en .txt.'],
                 ['Los 3 CSV en `MyDrive/BigData_U2/datos/` y la tabla de códigos que deja el notebook 01.',
                  'Notebooks del curso 02 (SparkSession), 03 (explain, nulos, outliers, broadcast) y 04 (pipeline robusto).'],
                 '~3 minutos'),
        md('## 1. Configuración del entorno'),
        code(ENTORNO),
        code(MEDICION),
        md('## 2. SparkSession optimizada (notebook 02 del curso)'),
        code(SPARK),
        md('''
## 3. Diseño del pipeline

Se adapta el `RobustPipeline` del notebook 04 del curso a PySpark, con las etapas del ETL:

1. **Extract:** lectura de los 3 CSV desde Drive con **esquema explícito** (todo texto, nada se infiere) y columnas
   de procedencia (`archivo_origen`, `periodo`).
2. **Transform:** duplicados exactos apartados; `N/A` → nulo (sin imputar); fechas, edad y código de localidad a su
   tipo; textos y códigos estandarizados; **edad homologada a años** según `UNIDAD` (meses, días y horas);
   **minutos entre el inicio del desplazamiento y `RECEPCION`**; marca `observacion_calidad`; **broadcast join** con
   la tabla de códigos.
3. **Validate:** 12 controles de calidad. Tasa de éxito = controles aprobados / controles evaluados × 100.
   Las columnas originales se conservan tal cual; las convertidas van en columnas nuevas (`fecha_inicio`, `edad_num`,
   `edad_anios`, `cod_localidad`, `genero_norm`, …), porque Spark no distingue mayúsculas en los nombres de columna.
4. **Load:** Parquet en Drive particionado por **mes y localidad** (`periodo` / `cod_localidad`), como pide la guía,
   más los agregados y los duplicados apartados.

> **Sobre `RECEPCION`:** el diccionario de datos no define este campo. En los datos siempre es posterior al inicio del
> desplazamiento (mediana de unas 3 horas), así que **no** es el tiempo de respuesta a la llamada. Se reporta con su
> nombre literal (`min_desplazamiento_a_recepcion`) y no se usa como KPI de respuesta.

Cada etapa queda en el log `.txt` con sus registros, errores y tiempo.
'''),
        code(NORMALIZACION + PIPELINE),
        md('## 4. Ejecución del PoC'),
        code(r'''
if not os.path.exists(f'{RESULTADOS}/catalogo_tipos_derivado.csv'):
    raise FileNotFoundError('Ejecuta primero el notebook 01: crea la tabla de códigos derivada.')
catalogo_sp = leer_catalogo_spark(spark)
DESTINO = f'{RESULTADOS}/parquet/poc'
LOG = f'{RESULTADOS}/logs/validacion_poc.txt'

pipeline = PipelineEmergencias(spark, 'PoC_Emergencias123', DESTINO, LOG)
with MonitorMemoria() as monitor:
    controles = pipeline.run(RUTAS, catalogo_sp)
print(f"\n✅ PoC completado en {pipeline.metrics['tiempo_total_s']:.2f} s · memoria pico del sistema {monitor.pico:.1f} %")
'''),
        md('## 5. Resultados de la validación'),
        code(r'''
print(f"Tasa de éxito de validaciones: {pipeline.metrics['tasa_validaciones_pct']} %")
print(f"Registros válidos (aceptados / leídos): {pipeline.metrics['aceptados'] / pipeline.metrics['leidos'] * 100:.2f} %")
controles
'''),
        md('''
### 5.1 Log de validación (`resultados/logs/validacion_poc.txt`)

Es el entregable `.txt` que pide la guía: registros procesados, errores y tiempo de ejecución.
'''),
        code("print(open(LOG, encoding='utf-8').read())"),
        md('''
## 6. Lectura del Parquet en Drive

Se relee el Parquet desde Drive para comprobar el esquema y las particiones. Gracias al particionamiento por
mes y localidad, un filtro por mes o por localidad solo lee esas carpetas (*partition pruning*).
'''),
        code(r'''
detalle = spark.read.parquet(f'{DESTINO}/detalle')
detalle.printSchema()
carpetas = {p: sorted(d for d in os.listdir(f'{DESTINO}/detalle/{p}') if d.startswith('cod_localidad='))
            for p in sorted(os.listdir(f'{DESTINO}/detalle')) if p.startswith('periodo=')}
for p, locs in carpetas.items():
    print(f'{p}: {len(locs)} carpetas de localidad')
print(f'Total: {sum(map(len, carpetas.values()))} particiones mes/localidad')
detalle.groupBy('periodo').count().orderBy('periodo').show()
detalle.select('periodo', 'cod_localidad', 'localidad_norm', 'codigo_tipo', 'fecha_inicio', 'EDAD', 'UNIDAD',
               'edad_anios', 'min_desplazamiento_a_recepcion', 'observacion_calidad').show(5, truncate=False)
'''),
        md('''
### 6.1 Variables derivadas: edad en años y minutos hasta `RECEPCION`

La edad viene en distintas unidades (`Años`, `Meses`, `Dias`, `Horas`); se homologa a años para poder compararla.
La duración entre el inicio del desplazamiento y `RECEPCION` se describe tal como está, sin interpretarla como
tiempo de respuesta.
'''),
        code(r'''
detalle.groupBy('UNIDAD').agg(F.count('*').alias('registros'), F.min('edad_num').alias('edad_min'),
                              F.max('edad_num').alias('edad_max'), F.max('edad_anios').alias('max_en_anios')) \
       .orderBy(F.desc('registros')).show()
cuantiles = detalle.approxQuantile('min_desplazamiento_a_recepcion', [0.05, 0.25, 0.5, 0.75, 0.95], 0.001)
con_dato = detalle.filter(F.col('min_desplazamiento_a_recepcion').isNotNull()).count()
print(f'Minutos desplazamiento → RECEPCION ({con_dato:,} registros con ambas fechas):')
print('   p5 / p25 / mediana / p75 / p95 =', ' / '.join(f'{q:.1f}' for q in cuantiles))
'''),
        md('''
## 7. Datos faltantes y anomalías (notebook 03 del curso)

Se usan `analyze_nulls` y `detect_outliers_iqr` del curso. A diferencia del ejemplo del curso, aquí **no** se
eliminan ni se rellenan: la regla del proyecto es conservar los registros y marcarlos en `observacion_calidad`.
'''),
        code(r'''
def analyze_nulls(df):
    """Analiza valores nulos en cada columna (notebook 03 del curso)."""
    total_rows = df.count()
    filas = [{'columna': c, 'nulos': df.filter(F.col(c).isNull()).count()} for c in df.columns]
    resultado = pd.DataFrame(filas)
    resultado['porcentaje'] = (resultado['nulos'] / total_rows * 100).round(2)
    return resultado[resultado['nulos'] > 0]


def detect_outliers_iqr(df, column):
    """Detecta outliers con el método IQR (notebook 03 del curso); aquí solo se marcan."""
    q1, q3 = df.filter(F.col(column).isNotNull()).approxQuantile(column, [0.25, 0.75], 0.01)
    iqr = q3 - q1
    inferior, superior = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    marcado = df.withColumn(f'{column}_outlier', (F.col(column) < inferior) | (F.col(column) > superior))
    return marcado, inferior, superior


display(analyze_nulls(detalle.select(*COLUMNAS, 'fecha_inicio', 'edad_num', 'edad_anios', 'cod_localidad',
                                     'genero_norm')))
marcado, inferior, superior = detect_outliers_iqr(detalle, 'edad_anios')
print(f'Edad (años): límites IQR [{inferior:.1f}, {superior:.1f}] → '
      f"{marcado.filter(F.col('edad_anios_outlier')).count()} valores atípicos (se conservan)")
print('\nObservaciones de calidad más frecuentes:')
detalle.groupBy('observacion_calidad').count().orderBy(F.desc('count')).show(8, truncate=False)
'''),
        md('''
## 8. Plan de ejecución y optimizaciones (notebook 03 del curso)

`explain()` muestra cómo ejecuta Spark una consulta. Se verifica la **poda de particiones** y el filtro empujado a la
lectura del Parquet (*predicate pushdown*), y que el join con la tabla de códigos sea un **broadcast join** (la tabla
pequeña se envía completa a cada tarea, sin *shuffle*).
'''),
        code(r'''
consulta = (spark.read.parquet(f'{DESTINO}/detalle')
            .filter((F.col('periodo') == '2026-08') & (F.col('cod_localidad') == 1))   # agosto · USAQUÉN
            .groupBy('codigo_tipo').count())
consulta.explain(mode='formatted')
plan_join = (spark.read.csv(RUTAS, schema=ESQUEMA, sep=';', header=True)
             .withColumn('codigo_tipo', F.trim(F.split(F.col('TIPO_INCIDENTE'), ' - ').getItem(0)))
             .join(F.broadcast(catalogo_sp), 'codigo_tipo', 'left'))
plan_join.explain()
'''),
        md('''
## 9. Conclusiones del PoC

- El pipeline ingiere los 3 CSV desde Drive, aplica limpieza y estandarización sin borrar datos (solo aparta los
  duplicados exactos), valida la calidad con 12 controles y deja en Drive el Parquet particionado por mes y localidad
  junto con su log.
- Homologa la edad a años y calcula los minutos entre el despacho y `RECEPCION`, sin presentarlos como tiempo de
  respuesta porque el significado de `RECEPCION` no está documentado.
- Las métricas de rendimiento (3 ejecuciones frente a Pandas) y la escalabilidad están en el notebook 04 (tarea 2.4).
'''),
        code(r'''
with open(f'{MEDICIONES}/poc_validacion.json', 'w', encoding='utf-8') as f:
    json.dump({'metricas': pipeline.metrics, 'controles': controles.astype(str).to_dict('records'),
               'mem_pct_pico': monitor.pico}, f, indent=2, ensure_ascii=False, default=str)
spark.stop()
print('✓ Resumen guardado y SparkSession detenida')
'''),
    ])


# ============================================================================ 04 · tarea 2.4
def nb_24():
    return notebook([
        cabecera('2.4', 'Métricas de rendimiento y escalabilidad', 'Actividad 2 · Diseño de arquitectura y PoC (evaluativa)',
                 ['Ejecutar el PoC 3 veces y medir tiempo total (s), memoria pico (%), throughput (registros/min) y '
                  'tasa de éxito de validaciones (%).',
                  'Comparar con el mismo proceso en Pandas.',
                  'Estimar la escalabilidad con volúmenes de 1 y 2 años (datos replicados) y proyectarla.'],
                 ['`03_T2.2_PoC_PySpark.ipynb` ejecutado (tabla de códigos y Parquet en Drive).'], '~6 minutos'),
        md('## 1. Configuración del entorno'),
        code(ENTORNO),
        code(MEDICION),
        code(SPARK),
        md('''
## 2. El pipeline del PoC y su equivalente en Pandas

Es el **mismo** `PipelineEmergencias` del notebook 03 (tarea 2.2). Para comparar en igualdad de condiciones,
`pipeline_pandas` hace exactamente lo mismo en Pandas: mismas reglas de limpieza, mismos 12 controles y las mismas
salidas en Parquet. Aquí ambas escriben en el disco local del VM, para que la latencia de Drive no afecte la comparación.
'''),
        code(NORMALIZACION + PIPELINE),
        code(PIPELINE_PANDAS),
        md('''
## 3. Tres ejecuciones de cada herramienta

Métricas que pide la guía, medidas de la carga a la exportación:
- **Tiempo total (s)** del pipeline.
- **Memoria pico (%)**: máximo de `psutil.virtual_memory().percent` durante la ejecución.
- **Throughput (registros/min)** = registros leídos / (tiempo total / 60).
- **Tasa de éxito de validaciones (%)** = controles aprobados / controles evaluados × 100.
'''),
        code(r'''
catalogo_sp = leer_catalogo_spark(spark)
EJECUCIONES = 3
metricas = []
for i in range(1, EJECUCIONES + 1):
    for herramienta in ('spark', 'pandas'):
        destino = f'/content/poc_{herramienta}_e{i}'
        gc.collect()
        with MonitorMemoria() as monitor:
            if herramienta == 'spark':
                p = PipelineEmergencias(spark, f'PoC_e{i}', destino, f'{RESULTADOS}/logs/poc_spark_e{i}.txt')
                p.run(RUTAS, catalogo_sp)
                m = p.metrics
            else:
                m = pipeline_pandas(RUTAS, destino, catalogo_pd)
        metricas.append({'herramienta': herramienta, 'ejecucion': i, 'tiempo_total_s': m['tiempo_total_s'],
                         'mem_pct_pico': monitor.pico, 'throughput_reg_min': m['leidos'] / (m['tiempo_total_s'] / 60),
                         'tasa_validaciones_pct': m['tasa_validaciones_pct'], 'leidos': m['leidos'],
                         'aceptados': m['aceptados'], 'errores': m['errores']})
        print(f"✓ Ejecución {i} · {herramienta}: {m['tiempo_total_s']:.2f} s, pico {monitor.pico:.1f} %")
metricas = pd.DataFrame(metricas)
metricas
'''),
        md('### 3.1 Promedios y comparación'),
        code(r'''
COLS = ['tiempo_total_s', 'mem_pct_pico', 'throughput_reg_min', 'tasa_validaciones_pct']
display(metricas.groupby('herramienta')[COLS].agg(['mean', 'std']).round(2))
medias = metricas.groupby('herramienta')[COLS].mean()
ps, pp = medias.loc['spark'], medias.loc['pandas']
if ps['tiempo_total_s'] > pp['tiempo_total_s']:
    print(f"PySpark fue {ps['tiempo_total_s'] / pp['tiempo_total_s']:.1f} veces MÁS LENTO que Pandas con este volumen.")
else:
    print(f"PySpark fue {pp['tiempo_total_s'] / ps['tiempo_total_s']:.1f} veces más rápido que Pandas.")
print(f"Memoria pico: PySpark {ps['mem_pct_pico']:.1f} % · Pandas {pp['mem_pct_pico']:.1f} %")
print(f"Throughput: PySpark {ps['throughput_reg_min']:,.0f} · Pandas {pp['throughput_reg_min']:,.0f} registros/min")
'''),
        code(r'''
fig, ejes = plt.subplots(1, 2, figsize=(11, 4))
colores = ['#F58518', '#4C78A8']
for eje, col, titulo in ((ejes[0], 'tiempo_total_s', 'Tiempo total (s)'), (ejes[1], 'mem_pct_pico', 'Memoria pico del sistema (%)')):
    g = metricas.groupby('herramienta')[col].agg(['mean', 'std']).loc[['spark', 'pandas']]
    eje.bar(['PySpark', 'Pandas'], g['mean'], yerr=g['std'], capsize=5, color=colores)
    eje.set_title(titulo)
    eje.grid(True, axis='y', alpha=0.3)
fig.suptitle('PoC: PySpark frente a Pandas (media de 3 ejecuciones ± desv. estándar)', fontweight='bold')
plt.tight_layout()
plt.show()
'''),
        md('''
## 4. Escalabilidad: 1 y 2 años de datos

Tres meses son ~27 000 registros; un año son ~4 veces y dos años ~8 veces más. Para medirlo sin inventar se crean
volúmenes **sintéticos** replicando los 3 archivos 4 y 8 veces (a cada copia se le cambia `NUMERO_INCIDENTE` para que
no sea un duplicado exacto). Se ejecuta una vez cada pipeline por volumen.
'''),
        code(r'''
def replicar(factor):
    carpeta = f'/content/escala_x{factor}'
    shutil.rmtree(carpeta, ignore_errors=True)
    os.makedirs(carpeta)
    rutas = []
    for a, r in zip(ARCHIVOS, RUTAS):
        base = pd.read_csv(r, sep=';', dtype=str, encoding='utf-8-sig', keep_default_na=False)
        copias = [base.assign(NUMERO_INCIDENTE=base['NUMERO_INCIDENTE'] + (f'-c{k}' if k else '')) for k in range(factor)]
        destino = f'{carpeta}/{a}'
        pd.concat(copias).to_csv(destino, sep=';', index=False, encoding='utf-8-sig')
        rutas.append(destino)
    return rutas


escala = []
for factor in (1, 4, 8):
    rutas = RUTAS if factor == 1 else replicar(factor)
    for herramienta in ('spark', 'pandas'):
        gc.collect()
        with MonitorMemoria() as monitor:
            if herramienta == 'spark':
                p = PipelineEmergencias(spark, f'Escala_x{factor}', f'/content/esc_spark_x{factor}',
                                        f'/content/esc_logs/esc_x{factor}.txt')
                p.run(rutas, catalogo_sp)
                m = p.metrics
            else:
                m = pipeline_pandas(rutas, f'/content/esc_pandas_x{factor}', catalogo_pd)
        escala.append({'factor': factor, 'meses_equivalentes': 3 * factor, 'herramienta': herramienta,
                       'registros': m['leidos'], 'tiempo_s': m['tiempo_total_s'], 'mem_pct_pico': monitor.pico,
                       'sintetico': factor > 1})
        print(f"✓ x{factor} · {herramienta}: {m['leidos']:,} registros en {m['tiempo_total_s']:.2f} s")
escala = pd.DataFrame(escala)
escala
'''),
        md('''
### 4.1 Tendencia y proyección

Se ajusta una recta `tiempo = a + b × registros` con los tres puntos medidos. Doce y 24 meses están dentro del rango
medido (datos sintéticos); 48 meses es una **estimación teórica** fuera de ese rango.
'''),
        code(r'''
fig, ax = plt.subplots(figsize=(8, 4.5))
proyeccion = []
for herramienta, color in (('spark', '#F58518'), ('pandas', '#4C78A8')):
    d = escala[escala['herramienta'] == herramienta]
    b, a = np.polyfit(d['registros'], d['tiempo_s'], 1)
    ax.plot(d['registros'], d['tiempo_s'], 'o-', color=color, label=f'{herramienta.capitalize()} (medido)')
    x = np.linspace(d['registros'].min(), d['registros'].max() * 2, 50)
    ax.plot(x, a + b * x, '--', color=color, alpha=0.5, label=f'{herramienta.capitalize()} (tendencia)')
    base = int(d.loc[d['factor'] == 1, 'registros'].iloc[0])
    for meses in (12, 24, 48):
        registros = base * meses // 3
        proyeccion.append({'herramienta': herramienta, 'meses': meses, 'registros': registros,
                           'tiempo_estimado_s': round(a + b * registros, 2), 'segundos_por_10k_registros': round(b * 1e4, 3),
                           'tipo': 'dentro del rango medido (sintético)' if meses <= 24 else 'estimación teórica'})
ax.set_xlabel('Registros procesados')
ax.set_ylabel('Tiempo total (s)')
ax.set_title('Escalabilidad del pipeline: PySpark vs Pandas')
ax.grid(True, alpha=0.3)
ax.legend()
plt.tight_layout()
plt.show()
proyeccion = pd.DataFrame(proyeccion)
proyeccion
'''),
        md('## 5. Guardar las métricas en Drive'),
        code(r'''
metricas.to_csv(f'{MEDICIONES}/poc_metricas.csv', index=False)
escala.to_csv(f'{MEDICIONES}/escalabilidad.csv', index=False)
proyeccion.to_csv(f'{MEDICIONES}/proyeccion.csv', index=False)
print('✓ Guardado en', MEDICIONES, '→', sorted(os.listdir(MEDICIONES)))
spark.stop()
'''),
        md('''
## 6. Interpretación

- Con 3 meses de datos, PySpark carga con costos fijos (JVM, planificación, coordinación) que Pandas no tiene; si
  resulta más lento o usa más memoria, así se reporta.
- La tasa de éxito de validaciones debe ser igual en ambas herramientas, porque aplican los mismos controles.
- La ventaja de PySpark aparece cuando los datos ya no caben en la memoria de una máquina: puede repartir el trabajo
  entre varios nodos sin cambiar el código. Colab tiene un solo nodo, así que eso no se mide aquí y queda como
  justificación técnica de la arquitectura.
'''),
    ])


def main():
    destino = RAIZ / 'notebooks'
    destino.mkdir(exist_ok=True)
    for viejo in destino.glob('*.ipynb'):
        if not viejo.stem.endswith('_output'):   # los ejecutados en Colab son evidencia: no se borran
            viejo.unlink()
    for clave, fabrica in (('1.1', nb_11), ('1.2', nb_12), ('2.2', nb_22), ('2.4', nb_24)):
        nb = fabrica()
        nbf.validate(nb)
        nbf.write(nb, destino / NB[clave])
        print('Escrito', NB[clave], f'({len(nb.cells)} celdas)')


if __name__ == '__main__':
    main()
