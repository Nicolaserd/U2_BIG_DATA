"""Operaciones del benchmark en Pandas (ejecución inmediata: cada llamada ya materializa)."""
import pandas as pd

from .normalizacion import CON_TILDE, SIN_TILDE

TILDES = str.maketrans(CON_TILDE, SIN_TILDE)


def _normalizar(serie):
    return serie.str.translate(TILDES).str.replace(r'\s+', ' ', regex=True).str.strip().str.upper()


def carga(rutas, separador=';', codificacion='utf-8-sig'):
    # >>> op:carga
    partes = [pd.read_csv(r, sep=separador, encoding=codificacion, dtype=str,
                          keep_default_na=False, na_values=['']) for r in rutas]
    df = pd.concat(partes, ignore_index=True)
    # <<< op:carga
    return df


def filtrado(df, localidades):
    # >>> op:filtrado
    df = df.assign(localidad_norm=_normalizar(df['LOCALIDAD']),
                   codigo_tipo=_normalizar(df['TIPO_INCIDENTE']).str.split(' - ', n=1).str[0])
    df = df[df['localidad_norm'].isin(localidades)].reset_index(drop=True)
    # <<< op:filtrado
    return df


def agregacion(df):
    # >>> op:agregacion
    conteo = df.groupby('codigo_tipo').size().reset_index(name='conteo')
    conteo = conteo.sort_values(['conteo', 'codigo_tipo'], ascending=[False, True], ignore_index=True)
    # <<< op:agregacion
    return conteo


def join(df, ruta_catalogo):
    # >>> op:join
    catalogo = pd.read_csv(ruta_catalogo, dtype=str, usecols=['codigo_tipo', 'descripcion_tipo', 'codigo_explicito'])
    catalogo['codigo_explicito'] = catalogo['codigo_explicito'] == 'True'
    enriquecido = df.merge(catalogo, on='codigo_tipo', how='left', validate='many_to_one')
    # <<< op:join
    return enriquecido


def exportacion(df, ruta_salida):
    # >>> op:exportacion
    df.to_parquet(ruta_salida / 'parte-0.parquet', index=False)
    # <<< op:exportacion


def filas(df):
    return len(df)


def a_dict_conteo(conteo):
    return dict(zip(conteo['codigo_tipo'], conteo['conteo'].astype(int)))


def sin_coincidencia(df):
    return int(df['descripcion_tipo'].isna().sum())
