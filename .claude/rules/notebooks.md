---
paths:
  - "notebooks/**"
  - "scripts/construir_notebooks.py"
---

# Regla: notebooks (solo Google Colab)

- Los programas del proyecto son **solo dos notebooks** (decisión del usuario, 2026-11-10):
  `U2_procesamiento_distribuido` (datos, Actividad 1, Actividad 2, optimización y pruebas) y
  `U2_informes_y_entregables` (informes, sustentación y carpeta del proyecto). Se generan con
  `scripts/construir_notebooks.py` a partir de `src/`, `config/` y `tests/` (fuente local del código de apoyo).
- En Drive solo se sube lo necesario: los 2 `.ipynb` en `MyDrive/BigData_U2/`. Cada notebook **escribe su propio
  código de apoyo** en `/content/u2lib` (celdas `%%writefile` del **Anexo A**, sección plegada) porque las mediciones
  corren en subprocesos que importan desde archivos. Nada de ese código se guarda en Drive.
- El relato va en el orden de la guía (secciones por actividad y tarea) y **muestra en pantalla el código que se
  defiende** (`ver_codigo()`: `measure_performance`, las 5 operaciones, el pipeline); el volcado de módulos solo en el Anexo A.
- La primera celda comprueba `google.colab` y monta Drive si hace falta. Sin instrucciones locales.
- Los datos: `adquisicion.asegurar_datos` (carpeta del proyecto → carpeta de la Unidad 1 por nombre o SHA-256 →
  portal), siempre con verificación SHA-256.
- Los notebooks que se entregan son los **ejecutados en Colab**, con sus salidas. Nunca salidas locales.
- Orden ejecutable desde un runtime nuevo, con Markdown explicativo en español formal. Sin credenciales, tokens,
  correos ni rutas privadas. Las mediciones se lanzan en subprocesos nuevos (skill `benchmark-u2`).
- Si se cambia un módulo de `src/`, se regeneran los notebooks y se vuelve a ejecutar en Colab.
