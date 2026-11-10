"""(Herramienta del agente; se ejecuta EN Colab) Empaqueta la carpeta única del proyecto en Drive para descargarla.

Comprime MyDrive/BigData_U2 completa (notebooks, datos, Actividad_1/2, Sustentacion, LEEME.md y resultados con
el Parquet del PoC) en /content/u2_proyecto.zip, para reflejarla en ENTREGABLES/ del equipo local.
Uso: colab exec -s u2bd -f .claude/scripts/colab_empaquetar_resultados.py --timeout 900
"""
import zipfile
from pathlib import Path

BASE = Path('/content/drive/MyDrive/BigData_U2')
DESTINO = Path('/content/u2_proyecto.zip')

n = 0
with zipfile.ZipFile(DESTINO, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(BASE.rglob('*')):
        if p.is_file() and not p.name.endswith('.crc') and '.ipynb_checkpoints' not in p.parts:
            z.write(p, p.relative_to(BASE).as_posix())
            n += 1
print(f'{n} archivos -> {DESTINO} ({DESTINO.stat().st_size / 2**20:.1f} MB)')
