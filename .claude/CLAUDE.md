# Proyecto U2 — Procesamiento distribuido (Emergencias 123 Bogotá)

Benchmark Pandas / Polars / PySpark, matriz de decisión y PoC en PySpark sobre Google Colab,
según `Guia de actividades_U2 (6) (1).pdf`. Plan aprobado:
`C:\Users\Nicolas\.claude\plans\crea-un-calude-wiggly-seal.md`.

## Organización de `.claude/`

| Ruta | Qué contiene |
|---|---|
| `CLAUDE.md` | Este archivo: reglas generales y mapa |
| `PROGRESO.md` | Bitácora por bloques. Un hook la inyecta al iniciar sesión y tras compactar |
| `rules/*.md` | Reglas modulares. Las que llevan `paths:` se cargan solo al tocar esos archivos |
| `skills/<nombre>/SKILL.md` | Procedimientos: `colab-u2`, `benchmark-u2`, `pipeline-pyspark-u2`, `entregables-u2` |
| `hooks/*.py` | Guardas automáticas (ver `settings.json`) |
| `settings.json` | Registro de los hooks del proyecto |

## Reglas generales (siempre vigentes)

1. **U1 es de solo lectura** (cambio del usuario, 2026-11-10). Se puede leer `../U1_Guia_Actividades` y COPIAR
   dentro de U2 lo que sirva, revisando antes que su lógica sea adecuada. Nunca se modifica U1: un hook bloquea
   editar, mover o borrar ahí. La copia de referencia está en `U2/U1_referencia/`.
2. **El `.venv` de U2 es solo una herramienta de desarrollo del agente** (editar código, pruebas rápidas y
   revisión visual), invocado por ruta (`.venv/Scripts/python.exe`); no forma parte del flujo del proyecto,
   que es solo-Colab (regla 3b). Nunca instalar en el Python global (un hook lo bloquea). Las versiones que
   valen son las de Colab (`requirements-colab.txt`).
3. **Evidencia real.** Las cifras del benchmark y del PoC salen de ejecuciones en Colab. Nada
   simulado, local-presentado-como-Colab ni inventado. Si algo no se pudo hacer, se dice qué,
   por qué y cómo resolverlo.
3b. **Netamente desde Colab, solo notebooks** (pedido del usuario, 2026-11-09 y 2026-11-10). Los programas son
   dos notebooks (`U2_procesamiento_distribuido` y `U2_informes_y_entregables`) y en Drive hay UNA sola carpeta,
   `MyDrive/BigData_U2/`, con lo que pide la guía: los 2 notebooks, `datos/`, `Actividad_1/`, `Actividad_2/`,
   `Sustentacion/` y `resultados/`. Solo se sube lo necesario (los 2 `.ipynb`): el código de apoyo lo escribe el
   propio notebook en el VM. Los informes se verifican con LibreOffice dentro de Colab. El CLI `colab` es solo el
   medio del agente para ejecutar; no se presenta como parte del flujo. Los notebooks deben poder presentarse y
   sustentarse: relato en el orden de la guía y código importante visible.
4. **Datos originales de solo lectura** (`BigData_Emergencias_123/`, protegido por hook). Datos,
   Parquet y credenciales fuera de git. Sin commits salvo pedido explícito.
5. **Catálogo de tipos "derivado, no oficial"** en todo lugar donde aparezca.
6. **Sin borrados ni imputaciones silenciosas** (decisión del usuario, 2026-11-10): solo se eliminan los
   duplicados al 100 % de sus atributos (se guardan aparte en `duplicados_eliminados/`); los nulos y demás
   anomalías se conservan y se marcan en `observacion_calidad`. Nunca se imputa.
7. **Fuente única de los informes:** `resultados/mediciones/`. Los informes se regeneran sin
   volver a medir.
8. **Colab:** sesión `u2bd`, solo CPU (un hook bloquea GPU/TPU/high-mem/pay). `drivemount` y
   cualquier autorización de Google las hace el usuario. Terminar con `colab stop -s u2bd`.
9. **Nada público:** no publicar ni compartir archivos ni artefactos.
10. Reglas específicas en `rules/`: `datos-y-evidencia`, `codigo-python`, `notebooks`, `informes`.

## Gestión de contexto

- Se trabaja por bloques (0–7 del plan). Al **cerrar cada bloque** se actualiza `.claude/PROGRESO.md`.
- Al retomar, leer `PROGRESO.md` (llega inyectado por hook) y la skill del bloque en curso.
- Los archivos grandes se leen por partes. No volcar CSV, Parquet ni notebooks completos en el contexto.

## Hechos de los datos (inspección del 2026-11-07)

- 3 CSV (jul 8 965 · ago 9 204 · sep 9 265 = **27 434** filas), UTF-8 con BOM, separador `;`, CRLF.
- Columnas: `NUMERO_INCIDENTE, FECHA_INICIO_DESPLAZAMIENTO_MOVIL, CODIGO_LOCALIDAD, LOCALIDAD,
  EDAD, UNIDAD, GENERO, TIPO_INCIDENTE, PRIORIDAD_FINAL, RECEPCION`.
- `N/A` en EDAD/UNIDAD/GENERO (~8 990 filas). RECEPCION vacía en 12 062 filas. Las fechas
  `%Y-%m-%d %H:%M:%S` son válidas, pero cada archivo trae registros del día 1 del mes siguiente.
- Localidades con tilde (`USAQUÉN`, `CHAPINERO`, …), códigos 1–19 y una fila `SIN_D`.
- TIPO_INCIDENTE: 23 valores. 19 tienen la forma `COD - DESCRIPCIÓN` (uno con doble espacio)
  y 4 no traen código.
- Duplicados exactos: 84 filas involucradas = 44 copias adicionales (jul 10, ago 14, sep 20).
  3 699 filas con NUMERO_INCIDENTE repetido (25 366 incidentes únicos; varios despachos, legítimos).
- 15 registros caen fuera del mes de su archivo (jul 3, ago 4, sep 8). Todos son del día 1 del mes
  siguiente y quedan dentro de la ventana con 1 día de tolerancia.
- Catálogo derivado: 23 códigos (19 explícitos y 4 sin código). Pares código↔localidad
  consistentes con la división oficial; 1 fila `SIN_D|SIN_D`.
