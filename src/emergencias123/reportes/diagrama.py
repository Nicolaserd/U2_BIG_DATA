"""Diagrama de arquitectura del PoC desde UNA especificación: fuente editable .drawio + PNG de alta resolución.

Las coordenadas están en unidades de draw.io (px); el PNG se dibuja con matplotlib usando las mismas
coordenadas, así ambas salidas representan exactamente lo mismo.
"""
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ANCHO, ALTO = 1700, 980
CARRILES = [  # id, título, x, ancho, color de fondo
    ('ingesta', '1 · Ingesta', 20, 330, '#EEF4FB'),
    ('proc', '2 · Procesamiento (PySpark 4.0, local[2] en Colab)', 370, 520, '#EEF8F3'),
    ('alm', '3 · Almacenamiento (Google Drive)', 910, 360, '#FDF3EC'),
    ('sal', '4 · Salidas, monitoreo y KPIs', 1290, 390, '#F4F2FB'),
]
COLOR = {'dato': '#2a78d6', 'proc': '#1a8a62', 'alm': '#c4561f', 'sal': '#6250d6', 'conf': '#7a7873'}
NODOS = [  # id, x, y, ancho, alto, tipo, texto
    ('fuente', 40, 90, 290, 90, 'dato', 'Línea 123 Bogotá\n3 CSV mensuales (jul–sep 2026)\n27 434 registros · ~3 MB · «;» · UTF-8'),
    ('drive_in', 40, 230, 290, 80, 'alm', 'Google Drive\nMyDrive/BigData_U2/datos\n(huella SHA-256 verificada)'),
    ('montaje', 40, 360, 290, 80, 'dato', 'Colab VM (2 vCPU, 12.7 GB)\nDrive montado en /content/drive'),
    ('config', 40, 490, 290, 120, 'conf', 'Configuración versionada\nconfig.yaml · esquema · periodos\nlocalidades_bogota.csv (oficial)\ncatalogo_tipos_derivado.csv\n(derivado, NO oficial)'),
    ('codigo', 40, 660, 290, 80, 'conf', 'Código: 2 notebooks de Colab\n(MyDrive/BigData_U2/*.ipynb)'),
    ('prev', 390, 90, 230, 80, 'proc', 'Prevalidación\narchivos · columnas · filas'),
    ('lectura', 640, 90, 230, 80, 'proc', 'Lectura CSV\nesquema explícito (texto)\n+ _corrupt_record'),
    ('limpieza', 390, 200, 230, 80, 'proc', 'Nulos explícitos (N/A → null)\nsin imputación · procedencia\n(archivo_origen, periodo)'),
    ('tipos', 640, 200, 230, 80, 'proc', 'Tipado seguro (ANSI)\ntry_to_timestamp · try_cast\nedad en años según UNIDAD'),
    ('estd', 390, 320, 230, 80, 'proc', 'Estandarización\nlocalidad · código de tipo\nprioridad · género'),
    ('reglas', 640, 320, 230, 80, 'proc', 'Reglas de calidad\nanomalías marcadas (se conservan)\nduplicados exactos eliminados'),
    ('join', 390, 440, 230, 80, 'proc', 'Broadcast join\ncatálogo de tipos (23 filas)\nm:1, sin multiplicar filas'),
    ('agg', 640, 440, 230, 80, 'proc', 'Agregados\nperiodo×localidad×tipo\nperiodo×prioridad · diario'),
    ('escritura', 390, 560, 480, 70, 'proc', 'Escritura Parquet particionada por mes y localidad\nrepartition / partitionBy(periodo, cod_localidad)'),
    ('valid', 390, 670, 480, 80, 'proc', 'Validación de salidas V01–V20 (relectura de Parquet)\ntasa = aprobados / evaluados · conservados / leídos'),
    ('det', 930, 90, 320, 90, 'alm', 'parquet/poc/spark/eN/detalle/\nperiodo=2026-07…09 / cod_localidad=1…19\n(columnas tipadas)'),
    ('aggp', 930, 230, 320, 80, 'alm', 'parquet/poc/spark/eN/agregados/\n3 tablas resumidas'),
    ('rech', 930, 360, 320, 80, 'alm', 'parquet/poc/spark/eN/duplicados_eliminados/\ncopias exactas (100 % de atributos)'),
    ('med', 930, 490, 320, 80, 'alm', 'resultados/mediciones/\nbenchmark.jsonl · poc.jsonl · entorno'),
    ('logs', 930, 620, 320, 70, 'alm', 'resultados/logs/\nvalidacion_poc_spark.txt'),
    ('monitor', 1310, 90, 350, 110, 'sal', 'Monitoreo (MemorySampler, 20 ms)\n% RAM del sistema (psutil)\nRSS proceso + JVM · tiempo perf_counter'),
    ('kpi', 1310, 250, 350, 110, 'sal', 'KPIs del PoC\ntiempo total (s) · memoria pico (%)\nthroughput (registros/min)\ntasa de validaciones (%)'),
    ('informes', 1310, 410, 350, 100, 'sal', 'Informes\nxlsx (fórmulas) · docx · gráficos PNG\nnotebooks ejecutados en Colab'),
    ('consumo', 1310, 560, 350, 100, 'sal', 'Consumo analítico\nconsultas por periodo/localidad\n(poda de particiones + estadísticas)'),
]
ARISTAS = [  # origen, destino, etiqueta
    ('fuente', 'drive_in', 'carga'), ('drive_in', 'montaje', 'FUSE'), ('montaje', 'prev', ''),
    ('config', 'prev', ''), ('codigo', 'valid', ''),
    ('prev', 'lectura', ''), ('lectura', 'limpieza', ''), ('limpieza', 'tipos', ''), ('tipos', 'estd', ''),
    ('estd', 'reglas', ''), ('reglas', 'join', 'conservados'), ('join', 'agg', ''), ('agg', 'escritura', ''),
    ('escritura', 'valid', ''), ('escritura', 'det', ''), ('escritura', 'aggp', ''), ('reglas', 'rech', 'duplicados'),
    ('valid', 'logs', ''), ('valid', 'med', 'métricas'), ('med', 'kpi', ''), ('logs', 'kpi', ''),
    ('med', 'informes', ''), ('det', 'consumo', ''), ('monitor', 'kpi', ''),
]
NOTA = ('Ejecución real implementada: Spark en modo local dentro de UNA VM de Colab (no es un clúster). '
        'Despliegue distribuido propuesto: mismo código en Databricks / clúster Spark con almacenamiento de objetos.')


def _nodo(nid):
    return next(n for n in NODOS if n[0] == nid)


def _anclas(a, b):
    """Puntos de salida/entrada entre dos cajas (lado más cercano)."""
    _, ax, ay, aw, ah, *_ = a
    _, bx, by, bw, bh, *_ = b
    if bx >= ax + aw:  # destino a la derecha
        return (ax + aw, ay + ah / 2), (bx, by + bh / 2)
    if bx + bw <= ax:  # destino a la izquierda
        return (ax, ay + ah / 2), (bx + bw, by + bh / 2)
    if by >= ay + ah:  # destino abajo
        return (ax + aw / 2, ay + ah), (bx + bw / 2, by)
    return (ax + aw / 2, ay), (bx + bw / 2, by + bh)


def escribir_drawio(ruta):
    celdas = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for cid, titulo, x, w, fondo in CARRILES:
        celdas.append(f'<mxCell id="carril_{cid}" value="{escape(titulo)}" style="swimlane;startSize=36;fillColor={fondo};'
                      f'strokeColor=#BFBFBF;fontStyle=1;fontSize=15;rounded=1;" vertex="1" parent="1">'
                      f'<mxGeometry x="{x}" y="20" width="{w}" height="{ALTO - 110}" as="geometry"/></mxCell>')
    for nid, x, y, w, h, tipo, texto in NODOS:
        valor = escape(texto).replace('\n', '&#xa;')
        celdas.append(f'<mxCell id="{nid}" value="{valor}" style="rounded=1;whiteSpace=wrap;html=0;fillColor=#FFFFFF;'
                      f'strokeColor={COLOR[tipo]};strokeWidth=2;fontSize=12;" vertex="1" parent="1">'
                      f'<mxGeometry x="{x}" y="{y + 20}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    for i, (o, d, etiqueta) in enumerate(ARISTAS):
        celdas.append(f'<mxCell id="e{i}" value="{escape(etiqueta)}" style="endArrow=block;html=0;strokeColor=#52514e;'
                      f'fontSize=11;edgeStyle=orthogonalEdgeStyle;rounded=1;" edge="1" parent="1" source="{o}" target="{d}">'
                      f'<mxGeometry relative="1" as="geometry"/></mxCell>')
    celdas.append(f'<mxCell id="nota" value="{escape(NOTA)}" style="text;html=0;fontSize=12;fontStyle=2;align=left;" '
                  f'vertex="1" parent="1"><mxGeometry x="20" y="{ALTO - 80}" width="{ANCHO - 40}" height="40" as="geometry"/></mxCell>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="emergencias123" type="device">'
           '<diagram id="arquitectura" name="Arquitectura PoC Emergencias 123">'
           f'<mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" page="1" pageWidth="{ANCHO}" pageHeight="{ALTO}">'
           f'<root>{"".join(celdas)}</root></mxGraphModel></diagram></mxfile>\n')
    ruta.write_text(xml, encoding='utf-8')
    return ruta


def escribir_png(ruta, dpi=300):
    fig = plt.figure(figsize=(ANCHO / 100, ALTO / 100), facecolor='#FCFCFB')
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, ANCHO)
    ax.set_ylim(ALTO, 0)
    ax.axis('off')
    ax.text(20, 8, 'Arquitectura del PoC — Pipeline PySpark de Emergencias 123 Bogotá (U2)', fontsize=17,
            fontweight='bold', va='top', color='#0b0b0b')
    for _, titulo, x, w, fondo in CARRILES:
        ax.add_patch(FancyBboxPatch((x, 40), w, ALTO - 130, boxstyle='round,pad=0,rounding_size=12',
                                    facecolor=fondo, edgecolor='#BFBFBF', linewidth=1))
        ax.text(x + 12, 62, titulo, fontsize=12.5, fontweight='bold', va='center', color='#0b0b0b')
    for nid, x, y, w, h, tipo, texto in NODOS:
        ax.add_patch(FancyBboxPatch((x, y + 20), w, h, boxstyle='round,pad=0,rounding_size=10',
                                    facecolor='#FFFFFF', edgecolor=COLOR[tipo], linewidth=2))
        lineas = texto.split('\n')
        paso = 15.5
        y0 = y + 20 + h / 2 - (len(lineas) - 1) * paso / 2
        for k, linea in enumerate(lineas):
            ax.text(x + w / 2, y0 + k * paso, linea, ha='center', va='center', fontsize=9.0,
                    color='#0b0b0b' if k == 0 else '#3a3936', fontweight='bold' if k == 0 else 'normal')
    for o, d, etiqueta in ARISTAS:
        (x1, y1), (x2, y2) = _anclas(_nodo(o), _nodo(d))
        ax.add_patch(FancyArrowPatch((x1, y1 + 20), (x2, y2 + 20), arrowstyle='-|>', mutation_scale=13,
                                     color='#52514e', linewidth=1.3, connectionstyle='arc3,rad=0.0', shrinkA=2, shrinkB=2))
        if etiqueta:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 14, etiqueta, fontsize=8.5, color='#52514e', ha='center',
                    bbox={'facecolor': '#FCFCFB', 'edgecolor': 'none', 'pad': 1})
    leyenda = [('Datos/infraestructura', 'dato'), ('Procesamiento Spark', 'proc'), ('Almacenamiento', 'alm'),
               ('Salidas/monitoreo', 'sal'), ('Configuración', 'conf')]
    for i, (nombre, tipo) in enumerate(leyenda):
        x = 20 + i * 210
        ax.add_patch(FancyBboxPatch((x, ALTO - 60), 18, 14, boxstyle='round,pad=0,rounding_size=3',
                                    facecolor='#FFFFFF', edgecolor=COLOR[tipo], linewidth=2))
        ax.text(x + 26, ALTO - 53, nombre, fontsize=9.5, va='center', color='#52514e')
    ax.text(20, ALTO - 22, NOTA, fontsize=10, style='italic', color='#52514e', va='center')
    fig.savefig(ruta, dpi=dpi, facecolor='#FCFCFB')
    plt.close(fig)
    return ruta
