"""Entregables por tarea de la guía. Cada notebook de tarea llama a UNA función y escribe directo en BigData_U2.

Orden de ejecución (cada paso lee solo lo que dejaron los anteriores en `resultados/mediciones/`):

    1.1 benchmark -> 1.2 matriz -> 2.2 PoC -> 2.4 métricas y escalabilidad -> 1.3 selección -> 2.1 arquitectura -> cierre

Ninguna función vuelve a medir. Las verificaciones (LibreOffice) quedan en `resultados/mediciones/verificacion_<tarea>.json`.
"""
import json
import tempfile
from pathlib import Path

from . import diagrama, documentos, excel, graficos, sustentacion
from .generador import leer_matriz
from .resumen import cargar_todo, resumen_benchmark
from .verificacion import docx_a_pdf, libro_calculado, recalcular_excel

ACT1, ACT2, SUST = 'Actividad_1', 'Actividad_2', 'Sustentacion'
PLACEHOLDERS = {'autor': '[Nombre del estudiante o del equipo]', 'institucion': '[Nombre de la institución]',
                'docente': '[Nombre del docente]'}


def _carpetas(base):
    base = Path(base)
    return base, base / 'resultados', base / 'resultados' / 'mediciones'


def _guardar_verif(med, tarea, datos):
    (med / f'verificacion_{tarea}.json').write_text(json.dumps(datos, indent=2, ensure_ascii=False, default=str),
                                                    encoding='utf-8')


def autoria(base, cfg_documentos, autor=None, institucion=None, docente=None):
    """Datos del bloque de título APA. Se guardan en Drive la primera vez que se completan y los demás notebooks los reutilizan."""
    base, res, med = _carpetas(base)
    ruta = res / 'autoria.json'
    guardados = json.loads(ruta.read_text(encoding='utf-8')) if ruta.exists() else {}
    dados = {'autor': autor, 'institucion': institucion, 'docente': docente}
    datos = {}
    for k, marcador in PLACEHOLDERS.items():
        v = dados[k]
        datos[k] = v if v and v != marcador else guardados.get(k, marcador)
    if any(datos[k] != PLACEHOLDERS[k] for k in datos):
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    return {**cfg_documentos, **datos}


def _graficos_doc(R, tmp):
    """Figuras que incrustan los documentos (en una carpeta temporal; las entregables se guardan en su actividad)."""
    tmp = Path(tmp)
    return {
        'g_totales': graficos.grafico_totales(R['bench']['med'], tmp / 'benchmark_totales_memoria.png'),
        'g_totales_doc': graficos.grafico_totales(R['bench']['med'], tmp / 'benchmark_totales_2filas.png', por_fila=3),
        'g_poc': graficos.grafico_poc(R['poc']['principal'], tmp / 'comparativo_poc_vs_pandas.png'),
        'diagrama': diagrama.escribir_png(tmp / 'diagrama_arquitectura.png'),
    }


def tarea_1_2(base):
    """Matriz de decisión: libro Excel con fórmulas (promedios, reglas de puntaje y SUMPRODUCT)."""
    base, res, med = _carpetas(base)
    dest = base / ACT1
    dest.mkdir(parents=True, exist_ok=True)
    b = resumen_benchmark(med)
    entorno = json.loads((med / 'entorno_colab.json').read_text(encoding='utf-8'))
    loc = json.loads((med / 'loc_benchmark.json').read_text(encoding='utf-8'))
    xlsx = excel.reporte_benchmark(b['crudo'], loc, b['equivalencia'], entorno, dest / 'reporte_comparativo_benchmark.xlsx')
    verif = recalcular_excel(xlsx)
    assert not verif['errores'], verif['errores']
    matriz = leer_matriz(xlsx, libro_calculado(xlsx))
    (med / 'matriz_decision.json').write_text(json.dumps(matriz, indent=2, ensure_ascii=False), encoding='utf-8')
    _guardar_verif(med, 'T1_2', {'xlsx': verif, 'matriz': matriz})
    return {'verificacion': verif, 'matriz': matriz}


def tarea_2_4(base, datos_doc):
    """Métricas de las 3 ejecuciones (xlsx), gráfico frente a Pandas y análisis de escalabilidad (docx de 1 página)."""
    base, res, med = _carpetas(base)
    dest = base / ACT2
    dest.mkdir(parents=True, exist_ok=True)
    R = cargar_todo(res)
    graficos.grafico_poc(R['poc']['principal'], dest / 'comparativo_poc_vs_pandas.png')
    crudo_ok = R['poc']['crudo'][R['poc']['crudo']['estado'] == 'ok']
    xp = excel.reporte_poc(crudo_ok, R['poc']['ultima_spark']['controles'], dest / 'metricas_poc.xlsx', R['entorno'])
    verif = {'metricas_poc.xlsx': recalcular_excel(xp)}
    assert not verif['metricas_poc.xlsx']['errores'], verif
    docx = documentos.doc_escalabilidad(R, dest / 'analisis_escalabilidad.docx', datos_doc)
    with tempfile.TemporaryDirectory() as tmp:
        verif['analisis_escalabilidad.docx'] = {'paginas': docx_a_pdf(docx, Path(tmp) / 'escalabilidad.pdf')}
    assert verif['analisis_escalabilidad.docx']['paginas'] == 1, 'La escalabilidad debe ocupar 1 página'
    _guardar_verif(med, 'T2_4', verif)
    return verif


def tarea_1_3(base, datos_doc):
    """Selección tecnológica justificada (docx): decisión, criterios por volumen, plan por fases y limitaciones."""
    base, res, med = _carpetas(base)
    dest = base / ACT1
    dest.mkdir(parents=True, exist_ok=True)
    R = cargar_todo(res)
    matriz = json.loads((med / 'matriz_decision.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as tmp:
        rutas = _graficos_doc(R, tmp)
        docx = documentos.doc_decision(R, matriz, rutas, dest / 'analisis_decision_tecnologica.docx', datos_doc)
        verif = {'analisis_decision_tecnologica.docx': {'paginas': docx_a_pdf(docx, Path(tmp) / 'decision.pdf')}}
    _guardar_verif(med, 'T1_3', verif)
    return verif


def tarea_2_1(base, datos_doc):
    """Arquitectura técnica: diagrama (.png y .drawio) y documento .docx de 5 a 8 páginas."""
    base, res, med = _carpetas(base)
    dest = base / ACT2
    dest.mkdir(parents=True, exist_ok=True)
    R = cargar_todo(res)
    matriz = json.loads((med / 'matriz_decision.json').read_text(encoding='utf-8'))
    diagrama.escribir_png(dest / 'diagrama_arquitectura.png')
    diagrama.escribir_drawio(dest / 'diagrama_arquitectura.drawio')
    crudo_ok = R['poc']['crudo'][R['poc']['crudo']['estado'] == 'ok']
    config_spark = crudo_ok[crudo_ok['herramienta'] == 'spark']['config_spark'].dropna().iloc[-1]
    with tempfile.TemporaryDirectory() as tmp:
        rutas = _graficos_doc(R, tmp)
        rutas['diagrama'] = dest / 'diagrama_arquitectura.png'
        docx = documentos.doc_arquitectura(R, matriz, rutas, config_spark, dest / 'arquitectura_tecnica.docx', datos_doc)
        verif = {'arquitectura_tecnica.docx': {'paginas': docx_a_pdf(docx, Path(tmp) / 'arquitectura.pdf')}}
    assert 5 <= verif['arquitectura_tecnica.docx']['paginas'] <= 8, 'La arquitectura debe tener 5-8 páginas'
    _guardar_verif(med, 'T2_1', verif)
    return verif


def cierre(base, datos_doc):
    """Documento de sustentación para no especialistas y hoja de sustentación de 5 minutos."""
    base, res, med = _carpetas(base)
    dest = base / SUST
    dest.mkdir(parents=True, exist_ok=True)
    R = cargar_todo(res)
    matriz = json.loads((med / 'matriz_decision.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as tmp:
        rutas = _graficos_doc(R, tmp)
        docx = sustentacion.doc_sustentacion(R, matriz, rutas, dest / 'Sustentacion_proyecto_U2.docx', datos_doc)
        verif = {'Sustentacion_proyecto_U2.docx': {'paginas': docx_a_pdf(docx, Path(tmp) / 'sustentacion.pdf')}}
    sustentacion.guion_sustentacion(R, matriz, dest / 'Hoja_de_sustentacion_5min.md', datos_doc)
    _guardar_verif(med, 'cierre', verif)
    return verif
