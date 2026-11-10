---
paths:
  - "informes/**"
  - "src/emergencias123/reportes/**"
  - "scripts/construir_notebooks.py"
  - "README.md"
  - "docs/**"
---

# Regla: informes y entregables (generados en Colab, redacción APA 7)

- Se generan **en Colab** con el notebook `U2_informes_y_entregables` (`reportes.generador.generar_todo`) a partir de
  `resultados/mediciones/` en Drive. No se editan a mano los xlsx ni los docx generados.
- Verificación en Colab con LibreOffice instalado en el runtime: xlsx recalculados sin `#DIV/0!`, `#REF!`,
  `#NAME?` ni `#VALUE!`; arquitectura de 5–8 páginas y escalabilidad de 1 página (docx → PDF → conteo).
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
