"""Reglas de normalización de texto compartidas por las tres herramientas.

Se usa un mapa explícito de tildes del español (y no NFKD) porque Spark no tiene una función
de normalización Unicode. Así Pandas, Polars y Spark aplican exactamente la misma transformación.
La inspección de los datos confirmó que no hay otros caracteres no ASCII en los campos normalizados.
"""
import re

CON_TILDE = 'ÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÑáàäâéèëêíìïîóòöôúùüûñ'
SIN_TILDE = 'AAAAEEEEIIIIOOOOUUUUNaaaaeeeeiiiioooouuuun'
TABLA_TILDES = str.maketrans(CON_TILDE, SIN_TILDE)
SEPARADOR_CODIGO = ' - '
ESPACIOS = re.compile(r'\s+')


def normalizar_texto(valor):
    """Quita tildes, colapsa espacios, recorta y pasa a mayúsculas. Vacío -> None."""
    if valor is None:
        return None
    texto = ESPACIOS.sub(' ', str(valor).translate(TABLA_TILDES)).strip().upper()
    return texto or None


def colapsar_espacios(valor):
    if valor is None:
        return None
    return ESPACIOS.sub(' ', str(valor)).strip() or None


def extraer_codigo_tipo(tipo_incidente):
    """'INTSUI - INTENTO DE SUICIDIO' -> 'INTSUI'; sin código ('ENFERMO') -> el texto completo."""
    texto = normalizar_texto(tipo_incidente)
    if texto is None:
        return None
    return texto.split(SEPARADOR_CODIGO, 1)[0]


def extraer_descripcion_tipo(tipo_incidente):
    """Descripción legible (con tildes): lo que sigue al primer ' - ', o el texto completo."""
    texto = colapsar_espacios(tipo_incidente)
    if texto is None:
        return None
    return texto.split(SEPARADOR_CODIGO, 1)[-1]
