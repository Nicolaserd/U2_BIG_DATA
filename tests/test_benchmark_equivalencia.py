from pathlib import Path

import pytest

from conftest import ESPERADO
from emergencias123.benchmark import OPERACIONES, measure_performance, plan_benchmark
from emergencias123.equivalencia import comparar

HERRAMIENTAS_LOCALES = ['pandas', 'polars']


def _ejecutar(cfg, herramientas, modo):
    rutas = {}
    for h in herramientas:
        regs = measure_performance(h, 1, modo, False, cfg)
        assert all(r['estado'] == 'ok' for r in regs), regs[-1].get('error')
        ops = {r['operacion']: r for r in regs}
        esperadas = (OPERACIONES if modo == 'por_operacion' else ['extremo_a_extremo']) + ['total']
        assert set(esperadas) <= set(ops)
        for r in regs:
            assert r['mem_sis_pico_pct'] >= r['mem_sis_base_pct'] and r['rss_pico_mb'] >= r['rss_base_mb']
            assert r['n_muestras'] >= 1 and r['segundos'] >= 0
        if modo == 'por_operacion':
            assert ops['join']['filas_entrada'] == ops['join']['filas_salida'], 'el join multiplicó filas'
        rutas[h] = Path(regs[0]['ruta_salida'])
    return rutas


@pytest.mark.parametrize('modo', ['por_operacion', 'extremo_a_extremo', 'extremo_a_extremo_caliente'])
def test_equivalencia_fixture_pandas_polars(cfg_fixture, modo):
    res = comparar(_ejecutar(cfg_fixture, HERRAMIENTAS_LOCALES, modo))
    assert res['equivalentes'], res['criterios']
    assert res['resumenes']['pandas']['filas'] == ESPERADO['filtrado_benchmark']


def test_equivalencia_datos_reales_pandas_polars(cfg_real):
    res = comparar(_ejecutar(cfg_real, HERRAMIENTAS_LOCALES, 'por_operacion'))
    assert res['equivalentes'], res['criterios']
    assert res['resumenes']['pandas']['filas'] == 1103 + 659


@pytest.mark.spark
@pytest.mark.parametrize('modo', ['por_operacion', 'extremo_a_extremo', 'extremo_a_extremo_caliente'])
def test_equivalencia_tres_herramientas(cfg_real, modo):
    res = comparar(_ejecutar(cfg_real, ['pandas', 'polars', 'spark'], modo))
    assert res['equivalentes'], res['criterios']


def test_plan_rota_orden_y_separa_calentamiento(cfg_real):
    plan = plan_benchmark(cfg_real, modos=['por_operacion'], repeticiones=3)
    calentamientos = [p for p in plan if p[3]]
    medidas = [p for p in plan if not p[3]]
    assert len(calentamientos) == 3 and len(medidas) == 9
    primeras = [medidas[i * 3][0] for i in range(3)]
    assert primeras == ['pandas', 'polars', 'spark']
