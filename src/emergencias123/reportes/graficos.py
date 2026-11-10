"""Gráficos del benchmark y del PoC (matplotlib, 300 dpi).

Paleta categórica validada (orden fijo, color ligado a la herramienta y no a su posición):
Pandas azul, Polars naranja, Spark aqua. El aqua queda bajo 3:1 de contraste sobre la superficie,
por eso cada barra lleva su valor rotulado. Nunca se usan dos ejes Y: cada magnitud va en su panel.
"""
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

COLORES = {'pandas': '#2a78d6', 'polars': '#eb6834', 'spark': '#1baf7a'}
NOMBRES = {'pandas': 'Pandas', 'polars': 'Polars', 'spark': 'PySpark'}
ORDEN = ['pandas', 'polars', 'spark']
SUPERFICIE, TINTA, TINTA_2, MUTED, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9'
OPERACIONES = ['carga', 'filtrado', 'agregacion', 'join', 'exportacion']
ETIQUETAS_OP = {'carga': 'Carga', 'filtrado': 'Filtrado', 'agregacion': 'Agregación', 'join': 'Join',
                'exportacion': 'Exportación'}


def _estilo(ax, titulo, eje):
    ax.set_facecolor(SUPERFICIE)
    ax.set_title(titulo, loc='left', fontsize=11, color=TINTA, fontweight='bold', pad=10)
    ax.set_xlabel(eje, color=TINTA_2, fontsize=9)
    ax.tick_params(colors=TINTA_2, labelsize=9, length=0)
    for lado in ('top', 'right', 'left'):
        ax.spines[lado].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.grid(axis='x', color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _rotular(ax, barras, valores, desv, fmt):
    for b, v, e in zip(barras, valores, desv):
        ax.annotate(fmt.format(v), (b.get_width() + (e or 0), b.get_y() + b.get_height() / 2), xytext=(6, 0),
                    textcoords='offset points', va='center', fontsize=8, color=TINTA)


def _barras_h(ax, etiquetas, medias, desv, colores, fmt):
    pos = range(len(etiquetas))
    barras = ax.barh(list(pos), medias, xerr=desv, color=colores, height=0.6,
                     error_kw={'ecolor': MUTED, 'elinewidth': 1, 'capsize': 3})
    ax.set_yticks(list(pos), etiquetas)
    ax.invert_yaxis()
    _rotular(ax, barras, medias, desv, fmt)
    limite = max(m + (d or 0) for m, d in zip(medias, desv)) * 1.45
    ax.set_xlim(0, min(limite, 100) if '%' in fmt else limite)


def _figura(ncols, ancho, alto, nrows=1):
    fig, axes = plt.subplots(nrows, ncols, figsize=(ancho, alto), facecolor=SUPERFICIE, squeeze=False)
    return fig, list(axes.flat)


def _guardar(fig, ruta, titulo, nota):
    fig.suptitle(titulo, x=0.01, ha='left', fontsize=13, fontweight='bold', color=TINTA)
    fig.text(0.01, 0.005, nota, fontsize=7.5, color=TINTA_2, ha='left', va='bottom', wrap=True)
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(ruta, dpi=300, facecolor=SUPERFICIE)
    plt.close(fig)
    return ruta


def grafico_operaciones(medidas, ruta):
    """Tiempo medio por operación (modo por_operacion), un panel por operación (escalas propias)."""
    d = medidas[(medidas['modo'] == 'por_operacion') & medidas['operacion'].isin(OPERACIONES)]
    est = d.groupby(['operacion', 'herramienta'])['segundos'].agg(['mean', 'std']).reset_index()
    fig, axes = _figura(len(OPERACIONES), 17, 3.4)
    for ax, op in zip(axes, OPERACIONES):
        e = est[est['operacion'] == op].set_index('herramienta').reindex(ORDEN).dropna(subset=['mean'])
        _barras_h(ax, [NOMBRES[h] for h in e.index], e['mean'].tolist(), e['std'].fillna(0).tolist(),
                  [COLORES[h] for h in e.index], '{:.3f} s')
        _estilo(ax, ETIQUETAS_OP[op], 'segundos (media ± desv. est.)')
    n = int(d.groupby('herramienta')['ejecucion'].nunique().min())
    return _guardar(fig, ruta, 'Benchmark: tiempo por operación (modo por operación)',
                    f'{n} repeticiones medidas por herramienta, cada una en un proceso nuevo; calentamiento excluido. '
                    'Spark materializa cada operación con cache()+count(); el arranque de la sesión se mide aparte.')


def grafico_totales(medidas, ruta, por_fila=None):
    """Tiempo total por modo y memoria pico (RSS proceso+hijos y % del sistema), en paneles separados.

    `por_fila` reparte los paneles en varias filas (versión para documentos de página vertical).
    """
    tot = medidas[medidas['operacion'] == 'total']
    paneles = [
        ('Total extremo a extremo', tot[tot['modo'] == 'extremo_a_extremo'], 'segundos', 'segundos (media ± d.e.)', '{:.2f} s'),
        ('Total por operación (suma)', tot[tot['modo'] == 'por_operacion'], 'segundos', 'segundos (media ± d.e.)', '{:.2f} s'),
        ('Extremo a extremo, proceso caliente*', tot[tot['modo'] == 'extremo_a_extremo_caliente'], 'segundos',
         'segundos (media ± d.e.)', '{:.2f} s'),
        ('RSS pico proceso + hijos (JVM)', tot[tot['modo'] == 'extremo_a_extremo'], 'rss_pico_mb', 'MB (media ± d.e.)', '{:.0f} MB'),
        ('Memoria del sistema, pico', tot[tot['modo'] == 'extremo_a_extremo'], 'mem_sis_pico_pct', '% de la RAM total (media ± d.e.)', '{:.1f} %'),
    ]
    paneles = [p for p in paneles if len(p[1])]
    columnas = min(por_fila or len(paneles), len(paneles))
    filas = -(-len(paneles) // columnas)
    fig, axes = _figura(columnas, 4.3 * columnas, 3.2 * filas + 0.4, nrows=filas)
    for ax in axes[len(paneles):]:
        ax.set_visible(False)
    for ax, (titulo, d, col, eje, fmt) in zip(axes, paneles):
        e = d.groupby('herramienta')[col].agg(['mean', 'std']).reindex(ORDEN).dropna(subset=['mean'])
        _barras_h(ax, [NOMBRES[h] for h in e.index], e['mean'].tolist(), e['std'].fillna(0).tolist(),
                  [COLORES[h] for h in e.index], fmt)
        _estilo(ax, titulo, eje)
    return _guardar(fig, ruta, 'Benchmark: tiempo total y memoria (de la carga a la exportación)',
                    'Tiempos sin el arranque de SparkSession. *Proceso caliente: 2.ª pasada en el mismo proceso tras una '
                    'pasada sin medir (complementario). Memoria muestreada cada 20 ms; el % del sistema incluye todo el '
                    'runtime de Colab y no es memoria exclusiva de la herramienta.')


def grafico_poc(metricas, ruta):
    """Comparación PoC PySpark vs Pandas (mismo alcance): tiempo, memoria del sistema y RSS."""
    paneles = [
        ('Tiempo total carga→exportación', 'tiempo_total_s', 'segundos (media ± d.e.)', '{:.2f} s'),
        ('Memoria del sistema, pico', 'mem_sis_pico_pct', '% de la RAM total (media ± d.e.)', '{:.1f} %'),
        ('RSS pico proceso + hijos (JVM)', 'rss_pico_mb', 'MB (media ± d.e.)', '{:.0f} MB'),
    ]
    fig, axes = _figura(3, 14, 3.0)
    for ax, (titulo, col, eje, fmt) in zip(axes, paneles):
        e = metricas.groupby('herramienta')[col].agg(['mean', 'std']).reindex(['pandas', 'spark']).dropna(subset=['mean'])
        _barras_h(ax, [NOMBRES[h] for h in e.index], e['mean'].tolist(), e['std'].fillna(0).tolist(),
                  [COLORES[h] for h in e.index], fmt)
        _estilo(ax, titulo, eje)
    n = int(metricas.groupby('herramienta')['ejecucion'].nunique().min())
    return _guardar(fig, ruta, 'PoC: PySpark frente a Pandas con el mismo alcance (3 meses, Colab)',
                    f'{n} ejecuciones por herramienta, cada una en un proceso nuevo. Valores más bajos son mejores. '
                    'El tiempo de Spark excluye el arranque de la sesión, que se reporta aparte.')


def cargar_mediciones(ruta_jsonl):
    df = pd.read_json(ruta_jsonl, lines=True)
    return df[(df['estado'] == 'ok') & (~df['calentamiento'].astype(bool))] if 'calentamiento' in df else df
