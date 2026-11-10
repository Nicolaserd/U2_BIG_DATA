import csv

import pandas as pd
import polars as pl
import pytest

from emergencias123 import ops_pandas, ops_polars
from emergencias123.catalogo import derivar_catalogo, leer_catalogo
from emergencias123.loc import loc_por_herramienta
from emergencias123.normalizacion import extraer_codigo_tipo, extraer_descripcion_tipo, normalizar_texto


@pytest.mark.parametrize('entrada, esperado', [
    ('  Usaquén ', 'USAQUEN'), ('LOS MÁRTIRES', 'LOS MARTIRES'), ('ANTONIO NARIÑO', 'ANTONIO NARINO'),
    ('', None), (None, None), ('a  b\tc', 'A B C'),
])
def test_normalizar_texto(entrada, esperado):
    assert normalizar_texto(entrada) == esperado


@pytest.mark.parametrize('entrada, codigo, descripcion', [
    ('INTSUI - INTENTO DE SUICIDIO', 'INTSUI', 'INTENTO DE SUICIDIO'),
    ('AMESUI  - AMENAZA DE SUICIDIO', 'AMESUI', 'AMENAZA DE SUICIDIO'),
    ('CONVULSIÓN - CONVULSIÓN', 'CONVULSION', 'CONVULSIÓN'),
    ('ENFERMO', 'ENFERMO', 'ENFERMO'),
    ('ELECTROCUC - ELECTROCUCIÓN / RESCATE', 'ELECTROCUC', 'ELECTROCUCIÓN / RESCATE'),
])
def test_extraer_codigo_y_descripcion(entrada, codigo, descripcion):
    assert extraer_codigo_tipo(entrada) == codigo
    assert extraer_descripcion_tipo(entrada) == descripcion


def _valores_reales(cfg, columna):
    valores = set()
    for ruta in cfg.rutas_csv:
        with open(ruta, encoding=cfg.datos['codificacion'], newline='') as f:
            valores |= {r[columna] for r in csv.DictReader(f, delimiter=';')}
    return sorted(valores)


def test_vectorizado_pandas_polars_igual_a_referencia(cfg_real):
    """Las versiones vectorizadas reproducen exactamente la función de referencia en los datos reales."""
    for col in ('LOCALIDAD', 'TIPO_INCIDENTE'):
        valores = _valores_reales(cfg_real, col)
        ref = [normalizar_texto(v) for v in valores]
        assert ops_pandas._normalizar(pd.Series(valores)).tolist() == ref
        assert pl.DataFrame({col: valores}).select(ops_polars._normalizar(col))[col].to_list() == ref
        assert all(r.isascii() for r in ref), 'quedan caracteres no ASCII sin mapear'


def test_catalogo_real_clave_unica_y_cobertura(cfg_real):
    catalogo = leer_catalogo(cfg_real.ruta_catalogo_tipos)
    assert len(catalogo) == 23
    codigos = {c['codigo_tipo'] for c in catalogo}
    assert {extraer_codigo_tipo(v) for v in _valores_reales(cfg_real, 'TIPO_INCIDENTE')} <= codigos
    assert all('no oficial' in c['fuente'] for c in catalogo)


def test_catalogo_ambiguo_falla():
    with pytest.raises(ValueError):
        derivar_catalogo(['ABC - UNO', 'ABC - DOS'])


def test_loc_contadas_para_todas_las_operaciones():
    loc = loc_por_herramienta()
    for herramienta, conteos in loc.items():
        assert set(conteos) == {'carga', 'filtrado', 'agregacion', 'join', 'exportacion'}, herramienta
        assert all(n > 0 for n in conteos.values()), herramienta
