"""Operaciones del benchmark en Polars.

Las mismas funciones sirven para DataFrame (modo por_operacion, eager) y LazyFrame
(modo extremo_a_extremo, perezoso): la API de expresiones es común a ambos.
"""
import polars as pl

from .normalizacion import CON_TILDE, SIN_TILDE


def _normalizar(columna):
    return (pl.col(columna).str.replace_many(list(CON_TILDE), list(SIN_TILDE))
            .str.replace_all(r'\s+', ' ').str.strip_chars().str.to_uppercase())


def carga(rutas, separador=';', perezoso=False):
    # >>> op:carga
    leer = pl.scan_csv if perezoso else pl.read_csv
    df = pl.concat([leer(r, separator=separador, infer_schema=False) for r in rutas])
    # <<< op:carga
    return df


def filtrado(df, localidades):
    # >>> op:filtrado
    df = df.with_columns(localidad_norm=_normalizar('LOCALIDAD'),
                         codigo_tipo=_normalizar('TIPO_INCIDENTE').str.split(' - ').list.first())
    df = df.filter(pl.col('localidad_norm').is_in(localidades))
    # <<< op:filtrado
    return df


def agregacion(df):
    # >>> op:agregacion
    conteo = df.group_by('codigo_tipo').agg(conteo=pl.len())
    conteo = conteo.sort(['conteo', 'codigo_tipo'], descending=[True, False])
    # <<< op:agregacion
    return conteo


def join(df, ruta_catalogo):
    # >>> op:join
    catalogo = pl.read_csv(ruta_catalogo, infer_schema=False,
                           columns=['codigo_tipo', 'descripcion_tipo', 'codigo_explicito'])
    catalogo = catalogo.with_columns(codigo_explicito=pl.col('codigo_explicito') == 'True')
    enriquecido = df.join(catalogo.lazy() if isinstance(df, pl.LazyFrame) else catalogo,
                          on='codigo_tipo', how='left', validate='m:1')
    # <<< op:join
    return enriquecido


def exportacion(df, ruta_salida):
    # >>> op:exportacion
    df.write_parquet(ruta_salida / 'parte-0.parquet')
    # <<< op:exportacion


def filas(df):
    return df.height


def a_dict_conteo(conteo):
    return dict(zip(conteo['codigo_tipo'].to_list(), conteo['conteo'].to_list()))


def sin_coincidencia(df):
    return int(df['descripcion_tipo'].null_count())
