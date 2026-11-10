"""Genera y verifica todos los informes a partir de las mediciones guardadas (sin volver a medir).

En Colab (notebook de informes): generar_todo(cfg.dir_resultados, cfg.dir_informes) escribe en Drive los xlsx, docx, png y drawio,
los verifica con LibreOffice (fórmulas sin errores, páginas de cada docx) y guarda verificacion_informes.json.
"""
import json
from pathlib import Path

from openpyxl import load_workbook

from . import diagrama, documentos, excel, graficos, sustentacion
from .resumen import cargar_todo
from .verificacion import docx_a_pdf, libro_calculado, recalcular_excel


def leer_matriz(ruta_xlsx, ruta_recalculada=None):
    """Lee la matriz de un libro con valores calculados (el recalculado por LibreOffice/Excel)."""
    ws = load_workbook(ruta_recalculada or ruta_xlsx, data_only=True)['Matriz']
    filas = {ws.cell(i, 1).value: i for i in range(1, ws.max_row + 1) if ws.cell(i, 1).value}
    herramientas = {'pandas': 3, 'polars': 4, 'spark': 5}
    criterios = ['Rendimiento', 'Facilidad de uso', 'Escalabilidad', 'Recursos', 'Curva de aprendizaje']
    return {
        'pesos': {c: ws.cell(filas[c], 2).value for c in criterios},
        'puntajes': {c: {h: ws.cell(filas[c], col).value for h, col in herramientas.items()} for c in criterios},
        'ponderado': {h: ws.cell(filas['Puntaje ponderado'], col).value for h, col in herramientas.items()},
        'loc': {h: ws.cell(filas['LOC totales'], col).value for h, col in herramientas.items()},
    }


def generar_todo(dir_resultados, dir_informes, dir_render=None, datos_doc=None, dir_base=None):
    dir_resultados, dir_informes = Path(dir_resultados), Path(dir_informes)
    if datos_doc is None:
        from ..config import cargar_config
        datos_doc = cargar_config().documentos
    dir_informes.mkdir(parents=True, exist_ok=True)
    dir_render = Path(dir_render or dir_informes / 'verificacion_pdf')
    dir_render.mkdir(parents=True, exist_ok=True)
    R = cargar_todo(dir_resultados)
    verif = {}

    rutas = {
        'g_operaciones': graficos.grafico_operaciones(R['bench']['med'], dir_informes / 'benchmark_operaciones.png'),
        'g_totales': graficos.grafico_totales(R['bench']['med'], dir_informes / 'benchmark_totales_memoria.png'),
        'g_totales_doc': graficos.grafico_totales(R['bench']['med'], dir_informes / 'benchmark_totales_memoria_2filas.png',
                                                  por_fila=3),
        'g_poc': graficos.grafico_poc(R['poc']['principal'], dir_informes / 'comparativo_poc_vs_pandas.png'),
        'diagrama': diagrama.escribir_png(dir_informes / 'diagrama_arquitectura.png'),
    }
    diagrama.escribir_drawio(dir_informes / 'diagrama_arquitectura.drawio')

    # Las líneas de código las cuenta el notebook de análisis (sección del benchmark) y las deja en mediciones/.
    loc = json.loads((dir_resultados / 'mediciones' / 'loc_benchmark.json').read_text(encoding='utf-8'))
    xb = excel.reporte_benchmark(R['bench']['crudo'], loc, R['bench']['equivalencia'], R['entorno'],
                                 dir_informes / 'reporte_comparativo_benchmark.xlsx')
    verif['reporte_comparativo_benchmark.xlsx'] = recalcular_excel(xb)
    crudo_ok = R['poc']['crudo'][R['poc']['crudo']['estado'] == 'ok']
    xp = excel.reporte_poc(crudo_ok, R['poc']['ultima_spark']['controles'], dir_informes / 'metricas_poc.xlsx', R['entorno'])
    verif['metricas_poc.xlsx'] = recalcular_excel(xp)
    matriz = leer_matriz(xb, libro_calculado(xb))

    config_spark = crudo_ok[crudo_ok['herramienta'] == 'spark']['config_spark'].dropna().iloc[-1]
    docs = {
        'analisis_decision_tecnologica.docx': documentos.doc_decision(R, matriz, rutas, dir_informes / 'analisis_decision_tecnologica.docx', datos_doc),
        'arquitectura_tecnica.docx': documentos.doc_arquitectura(R, matriz, rutas, config_spark, dir_informes / 'arquitectura_tecnica.docx', datos_doc),
        'analisis_escalabilidad.docx': documentos.doc_escalabilidad(R, dir_informes / 'analisis_escalabilidad.docx', datos_doc),
    }
    carpeta_sust = Path(dir_base or dir_informes.parent) / 'Sustentacion'
    carpeta_sust.mkdir(parents=True, exist_ok=True)
    docs['Sustentacion_proyecto_U2.docx'] = sustentacion.doc_sustentacion(
        R, matriz, rutas, carpeta_sust / 'Sustentacion_proyecto_U2.docx', datos_doc)
    sustentacion.guion_sustentacion(R, matriz, carpeta_sust / 'Hoja_de_sustentacion_5min.md', datos_doc)
    for nombre, ruta in docs.items():
        verif[nombre] = {'paginas': docx_a_pdf(ruta, dir_render / nombre.replace('.docx', '.pdf'))}
    verif['matriz'] = matriz
    (dir_resultados / 'mediciones' / 'verificacion_informes.json').write_text(
        json.dumps(verif, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    return verif
