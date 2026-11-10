from pathlib import Path

import pytest

from emergencias123.poc import ejecutar_poc


@pytest.mark.spark
def test_planes_formatos_nulos_atipicos(cfg_fixture, tmp_path):
    from emergencias123.optimizacion import atipicos_iqr, comparar_formatos, perfil_nulos, planes_ejecucion
    from emergencias123.spark_session import crear_sesion, detener_sesion

    # Parquet de detalle escrito por Spark (el que analiza el notebook). El de Pandas usa marcas de tiempo en
    # nanosegundos, que Spark 4 no sabe leer (PARQUET_TYPE_ILLEGAL), así que no sirve como entrada de este análisis.
    metricas, _, _ = ejecutar_poc('spark', 1, cfg_fixture)
    detalle = Path(metricas['ruta_salida']) / 'detalle'
    spark = crear_sesion(cfg_fixture)
    try:
        planes = planes_ejecucion(spark, detalle, cfg_fixture.ruta_catalogo_tipos)
        assert planes['poda_particiones'] and planes['predicado_empujado'] and planes['broadcast_join']
        formatos = comparar_formatos(spark, detalle, tmp_path / 'formatos', repeticiones=1)
        assert [f['formato'] for f in formatos['formatos']] == ['CSV', 'JSON', 'Parquet']
        assert all(f['filas'] == formatos['registros'] for f in formatos['formatos'])
        df = spark.read.parquet(str(detalle))
        nulos = {n['columna']: n['nulos'] for n in perfil_nulos(df)}
        assert nulos['edad'] >= 1  # el fixture trae edades N/A convertidas a nulo, no imputadas
        assert atipicos_iqr(df, 'edad_anios')['atipicos'] >= 0
    finally:
        detener_sesion(spark)
