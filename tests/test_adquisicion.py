"""Adquisición de datos (lógica adaptada de la Unidad 1): carpeta del proyecto → carpeta alterna → portal."""
import dataclasses

import pytest

from emergencias123.adquisicion import asegurar_datos, sha256


def _cfg_con(cfg, dir_datos, alternos, huellas):
    datos = dict(cfg.datos, archivos=[dict(a, sha256=huellas[a['nombre']], url=None) for a in cfg.datos['archivos']])
    return dataclasses.replace(cfg, dir_datos=dir_datos, datos_alternos=tuple(alternos), datos=datos)


def test_copia_desde_carpeta_alterna_y_verifica_huella(cfg_fixture, tmp_path):
    huellas = {p.name: sha256(p) for p in cfg_fixture.rutas_csv}
    cfg = _cfg_con(cfg_fixture, tmp_path / 'vacia', [cfg_fixture.dir_datos], huellas)
    r = asegurar_datos(cfg, permitir_descarga=False)
    assert all(v['origen'].startswith('copiado de') for v in r.values())
    assert all((tmp_path / 'vacia' / n).exists() for n in huellas)
    r2 = asegurar_datos(cfg, permitir_descarga=False)  # segunda vez: ya están en la carpeta del proyecto
    assert all(v['origen'] == 'carpeta del proyecto' for v in r2.values())


def test_huella_distinta_detiene_sin_corregir_en_silencio(cfg_fixture):
    huellas = {p.name: '0' * 64 for p in cfg_fixture.rutas_csv}
    with pytest.raises(RuntimeError, match='SHA-256'):
        asegurar_datos(_cfg_con(cfg_fixture, cfg_fixture.dir_datos, [], huellas), permitir_descarga=False)


def test_config_real_tiene_huella_y_url_por_archivo(cfg_real):
    for a in cfg_real.datos['archivos']:
        assert len(a['sha256']) == 64 and a['url'].startswith('https://datosabiertos.bogota.gov.co/')
    assert asegurar_datos(cfg_real, permitir_descarga=False)  # los CSV del proyecto tienen la huella esperada


def test_encuentra_en_carpeta_alterna_con_otro_nombre_por_huella(cfg_fixture, tmp_path):
    alterna = tmp_path / 'u1'
    alterna.mkdir()
    huellas = {}
    for i, p in enumerate(cfg_fixture.rutas_csv):
        huellas[p.name] = sha256(p)
        (alterna / f'otro_nombre_{i}.csv').write_bytes(p.read_bytes())
    cfg = _cfg_con(cfg_fixture, tmp_path / 'proyecto', [alterna], huellas)
    r = asegurar_datos(cfg, permitir_descarga=False)
    assert all(v['origen'].startswith('copiado de') for v in r.values())
    assert all((tmp_path / 'proyecto' / n).exists() for n in huellas)
