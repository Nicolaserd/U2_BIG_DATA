import pyarrow.dataset as ds
import pytest

from conftest import ESPERADO
from emergencias123.poc import ejecutar_poc
from emergencias123.validaciones import COLUMNAS_DETALLE, tasas


def _verificar_hechos(metricas, hechos, controles):
    assert metricas['estado'] == 'ok', metricas.get('traza')
    for clave in ('leidos', 'aceptados', 'rechazados', 'duplicados_exactos', 'filas_incidente_repetido',
                  'codigos_no_reconocidos', 'fuera_mes_aceptados', 'fuera_ventana_aceptados', 'rechazos_por_motivo',
                  'observaciones_por_motivo', 'nulos_criticos_aceptados', 'nulos_criticos_sin_observacion'):
        assert hechos[clave] == ESPERADO[clave], clave
    # El fixture provoca a propósito 4 advertencias: fecha no parseable (V05), código nuevo no reconocido (V08),
    # código de localidad inconsistente (V10) y edad fuera de rango (V11). Esos registros se CONSERVAN marcados.
    fallidos = {c['id'] for c in controles if not c['aprobado']}
    assert fallidos == {'V05', 'V08', 'V10', 'V11'}
    assert metricas['tasa_validaciones_pct'] == round(100 * 12 / 16, 2)
    assert metricas['registros_validos_pct'] == round(100 * 11 / 12, 4)
    detalle = ds.dataset(metricas['ruta_salida'] + '/detalle', format='parquet', partitioning='hive').to_table()
    assert sorted(detalle.column_names) == sorted(COLUMNAS_DETALLE)
    assert detalle.num_rows == ESPERADO['aceptados']
    observaciones = [o for o in detalle.column('observacion_calidad').to_pylist() if o]
    assert len(observaciones) == 4, 'las anomalías se conservan marcadas, no se eliminan'
    duplicados = ds.dataset(metricas['ruta_salida'] + '/duplicados_eliminados', format='parquet').to_table()
    assert duplicados.num_rows == ESPERADO['rechazados'], 'la copia eliminada queda registrada aparte'


def test_pipeline_pandas_reglas(cfg_fixture):
    _verificar_hechos(*ejecutar_poc('pandas', 1, cfg_fixture))


@pytest.mark.spark
def test_pipeline_spark_reglas(cfg_fixture):
    _verificar_hechos(*ejecutar_poc('spark', 1, cfg_fixture))


@pytest.mark.spark
def test_pipeline_spark_y_pandas_coinciden_en_datos_reales(cfg_real):
    m_s, h_s, _ = ejecutar_poc('spark', 1, cfg_real)
    m_p, h_p, _ = ejecutar_poc('pandas', 1, cfg_real)
    for clave in ('leidos', 'aceptados', 'rechazados', 'rechazos_por_motivo', 'duplicados_exactos',
                  'observaciones_por_motivo', 'nulos_criticos_aceptados', 'filas_incidente_repetido',
                  'parquet_conteo', 'suma_agregado_principal'):
        assert h_s[clave] == h_p[clave], clave
    # Solo se eliminan las 44 copias duplicadas exactas de los datos reales; los nulos se conservan.
    assert h_s['leidos'] - h_s['aceptados'] == h_s['duplicados_exactos'] == 44
    assert m_s['tasa_validaciones_pct'] == m_p['tasa_validaciones_pct'] == 100.0


def test_formula_tasas_excluye_informativos():
    controles = [{'id': 'A', 'severidad': 'bloqueante', 'aprobado': True},
                 {'id': 'B', 'severidad': 'advertencia', 'aprobado': False},
                 {'id': 'C', 'severidad': 'informativo', 'aprobado': True},
                 {'id': 'D', 'severidad': 'bloqueante', 'aprobado': True}]
    t = tasas(controles, {'aceptados': 90, 'leidos': 100})
    assert t['tasa_validaciones_pct'] == round(100 * 2 / 3, 2)
    assert t['controles_fallidos'] == ['B']
    assert t['registros_validos_pct'] == 90.0


def test_replicacion_escala_el_volumen_sin_crear_duplicados_exactos(cfg_fixture, tmp_path, monkeypatch):
    """Las réplicas sintéticas del experimento de escalabilidad no deben eliminarse como duplicados exactos."""
    from emergencias123.config import cargar_config
    from emergencias123.poc import replicar_datos
    destino = replicar_datos(cfg_fixture, 3, tmp_path / 'x3')
    monkeypatch.setenv('U2_DIR_DATOS', str(destino))
    cfg3 = cargar_config(entorno='local', dir_resultados=tmp_path / 'res_x3')
    metricas, hechos, _ = ejecutar_poc('pandas', 1, cfg3)
    assert metricas['estado'] == 'ok', metricas.get('traza')
    assert hechos['leidos'] == 3 * ESPERADO['leidos']
    assert hechos['aceptados'] == 3 * ESPERADO['aceptados']
    assert hechos['duplicados_exactos'] == 3 * ESPERADO['duplicados_exactos']
