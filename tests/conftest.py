import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'src'))

from emergencias123.config import cargar_config  # noqa: E402

ENCABEZADO = ('NUMERO_INCIDENTE;FECHA_INICIO_DESPLAZAMIENTO_MOVIL;CODIGO_LOCALIDAD;LOCALIDAD;EDAD;UNIDAD;'
              'GENERO;TIPO_INCIDENTE;PRIORIDAD_FINAL;RECEPCION')
# Datos sintéticos de prueba (no son registros reales): cada fila ejercita una regla del pipeline.
FIXTURE = {
    'llamadas123_julio_2026.csv': [
        'CRU-1;2026-07-01 00:08:54;14;LOS MÁRTIRES;1;Años;MASCULINO;ACOMPAÑAMIENTO A EVENTO;Baja;',
        'CRU-2;2026-07-02 10:00:00;1;USAQUÉN;42;Años;FEMENINO;ENFERMO;Media;2026-07-02 11:00:00',
        'CRU-3;2026-07-03 10:00:00;2;CHAPINERO;N/A;N/A;N/A;AMESUI  - AMENAZA DE SUICIDIO;Alta;',
        'CRU-2;2026-07-02 10:00:00;1;USAQUÉN;42;Años;FEMENINO;ENFERMO;Media;2026-07-02 11:00:00',
        'CRU-4;fecha-mala;1;USAQUÉN;30;Años;MASCULINO;INTSUI - INTENTO DE SUICIDIO;Alta;',
        'CRU-5;2026-07-05 10:00:00;SIN_D;SIN_D;N/A;N/A;N/A;ENFERMO;Baja;',
        'CRU-6;2026-07-06 10:00:00;3;USAQUÉN;30;Años;MASCULINO;ENFERMO;Baja;',
        'CRU-7;2026-07-07 10:00:00;1;USAQUÉN;150;Años;MASCULINO;ENFERMO;Baja;',
        'CRU-8;2026-08-01 00:30:00;2;CHAPINERO;5;Meses;FEMENINO;CONVULSIÓN - CONVULSIÓN;Critica;',
    ],
    'llamadaslinea123agosto2026.csv': [
        'CRU-2;2026-08-02 10:00:00;1;USAQUÉN;42;Años;FEMENINO;ENFERMO;Media;',
        'CRU-9;2026-08-03 10:00:00;10;ENGATIVÁ;20;Años;MASCULINO;HERIDO - HERIDOS ACCIDENTALES;Alta;',
    ],
    'llamadaslinea123Septiembre.csv': [
        'CRU-10;2026-09-10 10:00:00;2;CHAPINERO;33;Años;FEMENINO;CODNUEVO - TIPO NUEVO;Alta;',
    ],
}
# Regla de limpieza: solo se elimina la copia duplicada exacta (CRU-2 repetido en julio). Las demás anomalías
# se conservan y quedan marcadas en `observacion_calidad`.
ESPERADO = {'leidos': 12, 'aceptados': 11, 'rechazados': 1, 'duplicados_exactos': 1, 'filas_incidente_repetido': 2,
            'codigos_no_reconocidos': 1, 'fuera_mes_aceptados': 1, 'fuera_ventana_aceptados': 0,
            'rechazos_por_motivo': {'duplicado_exacto': 1},
            'observaciones_por_motivo': {'fecha_inicio_invalida': 1, 'localidad_sin_dato': 1,
                                         'codigo_localidad_inconsistente': 1, 'edad_fuera_rango': 1},
            'nulos_criticos_aceptados': 2, 'nulos_criticos_sin_observacion': 0,
            'filtrado_benchmark': 9}


def pytest_configure(config):
    config.addinivalue_line('markers', 'spark: requiere PySpark con JVM (runtime de Google Colab)')


def pytest_collection_modifyitems(config, items):
    if not sys.platform.startswith('linux'):  # el proyecto se ejecuta en el runtime Linux de Colab
        omitir = pytest.mark.skip(reason='Las pruebas de Spark se ejecutan en el runtime de Google Colab')
        for item in items:
            if 'spark' in item.keywords:
                item.add_marker(omitir)


@pytest.fixture
def cfg_fixture(tmp_path, monkeypatch):
    datos = tmp_path / 'datos'
    datos.mkdir()
    for nombre, filas in FIXTURE.items():
        (datos / nombre).write_bytes(('﻿' + '\r\n'.join([ENCABEZADO, *filas]) + '\r\n').encode('utf-8'))
    monkeypatch.setenv('U2_DIR_DATOS', str(datos))
    return cargar_config(entorno='local', dir_resultados=tmp_path / 'resultados')


@pytest.fixture
def cfg_real(tmp_path):
    cfg = cargar_config(dir_resultados=tmp_path / 'resultados')
    if not all(r.exists() for r in cfg.rutas_csv):
        pytest.skip('CSV reales no disponibles en este entorno')
    return cfg
