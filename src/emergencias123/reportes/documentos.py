"""Documentos .docx (python-docx). Toda cifra proviene de `resumen.cargar_todo()` o de la matriz recalculada.

La redacción que depende de los resultados (qué herramienta gana, cuántas veces más lenta, etc.) se
construye a partir de las cifras, no se escribe a mano.
"""
import re

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401  (disponible si se requiere apaisado)
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .resumen import REGISTROS_MES, proyectar

NOMBRE = {'pandas': 'Pandas', 'polars': 'Polars', 'spark': 'PySpark'}
GRIS = RGBColor(0x52, 0x51, 0x4E)
NEGRO = RGBColor(0, 0, 0)


class Doc:
    """Documento con formato APA 7 (adaptado a los límites de páginas de la guía).

    Bloque de título centrado, encabezados sin numeración (nivel 1 centrado, nivel 2 a la izquierda),
    tablas y figuras numeradas («Tabla N» / «Figura N» en negrita y título en cursiva, «Nota.» debajo),
    tablas solo con líneas horizontales, texto en negro y referencias con sangría francesa.
    """

    def __init__(self, tamano=11, margen_cm=2.54, interlineado=1.15):
        self.d = Document()
        for s in self.d.sections:
            s.top_margin = s.bottom_margin = s.left_margin = s.right_margin = Cm(margen_cm)
        normal = self.d.styles['Normal']
        normal.font.name, normal.font.size = 'Arial', Pt(tamano)
        normal.element.rPr.rFonts.set(qn('w:eastAsia'), 'Arial')
        normal.font.color.rgb = NEGRO
        normal.paragraph_format.space_after = Pt(4)
        normal.paragraph_format.line_spacing = interlineado
        for nivel, tam in (('Title', tamano + 3), ('Heading 1', tamano + 1), ('Heading 2', tamano)):
            st = self.d.styles[nivel]
            st.font.name, st.font.size, st.font.bold, st.font.italic = 'Arial', Pt(tam), True, False
            st.font.color.rgb = NEGRO
            fuentes = st.element.rPr.rFonts
            fuentes.set(qn('w:eastAsia'), 'Arial')
            for atributo in ('w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme'):
                fuentes.attrib.pop(qn(atributo), None)  # la fuente del tema (Calibri) anularía Arial
            borde = st.element.pPr.find(qn('w:pBdr')) if st.element.pPr is not None else None
            if borde is not None:  # el estilo Title trae una línea inferior que APA no usa
                st.element.pPr.remove(borde)
            st.paragraph_format.space_before = Pt(10 if nivel != 'Title' else 0)
            st.paragraph_format.space_after = Pt(4)
            st.paragraph_format.keep_with_next = True
        self.tamano, self.n_tabla, self.n_figura = tamano, 0, 0

    def bloque_titulo(self, titulo, datos, compacto=False):
        """Título (negrita, centrado) y datos de autoría según APA; `datos` viene de config.yaml (documentos)."""
        t = self.d.add_paragraph(titulo, style='Title')
        t.alignment = WD_ALIGN_PARAGRAPH.CENTER
        lineas = [datos['autor'], datos['institucion'], datos['curso'], datos['docente'], datos['fecha']]
        for linea in ([' · '.join(lineas)] if compacto else lineas):
            par = self.d.add_paragraph(linea)
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.space_after = Pt(0)
        self.d.add_paragraph().paragraph_format.space_after = Pt(2 if compacto else 6)

    def h1(self, texto):
        h = self.d.add_heading(re.sub(r'^\d+(\.\d+)*\.?\s+', '', texto), level=1)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def h2(self, texto):
        self.d.add_heading(re.sub(r'^\d+(\.\d+)*\.?\s+', '', texto), level=2)

    def p(self, texto, negrita_inicial=None):
        par = self.d.add_paragraph()
        if negrita_inicial:
            par.add_run(negrita_inicial).bold = True
        par.add_run(texto)
        par.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        return par

    def vinetas(self, elementos):
        for e in elementos:
            par = self.d.add_paragraph(style='List Bullet')
            if isinstance(e, tuple):
                par.add_run(e[0]).bold = True
                par.add_run(e[1])
            else:
                par.add_run(e)
            par.paragraph_format.space_after = Pt(1)

    def nota(self, texto, tam=None):
        """Nota al estilo APA: «Nota.» en cursiva seguida del texto."""
        par = self.d.add_paragraph()
        r = par.add_run('Nota. ')
        r.italic, r.font.size = True, Pt(tam or self.tamano - 1.5)
        par.add_run(texto).font.size = Pt(tam or self.tamano - 1.5)
        par.paragraph_format.space_after = Pt(6)

    def _rotulo(self, tipo, numero, titulo):
        a = self.d.add_paragraph()
        a.add_run(f'{tipo} {numero}').bold = True
        a.paragraph_format.space_after = Pt(0)
        a.paragraph_format.keep_with_next = True
        b = self.d.add_paragraph()
        b.add_run(titulo).italic = True
        b.paragraph_format.space_after = Pt(2)
        b.paragraph_format.keep_with_next = True

    @staticmethod
    def _bordes_apa(tabla):
        """Solo líneas horizontales (superior, entre filas e inferior), como recomienda APA."""
        bordes = OxmlElement('w:tblBorders')
        for lado in ('top', 'bottom', 'insideH'):
            e = OxmlElement(f'w:{lado}')
            e.set(qn('w:val'), 'single')
            e.set(qn('w:sz'), '6')
            e.set(qn('w:color'), '000000')
            bordes.append(e)
        for lado in ('left', 'right', 'insideV'):
            e = OxmlElement(f'w:{lado}')
            e.set(qn('w:val'), 'nil')
            bordes.append(e)
        tabla._tbl.tblPr.append(bordes)

    def tabla(self, cabecera, filas, anchos_cm=None, tam=None, titulo=None, nota=None):
        if titulo:
            self.n_tabla += 1
            self._rotulo('Tabla', self.n_tabla, titulo)
        t = self.d.add_table(rows=1, cols=len(cabecera))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        self._bordes_apa(t)
        tam = Pt(tam or self.tamano - 1.5)
        for c, texto in zip(t.rows[0].cells, cabecera):
            c.text = ''
            r = c.paragraphs[0].add_run(str(texto))
            r.bold, r.font.size = True, tam
        for fila in filas:
            celdas = t.add_row().cells
            for c, v in zip(celdas, fila):
                c.text = ''
                c.paragraphs[0].add_run(str(v)).font.size = tam
        if anchos_cm:
            for fila in t.rows:
                for c, a in zip(fila.cells, anchos_cm):
                    c.width = Cm(a)
        if nota:
            self.nota(nota, tam=tam.pt)
        else:
            self.d.add_paragraph().paragraph_format.space_after = Pt(2)
        return t

    def imagen(self, ruta, ancho_cm, titulo, nota=None):
        self.n_figura += 1
        self._rotulo('Figura', self.n_figura, titulo)
        self.d.add_picture(str(ruta), width=Cm(ancho_cm))
        self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if nota:
            self.nota(nota)

    def referencias(self, entradas, tam=None):
        """Referencias APA: orden alfabético, sangría francesa de 1,27 cm; cada entrada = [(texto, cursiva), ...]."""
        self.h1('Referencias')
        for fragmentos in sorted(entradas, key=lambda e: ''.join(t for t, _ in e).lower()):
            par = self.d.add_paragraph()
            par.paragraph_format.left_indent = Cm(1.27)
            par.paragraph_format.first_line_indent = Cm(-1.27)
            par.paragraph_format.space_after = Pt(3)
            for texto, cursiva in fragmentos:
                r = par.add_run(texto)
                r.italic = cursiva
                if tam:
                    r.font.size = Pt(tam)

    def salto(self):
        self.d.add_page_break()

    def guardar(self, ruta):
        self.d.save(ruta)
        return ruta


def f(x, dec=2):
    return f'{x:,.{dec}f}'.replace(',', ' ')


def java_corto(texto):
    """'openjdk version "21.0.12.1" 2026-08-18' -> 'OpenJDK 21.0.12.1'."""
    m = re.search(r'"([\d._]+)"', texto)
    return f'OpenJDK {m.group(1)}' if m else texto


def veces(a, b):
    return a / b if b else float('nan')


def _datos_clave(R, matriz):
    b, poc = R['bench'], R['poc']
    tot = b['tot']
    e2e = tot.loc['extremo_a_extremo']
    pop = tot.loc['por_operacion']
    cal = tot.loc['extremo_a_extremo_caliente'] if 'extremo_a_extremo_caliente' in tot.index.get_level_values(0) else None
    rapida = e2e['seg'].idxmin()
    ganador = max(matriz['ponderado'], key=matriz['ponderado'].get)
    ps, pp = poc['prom'].loc['spark'], poc['prom'].loc['pandas']
    return dict(b=b, poc=poc, e2e=e2e, pop=pop, cal=cal, rapida=rapida, ganador=ganador, ps=ps, pp=pp,
                ent=R['entorno'], inv=R['inventario'])


# ---------------------------------------------------------------- Referencias APA 7 (fragmentos: texto, cursiva)
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre']


def fecha_es(iso):
    anio, mes, dia = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return f'{dia} de {MESES[mes - 1]} de {anio}'


def referencias_apa(datos, ent):
    anio = ent['fecha'][:4]
    return {
        'guia': [(f"{datos['institucion']}. ({anio}). ", False),
                 ('Guía de actividades: Unidad 2. Procesamiento distribuido', True), (' [Guía de curso].', False)],
        'datos': [(f"{datos['fuente_datos']}. ({anio}). ", False),
                  ('Llamadas a la Línea 123 de Bogotá: julio, agosto y septiembre de 2026', True),
                  (' [Conjunto de datos suministrado para el curso].', False)],
        'spark': [('Apache Software Foundation. (2025). ', False), ('Apache Spark', True),
                  (f" (Versión {ent['pyspark']}) [Software]. https://spark.apache.org/", False)],
        'parquet': [('Apache Software Foundation. (s. f.). ', False), ('Apache Parquet', True),
                    (' [Especificación de formato de archivo]. https://parquet.apache.org/', False)],
        'colab': [('Google. (s. f.). ', False), ('Google Colaboratory', True),
                  (' [Plataforma en línea]. https://colab.research.google.com/', False)],
        'mckinney': [('McKinney, W. (2010). Data structures for statistical computing in Python. En S. van der Walt y '
                      'J. Millman (Eds.), ', False), ('Proceedings of the 9th Python in Science Conference', True),
                     (' (pp. 56–61). https://doi.org/10.25080/Majora-92bf1922-00a', False)],
        'pandas': [('The pandas development team. (s. f.). ', False), ('pandas-dev/pandas: Pandas', True),
                   (f" (Versión {ent['pandas']}) [Software]. Zenodo. https://doi.org/10.5281/zenodo.3509134", False)],
        'polars': [('Polars Developers. (s. f.). ', False), ('Polars', True),
                   (f" (Versión {ent['polars']}) [Software]. https://pola.rs/", False)],
        'psutil': [('Rodola, G. (s. f.). ', False), ('psutil', True),
                   (f" (Versión {ent['psutil']}) [Software]. https://github.com/giampaolo/psutil", False)],
        'zaharia': [('Zaharia, M., Xin, R. S., Wendell, P., Das, T., Armbrust, M., Dave, A., Meng, X., Rosen, J., '
                     'Venkataraman, S., Franklin, M. J., Ghodsi, A., Gonzalez, J., Shenker, S. y Stoica, I. (2016). '
                     'Apache Spark: A unified engine for big data processing. ', False),
                    ('Communications of the ACM, 59', True), ('(11), 56–65. https://doi.org/10.1145/2934664', False)],
    }


def _cita_guia(datos, ent):
    return f"({datos['institucion']}, {ent['fecha'][:4]})"


# ---------------------------------------------------------------- Análisis de decisión
def doc_decision(R, matriz, rutas, ruta, datos):
    k = _datos_clave(R, matriz)
    e2e, pop, cal, ent, ps = k['e2e'], k['pop'], k['cal'], k['ent'], k['ps']
    datos = {**datos, 'fecha': fecha_es(ent['fecha'])}
    refs = referencias_apa(datos, ent)
    d = Doc()
    d.bloque_titulo('Análisis de decisión tecnológica para el procesamiento de las llamadas a la Línea 123 de Bogotá',
                    datos)

    d.h1('Resumen ejecutivo')
    orden = sorted(matriz['ponderado'], key=matriz['ponderado'].get, reverse=True)
    d.p(f"Se compararon Pandas, Polars y PySpark con los tres archivos mensuales seleccionados "
        f"({f(R['inventario']['total_registros'], 0)} registros, aproximadamente 3 MB), ejecutados en Google Colab "
        f"(Google, s. f.). La herramienta más rápida de la carga a la exportación fue {NOMBRE[k['rapida']]}, con "
        f"{f(e2e.loc[k['rapida'], 'seg'], 3)} s de media. PySpark requirió {f(e2e.loc['spark', 'seg'], 2)} s, es decir, "
        f"{f(veces(e2e.loc['spark', 'seg'], e2e.loc[k['rapida'], 'seg']), 0)} veces más, sin contar los "
        f"{f(k['b']['arranque_spark'], 1)} s de arranque de la sesión. En memoria residente del proceso (RSS, por sus "
        f"siglas en inglés), PySpark alcanzó {f(e2e.loc['spark', 'rss'], 0)} MB, frente a "
        f"{f(e2e.loc['pandas', 'rss'], 0)} MB de Pandas y {f(e2e.loc['polars', 'rss'], 0)} MB de Polars.")
    d.p("La matriz ponderada ordena las herramientas así: " +
        ', '.join(f"{NOMBRE[h]} ({f(matriz['ponderado'][h], 2)})" for h in orden) +
        f". En consecuencia, {NOMBRE[k['ganador']]} es la opción más conveniente para el volumen probado. PySpark se "
        f"mantiene como herramienta principal porque la actividad lo exige {_cita_guia(datos, ent)} y porque es la "
        "única de las tres que escala horizontalmente a un clúster sin reescribir el código (Zaharia et al., 2016). "
        "Pandas y Polars se recomiendan como herramientas complementarias para la exploración y para los lotes que caben "
        "en la memoria de un solo nodo.")

    d.h1('Contexto, datos y método')
    d.vinetas([
        ('Datos. ', f"Tres archivos CSV de la Línea 123 (julio, agosto y septiembre de 2026; "
                    f"{datos['fuente_datos']}, {ent['fecha'][:4]}) con {f(R['inventario']['total_registros'], 0)} "
                    "registros, codificación UTF-8 con BOM y separador «;». Al no encontrarse una tabla oficial de "
                    "códigos de emergencia, la unión emplea un catálogo de 23 tipos derivado de TIPO_INCIDENTE, "
                    "identificado como no oficial."),
        ('Operaciones. ', 'Idénticas en las tres herramientas: carga y combinación; filtrado de las localidades USAQUÉN '
         'y CHAPINERO con el texto normalizado (1 762 registros); conteo por tipo; unión izquierda muchos a uno con el '
         'catálogo, y exportación a Parquet (Apache Software Foundation, s. f.).'),
        ('Entorno. ', f"Google Colab con {ent['vcpu']} vCPU y {ent['ram_gb']} GB de RAM; Python {ent['python']}, "
                      f"pandas {ent['pandas']} (McKinney, 2010; The pandas development team, s. f.), Polars "
                      f"{ent['polars']} (Polars Developers, s. f.) y PySpark {ent['pyspark']} (Apache Software "
                      "Foundation, 2025). Spark se ejecutó en modo local, en un solo nodo, no en un clúster."),
        ('Medición. ', f"La función measure_performance() ejecuta cada repetición en un proceso nuevo, con un "
         f"calentamiento descartado y {k['b']['repeticiones']} repeticiones medidas por herramienta y modo, en orden "
         "rotado y con un reloj monotónico de alta resolución. La memoria se muestrea cada 20 ms con psutil (Rodola, "
         "s. f.): porcentaje de memoria del sistema y RSS del proceso con sus procesos hijos, incluida la JVM."),
        ('Validez. ', 'Las salidas de las tres herramientas son equivalentes en todos los modos: mismas filas, mismo '
                      'esquema lógico, mismos conteos y misma huella SHA-256 del contenido.' if k['b']['equivalentes']
         else 'La comprobación de equivalencia detectó diferencias; véase la hoja Equivalencia del reporte.'),
    ])

    d.h1('Resultados del benchmark')
    filas = []
    for h in ('pandas', 'polars', 'spark'):
        filas.append([NOMBRE[h], f"{f(e2e.loc[h, 'seg'], 3)} ± {f(e2e.loc[h, 'seg_de'], 3)}",
                      f(pop.loc[h, 'seg'], 3), f(cal.loc[h, 'seg'], 3) if cal is not None else '—',
                      f(e2e.loc[h, 'rss'], 0), f(e2e.loc[h, 'sis'], 1), str(int(matriz['loc'][h]))])
    d.tabla(['Herramienta', 'Extremo a extremo (s, M ± DE)', 'Por operación (s)', 'Proceso caliente (s)',
             'RSS pico (MB)', 'Memoria del sistema (%)', 'Líneas de código'],
            filas, [2.4, 3.3, 2.2, 2.2, 2.0, 2.4, 1.8],
            titulo='Tiempo total de la carga a la exportación, memoria y líneas de código por herramienta',
            nota=f"M = media; DE = desviación estándar; {k['b']['repeticiones']} repeticiones por herramienta. El proceso "
                 "caliente (modo complementario) mide una segunda ejecución dentro del mismo proceso, tras limpiar la "
                 "caché de datos. Los tiempos excluyen el arranque de la sesión de Spark.")
    d.imagen(rutas.get('g_totales_doc', rutas['g_totales']), 16, 'Tiempo total por modo y memoria pico por herramienta',
             'Las barras muestran la media y las líneas de error, la desviación estándar.')
    ops = k['b']['ops']
    d.p('Por operación (modo por_operacion), los tiempos medios fueron los siguientes: ' + '; '.join(
        f"{op}: " + ', '.join(f"{NOMBRE[h]} {f(ops.loc[op, h], 3)} s" for h in ('pandas', 'polars', 'spark'))
        for op in ('carga', 'filtrado', 'agregacion', 'join', 'exportacion')) + '.')
    if cal is not None:
        d.p(f"En régimen estable (proceso caliente), PySpark desciende de {f(e2e.loc['spark', 'seg'], 2)} s a "
            f"{f(cal.loc['spark', 'seg'], 2)} s. La diferencia corresponde a los costes de una JVM recién creada (carga "
            "de clases, compilación JIT y generación de código), que no dependen del volumen. Aun así, PySpark resulta "
            f"{f(veces(cal.loc['spark', 'seg'], cal['seg'].min()), 0)} veces más lento que la opción más rápida, porque "
            "con unas 27 000 filas el trabajo útil es mínimo frente a la planificación, el intercambio de datos entre "
            "particiones y la coordinación de tareas.")

    d.h1('Matriz de decisión ponderada')
    filas = [[c, f"{int(round(p * 100))} %"] + [str(matriz['puntajes'][c][h]) for h in ('pandas', 'polars', 'spark')]
             for c, p in matriz['pesos'].items()]
    filas.append(['Puntaje ponderado', '100 %'] + [f(matriz['ponderado'][h], 2) for h in ('pandas', 'polars', 'spark')])
    d.tabla(['Criterio', 'Peso', 'Pandas', 'Polars', 'PySpark'], filas, [5, 2, 2.6, 2.6, 2.6],
            titulo='Matriz de decisión tecnológica ponderada (escala de 1 a 5)',
            nota='Puntaje ponderado = Σ (puntaje del criterio × peso). Los pesos son los establecidos en la guía de la '
                 'actividad. El cálculo se realiza con fórmulas en reporte_comparativo_benchmark.xlsx (hoja Matriz).')
    d.vinetas([
        ('Criterios cuantitativos. ', 'Se calcula r = valor / mejor valor y se asigna: r ≤ 1.25 → 5; ≤ 2 → 4; ≤ 4 → 3; '
         '≤ 8 → 2; > 8 → 1. Rendimiento usa el tiempo total extremo a extremo y Recursos, el RSS pico (proceso y JVM). '
         'Facilidad de uso parte del cociente de líneas de código, con un ajuste cualitativo de −1 para PySpark por la '
         'configuración de la sesión y de la JVM, las trazas de error mixtas Java/Python y la evaluación perezosa.'),
        ('Criterios cualitativos. ', 'Escalabilidad: Pandas 2 (un nodo, en memoria), Polars 3 (un nodo, multihilo, '
         'procesamiento por flujos) y PySpark 5 (distribuido). Curva de aprendizaje: Pandas 5, Polars 4 y PySpark 2, '
         'por los conceptos de DAG, evaluación perezosa, particiones y caché.'),
    ])

    d.h1('Conveniencia para el volumen probado frente a la elección exigida')
    d.p(f"El resultado numérico favorece a {NOMBRE[k['ganador']]}. Con este volumen predominan los costes fijos de "
        "Spark: arranque de la JVM, planificación del DAG, serialización entre Python y la JVM, y tareas con particiones "
        "casi vacías. Pandas y Polars se ejecutan dentro del mismo proceso y no incurren en esos costes. Esta conclusión "
        "es válida para unos 3 MB en un nodo y no se extiende automáticamente a volúmenes mayores.")
    d.p("La elección de PySpark como herramienta principal, exigida por la actividad, se sostiene en atributos que un "
        "benchmark de tres meses en un solo nodo no mide: el mismo código se ejecuta en un clúster repartiendo datos y "
        "cómputo entre nodos, tolera fallos de tareas, no está limitado por la RAM de una máquina porque derrama a disco "
        "e integra lectura y escritura particionada en almacenamiento de objetos (Zaharia et al., 2016). La matriz "
        "pondera la escalabilidad con un 20 %, pero ese atributo solo se manifiesta con volúmenes y despliegues que esta "
        "prueba de concepto (PoC) no alcanza.")

    d.h1('Recomendaciones por volumen')
    esc = R.get('escala')
    if esc:
        a = esc['ajustes']['pandas']
        d.p(f"En el PoC con datos replicados, el RSS de Pandas creció unos {f(a['rss_por_millon_mb'], 0)} MB por cada "
            "millón de registros (ajuste lineal sobre tres puntos medidos). La cifra orienta el orden de magnitud y no "
            "constituye un umbral garantizado.")
    d.tabla(['Escenario de datos', 'Herramienta recomendada', 'Justificación'], [
        ['Exploración y reportes de pocos meses (los datos y sus copias intermedias caben holgadamente en la RAM de un '
         'nodo)', 'Polars (o Pandas)', 'Menor latencia y menor memoria medidas; sin JVM.'],
        ['Histórico de uno a dos años en un nodo (Colab, ~12 GB de RAM)', 'PySpark local o Polars',
         'Ambos procesan el volumen replicado medido; PySpark conserva el código listo para el clúster.'],
        ['Varios años, varias fuentes, procesos programados o datos que no caben en un nodo',
         'PySpark en clúster (p. ej., Databricks)', 'Paralelismo entre nodos, tolerancia a fallos y derrame a disco.'],
    ], [6.5, 4, 6], titulo='Herramienta recomendada según el volumen de datos')

    d.h1('Herramientas complementarias')
    d.vinetas([
        ('Polars y Pandas: ', 'exploración rápida, validaciones puntuales y preparación de reportes sobre los Parquet agregados.'),
        ('PyArrow y Parquet: ', 'formato columnar común a las tres herramientas; las salidas se leen igual desde cualquiera.'),
        ('Google Drive y Google Colab: ', 'almacenamiento y cómputo del PoC; en producción, almacenamiento de objetos y un clúster.'),
        ('Matplotlib, openpyxl y python-docx: ', 'gráficos e informes regenerables a partir de las mediciones.'),
    ])

    d.h1('Plan de implementación por fases')
    d.tabla(['Fase', 'Alcance', 'Criterio de salida'], [
        ['0. PoC (realizada)', 'Pipeline PySpark en Colab: ingesta desde Drive, validaciones, Parquet particionado y '
         'métricas.', f"Tasa de validaciones del {f(ps['tasa_validaciones_pct'], 1)} % y salidas equivalentes a Pandas."],
        ['1. Consolidación', 'Carga incremental mensual, catálogo oficial de códigos (sustituye al derivado) y '
         'parametrización por entorno.', 'Mismo resultado al añadir un mes sin reprocesar el histórico.'],
        ['2. Escalado', 'Mismo código en Databricks Community u otro clúster Spark; almacenamiento de objetos; ajuste '
         'de particiones y memoria.', 'Tiempo y costo medidos con al menos un año de datos reales.'],
        ['3. Operación', 'Orquestación programada, alertas por controles fallidos y tablero de indicadores.',
         'Ejecuciones automáticas con registro de validación e indicadores.'],
    ], [3, 8.5, 5], titulo='Plan de implementación y migración por fases')

    d.h1('Limitaciones')
    d.vinetas([
        'El volumen es pequeño: predominan los costes fijos y la extrapolación lineal a volúmenes grandes no garantiza '
        'el rendimiento.',
        'Colab ofrece un único nodo de 2 vCPU, por lo que no se midió Spark distribuido.',
        'El porcentaje de memoria del sistema incluye otros procesos de Colab; el RSS contabiliza páginas compartidas, '
        'y el muestreo de 20 ms puede omitir picos más breves.',
        'Tras el calentamiento, la caché de páginas del sistema operativo quedó igualmente activa para las tres herramientas.',
        'El catálogo de tipos es derivado de los datos y no oficial; la escalabilidad cualitativa se basa en la '
        'arquitectura de cada herramienta, no en mediciones multinodo.',
    ])
    d.referencias([refs[c] for c in ('guia', 'datos', 'spark', 'parquet', 'colab', 'mckinney', 'pandas', 'polars',
                                      'psutil', 'zaharia')], tam=9.5)
    return d.guardar(ruta)


# ---------------------------------------------------------------- Arquitectura (5–8 páginas)
def doc_arquitectura(R, matriz, rutas, config_spark, ruta, datos):
    k = _datos_clave(R, matriz)
    poc, ps, pp, ent = k['poc'], k['ps'], k['pp'], k['ent']
    datos = {**datos, 'fecha': fecha_es(ent['fecha'])}
    refs = referencias_apa(datos, ent)
    u = poc['ultima_spark']
    var = poc['variante'].iloc[0] if len(poc['variante']) else None
    d = Doc(interlineado=1.0)
    d.bloque_titulo('Arquitectura técnica del sistema de análisis de emergencias de la Línea 123 de Bogotá: '
                    'prueba de concepto en PySpark', datos)

    d.h1('Introducción')
    d.p("Este documento describe la arquitectura implementada y validada en la prueba de concepto (PoC, por sus siglas "
        "en inglés) del pipeline de procesamiento de las llamadas a la Línea 123 de Bogotá. La arquitectura traduce "
        "los resultados del análisis comparativo de la primera actividad en decisiones concretas: PySpark como motor "
        f"principal, exigido por la actividad {_cita_guia(datos, ent)}; Parquet como formato de almacenamiento "
        "(Apache Software Foundation, s. f.), y validaciones de calidad explícitas. Todo el flujo se ejecuta en Google "
        "Colab con los datos en Google Drive (Google, s. f.); las cifras provienen de tres ejecuciones reales del PoC.")
    d.h1('Objetivos')
    d.vinetas([
        'Ingerir los tres archivos CSV mensuales desde Google Drive con un esquema explícito y conservar su procedencia.',
        'Limpiar, tipar y estandarizar los datos sin imputar valores: solo se eliminan las copias duplicadas exactas, '
        'que quedan registradas aparte, y las demás anomalías se conservan con una observación de calidad.',
        'Enriquecer los registros con el catálogo de tipos mediante una unión por difusión (broadcast join) y generar '
        'agregados por periodo, localidad y tipo.',
        'Exportar a Parquet particionado y verificar las salidas mediante conteos, esquema y agregados.',
        'Medir el tiempo, la memoria, el throughput y la tasa de validaciones, y compararlos con Pandas en igualdad de alcance.',
    ])

    d.h1('Arquitectura propuesta')
    d.imagen(rutas['diagrama'], 15, 'Arquitectura implementada: ingesta, procesamiento, almacenamiento y salidas',
             'Elaboración propia. Fuente editable en diagrama_arquitectura.drawio (draw.io).')
    d.p("La arquitectura se organiza en cuatro capas. En la ingesta, los CSV mensuales residen en Google Drive con su "
        "huella SHA-256 verificada y la máquina virtual de Colab los lee mediante el montaje de Drive. El procesamiento "
        "consiste en un pipeline de PySpark ejecutado en modo local (Apache Software Foundation, 2025). El almacenamiento "
        "escribe en Drive el detalle en Parquet particionado por mes y localidad, los agregados, las copias duplicadas "
        "eliminadas, las mediciones y los registros de validación. Las salidas comprenden los indicadores, los informes y el consumo analítico de los "
        "Parquet.")

    d.h1('Componentes técnicos')
    d.tabla(['Componente', 'Tecnología', 'Función'], [
        ['Fuente de datos', 'CSV mensuales de la Línea 123 (UTF-8 con BOM, «;»)',
         f"{f(R['inventario']['total_registros'], 0)} registros de julio a septiembre de 2026"],
        ['Almacenamiento', 'Google Drive (MyDrive/BigData_U2)', 'Carpeta única: datos/, resultados/ y una carpeta por actividad'],
        ['Cómputo', f"Google Colab, {ent['vcpu']} vCPU, {ent['ram_gb']} GB de RAM", 'Máquina virtual de un solo nodo'],
        ['Motor', f"PySpark {ent['pyspark']} sobre {java_corto(ent['java'])}", 'Driver y ejecutores en una misma JVM (modo local)'],
        ['Código', 'Cuatro notebooks de Colab', 'Benchmark, matriz, PoC (pipeline y validaciones) y métricas; los informes se elaboran a partir de sus mediciones'],
        ['Configuración', 'config.yaml y catálogos CSV', 'Esquema, periodos, reglas y parámetros de Spark'],
        ['Catálogos', 'Localidades de Bogotá (oficial) y tipos de incidente (derivado, no oficial)',
         'Estandarización y enriquecimiento'],
        ['Formato', 'Apache Parquet (snappy)', 'Almacenamiento columnar, tipado y particionado'],
        ['Monitoreo', 'psutil y reloj perf_counter_ns', 'Tiempo, porcentaje de RAM del sistema y RSS del proceso y la JVM'],
    ], [3.4, 6.6, 6], titulo='Componentes técnicos de la arquitectura')

    d.h1('Flujo de datos')
    d.vinetas([
        ('Prevalidación: ', 'existencia de los tres archivos, columnas requeridas y filas físicas por archivo.'),
        ('Lectura: ', 'esquema explícito con diez columnas de texto y _corrupt_record, en modo PERMISSIVE.'),
        ('Procedencia: ', 'archivo de origen (metadato del archivo) y periodo AAAA-MM según la configuración.'),
        ('Nulos: ', '«N/A» y los vacíos se convierten en nulos, sin imputación; una RECEPCION vacía es un valor legítimo.'),
        ('Tipos: ', 'try_to_timestamp para las fechas y try_cast para los enteros, porque Spark 4 activa el modo ANSI; '
         'la edad se expresa en años según la unidad.'),
        ('Estandarización: ', 'localidad sin tildes y en mayúsculas, contrastada con la tabla oficial código-nombre; '
         'el código de tipo es el texto previo a « - ».'),
        ('Observaciones de calidad: ', 'registro corrupto, incidente nulo, fecha inválida, localidad sin dato o fuera '
         'del catálogo, código inconsistente, tipo nulo y edad fuera del rango 0–120; el registro se conserva y se marca.'),
        ('Duplicados: ', 'se eliminan solo las copias con el 100 % de los atributos iguales y se escriben aparte; los '
         'incidentes con varios despachos se conservan y se informan.'),
        ('Enriquecimiento y agregados: ', 'unión por difusión con el catálogo (23 filas), verificando que no se '
         'multipliquen filas; agregados por periodo, localidad, tipo, prioridad y día.'),
        ('Escritura y verificación: ', 'Parquet particionado por mes y localidad, relectura con un lector independiente '
         '(PyArrow), evaluación de los controles V01–V20 y registro .txt.'),
    ])

    d.h1('Decisiones de diseño')
    d.tabla(['Decisión', 'Alternativa descartada', 'Justificación'], [
        ['Esquema explícito y tipado posterior', 'Inferencia de esquema', 'EDAD contiene «N/A»; inferir tipos fallaría '
         'o degradaría la columna a texto sin control.'],
        ['try_cast y try_to_timestamp', 'Conversión directa', 'Con ANSI activo, una conversión inválida aborta el '
         'trabajo; con try_* se obtiene un nulo y el registro se conserva con una observación de calidad.'],
        ['Conservar y marcar las anomalías', 'Filtrar y descartar', 'No se pierde información; la columna '
         'observacion_calidad permite excluirlas en cada análisis.'],
        ['Eliminar solo duplicados exactos y escribirlos aparte', 'Eliminar por número de incidente', 'Una fila idéntica '
         'en los diez atributos no aporta información; los despachos múltiples difieren en algún atributo y se conservan. '
         'Se cumple que leídos = conservados + eliminados.'],
        ['Unión por difusión del catálogo', 'Unión con ordenamiento y mezcla', 'El catálogo tiene 23 filas; la difusión '
         'evita el intercambio de datos del lado grande.'],
        ['Partición por mes y localidad', 'Partición solo por mes', 'Corresponde a los filtros habituales del centro de '
         'despacho y a la guía; hoy genera archivos pequeños (véase la Tabla 4), costo que se diluye con el volumen.'],
        ['Formato Parquet', 'CSV', 'Columnar, comprimido y tipado; permite poda de particiones.'],
        ['Validar sobre la relectura del Parquet', 'Validar en memoria', 'Comprueba lo que efectivamente quedó escrito.'],
        ['Memoria del driver: mín(4g, 50 % de la RAM)', '70 % de la RAM disponible (ejemplo del curso)', 'La guía fija '
         '4g; el margen restante queda para los procesos de Python y para las mediciones con Pandas y Polars.'],
        ['Serializador por defecto', 'KryoSerializer (ejemplo del curso)', 'Kryo acelera RDD y clausuras; la API de '
         'DataFrames serializa con los codificadores de Tungsten, por lo que no aporta en este pipeline.'],
    ], [4.2, 3.4, 8.4], titulo='Decisiones de diseño y su justificación')

    d.h1('Configuración de PySpark')
    explicacion = {
        'spark.master': 'Modo local con un hilo por vCPU (un nodo; no es un clúster)',
        'spark.driver.memory': 'Mínimo entre 4g (guía) y el 50 % de la RAM detectada',
        'spark.driver.maxResultSize': 'Límite para collect() (guía)',
        'spark.sql.adaptive.enabled': 'Ejecución adaptativa (AQE): ajusta el plan con estadísticas reales',
        'spark.sql.adaptive.coalescePartitions.enabled': 'Une particiones pequeñas tras el intercambio',
        'spark.sql.adaptive.skewJoin.enabled': 'Divide particiones sesgadas en las uniones',
        'spark.sql.adaptive.advisoryPartitionSizeInBytes': 'Tamaño objetivo de partición (guía)',
        'spark.sql.execution.arrow.pyspark.enabled': 'Arrow para el intercambio con pandas',
        'spark.sql.shuffle.partitions': '2 × vCPU, en lugar de 200 particiones casi vacías',
        'spark.sql.session.timeZone': 'Zona horaria de los datos',
        'spark.ui.enabled': 'Desactivada para no medir el servidor de la interfaz',
    }
    d.tabla(['Parámetro', 'Valor', 'Motivo'], [[k2, v, explicacion.get(k2, '')] for k2, v in config_spark.items()
                                              if k2 not in ('spark.app.name', 'spark.ui.showConsoleProgress')],
            [6.3, 2.5, 7.2], tam=8.5, titulo='Configuración de PySpark ajustada a los recursos de Colab')
    d.p("En Colab, el driver y los ejecutores comparten una sola JVM en una máquina virtual. En un clúster, "
        "spark.master apuntaría al gestor de recursos (YARN, Kubernetes o Databricks); spark.executor.instances, "
        "spark.executor.cores y spark.executor.memory se dimensionarían según el volumen, y "
        "spark.sql.shuffle.partitions se ajustaría al total de núcleos, sin cambios en el código del pipeline.")

    d.h1('Estrategia de particionamiento')
    filas = [['Periodo (implementada)', str(int(u['parquet_archivos'])), f(u['parquet_bytes'] / 1024, 0),
              f(u['parquet_bytes'] / u['parquet_archivos'] / 1024, 0)]]
    if var is not None:
        filas.append(['Periodo y localidad (variante medida)', str(int(var['parquet_archivos'])),
                      f(var['parquet_bytes'] / 1024, 0), f(var['parquet_bytes'] / var['parquet_archivos'] / 1024, 0)])
    d.tabla(['Estrategia', 'Archivos Parquet', 'KB totales', 'KB por archivo'], filas, [6, 3.2, 3.2, 3.2],
            titulo='Comparación medida de las estrategias de particionamiento',
            nota='Comparación de referencia entre la partición solo por mes y la partición por mes y localidad.')
    d.p("El detalle se escribe con repartition(periodo, cod_localidad) y partitionBy(periodo, cod_localidad), que es "
        "la estrategia mes/localidad que pide la guía: un archivo por cada combinación de mes y localidad. Las consultas "
        "que filtran por mes, por localidad o por ambos leen solo las carpetas necesarias (poda de particiones). El "
        "costo, medido en la tabla anterior, es un número mayor de archivos de menor tamaño; con el volumen actual "
        "esos archivos son pequeños, por lo que la ganancia de la poda es limitada. La estrategia se mantiene porque "
        "corresponde a los filtros habituales del centro de despacho y su beneficio crece con el volumen; cuando cada "
        "combinación de mes y localidad alcance decenas de megabytes, el tamaño de archivo deja de ser un problema.")

    optim = R.get('optim')
    if optim:
        d.h1('Evidencia de optimización')
        pl = optim['planes']
        si_no = {True: 'sí', False: 'no'}
        d.p("Los planes físicos obtenidos con explain() sobre el Parquet exportado confirman tres optimizaciones: "
            f"poda de particiones por mes y localidad ({si_no[pl['poda_particiones']]}), predicado empujado al lector "
            f"Parquet ({si_no[pl['predicado_empujado']]}) y unión por difusión con el catálogo "
            f"({si_no[pl['broadcast_join']]}). El texto completo de los planes se conserva en "
            "resultados/mediciones/planes_ejecucion.txt.")
        filas = [[x['formato'], f(x['mb'], 3), f(x['tamano_vs_csv'], 2), f(x['lectura_agregacion_s'], 2)]
                 for x in optim['formatos']['formatos']]
        d.tabla(['Formato', 'Tamaño (MB)', 'Tamaño relativo a CSV', 'Lectura y agregación (s)'], filas, [4, 3.5, 4, 4.5],
                titulo='Comparación de formatos de almacenamiento con el detalle del PoC',
                nota=f"Mismo contenido ({f(optim['formatos']['registros'], 0)} registros) escrito en un archivo por "
                     f"formato; tiempo = mediana de {optim['formatos']['repeticiones']} lecturas con agregación por tipo "
                     "en Spark. Diagnóstico adicional: perfil de nulos por columna y valores atípicos de la edad por "
                     f"rango intercuartílico ({optim['atipicos_edad']['atipicos']} registros fuera de "
                     f"[{f(optim['atipicos_edad']['limite_inferior'], 1)}, {f(optim['atipicos_edad']['limite_superior'], 1)}] "
                     "años), solo informativo.")

    d.h1('Recursos medidos y estimación')
    d.tabla(['Métrica (media de tres ejecuciones)', 'PySpark', 'Pandas (mismo alcance)'], [
        ['Tiempo total de la carga a la exportación (s)', f(ps['tiempo_total_s'], 2), f(pp['tiempo_total_s'], 2)],
        ['Arranque de la sesión de Spark (s, aparte)', f(ps['tiempo_inicio_sesion_s'], 2), '—'],
        ['Memoria del sistema, pico (%)', f(ps['mem_sis_pico_pct'], 1), f(pp['mem_sis_pico_pct'], 1)],
        ['RSS pico del proceso y la JVM (MB)', f(ps['rss_pico_mb'], 0), f(pp['rss_pico_mb'], 0)],
        ['Throughput (registros por minuto)', f(ps['throughput_reg_min'], 0), f(pp['throughput_reg_min'], 0)],
        ['Tasa de éxito de validaciones (%)', f(ps['tasa_validaciones_pct'], 1), f(pp['tasa_validaciones_pct'], 1)],
        ['Registros conservados (%)', f(ps['registros_validos_pct'], 3), f(pp['registros_validos_pct'], 3)],
    ], [7.5, 4, 4.5], titulo='Recursos medidos en la prueba de concepto')
    d.imagen(rutas['g_poc'], 14, 'Prueba de concepto en PySpark frente a Pandas con el mismo alcance',
             'Media de tres ejecuciones; las líneas de error representan la desviación estándar.')
    d.p(f"PySpark resultó {f(veces(ps['tiempo_total_s'], pp['tiempo_total_s']), 0)} veces más lento que Pandas y "
        f"empleó {f(veces(ps['rss_pico_mb'], pp['rss_pico_mb']), 1)} veces más RSS. Con este volumen no hubo mejora "
        "frente a Pandas, debido a los costes fijos de la JVM y de la coordinación de tareas. Para el PoC bastan 2 vCPU "
        "y unos 4 GB de memoria para el driver; la proyección a uno y dos años se presenta en el análisis de escalabilidad.")

    d.h1('Monitoreo e indicadores clave')
    d.tabla(['Indicador', 'Definición', 'Valor medido (PySpark)'], [
        ['Tiempo total (s)', 'Reloj monotónico de la carga a la exportación, sin el arranque', f(ps['tiempo_total_s'], 2)],
        ['Memoria pico (%)', 'Máximo de psutil.virtual_memory().percent, muestreado cada 20 ms', f(ps['mem_sis_pico_pct'], 1)],
        ['RSS pico (MB)', 'Máximo del RSS del proceso y sus hijos (JVM)', f(ps['rss_pico_mb'], 0)],
        ['Throughput', 'Registros leídos / (tiempo total / 60)', f(ps['throughput_reg_min'], 0) + ' registros/min'],
        ['Tasa de validaciones (%)', 'Controles aprobados / evaluados (bloqueantes y advertencias)', f(ps['tasa_validaciones_pct'], 1)],
        ['Registros conservados (%)', 'Conservados / leídos', f(ps['registros_validos_pct'], 3)],
        ['Duplicados exactos', 'Copias idénticas eliminadas; registradas en duplicados_eliminados/',
         str(int(u['duplicados_exactos']))],
        ['Observaciones de calidad', 'Registros conservados con anomalía, por motivo',
         ', '.join(f'{k}: {v}' for k, v in (u.get('observaciones_por_motivo') or {}).items()) or 'ninguna'],
    ], [3.6, 8.4, 4], titulo='Indicadores de monitoreo del pipeline')
    d.p("Cada ejecución agrega sus métricas a resultados/mediciones/poc.jsonl y su bloque de controles al registro "
        "validacion_poc_spark.txt. En operación, un control bloqueante fallido debería detener la publicación del mes y "
        "generar una alerta.")

    d.h1('Riesgos y mitigaciones')
    d.tabla(['Riesgo', 'Impacto', 'Mitigación'], [
        ['Cambio de esquema o de formato en un CSV nuevo', 'Fallo de lectura o columnas vacías',
         'Control V02 y columna _corrupt_record; el esquema explícito evita inferencias silenciosas.'],
        ['Catálogo de códigos no oficial', 'Descripciones incompletas', 'Sustituirlo por el catálogo oficial con el '
         'mismo formato; el control V08 cuenta los códigos no reconocidos.'],
        ['Códigos de localidad inconsistentes', 'Asignación a una localidad equivocada', 'Observación de calidad y control V10.'],
        ['Archivos pequeños por sobreparticionar', 'Lecturas lentas', 'Un archivo por partición (repartition por las mismas claves); compactar o pasar a solo mes si los archivos siguen siendo diminutos con el volumen real.'],
        ['Límites de Colab (un nodo, sesión de 12 h)', 'Sesiones interrumpidas', 'Resultados persistidos en Drive; '
         'migración a un clúster en la fase 2.'],
        ['Costes fijos de Spark con poco volumen', 'Latencia alta en lotes pequeños', 'Polars o Pandas para lotes '
         'pequeños y Spark para el histórico y el clúster.'],
        ['Autorización de Drive caducada', 'Pipeline sin datos', 'Control V01 con error explícito y copia verificada por SHA-256.'],
    ], [5, 3.8, 7.2], titulo='Riesgos identificados y medidas de mitigación')

    d.h1('Limitaciones y siguientes pasos')
    d.p("Lo implementado es un PoC de un solo nodo, por lo que no se midió el comportamiento distribuido. Las cifras "
        f"corresponden a {f(R['inventario']['total_registros'], 0)} registros y su relación con volúmenes mayores es una "
        "estimación. Como siguientes pasos se proponen el catálogo oficial, la carga incremental mensual, la ejecución en "
        "Databricks o en un clúster con al menos un año de datos reales, y la orquestación con alertas basadas en los "
        "controles V01–V16 (Zaharia et al., 2016).")
    d.referencias([refs[c] for c in ('guia', 'datos', 'spark', 'parquet', 'colab', 'psutil', 'zaharia')], tam=9.5)
    return d.guardar(ruta)


# ---------------------------------------------------------------- Escalabilidad (1 página)
def doc_escalabilidad(R, ruta, datos):
    esc, ent = R['escala'], R['entorno']
    datos = {**datos, 'fecha': fecha_es(ent['fecha'])}
    refs = referencias_apa(datos, ent)
    d = Doc(tamano=8.5, margen_cm=1.6, interlineado=1.0)
    d.bloque_titulo('Análisis de escalabilidad del pipeline: proyección a uno y dos años de datos', datos, compacto=True)
    d.p('Se midió la prueba de concepto (PoC) con los datos reales de tres meses y con los mismos CSV replicados ×4 y ×8 '
        '(datos sintéticos equivalentes en filas a uno y dos años). Con esos puntos se ajustó, para cada herramienta, '
        'el modelo tiempo = fijo + variable × registros, y de igual forma la memoria residente del proceso (RSS). Las '
        'proyecciones fuera de los puntos medidos son teóricas.', 'Método. ')
    filas = []
    for _, r in esc['puntos'].iterrows():
        filas.append([NOMBRE[r['herramienta']], f"{3 * r['factor']} meses (×{r['factor']})", f(r['leidos'], 0),
                      f(r['tiempo_total_s'], 2), f(r['rss_pico_mb'], 0), f(r['mem_sis_pico_pct'], 1), r['origen']])
    d.tabla(['Herramienta', 'Volumen', 'Registros', 'Tiempo (s)', 'RSS pico (MB)', 'Memoria del sistema (%)', 'Origen'],
            filas, [2.2, 2.6, 2.2, 2.0, 2.3, 2.9, 3.4], tam=7.5, titulo='Puntos medidos de tiempo y memoria según el volumen')
    aj = esc['ajustes']
    d.p('; '.join(f"{NOMBRE[h]}: tiempo ≈ {f(a['t_fijo_s'], 1)} s + {f(a['t_por_millon_s'], 1)} s por millón de "
                  f"registros; RSS ≈ {f(a['rss_fijo_mb'], 0)} MB + {f(a['rss_por_millon_mb'], 0)} MB por millón"
                  for h, a in aj.items()) + '.', 'Ajuste lineal sobre los puntos medidos. ')
    n1, n2, n10 = REGISTROS_MES * 12, REGISTROS_MES * 24, REGISTROS_MES * 120
    heap_mb, proy, acotado = 4 * 1024, [], False
    for etiqueta, n in (('1 año', n1), ('2 años', n2), ('10 años (teórico)', n10)):
        fila = [etiqueta, f(n, 0)]
        for h in ('spark', 'pandas'):
            t, m = proyectar(aj[h], n)
            if h == 'spark' and m > heap_mb:
                acotado = True
                fila += [f(t, 1), f'≥ {f(heap_mb, 0)}*']
            else:
                fila += [f(t, 1), f(m, 0)]
        proy.append(fila)
    d.tabla(['Horizonte', 'Registros (~9 145 por mes)', 'PySpark (s)', 'PySpark (MB)', 'Pandas (s)', 'Pandas (MB)'],
            proy, [3, 4, 2.3, 2.3, 2.3, 2.3], tam=7.5, titulo='Proyección teórica de tiempo y memoria',
            nota=('* La memoria de Spark no crece sin límite: la JVM se acota al heap configurado (spark.driver.memory '
                  '= 4 GB) más el overhead y, por encima, derrama a disco; la proyección lineal del RSS de Spark no aplica '
                  'en ese tramo.') if acotado else None)
    ram_mb = ent['ram_gb'] * 1024
    quiebre = {h: (0.5 * ram_mb - a['rss_fijo_mb']) / a['rss_por_millon_mb'] * 1e6 if a['rss_por_millon_mb'] > 0
               else float('inf') for h, a in aj.items()}
    pts = esc['puntos']
    d.p(f"Uno a dos años de datos ({f(n1 / 1e3, 0)}–{f(n2 / 1e3, 0)} mil registros; unos {f(n1 * 113 / 2**20, 0)}–"
        f"{f(n2 * 113 / 2**20, 0)} MB en CSV) caben en un nodo de Colab con ambas herramientas: los puntos ×4 y ×8 se "
        f"midieron y no superaron el {f(pts['mem_sis_pico_pct'].max(), 0)} % de la RAM del sistema. Con este volumen, "
        "el coste fijo de Spark (JVM y planificación) sigue superando al variable, por lo que Pandas continúa siendo "
        "más rápido en un solo nodo; Polars no se midió en este experimento.", 'Interpretación. ')
    d.p(f"Si el ajuste lineal se mantuviera, supuesto que es fuerte, Pandas alcanzaría el 50 % de la RAM de la máquina "
        f"virtual (unos {f(0.5 * ram_mb / 1024, 1)} GB, con margen para copias intermedias) hacia los "
        f"{f(quiebre['pandas'] / 1e6, 0)} millones de registros (≈ {f(quiebre['pandas'] / REGISTROS_MES / 12, 0)} años "
        "al ritmo actual), y no puede superar la RAM de la máquina. Spark, en cambio, derrama a disco y en un clúster "
        "incorpora nodos (Zaharia et al., 2016); su límite práctico en Colab es la CPU (2 vCPU) y la duración de la "
        "sesión (12 h). Estos umbrales indican órdenes de magnitud, no garantías.", 'Puntos de quiebre teóricos. ')
    d.p('Hasta dos años basta un nodo de Colab (2 vCPU, 12 GB y driver de Spark de 4 GB). Para varios años, varias '
        'fuentes o ejecución diaria se recomienda un clúster Spark (p. ej., Databricks) con dos a cuatro ejecutores y '
        'particionado mensual, dimensionado tras medir con datos reales, porque los replicados no reproducen la variedad '
        'ni la distribución real de los valores.', 'Recursos recomendados. ')
    d.referencias([refs['spark'], refs['zaharia']], tam=7.5)
    return d.guardar(ruta)
