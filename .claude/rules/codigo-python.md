---
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
  - "tests/**/*.py"
---

# Regla: código Python del proyecto (pensado para Google Colab)

- El código de medición se ejecuta en Google Colab, pero **no se sube a Drive**: los 4 notebooks lo escriben en el VM
  (`/content/u2lib`, Anexo A) y lo importan desde allí. `src/`, `config/` y `tests/` son la fuente local de ese
  código. Los informes (`src/emergencias123/reportes/`) los ejecuta el agente en local con
  `scripts/preparar_entregables.py`. Nada del procesamiento puede depender de herramientas locales. Lo que falte se
  instala en el runtime de Colab desde un notebook.
- Paquete `src/emergencias123/`. `scripts/construir_notebooks.py` (herramienta local) incrusta los módulos en los
  notebooks; no hay otros scripts en el flujo.
- Nombres y comentarios en español, sin tildes en los identificadores. Docstrings breves que explican el
  porqué, no el qué obvio.
- Toda ruta y todo parámetro sale de `config/config.yaml` mediante `emergencias123.config` (entorno `colab`:
  rutas de Drive). No se escriben rutas absolutas ni privadas en el código.
- La biblioteca usa `logging`, no `print`. Solo los scripts y los notebooks imprimen.
- Las tres implementaciones del benchmark (`ops_pandas`, `ops_polars`, `ops_spark`) aplican **la misma
  lógica** y delimitan cada operación con `# >>> op:<nombre>` / `# <<< op:<nombre>`. Si se cambia una, se
  cambian las tres y se corre la prueba de equivalencia.
- PySpark se importa de forma diferida (dentro de las funciones o de los módulos de Spark).
- Las pruebas de Spark llevan `@pytest.mark.spark` y se ejecutan en el runtime de Colab. La batería completa
  corre en el notebook 03. Un hook compila cada `.py` editado.
