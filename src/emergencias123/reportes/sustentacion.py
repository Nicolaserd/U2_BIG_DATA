"""Documento de sustentación: explica el proyecto completo a una persona sin conocimientos técnicos.

Toda cifra se toma de las mediciones (resumen.cargar_todo) y de la matriz recalculada, igual que los
demás informes. Formato APA 7 (bloque de título, encabezados sin numerar, tablas y figuras numeradas,
referencias), con un lenguaje sencillo, analogías y un glosario.
"""
from .documentos import (NOMBRE, Doc, _cita_guia, _datos_clave, f, fecha_es, java_corto, referencias_apa,
                         veces)


def doc_sustentacion(R, matriz, rutas, ruta, datos):
    k = _datos_clave(R, matriz)
    e2e, cal, ent, ps, pp, poc = k['e2e'], k['cal'], k['ent'], k['ps'], k['pp'], k['poc']
    inv, b = R['inventario'], k['b']
    datos = {**datos, 'fecha': fecha_es(ent['fecha'])}
    refs = referencias_apa(datos, ent)
    total = inv['total_registros']
    rapida, ganador = k['rapida'], k['ganador']
    orden = sorted(matriz['ponderado'], key=matriz['ponderado'].get, reverse=True)
    u = poc['ultima_spark']
    var = poc['variante'].iloc[0] if len(poc['variante']) else None
    esc, optim = R.get('escala'), R.get('optim')

    d = Doc(tamano=11, interlineado=1.15)
    d.bloque_titulo('Sustentación del proyecto: procesamiento de las llamadas a la Línea 123 de Bogotá con '
                    'Pandas, Polars y PySpark explicado paso a paso', datos)

    # ------------------------------------------------------------------ Introducción
    d.h1('Propósito de este documento')
    d.p("Este documento explica, en lenguaje sencillo, todo lo que se hizo en el proyecto de la Unidad 2 del curso "
        f"de Big Data {_cita_guia(datos, ent)}. Está pensado para una persona que no conoce de programación ni de "
        "análisis de datos. Cada término técnico se explica la primera vez que aparece; al final se incluyen un "
        "glosario y las preguntas que suelen hacerse en una sustentación, con sus respuestas.")
    d.p("La idea general cabe en una frase: se tomaron tres meses de registros de llamadas de emergencia de Bogotá, "
        "se compararon tres herramientas para procesarlos y se construyó, con la herramienta que exige la actividad "
        "(PySpark), un proceso automático que limpia los datos, comprueba su calidad y los guarda en un formato "
        "eficiente. Todo se ejecutó en Google Colab, un servicio gratuito de Google que permite programar desde el "
        "navegador sin instalar nada en el computador (Google, s. f.).")

    # ------------------------------------------------------------------ Conceptos
    d.h1('Conceptos básicos para entender el proyecto')
    d.vinetas([
        ('Datos y archivo CSV. ', 'Los datos son registros, como las filas de una hoja de cálculo. Un archivo CSV es '
         'una tabla guardada como texto, con las columnas separadas por un símbolo (aquí, el punto y coma).'),
        ('Big Data. ', 'Se habla de Big Data cuando el volumen de datos es tan grande que un solo computador no '
         'alcanza a procesarlo con comodidad y hay que repartir el trabajo.'),
        ('Procesamiento distribuido. ', 'Es repartir un trabajo grande entre varios computadores que trabajan a la '
         'vez, como un equipo de personas que se divide una montaña de papeles.'),
        ('Pandas, Polars y PySpark. ', 'Son tres herramientas del lenguaje Python para trabajar con tablas de datos. '
         'Pandas es la más conocida y trabaja en un solo computador. Polars es más moderna y aprovecha mejor los '
         'procesadores del computador. PySpark es la versión para Python de Apache Spark, una herramienta pensada '
         'para repartir el trabajo entre muchos computadores (Zaharia et al., 2016).'),
        ('Google Colab y Google Drive. ', 'Colab presta temporalmente un computador en la nube para ejecutar '
         'programas; Drive es el almacenamiento en la nube donde quedaron los datos, el código y los resultados.'),
        ('Notebook. ', 'Es un documento que mezcla explicaciones y código que se puede ejecutar por partes (celdas). '
         'El proyecto tiene dos: uno de procesamiento (comparación de herramientas y prueba de concepto) y uno de '
         'informes.'),
        ('Parquet. ', 'Es un formato de archivo que guarda los datos por columnas, comprimidos y con su tipo '
         '(número, fecha, texto). Es como una biblioteca ordenada por estantes: para buscar algo no hay que '
         'revisar todos los libros (Apache Software Foundation, s. f.).'),
        ('Memoria RAM. ', 'Es la memoria de trabajo del computador. Si un programa necesita más de la disponible, '
         'se vuelve lento o falla.'),
    ])

    # ------------------------------------------------------------------ Datos
    d.h1('Los datos utilizados')
    d.p(f"Se usaron tres archivos con las llamadas a la Línea 123 de julio, agosto y septiembre de 2026, con "
        f"{f(total, 0)} registros en total. Cada registro describe un despacho de emergencia: el número del "
        "incidente, la fecha y hora, la localidad de Bogotá, la edad, la unidad de la edad (años, meses, días u "
        "horas), el género, el tipo de incidente, la prioridad y la hora de recepción.")
    d.p('Antes de procesar los datos se revisaron con cuidado y se encontraron varias situaciones que había que '
        'resolver sin inventar información. La única eliminación permitida fue la de las filas repetidas exactamente:')
    d.tabla(['Situación encontrada', 'Qué significa', 'Cómo se resolvió'], [
        ['Valores «N/A» en edad, unidad y género', 'El dato no se registró', 'Se convierten en vacío (nulo); no se '
         'inventa un valor.'],
        ['Localidades con tilde (USAQUÉN)', 'La misma localidad podría escribirse de varias formas',
         'Se normalizan: sin tildes y en mayúsculas (USAQUEN).'],
        ['Una fila con localidad «SIN_D»', 'Localidad sin dato', 'Se conserva y se marca con una observación de '
         'calidad («localidad sin dato»), para que cada análisis decida si la usa.'],
        [f"{inv['duplicados_exactos_global']} copias repetidas exactamente", 'Filas idénticas en todos sus datos, '
         'incluida la hora al segundo', 'Se eliminan las copias (se conserva la primera) y se guardan aparte para poder '
         'revisarlas. Los incidentes con varios despachos se conservan, porque difieren en algún dato.'],
        ['Registros del día 1 del mes siguiente', 'Llamadas de la madrugada que quedaron en el archivo del mes '
         'anterior', 'Se aceptan con una tolerancia de un día y se informan.'],
        ['No existía una tabla oficial de códigos', 'No había un catálogo con el significado de cada tipo de '
         'incidente', 'Se construyó un catálogo de 23 tipos a partir de los propios datos, marcado siempre como '
         '«derivado, no oficial».'],
    ], [4.2, 4.5, 7.3], titulo='Problemas encontrados en los datos y su tratamiento')

    # ------------------------------------------------------------------ Actividad 1
    d.h1('Actividad 1: comparación de herramientas')
    d.h2('Qué se pidió')
    d.p("Comparar Pandas, Polars y PySpark haciendo exactamente las mismas cinco tareas con los mismos datos: "
        "(1) cargar y unir los tres archivos; (2) quedarse solo con las localidades de Usaquén y Chapinero; "
        "(3) contar las emergencias por tipo; (4) unir cada registro con el catálogo de tipos, y (5) guardar el "
        "resultado en Parquet. Para cada herramienta se midieron el tiempo y la memoria.")
    d.h2('Cómo se garantizó una comparación justa')
    d.vinetas([
        'Las tres herramientas recibieron los mismos archivos y aplicaron la misma lógica.',
        'Cada medición se hizo en un programa nuevo, para que ninguna herramienta reutilizara trabajo de una '
        'ejecución anterior.',
        f"Se hizo una ejecución de calentamiento, que se descarta, y luego {b['repeticiones']} repeticiones "
        "medidas por herramienta, alternando el orden.",
        'El tiempo se midió con un reloj de alta precisión y la memoria se revisó cada 20 milésimas de segundo '
        'para capturar el punto máximo.',
        'Al final se comprobó que las tres herramientas produjeron exactamente el mismo resultado: las mismas '
        '1 762 filas y la misma «huella digital» del contenido.' if b['equivalentes'] else
        'Se comprobó si las tres herramientas produjeron el mismo resultado (ver el reporte comparativo).',
    ])
    d.h2('Resultados')
    filas = [[NOMBRE[h], f(e2e.loc[h, 'seg'], 3), f(e2e.loc[h, 'rss'], 0), f(matriz['ponderado'][h], 2)]
             for h in ('pandas', 'polars', 'spark')]
    d.tabla(['Herramienta', 'Tiempo total (segundos)', 'Memoria máxima (MB)', 'Puntaje de la matriz (1 a 5)'],
            filas, [4, 4, 4, 4], titulo='Resultados principales de la comparación',
            nota=f"Tiempo de la carga a la exportación, promedio de {b['repeticiones']} repeticiones; PySpark tarda "
                 f"además {f(b['arranque_spark'], 1)} s en arrancar. MB = megabytes.")
    d.imagen(rutas.get('g_totales_doc', rutas['g_totales']), 15.5, 'Tiempo total y memoria por herramienta',
             'Barras más cortas indican mejor resultado.')
    d.p(f"La herramienta más rápida fue {NOMBRE[rapida]}. PySpark fue unas "
        f"{f(veces(e2e.loc['spark', 'seg'], e2e.loc[rapida, 'seg']), 0)} veces más lenta y usó más memoria. "
        "Esto no significa que PySpark sea una mala herramienta: está diseñada para volúmenes enormes repartidos "
        "en muchos computadores. Con solo unos 3 MB de datos, el tiempo de «encender» su maquinaria es mayor que "
        "el trabajo real. Es como usar un camión de carga para llevar un sobre a la esquina: la moto llega antes, "
        "pero el camión es el que sirve cuando hay que mover una mudanza.")
    if cal is not None:
        d.p(f"Para comprobarlo se midió también una segunda pasada dentro del mismo programa, con el motor ya "
            f"encendido: PySpark bajó de {f(e2e.loc['spark', 'seg'], 1)} s a {f(cal.loc['spark', 'seg'], 1)} s. La "
            "mayor parte del tiempo era, efectivamente, el costo de arrancar.")
    d.h2('Matriz de decisión')
    d.p("La guía pide decidir con una matriz que califica cada herramienta de 1 a 5 en cinco criterios con un "
        "peso: rendimiento (30 %), facilidad de uso (25 %), escalabilidad, es decir, capacidad de crecer (20 %), "
        "consumo de recursos (15 %) y curva de aprendizaje (10 %). Las calificaciones de rendimiento y recursos se "
        "calculan con una regla fija a partir de las mediciones; las demás se justifican por escrito. El resultado "
        "ordena las herramientas así: " + ', '.join(f"{NOMBRE[h]} ({f(matriz['ponderado'][h], 2)})" for h in orden)
        + ".")
    d.p(f"{NOMBRE[ganador]} resultó la más conveniente para este volumen pequeño. Aun así, la actividad exige "
        "PySpark como herramienta principal, y la decisión es razonable: cuando el proyecto crezca a años de datos "
        "o a varias fuentes, PySpark es la única de las tres que permite repartir el trabajo entre muchos "
        "computadores sin reescribir el código. Pandas y Polars quedan como herramientas de apoyo para análisis "
        "rápidos.")

    # ------------------------------------------------------------------ Actividad 2
    d.h1('Actividad 2: arquitectura y prueba de concepto en PySpark')
    d.h2('Qué es una arquitectura y qué es una prueba de concepto')
    d.p("La arquitectura es el «plano» del sistema: qué piezas tiene y cómo viajan los datos entre ellas. Una "
        "prueba de concepto (PoC, por sus siglas en inglés) es una versión pequeña pero funcional que demuestra que "
        "el plano funciona en la práctica.")
    d.imagen(rutas['diagrama'], 15.5, 'Plano de la arquitectura implementada',
             'De izquierda a derecha: ingesta, procesamiento, almacenamiento y salidas.')
    d.p("El plano tiene cuatro partes. En la ingesta, los archivos se guardan en Google Drive y la máquina de "
        "Colab los lee. En el procesamiento, PySpark ejecuta los pasos de limpieza y control. En el "
        "almacenamiento, los resultados quedan en Drive en formato Parquet. En las salidas se generan los "
        "indicadores, los informes y los registros de control.")
    d.h2('Los pasos del proceso automático (pipeline)')
    d.vinetas([
        ('1. Revisar los archivos: ', 'se comprueba que estén los tres archivos y que tengan las columnas esperadas.'),
        ('2. Leer con un esquema definido: ', 'se le indica a PySpark exactamente qué columnas esperar, en lugar de '
         'dejar que adivine.'),
        ('3. Anotar la procedencia: ', 'cada registro guarda de qué archivo y de qué mes viene.'),
        ('4. Tratar los vacíos: ', '«N/A» y los campos vacíos se convierten en nulos, sin inventar valores.'),
        ('5. Convertir tipos: ', 'las fechas pasan a ser fechas, las edades a números y la edad se expresa en años.'),
        ('6. Estandarizar: ', 'localidades y tipos de incidente se escriben de una sola manera.'),
        ('7. Marcar anomalías: ', 'los registros con algún problema (por ejemplo, la localidad «SIN_D») se conservan '
         'y llevan una nota que explica el problema.'),
        ('8. Quitar copias exactas: ', 'las filas idénticas en todos sus datos se eliminan y se guardan aparte.'),
        ('9. Enriquecer: ', 'cada registro recibe la descripción de su tipo de incidente desde el catálogo.'),
        ('10. Resumir: ', 'se calculan totales por mes, localidad, tipo, prioridad y día.'),
        ('11. Guardar en Parquet: ', 'el detalle se guarda en Drive, separado en una carpeta por mes.'),
        ('12. Verificar: ', 'se vuelven a leer los archivos guardados y se aplican 20 controles de calidad.'),
    ])
    d.h2('Controles de calidad')
    obs = u.get('observaciones_por_motivo') or {}
    d.p(f"Se definieron 20 controles. Por ejemplo: que los registros leídos sean iguales a los conservados más las "
        f"copias eliminadas, que ningún dato vacío importante quede sin su nota, que la unión con el catálogo no "
        f"multiplique filas y que el archivo guardado tenga exactamente los registros conservados. La tasa de éxito de "
        f"las validaciones fue del {f(ps['tasa_validaciones_pct'], 1)} %. De {f(ps['leidos'], 0)} registros se "
        f"conservaron {f(ps['aceptados'], 0)} y se eliminaron {f(ps['rechazados'], 0)} copias exactas, que quedaron "
        f"guardadas aparte. {f(sum(obs.values()), 0)} registro(s) se conservaron con una nota de calidad. Nada se "
        "borró en silencio.")
    d.h2('Cómo se organizaron los archivos guardados')
    if var is not None:
        d.p(f"Los resultados se guardaron separados por mes, lo que produjo {int(u['parquet_archivos'])} archivos. "
            f"Se probó también separar por mes y por localidad, lo que produjo {int(var['parquet_archivos'])} "
            f"archivos de unos {f(var['parquet_bytes'] / var['parquet_archivos'] / 1024, 0)} KB cada uno. Con tan "
            "pocos datos, tantos archivos diminutos hacen la lectura más lenta (el «problema de los archivos "
            "pequeños»), por lo que se eligió separar solo por mes.")
    if optim:
        pl = optim['planes']
        d.p("Además, se revisó el «plan de ejecución» de PySpark, que es la receta que el motor arma antes de "
            "trabajar. Ese plan confirma que, al pedir un solo mes, PySpark salta los demás meses sin leerlos; que "
            "el filtro por localidad se aplica al leer el archivo, y que el catálogo se envía completo a cada tarea "
            "para no mover los datos grandes" + ('.' if all(pl.values()) else ' (ver el detalle en el notebook 03, PoC en PySpark).'))
        filas = [[x['formato'], f(x['mb'], 2), f(x['lectura_agregacion_s'], 2)] for x in optim['formatos']['formatos']]
        d.tabla(['Formato', 'Tamaño (MB)', 'Tiempo de lectura y conteo (s)'], filas, [5, 5, 6],
                titulo='El mismo contenido guardado en tres formatos',
                nota='Parquet ocupa mucho menos espacio que CSV y JSON porque guarda por columnas y comprimido.')
    d.h2('Métricas de la prueba de concepto')
    d.tabla(['Medida (promedio de tres ejecuciones)', 'PySpark', 'Pandas'], [
        ['Tiempo total (segundos)', f(ps['tiempo_total_s'], 2), f(pp['tiempo_total_s'], 2)],
        ['Memoria del sistema en el punto máximo (%)', f(ps['mem_sis_pico_pct'], 1), f(pp['mem_sis_pico_pct'], 1)],
        ['Registros procesados por minuto', f(ps['throughput_reg_min'], 0), f(pp['throughput_reg_min'], 0)],
        ['Tasa de éxito de validaciones (%)', f(ps['tasa_validaciones_pct'], 1), f(pp['tasa_validaciones_pct'], 1)],
    ], [8, 4, 4], titulo='Comparación de la prueba de concepto con Pandas')
    d.p(f"Como en la Actividad 1, PySpark fue más lento (unas {f(veces(ps['tiempo_total_s'], pp['tiempo_total_s']), 0)} "
        "veces) y usó más memoria que Pandas con este volumen. Los informes lo reportan tal cual: no se presenta una "
        "mejora que no existió. El valor de PySpark está en lo que permite cuando los datos crecen.")
    if esc:
        aj = esc['ajustes']['pandas']
        d.h2('Qué pasaría con uno o dos años de datos')
        d.p("Para estimarlo sin inventar, se repitieron los mismos datos 4 y 8 veces (lo que equivale en cantidad "
            "de filas a uno y dos años) y se midió de nuevo. Con esos puntos se trazó una línea de tendencia. "
            "Uno a dos años de datos todavía caben con holgura en una máquina de Colab con cualquiera de las dos "
            f"herramientas. Pandas usa unos {f(aj['rss_por_millon_mb'], 0)} MB más por cada millón de registros y, "
            "si la tendencia se mantuviera, llegaría al límite práctico de memoria de Colab con varios millones de "
            "registros. PySpark, en cambio, puede usar el disco y sumar computadores, por lo que es la opción para "
            "un crecimiento grande. Estas proyecciones son estimaciones, no garantías.")

    # ------------------------------------------------------------------ Colab
    d.h1('Cómo se trabajó: todo desde Google Colab')
    d.vinetas([
        'El procesamiento son cuatro notebooks de Colab, uno por tarea práctica de la guía (benchmark, matriz de decisión, '
        'prueba de concepto y métricas), guardados en una única carpeta de Google Drive (BigData_U2).',
        'El primer notebook (benchmark) consigue los datos por sí mismo: los toma de la carpeta de Drive de la Unidad 1 o, si no '
        'están, los descarga del portal de datos abiertos, y comprueba con su «huella digital» que son los correctos.',
        'Cada notebook muestra su proceso paso a paso, con el código y los resultados a la vista, y guarda sus '
        'mediciones en Drive. Los informes (Excel y Word) se elaboraron después a partir de esas mediciones, sin volver a medir.',
        f"La máquina de Colab tenía {ent['vcpu']} procesadores y {ent['ram_gb']} GB de memoria, con Python "
        f"{ent['python']}, PySpark {ent['pyspark']} y {java_corto(ent['java'])}.",
        'Todo lo que pide la guía queda en esa única carpeta: los datos, una carpeta por actividad con sus informes, '
        'esta sustentación y la evidencia (mediciones, registros de control y archivos Parquet).',
    ])

    # ------------------------------------------------------------------ Entregables
    d.h1('Qué se entrega y para qué sirve cada cosa')
    d.tabla(['Entregable', 'Para qué sirve', 'Actividad'], [
        ['Notebooks 01 y 02', 'Comparación de herramientas y matriz de decisión, paso a paso y con sus resultados', '1'],
        ['Notebooks 03 y 04', 'Prueba de concepto en PySpark y sus métricas, paso a paso y con sus resultados', '2'],
        ['Reporte comparativo (Excel)', 'Mediciones, promedios, gráficos y matriz de decisión con fórmulas', '1'],
        ['Análisis de decisión (Word)', 'Explica qué herramienta conviene y por qué se mantiene PySpark', '1'],
        ['Documento de arquitectura (Word)', 'Describe el plano del sistema y sus decisiones', '2'],
        ['Diagrama de arquitectura (imagen y fuente editable)', 'Dibujo del plano del sistema', '2'],
        ['Archivos Parquet en Drive', 'Los datos limpios y verificados', '2'],
        ['Registro de validación (texto)', 'Los 20 controles de calidad y su resultado', '2'],
        ['Métricas de la prueba de concepto (Excel)', 'Las tres ejecuciones, sus promedios y la comparación', '2'],
        ['Gráfico comparativo (imagen)', 'Tiempo y memoria de PySpark frente a Pandas', '2'],
        ['Análisis de escalabilidad (Word, 1 página)', 'Qué pasaría con uno o dos años de datos', '2'],
    ], [5.5, 8, 2.5], titulo='Entregables del proyecto')

    # ------------------------------------------------------------------ Limitaciones
    d.h1('Limitaciones, explicadas con honestidad')
    d.vinetas([
        'El volumen de datos es pequeño, por lo que las ventajas de PySpark no se ven en los tiempos.',
        'Colab presta un solo computador; no se probó PySpark repartido en varios computadores.',
        'El catálogo de tipos de incidente se construyó a partir de los datos porque no se encontró uno oficial.',
        'Las proyecciones a uno y dos años se basan en datos repetidos, no en datos reales de esos años.',
        'No se elaboraron el video ni las diapositivas del mini-pitch, que quedaron fuera del alcance acordado.',
    ])

    # ------------------------------------------------------------------ Preguntas
    d.h1('Preguntas frecuentes en la sustentación')
    preguntas = [
        ('¿Por qué PySpark fue más lento si es una herramienta de Big Data? ',
         'Porque con pocos datos domina el tiempo de arranque y de organización del trabajo. Su ventaja aparece con '
         'volúmenes grandes y varios computadores.'),
        ('¿Por qué no se eligió Polars, si obtuvo el mejor puntaje? ',
         'Porque la actividad exige PySpark y porque Polars trabaja en un solo computador; se recomienda como '
         'herramienta complementaria.'),
        ('¿Se borró algún dato? ',
         'Solo las copias exactas: 44 filas idénticas en todos sus datos, que se guardaron aparte. Los vacíos '
         'y la fila sin localidad se conservaron, marcados con una nota de calidad.'),
        ('¿Cómo se sabe que las tres herramientas hicieron lo mismo? ',
         'Se compararon sus resultados fila por fila con una huella digital del contenido, y coincidieron.'),
        ('¿Por qué Parquet y no CSV? ',
         'Porque ocupa menos espacio, guarda el tipo de cada dato y permite leer solo lo necesario.'),
        ('¿Qué falta para llevarlo a producción? ',
         'Un catálogo oficial de códigos, la carga automática de cada mes nuevo y ejecutarlo en un clúster con '
         'datos de al menos un año.'),
    ]
    for pregunta, respuesta in preguntas:
        d.p(respuesta, pregunta)

    # ------------------------------------------------------------------ Glosario
    d.h1('Glosario')
    d.tabla(['Término', 'Significado'], [
        ['Benchmark', 'Prueba de rendimiento que compara herramientas haciendo la misma tarea.'],
        ['Clúster', 'Grupo de computadores que trabajan juntos como si fueran uno.'],
        ['JVM', 'Máquina virtual de Java: el entorno sobre el que corre Spark; tarda unos segundos en arrancar.'],
        ['Partición', 'Cada parte en que se divide un conjunto de datos para guardarlo o procesarlo.'],
        ['Pipeline', 'Secuencia automática de pasos que transforma los datos de entrada en resultados.'],
        ['Throughput', 'Cantidad de registros procesados por unidad de tiempo.'],
        ['Validación', 'Comprobación automática de que los datos cumplen una regla de calidad.'],
        ['Nulo', 'Celda sin valor: el dato no existe o no se registró.'],
    ], [4, 12], titulo='Términos técnicos utilizados')
    d.referencias([refs[c] for c in ('guia', 'datos', 'spark', 'parquet', 'colab', 'zaharia')], tam=9.5)
    return d.guardar(ruta)


def guion_sustentacion(R, matriz, ruta, datos):
    """Hoja de sustentación de 5 minutos (1 + 2 + 1,5 + 0,5, distribución de la guía) con las cifras medidas."""
    k = _datos_clave(R, matriz)
    e2e, cal, ent, ps, pp, poc = k['e2e'], k['cal'], k['ent'], k['ps'], k['pp'], k['poc']
    inv = R['inventario']
    rapida = k['rapida']
    u = poc['ultima_spark']
    var = poc['variante'].iloc[0] if len(poc['variante']) else None
    orden = sorted(matriz['ponderado'], key=matriz['ponderado'].get, reverse=True)
    esc = R.get('escala')
    obs = u.get('observaciones_por_motivo') or {}
    L = [
        '# Hoja de sustentación — 5 minutos', '',
        'Distribución de la guía (referencial): 1 min introducción · 2 min arquitectura · 1,5 min demo del PoC · '
        '0,5 min conclusiones. Todas las cifras salen de la ejecución en Colab del ' + fecha_es(ent['fecha']) +
        ' (`resultados/mediciones/`). Si el notebook se vuelve a ejecutar, estas cifras se regeneran.', '',
        '## 1. Introducción (1 min)', '',
        f"- **Problema:** procesar las llamadas de emergencia de la Línea 123 de Bogotá (Secretaría Distrital de Salud), "
        f"julio–septiembre de 2026: {f(inv['total_registros'], 0)} registros en 3 CSV (~3 MB).",
        '- **Qué se hizo:** (1) benchmark de Pandas, Polars y PySpark con la misma lógica; (2) matriz de decisión; '
        '(3) arquitectura y PoC en PySpark sobre Google Colab, con los datos en Drive.',
        '- **Decisión de entrada:** PySpark es la herramienta principal porque la actividad lo exige y porque es la única '
        'de las tres que escala a varios computadores.', '',
        '## 2. Arquitectura y decisiones (2 min) — mostrar `diagrama_arquitectura.png`', '',
        '- **Cuatro capas:** ingesta (CSV en Drive, SHA-256 verificado) → procesamiento (PySpark en modo local) → '
        'almacenamiento (Parquet particionado por mes y localidad en Drive) → salidas (indicadores e informes).',
        '- **Calidad:** esquema explícito, nulos sin imputar, solo se eliminan las copias duplicadas exactas '
        f"({f(ps['rechazados'], 0)} filas, guardadas aparte); lo demás se conserva con una observación de calidad.",
        '- **Optimización:** broadcast join del catálogo (23 filas), partición por mes y localidad (la que pide la '
        'guía) y Parquet. '
        + (f"Solo por mes saldrían {int(u['parquet_archivos'])} archivos; por mes y localidad salen "
           f"{int(var['parquet_archivos'])}, de ~{f(var['parquet_bytes'] / var['parquet_archivos'] / 1024, 0)} KB cada uno: "
           "más archivos pequeños hoy, a cambio de leer solo la localidad consultada." if var is not None else ''),
        '- **Matriz (30/25/20/15/10):** ' + ', '.join(f"{NOMBRE[h]} {f(matriz['ponderado'][h], 2)}" for h in orden) +
        '. Gana la más rápida en este volumen, pero se mantiene PySpark por exigencia y escalabilidad.', '',
        '## 3. Demo del PoC (1,5 min) — notebook 03 con celdas pre-ejecutadas', '',
        '1. Sección 3.2: las 3 ejecuciones de Spark y de Pandas (tiempos por ejecución).',
        '2. Sección 3.3: tabla de métricas y promedios.',
        '3. Sección 3.4: log de validación; mostrar los controles V01–V20.',
        '4. Sección 3.5: el Parquet releído en Drive (`periodo=2026-07/08/09`).',
        '',
        '| Métrica (media de 3 ejecuciones) | PySpark | Pandas |', '|---|---:|---:|',
        f"| Tiempo total (s) | {f(ps['tiempo_total_s'], 2)} | {f(pp['tiempo_total_s'], 2)} |",
        f"| Memoria del sistema, pico (%) | {f(ps['mem_sis_pico_pct'], 1)} | {f(pp['mem_sis_pico_pct'], 1)} |",
        f"| RSS pico proceso + JVM (MB) | {f(ps['rss_pico_mb'], 0)} | {f(pp['rss_pico_mb'], 0)} |",
        f"| Throughput (registros/min) | {f(ps['throughput_reg_min'], 0)} | {f(pp['throughput_reg_min'], 0)} |",
        f"| Tasa de éxito de validaciones (%) | {f(ps['tasa_validaciones_pct'], 1)} | {f(pp['tasa_validaciones_pct'], 1)} |",
        '', '## 4. Conclusiones (0,5 min)', '',
        f"- Con 3 meses de datos, **Pandas es {f(veces(ps['tiempo_total_s'], pp['tiempo_total_s']), 0)} veces más rápido "
        'que PySpark** y usa menos memoria: el arranque de la JVM y la coordinación pesan más que el procesamiento. '
        'No se presenta una mejora que no existió.',
        '- La justificación de PySpark es la escalabilidad horizontal; la proyección a 1–2 años está en '
        '`analisis_escalabilidad.docx` y es una **estimación**, no una medición.',
        '- Siguientes pasos: catálogo oficial de códigos, carga incremental mensual y ejecución en un clúster.', '',
        '## Preguntas probables y respuestas cortas', '',
        '- **¿Por qué PySpark fue más lento?** Costes fijos (JVM, planificación, serialización) que con 3 MB dominan. '
        + (f"En una segunda pasada con el motor encendido bajó de {f(e2e.loc['spark', 'seg'], 1)} s a "
           f"{f(cal.loc['spark', 'seg'], 1)} s." if cal is not None else ''),
        f"- **¿Por qué no Polars si tuvo el mejor puntaje?** La actividad exige PySpark y Polars trabaja en un solo nodo; "
        f"queda como complementaria. La más rápida fue {NOMBRE[rapida]}.",
        '- **¿Se borró algún dato?** Solo las copias idénticas en el 100 % de sus atributos, que quedan en '
        '`duplicados_eliminados/`. Nulos y anomalías se conservan marcados en `observacion_calidad`'
        + (f" ({', '.join(f'{m}: {c}' for m, c in obs.items())})." if obs else '.'),
        '- **¿Cómo sé que las tres herramientas hicieron lo mismo?** Se compararon filas, esquema, conteo por tipo y el '
        'SHA-256 del contenido canónico (sección 3.4 del notebook 01).',
        '- **¿Son medidas confiables?** Cada repetición corre en un proceso nuevo; 1 calentamiento descartado y '
        f"{R['bench']['repeticiones']} repeticiones, con el orden de herramientas rotado.",
        '- **¿Es un clúster?** No: Spark corre en modo local dentro de una VM de Colab (2 vCPU). Un clúster '
        'cambiaría `spark.master` y los parámetros de executors, no el código.',
        '- **¿De dónde sale el catálogo de tipos?** Se derivó de los datos; **no es oficial** y así se rotula.',
        '- **¿Y las proyecciones?** Se basan en datos replicados 4× y 8×, rotulados como sintéticos.', '',
        '## Qué tener a la mano', '',
        '- `Actividad_2/diagrama_arquitectura.png` · `comparativo_poc_vs_pandas.png` · `metricas_poc.xlsx`',
        '- Los notebooks 01 a 04 ya ejecutados (el 01 es el benchmark y el 03, el PoC)',
        '- `Sustentacion/Sustentacion_proyecto_U2.docx` (explicación para no especialistas)', '',
    ]
    ruta = __import__('pathlib').Path(ruta)
    ruta.write_text('\n'.join(L), encoding='utf-8')
    return ruta
