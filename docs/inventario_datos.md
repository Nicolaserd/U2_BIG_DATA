# Inventario de datos — Emergencias 123 Bogotá (U2)

Generado por `scripts/preparar_insumos.py` a partir de los archivos originales (sin modificarlos).

## Procedencia

- Llamadas a la Línea 123 de Bogotá (atención prehospitalaria), un archivo mensual por periodo,
  suministrados en `BigData_Emergencias_123/`. La URL de descarga no está en los insumos de U2;
  la integridad se fija con la huella SHA-256 de cada archivo.
- Meses seleccionados: julio, agosto y septiembre de 2026.

## Archivos

| Archivo | Periodo | Bytes | Registros | Líneas físicas | Fecha mín. | Fecha máx. | Fuera del mes | Dup. exactos | SHA-256 |
|---|---|---:|---:|---:|---|---|---:|---:|---|
| llamadas123_julio_2026.csv | 2026-07 | 1,011,718 | 8,965 | 8,966 | 2026-07-01 00:08:54 | 2026-08-01 00:10:48 | 3 | 10 | `21cbe766616d3240…` |
| llamadaslinea123agosto2026.csv | 2026-08 | 1,036,327 | 9,204 | 9,205 | 2026-08-01 00:01:39 | 2026-09-01 00:31:49 | 4 | 14 | `c421fe9d75edc4ed…` |
| llamadaslinea123Septiembre.csv | 2026-09 | 1,047,407 | 9,265 | 9,266 | 2026-09-01 00:30:26 | 2026-10-01 01:52:25 | 8 | 20 | `face37df8c679127…` |

**Total:** 27,434 registros · 25,366 incidentes únicos · 3,699 filas con NUMERO_INCIDENTE repetido · 44 copias duplicadas exactas.

## Formato y esquema

- Codificación UTF-8 con BOM: True; fin de línea CRLF; separador `;`; encabezado en la primera línea.
- Columnas (todas se leen como texto y se tipan después):

  1. `NUMERO_INCIDENTE` — nulos/`N/A`: 0
  2. `FECHA_INICIO_DESPLAZAMIENTO_MOVIL` — nulos/`N/A`: 0
  3. `CODIGO_LOCALIDAD` — nulos/`N/A`: 0
  4. `LOCALIDAD` — nulos/`N/A`: 0
  5. `EDAD` — nulos/`N/A`: 8,991
  6. `UNIDAD` — nulos/`N/A`: 8,990
  7. `GENERO` — nulos/`N/A`: 8,990
  8. `TIPO_INCIDENTE` — nulos/`N/A`: 0
  9. `PRIORIDAD_FINAL` — nulos/`N/A`: 0
  10. `RECEPCION` — nulos/`N/A`: 12,062

## Hallazgos que condicionan el diseño

- `EDAD`, `UNIDAD` y `GENERO` usan `N/A` como marcador de ausencia: se convierte a nulo y no se imputa.
- `RECEPCION` vacía significa que no hay recepción registrada: es un nulo legítimo, no un error.
- Cada archivo incluye registros de la madrugada del día 1 del mes siguiente (3, 4, 8 registros). Se conservan con el periodo de su archivo y se valida una ventana de 1 día de tolerancia.
- Las localidades vienen con tilde (`USAQUÉN`) y se normalizan a `USAQUEN`. Hay 1 fila con `SIN_D` (localidad sin dato), que el PoC rechaza con motivo explícito.
- `NUMERO_INCIDENTE` se repite cuando un incidente tiene varios despachos: no es un duplicado.
- Los duplicados exactos se marcan y no se eliminan: sin un identificador de despacho no se puede distinguir una doble exportación de dos despachos idénticos.

## Catálogo de tipos de incidente (derivado, NO oficial)

No se encontró una tabla oficial de códigos de emergencia entre los insumos. `config/catalogo_tipos_derivado.csv` se derivó de `TIPO_INCIDENTE` (23 códigos; 19 con código explícito `COD - DESCRIPCIÓN` y 4 sin código, en los que el texto normalizado actúa como código). Para usar un catálogo oficial basta con reemplazar ese archivo conservando sus columnas.

## Pares código ↔ localidad observados

| Código | Localidad normalizada | Registros |
|---|---|---:|
| 1 | USAQUEN | 1,103 |
| 10 | ENGATIVA | 2,846 |
| 11 | SUBA | 2,711 |
| 12 | BARRIOS UNIDOS | 712 |
| 13 | TEUSAQUILLO | 769 |
| 14 | LOS MARTIRES | 928 |
| 15 | ANTONIO NARINO | 387 |
| 16 | PUENTE ARANDA | 1,851 |
| 17 | LA CANDELARIA | 191 |
| 18 | RAFAEL URIBE URIBE | 1,337 |
| 19 | CIUDAD BOLIVAR | 1,992 |
| 2 | CHAPINERO | 659 |
| 3 | SANTA FE | 682 |
| 4 | SAN CRISTOBAL | 1,341 |
| 5 | USME | 1,070 |
| 6 | TUNJUELITO | 778 |
| 7 | BOSA | 2,251 |
| 8 | KENNEDY | 4,577 |
| 9 | FONTIBON | 1,248 |
| SIN_D | SIN_D | 1 |

## Entorno local de desarrollo

- Python: 3.11.0
- Sistema: Windows-10-10.0.19045-SP0
- pandas: 2.2.3
- polars: 1.35.2
- pyarrow: 23.0.1
- pyspark: 4.0.5
- psutil: 7.2.2
