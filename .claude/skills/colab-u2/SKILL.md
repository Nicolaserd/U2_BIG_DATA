---
name: colab-u2
description: Operar Google Colab para el proyecto U2 con el CLI `colab` (google-colab-cli 0.7.5) - crear la sesión u2bd, coordinar el montaje de Drive con el usuario, subir datos y código, instalar dependencias, ejecutar notebooks y scripts, descargar resultados y detener la sesión. Usar siempre que haya que ejecutar algo en Colab.
---

# Colab para U2

Base: la skill incluida en el CLI (`colab skill`) y su ayuda (`colab <cmd> --help`), verificadas
el 2026-11-07. El CLI está en `C:\Users\Nicolas\.local\bin\colab.exe` y ya está autorizado
(oauth2, `~/.config/colab-cli/token.json`).

## Reglas
- Ejecutar desde **Bash** (PowerShell no admite `< /dev/null`) con este prefijo:
  `export MSYS_NO_PATHCONV=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8;` y terminar cada comando con `< /dev/null`.
  **`MSYS_NO_PATHCONV=1` es obligatorio**: sin él, Git Bash convierte `/content/...` en
  `C:/Program Files/Git/content/...` y `upload`/`download` fallan con un 500.
- `colab upload` no crea carpetas: crearlas antes con
  `echo "import os; os.makedirs('/ruta', exist_ok=True)" | colab exec -s u2bd --timeout 60`.
- Para subir código: un zip de `src/ config/ tests/ scripts/ requirements-colab.txt`, que se
  descomprime con `exec`.
- Sesión única **`u2bd`**, runtime **CPU** (sin `--gpu`, `--tpu` ni `--high-mem`): sin recursos de pago.
- `colab exec` usa por defecto `--timeout 30`. Pasar siempre un timeout explícito
  (`--timeout 3600` para los notebooks).
- **Nunca** ejecutar `colab drivemount`, `colab auth`, `colab repl` ni `colab console` de forma
  interactiva desde el agente. `drivemount` lo ejecuta **el usuario** en su terminal.
- Si el CLI pide reautorización, detenerse y pedir al usuario que ejecute `colab sessions` en su
  terminal. El agente no introduce códigos ni contraseñas.
- Al terminar (o ante un error grave): `colab stop -s u2bd` y comprobar con `colab sessions`.

## Layout en Drive
```
/content/drive/MyDrive/BigData_U2/     (UNA sola carpeta; solo se sube lo necesario)
  U2_procesamiento_distribuido.ipynb   U2_informes_y_entregables.ipynb   LEEME.md
  datos/          3 CSV (los copia el notebook desde BigData_Emergencias_123 de la Unidad 1 o del portal)
  Actividad_1/  Actividad_2/  Sustentacion/     (los arma el notebook de informes)
  resultados/     mediciones/  logs/  parquet/poc/...
El código de apoyo NO está en Drive: cada notebook lo escribe en /content/u2lib.
```

## Flujo
1. `colab sessions` para comprobar que no haya sesiones huérfanas.
2. `colab new -s u2bd`.
3. Montar Drive (el consentimiento lo da SIEMPRE el usuario en su navegador):
   - Lanzar en segundo plano `python -I .claude/scripts/montar_drive.py <scratchpad>/drive u2bd`.
     El script abre la página de Google en el navegador del usuario y espera.
   - Pedir al usuario que acepte **todas** las casillas, pulse Continuar y espere a que la página termine.
   - Cuando el usuario diga "listo", crear `<scratchpad>/drive/continuar`: el script envía Enter.
   - Error 400 "Error propagating": se pulsó Enter antes de completar el consentimiento → relanzar.
   - "Credentials propagated" seguido de `mount failed` (en los logs de DriveFS: `auth/user-id` y
     `CANNOT_START_CORE`): el consentimiento quedó PARCIAL. Hay que crear una VM nueva, relanzar y pedir al
     usuario que en Google abra «ya tiene acceso parcial / N servicios» y marque TODOS los permisos,
     incluido el correo o información de la cuenta. Así funcionó el 2026-11-09.
   - Si la pestaña no se abre sola, pasar el enlace de `url.txt` en el chat como link clicable. El enlace de
     `colab url` abre la interfaz web, pero puede crear OTRO runtime: no sirve para montar en `u2bd`.
   - Si la sesión de Claude Code se reinicia mientras espera, el `drivemount` queda huérfano: hay que
     matarlo y relanzarlo.
   Comprobarlo con:
   `echo "import os;print(os.path.ismount('/content/drive'))" | colab exec -s u2bd --timeout 60`.
4. Subir los archivos: `colab upload -s u2bd <local> /content/drive/MyDrive/BigData_U2/<ruta>`
   (archivo por archivo). Para muchos archivos, empaquetar un zip local, subirlo a `/content/`
   y descomprimirlo con `exec`.
5. Dependencias: `colab install -s u2bd -r requirements-colab.txt` (usa uv/pip en el VM, nunca en
   este equipo).
6. Ejecutar:
   - notebook: `colab exec -s u2bd -f notebooks/X.ipynb --timeout 3600` → `notebooks/X_output.ipynb`;
   - script: `colab exec -s u2bd -f scripts/x.py --timeout N`.
   El estado del kernel persiste entre `exec`. Para empezar en limpio: `colab restart-kernel -s u2bd`.
7. Bajar los resultados: `colab download -s u2bd <remoto> <local>`.
8. Diagnóstico: `colab status -s u2bd`, `colab log -s u2bd -n 20`.
9. `colab stop -s u2bd`.

## Recuperación
- 404/401 "session not found": el VM fue liberado. `colab sessions` → `colab new -s u2bd` → pedir
  de nuevo `drivemount`.
- Kernel colgado: `colab restart-kernel -s u2bd`.
- Los archivos de `/content` (fuera de Drive) se pierden al liberar el VM: todo resultado durable
  va a Drive y se descarga a local.
