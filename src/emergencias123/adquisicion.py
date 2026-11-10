"""Garantiza que los 3 CSV estén en la carpeta de datos del proyecto, íntegros y trazables.

Adaptado de la celda de configuración de la Unidad 1 (copia en U1_referencia/), que leía los CSV de
`MyDrive/BigData_Emergencias_123` y, si Drive no estaba disponible, los descargaba del portal Datos Abiertos
Bogotá con reintentos. Cambios respecto a U1, tras revisar su lógica:
- U1 ignoraba en silencio un fallo de `drive.mount` (`except Exception: pass`). En U2 Drive es obligatorio porque
  los resultados (Parquet, mediciones, informes) se escriben allí; el montaje lo resuelve el notebook.
- U1 no comprobaba qué descargaba. Aquí cada archivo, venga de donde venga, se verifica con el SHA-256 de
  `config.yaml`; si no coincide, se detiene con un error y no se usa (el portal podría reemplazar un recurso).
- El origen de cada archivo queda registrado (local, carpeta U1 o portal) para la trazabilidad.
Orden de búsqueda: carpeta `datos` del proyecto → carpetas alternas (por nombre o por SHA-256) → portal.
"""
import hashlib
import logging
import shutil
import time
import urllib.request

log = logging.getLogger(__name__)


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def _descargar(url, destino, intentos=5, espera_s=10, timeout_s=90):
    """Descarga con reintentos (el portal a veces corta el handshake TLS, observado el 2026-11-10)."""
    ultimo = None
    for i in range(1, intentos + 1):
        try:
            solicitud = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(solicitud, timeout=timeout_s) as r:
                destino.write_bytes(r.read())
            return
        except OSError as e:
            ultimo = e
            log.warning('Descarga fallida (%s/%s) %s: %s', i, intentos, url, e)
            time.sleep(espera_s)
    raise RuntimeError(f'No se pudo descargar {url} tras {intentos} intentos: {ultimo}')


def _buscar_alterno(carpetas, nombre, esperado):
    """Busca el archivo por nombre y, si no, por contenido: la carpeta de la Unidad 1 los nombra distinto
    (p. ej. `llamadaslinea123_agosto_2026.csv`), así que se acepta cualquier CSV con el SHA-256 esperado."""
    for d in carpetas:
        if not d.is_dir():
            continue
        if (d / nombre).exists() and (not esperado or sha256(d / nombre) == esperado):
            return d / nombre
        if esperado:
            for c in sorted(d.glob('*.csv')):
                if sha256(c) == esperado:
                    return c
    return None


def asegurar_datos(cfg, permitir_descarga=True):
    """Deja los CSV en `cfg.dir_datos` con la huella esperada. Devuelve {archivo: {origen, sha256}}.

    Nunca sobrescribe un archivo existente con huella distinta: eso indicaría datos diferentes a los
    analizados y se informa como error en lugar de corregirse en silencio.
    """
    cfg.dir_datos.mkdir(parents=True, exist_ok=True)
    resultado = {}
    for a in cfg.datos['archivos']:
        nombre, esperado = a['nombre'], a.get('sha256')
        destino = cfg.dir_datos / nombre
        if destino.exists():
            origen = 'carpeta del proyecto'
        else:
            alterno = _buscar_alterno(cfg.datos_alternos, nombre, esperado)
            if alterno is not None:
                shutil.copy2(alterno, destino)
                origen = f'copiado de {alterno.parent}'
            elif permitir_descarga and a.get('url'):
                temporal = destino.with_suffix('.descarga')
                _descargar(a['url'], temporal)
                if esperado and sha256(temporal) != esperado:
                    temporal.unlink()
                    raise RuntimeError(f'{nombre} descargado del portal no coincide con el SHA-256 esperado: '
                                       'el recurso cambió y no se usa.')
                temporal.replace(destino)
                origen = 'descargado del portal Datos Abiertos Bogotá'
            else:
                raise FileNotFoundError(f'Falta {nombre} en {cfg.dir_datos} y no hay respaldo disponible.')
        huella = sha256(destino)
        if esperado and huella != esperado:
            raise RuntimeError(f'{destino} no coincide con el SHA-256 esperado ({huella[:16]}… ≠ {esperado[:16]}…).')
        resultado[nombre] = {'origen': origen, 'sha256': huella}
    return resultado
