"""Carga de config/config.yaml y resolución de rutas según el entorno (local o Colab)."""
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

RAIZ_CODIGO = Path(__file__).resolve().parents[2]
RUTA_CONFIG = RAIZ_CODIGO / 'config' / 'config.yaml'


def detectar_entorno():
    forzado = os.environ.get('U2_ENTORNO')
    if forzado:
        return forzado
    return 'colab' if Path('/content/drive/MyDrive').exists() else 'local'


@dataclass(frozen=True)
class Config:
    datos: dict
    esquema: dict
    catalogos: dict
    benchmark: dict
    poc: dict
    spark: dict
    documentos: dict
    entorno: str
    dir_datos: Path
    dir_resultados: Path
    dir_informes: Path
    dir_base: Path
    datos_alternos: tuple = ()     # otras carpetas donde buscar los CSV (p. ej. la de Drive de la Unidad 1)

    def ruta_csv(self, nombre):
        return self.dir_datos / nombre

    @property
    def rutas_csv(self):
        return [self.ruta_csv(a['nombre']) for a in self.datos['archivos']]

    @property
    def periodo_por_archivo(self):
        return {a['nombre']: a['periodo'] for a in self.datos['archivos']}

    @property
    def ruta_catalogo_tipos(self):
        return RAIZ_CODIGO / self.catalogos['tipos']

    @property
    def ruta_localidades(self):
        return RAIZ_CODIGO / self.catalogos['localidades']

    def dir_salida(self, *partes):
        ruta = self.dir_resultados.joinpath(*partes)
        ruta.mkdir(parents=True, exist_ok=True)
        return ruta


def _resolver(ruta):
    ruta = Path(ruta)
    return ruta if ruta.is_absolute() else RAIZ_CODIGO / ruta


def cargar_config(ruta=None, entorno=None, dir_resultados=None):
    """Lee el YAML. `dir_resultados` permite aislar salidas (pruebas o ejecuciones)."""
    with open(ruta or RUTA_CONFIG, encoding='utf-8') as f:
        crudo = yaml.safe_load(f)
    entorno = entorno or detectar_entorno()
    rutas = crudo['entornos'][entorno]
    return Config(
        datos=crudo['datos'], esquema=crudo['esquema'], catalogos=crudo['catalogos'],
        benchmark=crudo['benchmark'], poc=crudo['poc'], spark=crudo['spark'], documentos=crudo.get('documentos', {}),
        entorno=entorno,
        dir_datos=_resolver(os.environ.get('U2_DIR_DATOS', rutas['datos'])),
        dir_resultados=_resolver(dir_resultados or os.environ.get('U2_DIR_RESULTADOS', rutas['resultados'])),
        dir_informes=_resolver(rutas['informes']),
        dir_base=_resolver(rutas['base']),
        datos_alternos=tuple(_resolver(r) for r in rutas.get('datos_alternos', [])),
    )
