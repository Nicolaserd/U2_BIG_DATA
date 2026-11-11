---
paths:
  - "informes/**"
  - "src/emergencias123/reportes/**"
  - "scripts/construir_notebooks.py"
  - "README.md"
  - "docs/**"
---

# Regla: informes y entregables (preparados por el agente, redacción APA 7)

- Los prepara **el agente**, no los notebooks (decisión del usuario, 2026-11-10), con
  `.venv/Scripts/python.exe scripts/preparar_entregables.py ENTREGABLES`, a partir de `ENTREGABLES/resultados/`
  (copia descargada de `MyDrive/BigData_U2/resultados/`). Nunca se vuelve a medir. Todas las cifras salen de esas
  mediciones de Colab. No se editan a mano los xlsx ni los docx generados.
- Verificación: Excel/Word por COM en local (o LibreOffice si está): xlsx recalculados sin `#DIV/0!`, `#REF!`,
  `#NAME?` ni `#VALUE!`; arquitectura de 5–8 páginas y escalabilidad de 1 página (docx → PDF → conteo). La matriz del
  Excel debe coincidir con la calculada en el notebook 02.
- **Redacción formal y normas APA 7** en los docx:
  - bloque de título (título, autor, institución, curso, docente, fecha; datos en `config.yaml` → `documentos`);
  - encabezados sin numeración (nivel 1 centrado y en negrita, nivel 2 a la izquierda y en negrita);
  - «Tabla N» / «Figura N» en negrita con título en cursiva encima y «Nota.» debajo; tablas sin líneas verticales;
  - citas en el texto (Autor, año) y lista de **Referencias** con sangría francesa;
  - siglas definidas en su primer uso; voz impersonal; separador decimal uniforme (punto).
- No se inventan referencias: solo obras verificables o datos del curso. Los datos de autoría desconocidos
  quedan como marcadores `[...]` para que el usuario los complete.
- Gráficos a 300 dpi, con título neutral, unidades (s, %, MB), etiquetas legibles y barras de error.
- Quedan fuera el video, las diapositivas, el guion del pitch y las capturas manuales.
