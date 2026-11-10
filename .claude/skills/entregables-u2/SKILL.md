---
name: entregables-u2
description: Generar y verificar los entregables técnicos de U2 - xlsx con fórmulas y gráficos, docx (arquitectura 5-8 págs., decisión, escalabilidad 1 pág.), PNG de alta resolución, fuente .drawio, README y TRAZABILIDAD. Usar al tocar src/emergencias123/reportes/, scripts/generar_informes.py o informes/.
---

# Entregables U2

## Principios
- Todo se genera con el notebook `U2_informes_y_entregables` (`reportes.generador.generar_todo`) a partir de
  `resultados/mediciones/`, sin volver a medir. Los informes se crean en una carpeta temporal del VM y
  `reportes.entregables.construir` los copia a `Actividad_1/`, `Actividad_2/` y `Sustentacion/`.
- Cifras reales únicamente. Si PySpark sale más lento o usa más memoria, se dice tal cual. Los
  títulos de los gráficos son neutrales ("Comparación…", no "Mejora…").
- El catálogo se menciona siempre como **derivado de los datos, no oficial**.
- Quedan fuera el video, las diapositivas, el guion del pitch y las capturas manuales.

## xlsx (openpyxl)
- `informes/reporte_comparativo_benchmark.xlsx`, con las hojas `Mediciones` (crudas),
  `Promedios` (`AVERAGEIFS` / `STDEV` sobre `Mediciones`), `Reglas`, `Matriz` (pesos
  30/25/20/15/10, puntaje ponderado con `SUMPRODUCT`; los puntajes cuantitativos se calculan por
  fórmula a partir del cociente con la mejor herramienta), `Graficos` (BarChart nativo) y `Notas`.
- `informes/metricas_poc.xlsx`: las 3 ejecuciones de Spark y de Pandas, los promedios con
  fórmulas, la comparación y un gráfico.
- Verificación: recalcular con Excel COM (`pywin32`: abrir, `CalculateFull`, guardar), releer
  con `openpyxl data_only=True` y comprobar que ninguna celda tenga `#DIV/0!`, `#REF!`, `#NAME?`
  ni `#VALUE!`.

## Reglas de puntuación (1–5)
- Cuantitativas (cociente r = valor / mejor valor): r ≤ 1.25 → 5; ≤ 2 → 4; ≤ 4 → 3; ≤ 8 → 2;
  > 8 → 1.
  - Rendimiento: tiempo total extremo a extremo promedio.
  - Recursos: pico RSS (proceso + hijos) promedio.
  - Facilidad de uso: LOC total, con el mismo cociente, más un ajuste de ±1 justificado por
    escrito (API, depuración).
- Cualitativas, con justificación escrita:
  - Escalabilidad: 5 = distribuido multinodo nativo; 3 = un nodo multihilo con ejecución
    streaming/out-of-core; 2 = un nodo, en memoria, un hilo.
  - Curva de aprendizaje: la familiaridad del ecosistema y los conceptos nuevos que exige
    (lazy, DAG, particiones, JVM).

## docx (python-docx)
- `informes/arquitectura_tecnica.docx`: **5 a 8 páginas**. `informes/analisis_decision_tecnologica.docx`:
  formato ejecutivo. `informes/analisis_escalabilidad.docx`: **1 página**.
- Verificación: Word COM → exportar a PDF en el scratchpad, contar las páginas con PyMuPDF y
  revisar visualmente al menos la primera página renderizada.

## Gráficos y diagrama
- matplotlib a 300 dpi, con título, ejes con unidades (s, %, MB), etiquetas de valor legibles y
  barras de error (desviación estándar) cuando hay repeticiones.
- El diagrama sale de una única especificación en Python (nodos y aristas), que genera
  `informes/diagrama_arquitectura.drawio` (XML mxGraph editable en draw.io) y
  `informes/diagrama_arquitectura.png` (matplotlib, ≥ 3000 px de ancho).

## Cierre
- `README.md`: ejecución local y en Colab, rutas de Drive, dependencias, resultados y limitaciones.
- `docs/TRAZABILIDAD.md`: requisito del prompt o la guía → archivo o evidencia → estado
  (cumplido / parcial / pendiente, con el motivo).
