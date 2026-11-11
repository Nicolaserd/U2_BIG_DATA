"""Prepara los informes del proyecto (Excel, Word, gráficos, diagrama) a partir de las mediciones de Colab.

Decisión del usuario (2026-11-10): los notebooks solo muestran el proceso; los informes los prepara el agente aparte,
sin volver a medir. Fuente única: <base>/resultados/mediciones/ (descargada de MyDrive/BigData_U2/resultados).

Uso: .venv/Scripts/python.exe scripts/preparar_entregables.py ENTREGABLES
La verificación usa Excel y Word (COM) en Windows, o LibreOffice si está instalado.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'src'))

from emergencias123.config import cargar_config  # noqa: E402
from emergencias123.reportes import entregables, tareas  # noqa: E402
from emergencias123.reportes.graficos import grafico_operaciones, grafico_totales  # noqa: E402
from emergencias123.reportes.resumen import resumen_benchmark  # noqa: E402


def main(base):
    base = Path(base).resolve()
    med = base / 'resultados' / 'mediciones'
    assert (med / 'benchmark.jsonl').exists() and (med / 'poc.jsonl').exists(), f'Faltan las mediciones de Colab en {med}'
    cfg = cargar_config(entorno='local')
    datos_doc = tareas.autoria(base, cfg.documentos)

    act1 = base / tareas.ACT1
    act1.mkdir(parents=True, exist_ok=True)
    b = resumen_benchmark(med)
    grafico_operaciones(b['med'], act1 / 'benchmark_operaciones.png')
    grafico_totales(b['med'], act1 / 'benchmark_totales_memoria.png')
    print('Gráficos del benchmark: OK')

    matriz_nb = json.loads((med / 'matriz_decision.json').read_text(encoding='utf-8'))
    r12 = tareas.tarea_1_2(base)
    print('1.2', r12['verificacion'])
    for h, v in matriz_nb['ponderado'].items():   # el Excel debe dar lo mismo que el cálculo del notebook 02
        assert abs(r12['matriz']['ponderado'][h] - v) < 0.01, ('Matriz distinta del notebook 02', h, v)
    print('Matriz del Excel = matriz del notebook 02:', matriz_nb['ponderado'])

    print('2.4', tareas.tarea_2_4(base, datos_doc))
    print('1.3', tareas.tarea_1_3(base, datos_doc))
    print('2.1', tareas.tarea_2_1(base, datos_doc))
    print('Sustentación', tareas.cierre(base, datos_doc))
    print('Índices', entregables.escribir_indices(base))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else RAIZ / 'ENTREGABLES')
