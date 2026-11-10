"""Cifras que alimentan los documentos, calculadas SOLO a partir de resultados/mediciones/.

También contiene el modelo de escalabilidad: ajuste lineal tiempo/memoria vs. registros sobre los
puntos MEDIDOS (3 meses reales y replicados x4/x8). Lo que exceda esos puntos es extrapolación teórica.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERRAMIENTAS = ['pandas', 'polars', 'spark']
REGISTROS_MES = 27434 / 3


def _leer_jsonl(ruta):
    return pd.read_json(ruta, lines=True) if Path(ruta).exists() else pd.DataFrame()


def resumen_benchmark(dir_med):
    crudo = _leer_jsonl(dir_med / 'benchmark.jsonl')
    errores = int((crudo['estado'] != 'ok').sum())
    med = crudo[(crudo['estado'] == 'ok') & (~crudo['calentamiento'].astype(bool))]
    tot = (med[med['operacion'] == 'total'].groupby(['modo', 'herramienta'])
           .agg(seg=('segundos', 'mean'), seg_de=('segundos', 'std'), seg_min=('segundos', 'min'), seg_max=('segundos', 'max'),
                rss=('rss_pico_mb', 'mean'), sis=('mem_sis_pico_pct', 'mean'), sis_base=('mem_sis_base_pct', 'mean'),
                n=('segundos', 'size')))
    ops = (med[(med['modo'] == 'por_operacion')].groupby(['operacion', 'herramienta'])['segundos'].mean().unstack())
    arranque = med[(med['herramienta'] == 'spark') & (med['operacion'] == 'inicio_sesion')]['segundos']
    eq_ruta = dir_med / 'equivalencia_benchmark.json'
    equivalencia = json.loads(eq_ruta.read_text(encoding='utf-8')) if eq_ruta.exists() else {}
    return {'med': med, 'crudo': crudo, 'errores': errores, 'tot': tot, 'ops': ops,
            'arranque_spark': float(arranque.mean()), 'arranque_spark_de': float(arranque.std()),
            'repeticiones': int(med.groupby(['herramienta', 'modo'])['ejecucion'].nunique().min()),
            'equivalencia': equivalencia,
            'equivalentes': all(r.get('equivalentes') for r in equivalencia.values()) if equivalencia else None}


def resumen_poc(dir_med):
    crudo = _leer_jsonl(dir_med / 'poc.jsonl')
    ok = crudo[crudo['estado'] == 'ok']
    principal = ok[ok['etiqueta'].isna()]
    variante = ok[ok['etiqueta'] == 'variante_periodo_localidad']
    cols = ['tiempo_total_s', 'tiempo_inicio_sesion_s', 'mem_sis_pico_pct', 'mem_sis_base_pct', 'rss_pico_mb',
            'throughput_reg_min', 'tasa_validaciones_pct', 'registros_validos_pct', 'leidos', 'aceptados',
            'rechazados', 'errores', 'parquet_archivos', 'parquet_bytes']
    prom = principal.groupby('herramienta')[cols].mean()
    de = principal.groupby('herramienta')[cols].std()
    ultima = principal[principal['herramienta'] == 'spark'].sort_values('ejecucion').iloc[-1]
    return {'crudo': crudo, 'principal': principal, 'variante': variante, 'prom': prom, 'de': de,
            'ultima_spark': ultima, 'errores_ejecucion': int((crudo['estado'] != 'ok').sum()),
            'ejecuciones': int(principal.groupby('herramienta')['ejecucion'].nunique().min())}


def modelo_escalabilidad(poc, dir_med):
    """Ajuste lineal por herramienta: y = a + b·N con los puntos medidos (factor 1 real; 4 y 8 replicados)."""
    esc = _leer_jsonl(dir_med / 'escalabilidad.jsonl')
    if esc.empty:
        return None
    esc = esc[esc['estado'] == 'ok']
    puntos = []
    for h in ('spark', 'pandas'):
        p = poc['prom'].loc[h]
        puntos.append({'herramienta': h, 'factor': 1, 'leidos': p['leidos'], 'tiempo_total_s': p['tiempo_total_s'],
                       'rss_pico_mb': p['rss_pico_mb'], 'mem_sis_pico_pct': p['mem_sis_pico_pct'], 'origen': 'medido (real)'})
        for _, r in esc[esc['herramienta'] == h].iterrows():
            puntos.append({'herramienta': h, 'factor': int(r['factor_replica']), 'leidos': r['leidos'],
                           'tiempo_total_s': r['tiempo_total_s'], 'rss_pico_mb': r['rss_pico_mb'],
                           'mem_sis_pico_pct': r['mem_sis_pico_pct'], 'origen': 'medido (replicado)'})
    puntos = pd.DataFrame(puntos).sort_values(['herramienta', 'factor'])
    ajustes = {}
    for h, d in puntos.groupby('herramienta'):
        bt, at = np.polyfit(d['leidos'], d['tiempo_total_s'], 1)
        bm, am = np.polyfit(d['leidos'], d['rss_pico_mb'], 1)
        ajustes[h] = {'t_fijo_s': at, 't_por_millon_s': bt * 1e6, 'rss_fijo_mb': am, 'rss_por_millon_mb': bm * 1e6}
    return {'puntos': puntos, 'ajustes': ajustes}


def proyectar(ajuste, registros):
    return (ajuste['t_fijo_s'] + ajuste['t_por_millon_s'] * registros / 1e6,
            ajuste['rss_fijo_mb'] + ajuste['rss_por_millon_mb'] * registros / 1e6)


def cargar_todo(dir_resultados):
    dir_med = Path(dir_resultados) / 'mediciones'
    entorno = json.loads((dir_med / 'entorno_colab.json').read_text(encoding='utf-8'))
    inventario = json.loads((dir_med / 'inventario_datos.json').read_text(encoding='utf-8'))
    bench = resumen_benchmark(dir_med)
    poc = resumen_poc(dir_med)
    ruta_optim = dir_med / 'optimizacion_poc.json'
    return {'entorno': entorno, 'inventario': inventario, 'bench': bench, 'poc': poc,
            'escala': modelo_escalabilidad(poc, dir_med),
            'optim': json.loads(ruta_optim.read_text(encoding='utf-8')) if ruta_optim.exists() else None}
