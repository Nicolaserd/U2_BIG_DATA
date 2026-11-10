"""Reportes .xlsx con fórmulas (promedios, desviaciones, puntajes y ponderaciones se calculan en Excel).

Las mediciones crudas se escriben como valores. Todo lo derivado son fórmulas que las referencian,
para que el libro se recalcule si cambian los datos. La desviación estándar muestral se calcula con
SUMPRODUCT (sin fórmulas matriciales) para que funcione en cualquier Excel.
"""
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

FUENTE = 'Arial'
AZUL_INPUT = Font(name=FUENTE, color='0000FF')
NEGRITA = Font(name=FUENTE, bold=True)
NORMAL = Font(name=FUENTE)
TITULO = Font(name=FUENTE, bold=True, size=14)
CABECERA_FILL = PatternFill('solid', fgColor='DCE6F1')
INPUT_FILL = PatternFill('solid', fgColor='FFF2CC')
BORDE = Border(bottom=Side(style='thin', color='BFBFBF'))
HERRAMIENTAS = ['pandas', 'polars', 'spark']
NOMBRES = {'pandas': 'Pandas', 'polars': 'Polars', 'spark': 'PySpark'}
OPERACIONES = ['inicio_sesion', 'carga', 'filtrado', 'agregacion', 'join', 'exportacion', 'extremo_a_extremo',
               'total', 'total_con_arranque']
MODOS = ['por_operacion', 'extremo_a_extremo', 'extremo_a_extremo_caliente']


def _cabecera(ws, fila, columnas, anchos=None):
    for j, c in enumerate(columnas, 1):
        celda = ws.cell(fila, j, c)
        celda.font, celda.fill, celda.border = NEGRITA, CABECERA_FILL, BORDE
        celda.alignment = Alignment(wrap_text=True, vertical='center')
    for j, ancho in enumerate(anchos or [], 1):
        ws.column_dimensions[get_column_letter(j)].width = ancho


def _fuente_por_defecto(wb):
    for ws in wb.worksheets:
        for fila in ws.iter_rows():
            for c in fila:
                if c.value is not None and (c.font is None or c.font.name != FUENTE):
                    c.font = Font(name=FUENTE, bold=c.font.bold, color=c.font.color, size=c.font.size)


def _texto(ws, fila, texto, fuente=NORMAL, col=1):
    c = ws.cell(fila, col, texto)
    c.font, c.alignment = fuente, Alignment(wrap_text=True, vertical='top')
    return c


def _escribir_mediciones(ws, med, columnas):
    _cabecera(ws, 1, columnas, [12, 26, 9, 13, 18, 11, 12, 12, 11, 11, 11, 11, 7, 9, 40, 8])
    for i, fila in enumerate(med[columnas].itertuples(index=False), 2):
        for j, v in enumerate(fila, 1):
            if hasattr(v, 'item'):
                v = v.item()
            ws.cell(i, j, None if v != v else v)  # NaN -> vacío
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{get_column_letter(len(columnas))}{len(med) + 1}'
    return len(med) + 1


def _rangos(ultima, letras):
    return {k: f'Mediciones!${c}$2:${c}${ultima}' for k, c in letras.items()}


def reporte_benchmark(med, loc, equivalencia, entorno, ruta):
    """med: todas las filas de benchmark.jsonl (incluye calentamientos, que se excluyen por fórmula)."""
    wb = Workbook()
    ws0 = wb.active
    ws0.title = 'Resumen'
    columnas = ['herramienta', 'modo', 'ejecucion', 'calentamiento', 'operacion', 'segundos', 'mem_sis_base_pct',
                'mem_sis_pico_pct', 'rss_base_mb', 'rss_pico_mb', 'filas_entrada', 'filas_salida', 'loc',
                'usa_cache', 'accion_materializacion', 'estado']
    wsm = wb.create_sheet('Mediciones')
    ultima = _escribir_mediciones(wsm, med, columnas)
    R = _rangos(ultima, {'h': 'A', 'modo': 'B', 'cal': 'D', 'op': 'E', 'seg': 'F', 'sis': 'H', 'rss': 'J'})

    # --- Promedios (fórmulas sobre Mediciones, calentamiento excluido) ---
    wsp = wb.create_sheet('Promedios')
    _cabecera(wsp, 1, ['Modo', 'Operación', 'Herramienta', 'n', 'Segundos (media)', 'Segundos (desv. est.)',
                       'Segundos (mín.)', 'Segundos (máx.)', 'RSS pico MB (media)', 'Memoria sistema pico % (media)',
                       'Veces vs. la más rápida'], [22, 18, 12, 6, 14, 14, 13, 13, 14, 16, 14])
    fila, filas_total = 2, {}
    presentes = set(zip(med['modo'], med['operacion'], med['herramienta']))
    for modo in MODOS:
        for op in OPERACIONES:
            bloque = [h for h in HERRAMIENTAS if (modo, op, h) in presentes]
            if not bloque:
                continue
            inicio = fila
            for h in bloque:
                crit = f'{R["h"]},$C{fila},{R["modo"]},$A{fila},{R["op"]},$B{fila},{R["cal"]},FALSE'
                wsp.cell(fila, 1, modo)
                wsp.cell(fila, 2, op)
                wsp.cell(fila, 3, h)
                wsp.cell(fila, 4, f'=COUNTIFS({crit})')
                wsp.cell(fila, 5, f'=IFERROR(AVERAGEIFS({R["seg"]},{crit}),"")')
                cond = (f'({R["h"]}=$C{fila})*({R["modo"]}=$A{fila})*({R["op"]}=$B{fila})*({R["cal"]}=FALSE)')
                wsp.cell(fila, 6, f'=IF($D{fila}>1,SQRT(SUMPRODUCT({cond}*({R["seg"]}-$E{fila})^2)/($D{fila}-1)),"")')
                wsp.cell(fila, 7, f'=_xlfn.MINIFS({R["seg"]},{crit})')
                wsp.cell(fila, 8, f'=_xlfn.MAXIFS({R["seg"]},{crit})')
                wsp.cell(fila, 9, f'=IFERROR(AVERAGEIFS({R["rss"]},{crit}),"")')
                wsp.cell(fila, 10, f'=IFERROR(AVERAGEIFS({R["sis"]},{crit}),"")')
                if op == 'total':
                    filas_total[(modo, h)] = fila
                fila += 1
            for f in range(inicio, fila):
                wsp.cell(f, 11, f'=IFERROR(E{f}/MIN($E${inicio}:$E${fila - 1}),"")')
                for col, fmt in ((5, '0.000'), (6, '0.000'), (7, '0.000'), (8, '0.000'), (9, '0.0'), (10, '0.0'), (11, '0.0"x"')):
                    wsp.cell(f, col).number_format = fmt
    wsp.freeze_panes = 'A2'

    # --- LOC ---
    wsl = wb.create_sheet('LOC')
    ops5 = ['carga', 'filtrado', 'agregacion', 'join', 'exportacion']
    _cabecera(wsl, 1, ['Operación'] + [NOMBRES[h] for h in HERRAMIENTAS], [18, 12, 12, 12])
    for i, op in enumerate(ops5, 2):
        wsl.cell(i, 1, op)
        for j, h in enumerate(HERRAMIENTAS, 2):
            wsl.cell(i, j, loc[h][op])
    fila_tot_loc = len(ops5) + 2
    wsl.cell(fila_tot_loc, 1, 'TOTAL').font = NEGRITA
    for j in range(2, 5):
        col = get_column_letter(j)
        wsl.cell(fila_tot_loc, j, f'=SUM({col}2:{col}{fila_tot_loc - 1})').font = NEGRITA
    _texto(wsl, fila_tot_loc + 2, 'Criterio: líneas físicas no vacías ni de comentario entre los marcadores '
           '"# >>> op:<nombre>" y "# <<< op:<nombre>" de src/emergencias123/ops_*.py (sin la firma def).')

    # --- Reglas de puntuación ---
    wsr = wb.create_sheet('Reglas')
    wsr.column_dimensions['A'].width = 24
    wsr.column_dimensions['B'].width = 110
    reglas = [
        ('Escala', 'Puntajes de 1 (peor) a 5 (mejor). Puntaje ponderado = SUMPRODUCT(pesos, puntajes).'),
        ('Cuantitativos', 'r = valor de la herramienta / mejor valor entre las tres. r<=1.25 -> 5; r<=2 -> 4; r<=4 -> 3; '
                          'r<=8 -> 2; r>8 -> 1. Calculado por fórmula en la hoja Matriz.'),
        ('Rendimiento (30 %)', 'Tiempo total extremo a extremo (proceso nuevo por repetición, sin arranque de sesión), '
                               'media de las repeticiones medidas. Fuente: hoja Promedios.'),
        ('Recursos (15 %)', 'Pico de RSS del proceso más sus hijos (incluye la JVM), media, modo extremo a extremo. '
                            'Se usa RSS y no el % del sistema porque este último incluye procesos ajenos.'),
        ('Facilidad de uso (25 %)', 'Base cuantitativa: cociente de LOC totales (misma escala r). Ajuste cualitativo '
                                    'de -1 a +1 justificado en la hoja Matriz (configuración, depuración, '
                                    'dependencias). Resultado acotado a [1, 5].'),
        ('Escalabilidad (20 %)', 'Cualitativo: 5 = distribuido multinodo nativo; 3 = un nodo multihilo con ejecución '
                                 'streaming/out-of-core; 2 = un nodo, en memoria, principalmente un hilo.'),
        ('Curva de aprendizaje (10 %)', 'Cualitativo: 5 = API ampliamente conocida y sin conceptos nuevos; 4 = API '
                                        'nueva de expresiones similar a SQL/dataframes; 2 = conceptos de motor '
                                        'distribuido (evaluación perezosa, DAG, particiones, JVM, configuración).'),
        ('Celdas editables', 'Las celdas con fondo amarillo y texto azul son juicios cualitativos o ajustes '
                             'editables; todo lo demás se calcula.'),
    ]
    for i, (a, b) in enumerate(reglas, 1):
        _texto(wsr, i, a, NEGRITA)
        _texto(wsr, i, b, col=2)

    # --- Matriz de decisión ---
    wsx = wb.create_sheet('Matriz')
    for col, ancho in zip('ABCDEFGH', [26, 9, 14, 14, 14, 3, 70, 3]):
        wsx.column_dimensions[col].width = ancho
    _texto(wsx, 1, 'Matriz de decisión tecnológica ponderada (escala 1-5)', TITULO)
    _texto(wsx, 3, 'Insumos cuantitativos (fórmulas sobre Promedios y LOC)', NEGRITA)
    _cabecera(wsx, 4, ['Insumo', '', 'Pandas', 'Polars', 'PySpark'])
    t = filas_total
    insumos = [
        ('Tiempo total extremo a extremo (s)', [f"=Promedios!E{t[('extremo_a_extremo', h)]}" for h in HERRAMIENTAS], '0.000'),
        ('RSS pico proceso+hijos (MB)', [f"=Promedios!I{t[('extremo_a_extremo', h)]}" for h in HERRAMIENTAS], '0.0'),
        ('LOC totales', [f'=LOC!{c}{fila_tot_loc}' for c in 'BCD'], '0'),
    ]
    for i, (nombre, formulas, fmt) in enumerate(insumos, 5):
        wsx.cell(i, 1, nombre)
        for j, f in enumerate(formulas, 3):
            wsx.cell(i, j, f).number_format = fmt

    def puntaje(fila_insumo, col):
        r = f'{col}{fila_insumo}/MIN($C${fila_insumo}:$E${fila_insumo})'
        return f'=IF({r}<=1.25,5,IF({r}<=2,4,IF({r}<=4,3,IF({r}<=8,2,1))))'

    _texto(wsx, 9, 'Ajuste cualitativo de facilidad de uso (-1, 0, +1)', NEGRITA)
    ajustes = {'pandas': 0, 'polars': 0, 'spark': -1}
    for j, h in enumerate(HERRAMIENTAS, 3):
        c = wsx.cell(9, j, ajustes[h])
        c.font, c.fill = AZUL_INPUT, INPUT_FILL
    _texto(wsx, 9, 'PySpark -1: requiere configurar SparkSession y JVM, sus errores mezclan trazas de Java y Python y la '
           'evaluación perezosa exige acciones explícitas para ver resultados. Pandas y Polars se usan y depuran como una '
           'biblioteca más de Python.', col=7)

    _cabecera(wsx, 11, ['Criterio', 'Peso', 'Pandas', 'Polars', 'PySpark', '', 'Fundamento'])
    criterios = [
        ('Rendimiento', 0.30, [puntaje(5, c) for c in 'CDE'],
         'Cuantitativo: cociente del tiempo total extremo a extremo frente a la herramienta más rápida (fila 5).'),
        ('Facilidad de uso', 0.25, [f'=MAX(1,MIN(5,{puntaje(7, c)[1:]}+{c}9))' for c in 'CDE'],
         'Cociente de LOC (fila 7) más el ajuste cualitativo de la fila 9.'),
        ('Escalabilidad', 0.20, [2, 3, 5],
         'Pandas: un nodo, todo en memoria. Polars: un nodo, multihilo, streaming/out-of-core. '
         'PySpark: escala horizontalmente a un clúster (Databricks, Dataproc, etc.) sin cambiar el código.'),
        ('Recursos', 0.15, [puntaje(6, c) for c in 'CDE'],
         'Cuantitativo: cociente del pico de RSS del proceso más sus hijos (fila 6; incluye la JVM).'),
        ('Curva de aprendizaje', 0.10, [5, 4, 2],
         'Pandas: estándar de facto y la más conocida. Polars: API de expresiones nueva pero familiar. '
         'PySpark: exige evaluación perezosa, DAG, particiones, caché y configuración de la JVM.'),
    ]
    for i, (nombre, peso, puntajes, fundamento) in enumerate(criterios, 12):
        wsx.cell(i, 1, nombre)
        c = wsx.cell(i, 2, peso)
        c.number_format, c.font, c.fill = '0%', AZUL_INPUT, INPUT_FILL
        for j, p in enumerate(puntajes, 3):
            c = wsx.cell(i, j, p)
            if not str(p).startswith('='):
                c.font, c.fill = AZUL_INPUT, INPUT_FILL
        _texto(wsx, i, fundamento, col=7)
    fp = 12 + len(criterios)
    wsx.cell(fp, 1, 'Suma de pesos').font = NEGRITA
    wsx.cell(fp, 2, f'=SUM(B12:B{fp - 1})').number_format = '0%'
    wsx.cell(fp + 1, 1, 'Puntaje ponderado').font = NEGRITA
    for col in 'CDE':
        c = wsx.cell(fp + 1, ' CDE'.index(col) + 2, f'=SUMPRODUCT($B$12:$B${fp - 1},{col}12:{col}{fp - 1})')
        c.number_format, c.font = '0.00', NEGRITA
    wsx.cell(fp + 2, 1, 'Posición (1 = mejor)').font = NEGRITA
    for col in 'CDE':
        wsx.cell(fp + 2, ' CDE'.index(col) + 2, f'=RANK({col}{fp + 1},$C${fp + 1}:$E${fp + 1})')
    wsx.cell(fp + 3, 1, 'Mayor puntaje').font = NEGRITA
    wsx.cell(fp + 3, 3, f'=INDEX($C$4:$E$4,MATCH(MAX($C${fp + 1}:$E${fp + 1}),$C${fp + 1}:$E${fp + 1},0))')
    _texto(wsx, fp + 5, 'Lectura: la matriz refleja el volumen probado (3 meses, ~3 MB). PySpark es la herramienta '
           'principal OBLIGATORIA de la actividad; si otra herramienta obtiene mayor puntaje, eso indica cuál es más '
           'conveniente para este volumen, no reemplaza la elección exigida. Ver el análisis de decisión (.docx).', col=1)
    wsx.merge_cells(start_row=fp + 5, start_column=1, end_row=fp + 5, end_column=7)
    wsx.row_dimensions[fp + 5].height = 48

    # --- Gráficos nativos ---
    wsg = wb.create_sheet('Graficos')
    _cabecera(wsg, 1, ['Herramienta', 'Total extremo a extremo (s)', 'Total por operación (s)',
                       'Extremo a extremo, proceso caliente (s)', 'RSS pico (MB)', 'Memoria sistema pico (%)'],
              [14, 18, 18, 22, 14, 16])
    for i, h in enumerate(HERRAMIENTAS, 2):
        wsg.cell(i, 1, NOMBRES[h])
        for j, (modo, col) in enumerate((('extremo_a_extremo', 'E'), ('por_operacion', 'E'),
                                         ('extremo_a_extremo_caliente', 'E'), ('extremo_a_extremo', 'I'),
                                         ('extremo_a_extremo', 'J')), 2):
            if (modo, h) in t:
                wsg.cell(i, j, f'=Promedios!{col}{t[(modo, h)]}').number_format = '0.000'
    for k, (titulo, col, eje, ancla) in enumerate((
            ('Tiempo total de la carga a la exportación (media, s)', 2, 'segundos', 'A7'),
            ('RSS pico proceso + hijos (media, MB)', 5, 'MB', 'J7'),
            ('Memoria del sistema, pico (media, %)', 6, '% RAM', 'A24'))):
        g = BarChart()
        g.type, g.title, g.y_axis.title, g.x_axis.title = 'bar', titulo, eje, 'Herramienta'
        g.add_data(Reference(wsg, min_col=col, max_col=col + (2 if k == 0 else 0), min_row=1, max_row=4), titles_from_data=True)
        g.set_categories(Reference(wsg, min_col=1, min_row=2, max_row=4))
        g.height, g.width = 7.5, 16
        wsg.add_chart(g, ancla)

    # --- Equivalencia ---
    wse = wb.create_sheet('Equivalencia')
    _cabecera(wse, 1, ['Modo', 'Criterio', 'Resultado', 'Detalle'], [24, 14, 12, 90])
    i = 2
    for modo, r in equivalencia.items():
        for criterio, ok in r['criterios'].items():
            detalle = {h: (x[criterio] if criterio in ('filas',) else (x[criterio][:16] if criterio == 'sha256' else ''))
                       for h, x in r['resumenes'].items()}
            wse.cell(i, 1, modo)
            wse.cell(i, 2, criterio)
            wse.cell(i, 3, 'IGUAL' if ok else 'DIFERENTE')
            wse.cell(i, 4, str(detalle) if any(detalle.values()) else 'idéntico en las 3 herramientas' if ok else '')
            i += 1

    # --- Resumen ---
    ws0.column_dimensions['A'].width = 120
    lineas = [
        ('Reporte comparativo del benchmark Pandas vs Polars vs PySpark — Emergencias 123 Bogotá (U2)', TITULO),
        ('Fuente de datos: resultados/mediciones/benchmark.jsonl (ejecución real en Google Colab; '
         f"{entorno.get('fecha', '')}). Hoja Mediciones = valores crudos; el resto son fórmulas.", NORMAL),
        (f"Entorno: Python {entorno.get('python')}, pandas {entorno.get('pandas')}, polars {entorno.get('polars')}, "
         f"pyspark {entorno.get('pyspark')}, {entorno.get('java')}, {entorno.get('vcpu')} vCPU, "
         f"{entorno.get('ram_gb')} GB RAM. Spark en modo local (un nodo), no clúster.", NORMAL),
        ('Datos: 3 CSV mensuales (jul-sep 2026), 27 434 registros. Filtro USAQUEN+CHAPINERO = 1 762 registros. '
         'Catálogo de tipos DERIVADO de los datos (no oficial).', NORMAL),
        ('Metodología: measure_performance(); proceso nuevo por repetición; 1 calentamiento descartado + 5 medidas; '
         'orden rotado; reloj perf_counter_ns; memoria muestreada cada 20 ms (pico = máximo de muestras).', NORMAL),
        ('Modos: por_operacion (cada operación materializada; Spark con cache()+count()), extremo_a_extremo '
         '(mínima materialización) y extremo_a_extremo_caliente (complementario: 2.ª pasada en el mismo proceso).', NORMAL),
        ('Hojas: Mediciones · Promedios · LOC · Reglas · Matriz · Graficos · Equivalencia.', NORMAL),
        ('Limitaciones: volumen pequeño (dominan costes fijos); % de memoria del sistema incluye otros procesos de Colab; '
         'RSS incluye páginas compartidas; muestreo de 20 ms puede perder picos muy breves.', NORMAL),
    ]
    for i, (texto, fuente) in enumerate(lineas, 1):
        _texto(ws0, i, texto, fuente)
    _fuente_por_defecto(wb)
    wb.save(ruta)
    return ruta


def reporte_poc(poc, controles, ruta, entorno):
    """poc: filas de poc.jsonl (estado ok). controles: lista de controles de la última ejecución de Spark."""
    wb = Workbook()
    ws0 = wb.active
    ws0.title = 'Resumen'
    principal = poc[poc['etiqueta'].isna()].sort_values(['herramienta', 'ejecucion'])
    cols = ['herramienta', 'ejecucion', 'ts_inicio', 'tiempo_total_s', 'tiempo_inicio_sesion_s', 'tiempo_verificacion_s',
            'mem_sis_base_pct', 'mem_sis_pico_pct', 'rss_base_mb', 'rss_pico_mb', 'leidos', 'aceptados', 'rechazados',
            'throughput_reg_min', 'tasa_validaciones_pct', 'registros_validos_pct', 'controles_aprobados',
            'controles_evaluados', 'errores', 'parquet_archivos', 'parquet_bytes']
    wse = wb.create_sheet('Ejecuciones')
    _cabecera(wse, 1, cols, [11, 9, 20] + [13] * (len(cols) - 3))
    for i, fila in enumerate(principal[cols].itertuples(index=False), 2):
        for j, v in enumerate(fila, 1):
            wse.cell(i, j, v.item() if hasattr(v, 'item') else v)
    n = len(principal) + 1
    # Throughput recalculado por fórmula a partir de leídos y tiempo (comprueba la métrica guardada)
    wse.cell(1, len(cols) + 1, 'throughput (fórmula) reg/min').font = NEGRITA
    for i in range(2, n + 1):
        wse.cell(i, len(cols) + 1, f'=K{i}/(D{i}/60)').number_format = '#,##0'

    wsp = wb.create_sheet('Promedios')
    metricas = [('Tiempo total carga→exportación (s)', 'D', '0.000'), ('Arranque de sesión (s, aparte)', 'E', '0.000'),
                ('Memoria sistema pico (%)', 'H', '0.0'), ('RSS pico proceso+JVM (MB)', 'J', '0.0'),
                ('Throughput (registros/min)', 'N', '#,##0'), ('Tasa de éxito de validaciones (%)', 'O', '0.00'),
                ('Registros conservados (%)', 'P', '0.0000'), ('Registros procesados (leídos)', 'K', '#,##0'),
                ('Errores (controles fallidos)', 'S', '0')]
    _cabecera(wsp, 1, ['Métrica', 'PySpark media', 'PySpark desv. est.', 'Pandas media', 'Pandas desv. est.',
                       'PySpark / Pandas'], [36, 14, 16, 14, 16, 16])
    for i, (nombre, col, fmt) in enumerate(metricas, 2):
        wsp.cell(i, 1, nombre)
        for k, h in enumerate(('spark', 'pandas')):
            rango, crit = f'Ejecuciones!${col}$2:${col}${n}', f'Ejecuciones!$A$2:$A${n},"{h}"'
            media = wsp.cell(i, 2 + 2 * k, f'=AVERAGEIFS({rango},{crit})')
            media.number_format = fmt
            ref_media = f'{get_column_letter(2 + 2 * k)}{i}'
            desv = wsp.cell(i, 3 + 2 * k, f'=IF(COUNTIFS({crit})>1,SQRT(SUMPRODUCT((Ejecuciones!$A$2:$A${n}="{h}")*'
                                          f'({rango}-{ref_media})^2)/(COUNTIFS({crit})-1)),"")')
            desv.number_format = fmt
        wsp.cell(i, 6, f'=IFERROR(B{i}/D{i},"n/a (división entre 0)")').number_format = '0.00"x"'
    _texto(wsp, len(metricas) + 3, 'PySpark / Pandas > 1 significa que PySpark obtiene un valor mayor (en tiempo y '
           'memoria, peor; en throughput, mejor). Las cifras provienen de 3 ejecuciones por herramienta en Colab, '
           'cada una en un proceso nuevo.')
    wsp.merge_cells(start_row=len(metricas) + 3, start_column=1, end_row=len(metricas) + 3, end_column=6)
    wsp.row_dimensions[len(metricas) + 3].height = 45

    g = BarChart()
    g.type, g.title, g.y_axis.title = 'bar', 'Tiempo total medio (s): PySpark vs Pandas', 'segundos'
    g.add_data(Reference(wsp, min_col=2, max_col=2, min_row=1, max_row=2), titles_from_data=True)
    g.add_data(Reference(wsp, min_col=4, max_col=4, min_row=1, max_row=2), titles_from_data=True)
    g.set_categories(Reference(wsp, min_col=1, min_row=2, max_row=2))
    g.height, g.width = 6.5, 15
    wsp.add_chart(g, 'H2')
    g2 = BarChart()
    g2.type, g2.title, g2.y_axis.title = 'bar', 'RSS pico medio (MB): PySpark vs Pandas', 'MB'
    g2.add_data(Reference(wsp, min_col=2, max_col=2, min_row=4, max_row=5), titles_from_data=False)
    g2.add_data(Reference(wsp, min_col=4, max_col=4, min_row=4, max_row=5), titles_from_data=False)
    g2.set_categories(Reference(wsp, min_col=1, min_row=5, max_row=5))
    g2.height, g2.width = 6.5, 15
    wsp.add_chart(g2, 'H17')

    wsv = wb.create_sheet('Validaciones')
    _cabecera(wsv, 1, ['Id', 'Severidad', 'Descripción', 'Valor', 'Esperado', 'Aprobado'], [6, 12, 60, 30, 22, 10])
    for i, c in enumerate(controles, 2):
        for j, k in enumerate(('id', 'severidad', 'descripcion', 'valor', 'esperado', 'aprobado'), 1):
            v = c[k]
            wsv.cell(i, j, v if isinstance(v, (int, float, bool)) else str(v))
    fin = len(controles) + 1
    wsv.cell(fin + 2, 3, 'Controles evaluados (bloqueante + advertencia)').font = NEGRITA
    wsv.cell(fin + 2, 6, f'=COUNTIF(B2:B{fin},"bloqueante")+COUNTIF(B2:B{fin},"advertencia")')
    wsv.cell(fin + 3, 3, 'Controles aprobados').font = NEGRITA
    wsv.cell(fin + 3, 6, f'=COUNTIFS(B2:B{fin},"bloqueante",F2:F{fin},TRUE)+COUNTIFS(B2:B{fin},"advertencia",F2:F{fin},TRUE)')
    wsv.cell(fin + 4, 3, 'Tasa de éxito de validaciones = aprobados / evaluados').font = NEGRITA
    wsv.cell(fin + 4, 6, f'=F{fin + 3}/F{fin + 2}').number_format = '0.00%'

    variante = poc[poc['etiqueta'] == 'variante_periodo_localidad']
    wsq = wb.create_sheet('Particionamiento')
    _cabecera(wsq, 1, ['Estrategia', 'Archivos Parquet', 'Bytes', 'KB por archivo', 'Tiempo total (s)'], [22, 16, 14, 14, 16])
    ultima_spark = principal[principal['herramienta'] == 'spark'].tail(1)
    for i, (nombre, d) in enumerate((('periodo', ultima_spark), ('periodo/localidad', variante)), 2):
        if len(d):
            r = d.iloc[0]
            wsq.cell(i, 1, nombre)
            wsq.cell(i, 2, int(r['parquet_archivos']))
            wsq.cell(i, 3, int(r['parquet_bytes']))
            wsq.cell(i, 4, f'=C{i}/B{i}/1024').number_format = '0.0'
            wsq.cell(i, 5, float(r['tiempo_total_s'])).number_format = '0.00'
    _texto(wsq, 5, 'La variante periodo/localidad es una sola ejecución de referencia (no entra en los promedios).')

    ws0.column_dimensions['A'].width = 120
    for i, (texto, fuente) in enumerate((
        ('Reporte de métricas del PoC PySpark (3 ejecuciones) y comparación con Pandas — Emergencias 123 (U2)', TITULO),
        (f"Fuente: resultados/mediciones/poc.jsonl (ejecución real en Google Colab, {entorno.get('fecha', '')}). "
         'Hoja Ejecuciones = valores crudos; Promedios y tasas = fórmulas.', NORMAL),
        ('Tiempo total = carga → exportación (sin arranque de la SparkSession, que se reporta aparte). Throughput = '
         'registros leídos / minuto. Memoria del sistema = pico muestreado de psutil.virtual_memory().percent; RSS = '
         'proceso + hijos (JVM).', NORMAL),
        ('Tasa de éxito de validaciones = controles aprobados / controles evaluados (bloqueantes + advertencias). '
         'Registros conservados = conservados / leídos; solo se eliminan las copias duplicadas exactas (columnas '
         '"aceptados" = conservados y "rechazados" = copias eliminadas). Son métricas distintas.', NORMAL),
        (f"Entorno: {entorno.get('vcpu')} vCPU, {entorno.get('ram_gb')} GB RAM, pyspark {entorno.get('pyspark')}, "
         f"pandas {entorno.get('pandas')}; Spark local (un nodo).", NORMAL),
    ), 1):
        _texto(ws0, i, texto, fuente)
    _fuente_por_defecto(wb)
    wb.save(ruta)
    return ruta
