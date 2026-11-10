"""Organiza la ÚNICA carpeta del proyecto en Drive (MyDrive/BigData_U2) con lo que pide la guía U2.

Decisiones del usuario (2026-11-10): los programas son SOLO dos notebooks, y en Drive hay una sola carpeta con lo
necesario (datos, informes, notebooks, evidencia), sin copias duplicadas. Estructura final:

    BigData_U2/
      LEEME.md                            índice tarea → archivo y cómo ejecutar
      U2_procesamiento_distribuido.ipynb  datos, benchmark, PoC, validaciones (con sus salidas)
      U2_informes_y_entregables.ipynb     genera y verifica los informes y organiza esta carpeta
      datos/                              los 3 CSV (SHA-256 verificado)
      Actividad_1/  Actividad_2/          informes de cada actividad (QUE_SE_PIDE.md en cada una)
      Sustentacion/                       explicación para no especialistas
      resultados/                         evidencia: mediciones, logs y Parquet del PoC

Los informes se generan en una carpeta temporal del VM (`origen_informes`) y aquí se copian a su actividad.
Cada archivo va en UNA sola actividad; si otra tarea lo usa, QUE_SE_PIDE.md lo referencia con su ruta.
"""
import shutil
from pathlib import Path

DRIVE = 'MyDrive/BigData_U2'
NB_ANALISIS = 'U2_procesamiento_distribuido.ipynb'
NB_INFORMES = 'U2_informes_y_entregables.ipynb'
ACT1, ACT2 = 'Actividad_1', 'Actividad_2'

ACTIVIDADES = {
    ACT1: {
        'titulo': 'Actividad 1 · Análisis comparativo de herramientas (formativa)',
        'archivos': {  # nombre en la actividad -> origen (relativo a la carpeta temporal de informes o a la base)
            'reporte_comparativo_benchmark.xlsx': 'reporte_comparativo_benchmark.xlsx',
            'analisis_decision_tecnologica.docx': 'analisis_decision_tecnologica.docx',
            'benchmark_operaciones.png': 'benchmark_operaciones.png',
            'benchmark_totales_memoria.png': 'benchmark_totales_memoria.png',
        },
        'tareas': [
            ('1.1 Benchmark comparativo de herramientas',
             'Comparación empírica Pandas vs Polars vs PySpark con los mismos 3 archivos mensuales; measure_performance() '
             'con tiempo y memoria (psutil); carga, filtrado USAQUEN/CHAPINERO, agregación por tipo, join con la tabla de '
             'códigos y exportación Parquet; tiempo total y por operación; líneas de código por operación.',
             [f'../{NB_ANALISIS} (parte 3: benchmark con measure_performance, con sus salidas)',
              'reporte_comparativo_benchmark.xlsx (hojas Mediciones, Promedios, LOC, Graficos, Equivalencia)',
              'benchmark_operaciones.png', 'benchmark_totales_memoria.png',
              '../resultados/mediciones/benchmark.jsonl (mediciones crudas)',
              '../resultados/mediciones/equivalencia_benchmark.json']),
            ('1.2 Matriz de decisión tecnológica',
             'Criterios y pesos: rendimiento 30 %, facilidad de uso 25 %, escalabilidad 20 %, recursos 15 %, curva de '
             'aprendizaje 10 %; puntuación 1–5 basada en el benchmark; puntaje ponderado; restricciones de Colab.',
             ['reporte_comparativo_benchmark.xlsx (hojas Reglas y Matriz, con fórmulas SUMPRODUCT)',
              'analisis_decision_tecnologica.docx (§4)']),
            ('1.3 Selección tecnológica justificada',
             'Herramienta principal (obligatoria: PySpark) y complementarias, criterios de uso por volumen, plan de '
             'implementación por fases y limitaciones.',
             ['analisis_decision_tecnologica.docx (§5–§9)', 'reporte_comparativo_benchmark.xlsx (hoja Matriz)']),
        ],
        'nota': 'Los puntajes de la matriz ponderada están en reporte_comparativo_benchmark.xlsx (hoja Matriz) y su '
                'interpretación, en analisis_decision_tecnologica.docx. PySpark se mantiene como herramienta principal por '
                'exigencia de la actividad y por su escalabilidad horizontal, aunque con este volumen no sea la más rápida.',
    },
    ACT2: {
        'titulo': 'Actividad 2 · Diseño de arquitectura y PoC en PySpark (evaluativa)',
        'archivos': {
            'arquitectura_tecnica.docx': 'arquitectura_tecnica.docx',
            'diagrama_arquitectura.png': 'diagrama_arquitectura.png',
            'diagrama_arquitectura.drawio': 'diagrama_arquitectura.drawio',
            'metricas_poc.xlsx': 'metricas_poc.xlsx',
            'comparativo_poc_vs_pandas.png': 'comparativo_poc_vs_pandas.png',
            'analisis_escalabilidad.docx': 'analisis_escalabilidad.docx',
            'validacion_poc_spark.txt': 'resultados/logs/validacion_poc_spark.txt',
        },
        'tareas': [
            ('2.1 Documento de arquitectura técnica',
             'Documento .docx de 5 a 8 páginas con diagrama (ingesta, procesamiento, almacenamiento, salida), decisiones '
             'justificadas, configuraciones de PySpark, particionamiento mes/localidad, métricas de monitoreo/KPIs, '
             'estimación de recursos, riesgos; diagrama .png de alta resolución exportado aparte.',
             ['arquitectura_tecnica.docx (5–8 páginas, verificado al exportar a PDF)', 'diagrama_arquitectura.png (300 dpi)',
              'diagrama_arquitectura.drawio (fuente editable)']),
            ('2.2 Proof of Concept en PySpark',
             'Notebook de Colab funcional y documentado con outputs; PySpark en Colab; ingesta de 3 CSV desde Google Drive; '
             'limpieza de nulos, tipos, estandarización de códigos; validación de calidad; exportación Parquet subida a '
             'Drive; log de validación .txt (registros procesados, errores, tiempo).',
             [f'../{NB_ANALISIS} (partes 4 a 6: PoC en PySpark, con sus salidas)',
              f'../resultados/parquet/poc/spark/e1..e3/ (Parquet en Google Drive: {DRIVE}/resultados/parquet/poc/spark/)',
              'validacion_poc_spark.txt (log de validación)', '../datos/ (los 3 CSV de entrada)']),
            ('2.3 Mini-pitch técnico', 'Presentación de máx. 5 minutos (6 slides) y video .mp4.',
             ['EXCLUIDO del alcance del encargo. Insumos disponibles: diagrama_arquitectura.png, '
              'comparativo_poc_vs_pandas.png y ../Sustentacion/Sustentacion_proyecto_U2.docx']),
            ('2.4 Métricas de rendimiento',
             'PoC ejecutado 3 veces: tiempo total (s), memoria pico (%), throughput (registros/min), tasa de éxito de '
             'validaciones (%); comparación con las métricas de Pandas del benchmark; reporte .xlsx con 3 ejecuciones y '
             'promedios; gráfico .png de tiempo y memoria vs Pandas; análisis de escalabilidad .docx de 1 página.',
             ['metricas_poc.xlsx', 'comparativo_poc_vs_pandas.png', 'analisis_escalabilidad.docx (1 página)',
              '../resultados/mediciones/poc.jsonl y escalabilidad.jsonl (mediciones crudas)',
              '../Actividad_1/reporte_comparativo_benchmark.xlsx (métricas de Pandas del benchmark inicial)',
              'arquitectura_tecnica.docx (§9 recursos y §10 KPIs)']),
        ],
        'nota': 'Las métricas de las 3 ejecuciones y sus promedios están en metricas_poc.xlsx, y el detalle de los controles, '
                'en validacion_poc_spark.txt. Con 3 meses de datos PySpark no mejora a Pandas en tiempo ni en memoria, y así '
                'se reporta. Solo se eliminan las copias duplicadas exactas (100 % de sus atributos iguales), que quedan '
                'registradas aparte; los nulos y demás anomalías se conservan marcados en observacion_calidad.',
    },
}
EXCLUIDOS = 'Video, presentación/diapositivas, guion del mini-pitch y capturas manuales: excluidos por alcance del encargo.'
ESTRUCTURA = [
    ('LEEME.md', 'este índice'),
    ('Guia de actividades_U2 (6) (1).pdf', 'la guía de actividades de la Unidad 2'),
    (NB_ANALISIS, 'todo el procesamiento, narrado sección por sección y con sus salidas de Colab'),
    (NB_INFORMES, 'genera y verifica los informes (LibreOffice en Colab) y organiza esta carpeta'),
    ('datos/', 'los 3 CSV de julio, agosto y septiembre de 2026 (huella SHA-256 verificada)'),
    (f'{ACT1}/', 'entregables de la Actividad 1 y QUE_SE_PIDE.md'),
    (f'{ACT2}/', 'entregables de la Actividad 2 y QUE_SE_PIDE.md'),
    ('Sustentacion/', 'documento que explica todo el proyecto a una persona sin conocimientos técnicos y '
                      'hoja de sustentación de 5 minutos (Hoja_de_sustentacion_5min.md)'),
    ('resultados/', 'evidencia: mediciones crudas (JSONL/JSON), logs de validación y Parquet del PoC'),
]


def _resolver(origen, raices):
    for raiz in raices:
        p = Path(raiz) / origen
        if p.exists():
            return p
    return None


def _copiar(origen, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
        shutil.copytree(origen, destino, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '_SUCCESS', '.*.crc'))
    else:
        shutil.copy2(origen, destino)


def construir(base, origen_informes):
    """Rehace las carpetas de actividad dentro de `base` y escribe LEEME.md. No toca datos, notebooks ni resultados."""
    base, raices = Path(base), [Path(origen_informes), Path(base)]
    estados = {}
    indice = ['# Proyecto U2 — Procesamiento distribuido (Emergencias 123 Bogotá)', '',
              'Carpeta única del proyecto en Google Drive con lo que pide la guía de la Unidad 2. Los programas son '
              'únicamente los dos notebooks de esta carpeta.', '', '## Contenido', '']
    indice += [f'- `{n}`: {d}' for n, d in ESTRUCTURA]
    indice += ['', '## Cómo ejecutar (solo Google Colab)', '',
               f'1. Subir `{NB_ANALISIS}` y `{NB_INFORMES}` a `{DRIVE}/` en Google Drive.',
               f'2. Abrir `{NB_ANALISIS}` en Colab (runtime CPU) y elegir *Entorno de ejecución → Ejecutar todas*. Colab '
               'pide autorizar Drive. Los CSV se toman de `MyDrive/BigData_Emergencias_123` (carpeta de la Unidad 1) o, si '
               'no están, se descargan del portal Datos Abiertos Bogotá; en ambos casos se verifica su SHA-256.',
               f'3. Ese mismo notebook ejecuta al final `{NB_INFORMES}` (sección 9): genera los informes, los verifica y '
               'organiza esta carpeta. No hay que ejecutar nada más.',
               '']
    for carpeta, act in ACTIVIDADES.items():
        d = base / carpeta
        if d.exists():  # carpeta generada: se rehace para no dejar restos de una corrida anterior
            shutil.rmtree(d)
        d.mkdir(parents=True)
        faltantes = []
        for nombre, origen in act['archivos'].items():
            o = _resolver(origen, raices)
            if o:
                _copiar(o, d / nombre)
            else:
                faltantes.append(origen)
        texto = [f"# {act['titulo']}", '', act['nota'], '', '## Tareas de la guía y archivos que las cumplen', '',
                 'Las rutas que empiezan por `../` están en la carpeta del proyecto (no se duplican aquí).', '']
        for tarea, pedido, archivos in act['tareas']:
            texto += [f'### {tarea}', '', f'**Qué se pide:** {pedido}', '', '**Archivos:**', '']
            texto += [f'- {a}' for a in archivos] + ['']
        estado = 'COMPLETO' if not faltantes else 'INCOMPLETO: falta ' + ', '.join(faltantes)
        texto += [f'**Estado:** {estado}', '', f'_{EXCLUIDOS}_', '']
        (d / 'QUE_SE_PIDE.md').write_text('\n'.join(texto), encoding='utf-8')
        indice += [f"## [{act['titulo']}]({carpeta}/QUE_SE_PIDE.md)", '']
        indice += [f'- {t[0]}' for t in act['tareas']] + ['', f'Estado: {estado}', '']
        estados[carpeta] = estado
    indice += [f'_{EXCLUIDOS}_', '']
    (base / 'LEEME.md').write_text('\n'.join(indice), encoding='utf-8')
    return estados
