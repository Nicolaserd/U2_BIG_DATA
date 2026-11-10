"""Mismo alcance del PoC implementado en Pandas, para comparar en igualdad de condiciones.

Reproduce las reglas de pipeline_spark.py: tipado sin imputación, observaciones de calidad (sin eliminar),
eliminación solo de duplicados exactos, enriquecimiento con el catálogo derivado, agregados y Parquet particionado por periodo.
"""
import shutil

import numpy as np
import pandas as pd

from .catalogo import leer_catalogo
from .normalizacion import CON_TILDE, SIN_TILDE
from .validaciones import COLUMNAS_DETALLE, leer_localidades, prevalidar

TILDES = str.maketrans(CON_TILDE, SIN_TILDE)


def _norm(serie):
    return serie.str.translate(TILDES).str.replace(r'\s+', ' ', regex=True).str.strip().str.upper()


def procesar(cfg, salida, particionamiento=None):
    esq, poc = cfg.esquema, cfg.poc
    hechos = prevalidar(cfg)

    # 1-3. Ingesta (todo texto), procedencia y nulos explícitos
    partes = []
    for ruta in cfg.rutas_csv:
        if ruta.exists():
            p = pd.read_csv(ruta, sep=cfg.datos['separador'], encoding=cfg.datos['codificacion'], dtype=str,
                            keep_default_na=False, na_values=[''])
            partes.append(p.assign(archivo_origen=ruta.name, periodo=cfg.periodo_por_archivo[ruta.name]))
    df = pd.concat(partes, ignore_index=True)
    for c in esq['columnas']:
        df[c] = df[c].str.strip().where(~df[c].str.strip().isin(esq['valores_nulos']))

    # 4-5. Tipos y estandarización
    localidades = leer_localidades(cfg)
    df['fecha_inicio'] = pd.to_datetime(df['FECHA_INICIO_DESPLAZAMIENTO_MOVIL'], format=esq['formato_fecha'], errors='coerce')
    df['fecha_recepcion'] = pd.to_datetime(df['RECEPCION'], format=esq['formato_fecha'], errors='coerce')
    df['codigo_localidad'] = pd.to_numeric(df['CODIGO_LOCALIDAD'], errors='coerce').astype('Int32')
    df['edad'] = pd.to_numeric(df['EDAD'], errors='coerce').astype('Int32')
    df['localidad_norm'] = _norm(df['LOCALIDAD'])
    df['unidad'] = _norm(df['UNIDAD'])
    df['genero'] = _norm(df['GENERO'])
    df['prioridad'] = _norm(df['PRIORIDAD_FINAL'])
    df['codigo_tipo'] = _norm(df['TIPO_INCIDENTE']).str.split(' - ', n=1).str[0]
    df['edad_anios'] = df['edad'].astype('Float64') * df['unidad'].map(poc['factores_edad']).astype('Float64')
    df['paciente_completo'] = df['edad'].notna() & df['unidad'].notna() & df['genero'].notna()
    inicio_mes = pd.to_datetime(df['periodo'] + '-01')
    fin_mes = inicio_mes + pd.DateOffset(months=1)
    df['en_mes_archivo'] = (df['fecha_inicio'] >= inicio_mes) & (df['fecha_inicio'] < fin_mes)
    en_ventana = (df['fecha_inicio'] >= inicio_mes) & (
        df['fecha_inicio'] < fin_mes + pd.Timedelta(days=poc['tolerancia_dias_fin_mes']))

    # 6. Observaciones de calidad (la primera que aplique): el registro se CONSERVA, solo se marca
    esperado = df['localidad_norm'].map(localidades)
    edad_mala = df['edad_anios'].notna() & ((df['edad_anios'] < poc['edad_min_anios'])
                                            | (df['edad_anios'] > poc['edad_max_anios']))
    condiciones = [
        pd.Series(False, index=df.index),
        df['NUMERO_INCIDENTE'].isna(),
        df['fecha_inicio'].isna(),
        df['localidad_norm'].isna() | (df['localidad_norm'] == esq['localidad_sin_dato']),
        ~df['localidad_norm'].isin(list(localidades)),
        df['codigo_localidad'].isna() | (df['codigo_localidad'] != esperado),
        df['codigo_tipo'].isna(),
        edad_mala,
    ]
    motivos = ['registro_corrupto', 'numero_incidente_nulo', 'fecha_inicio_invalida', 'localidad_sin_dato',
               'localidad_fuera_catalogo', 'codigo_localidad_inconsistente', 'tipo_incidente_nulo', 'edad_fuera_rango']
    df['observacion_calidad'] = np.select([c.fillna(True).to_numpy(dtype=bool) for c in condiciones], motivos, default=None)
    df['observacion_calidad'] = df['observacion_calidad'].where(df['observacion_calidad'].notna(), None)

    # 7. Duplicados exactos: se ELIMINAN las copias (100 % de atributos iguales); se conserva la primera aparición
    df['es_duplicado_exacto'] = df.duplicated(subset=esq['columnas'], keep='first')
    df['incidente_multidespacho'] = df.groupby('NUMERO_INCIDENTE', dropna=False)['NUMERO_INCIDENTE'].transform('size') > 1

    rechazo = df['es_duplicado_exacto']  # lo único que se elimina
    hechos.update({
        'leidos': len(df), 'aceptados': int((~rechazo).sum()), 'rechazados': int(rechazo.sum()),
        'fechas_invalidas': int((df['FECHA_INICIO_DESPLAZAMIENTO_MOVIL'].notna() & df['fecha_inicio'].isna()).sum()),
        'duplicados_exactos': int(df['es_duplicado_exacto'].sum()),
        'filas_incidente_repetido': int((~rechazo & df['incidente_multidespacho']).sum()),
        'observaciones_por_motivo': {k: int(v) for k, v in
                                     df.loc[~rechazo, 'observacion_calidad'].value_counts().items()},
    })
    hechos['rechazos_por_motivo'] = {'duplicado_exacto': hechos['rechazados']} if hechos['rechazados'] else {}
    hechos['inconsistencias_localidad'] = hechos['observaciones_por_motivo'].get('codigo_localidad_inconsistente', 0)

    # 8. Enriquecimiento con el catálogo derivado
    filas_cat = leer_catalogo(cfg.ruta_catalogo_tipos)
    catalogo = pd.DataFrame(filas_cat)[['codigo_tipo', 'descripcion_tipo', 'codigo_explicito']]
    hechos['catalogo_clave_unica'] = catalogo['codigo_tipo'].is_unique
    aceptados = df.loc[~rechazo].assign(en_ventana=en_ventana[~rechazo])
    hechos['filas_antes_join'] = len(aceptados)
    enriquecido = aceptados.merge(catalogo, on='codigo_tipo', how='left', validate='many_to_one')
    enriquecido['codigo_reconocido'] = enriquecido['descripcion_tipo'].notna()
    detalle = enriquecido.rename(columns={'NUMERO_INCIDENTE': 'numero_incidente', 'LOCALIDAD': 'localidad',
                                          'TIPO_INCIDENTE': 'tipo_incidente'})
    criticos = ['numero_incidente', 'fecha_inicio', 'codigo_localidad', 'localidad_norm', 'codigo_tipo']
    hechos.update({
        'filas_despues_join': len(detalle),
        'codigos_no_reconocidos': int((~detalle['codigo_reconocido']).sum()),
        'fuera_ventana_aceptados': int((detalle['fecha_inicio'].notna() & ~detalle['en_ventana']).sum()),
        'fuera_mes_aceptados': int((detalle['fecha_inicio'].notna() & ~detalle['en_mes_archivo']).sum()),
        'nulos_criticos_aceptados': int(detalle[criticos].isna().any(axis=1).sum()),
        'nulos_criticos_sin_observacion': int((detalle[criticos].isna().any(axis=1)
                                               & detalle['observacion_calidad'].isna()).sum()),
        'edades_fuera_rango_aceptados': int((detalle['edad_anios'].notna() & (
            (detalle['edad_anios'] < poc['edad_min_anios']) | (detalle['edad_anios'] > poc['edad_max_anios']))).sum()),
    })
    detalle = detalle[COLUMNAS_DETALLE]

    # 9. Agregados
    agregados = {
        'periodo_localidad_tipo': detalle.groupby(['periodo', 'localidad_norm', 'codigo_tipo', 'descripcion_tipo'],
                                                  dropna=False).size().reset_index(name='conteo'),
        'periodo_prioridad': detalle.groupby(['periodo', 'prioridad'], dropna=False).size().reset_index(name='conteo'),
        'diario': detalle.groupby(detalle['fecha_inicio'].dt.date.rename('fecha'), dropna=False).size().reset_index(name='conteo'),
    }
    hechos['suma_agregado_principal'] = int(agregados['periodo_localidad_tipo']['conteo'].sum())

    # 10. Exportación Parquet (mismo particionamiento que Spark)
    modo = particionamiento or poc['particionamiento']
    columnas_particion = ['periodo', 'localidad_norm'] if modo == 'periodo_localidad' else ['periodo']
    for sub in ('detalle', 'agregados', 'duplicados_eliminados'):
        shutil.rmtree(salida / sub, ignore_errors=True)
    (detalle.sort_values(['periodo', 'localidad_norm', 'fecha_inicio'])
     .to_parquet(salida / 'detalle', partition_cols=columnas_particion, index=False))
    for nombre, agg in agregados.items():
        (salida / 'agregados' / nombre).mkdir(parents=True, exist_ok=True)
        agg.to_parquet(salida / 'agregados' / nombre / 'parte-0.parquet', index=False)
    (salida / 'duplicados_eliminados').mkdir(parents=True, exist_ok=True)
    (df.loc[rechazo, esq['columnas'] + ['archivo_origen', 'periodo']]
     .to_parquet(salida / 'duplicados_eliminados' / 'parte-0.parquet', index=False))
    hechos['particionamiento'] = modo
    return hechos
