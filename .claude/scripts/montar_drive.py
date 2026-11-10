"""Monta Google Drive en la sesión de Colab `u2bd` con el orden correcto de pasos.

1. Ejecuta `colab drivemount -s u2bd` y guarda su salida en <dir>/montaje.log.
2. Abre en el navegador del usuario el enlace de consentimiento de Google y lo guarda en <dir>/url.txt.
3. ESPERA a que exista <dir>/continuar (lo crea el agente cuando el usuario confirma que aceptó
   todos los permisos). El consentimiento lo da siempre el usuario en su navegador.
4. Recién entonces envía Enter al CLI y deja el resultado en el log.

Uso: python -I .claude/scripts/montar_drive.py <dir_trabajo> [sesion]
Solo usa la biblioteca estándar.
"""
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ESPERA_MAX_S = 20 * 60


def main():
    trabajo = Path(sys.argv[1])
    sesion = sys.argv[2] if len(sys.argv) > 2 else 'u2bd'
    trabajo.mkdir(parents=True, exist_ok=True)
    for nombre in ('continuar', 'url.txt', 'montaje.log', 'resultado.txt'):
        (trabajo / nombre).unlink(missing_ok=True)
    colab = shutil.which('colab')
    if not colab:
        sys.exit('No se encontró el comando colab')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    proceso = subprocess.Popen([colab, 'drivemount', '-s', sesion], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    texto = []
    log = open(trabajo / 'montaje.log', 'w', encoding='utf-8')

    def leer():
        # read1 entrega lo disponible aunque no haya salto de línea: el CLI imprime
        # "Press Enter after you have granted access..." sin '\n' y readline() se quedaría esperando.
        while bloque := proceso.stdout.read1(4096):
            s = bloque.decode('utf-8', errors='replace')
            texto.append(s)
            log.write(s)
            log.flush()

    lector = threading.Thread(target=leer, daemon=True)
    lector.start()

    url, inicio = None, time.time()
    while proceso.poll() is None and time.time() - inicio < ESPERA_MAX_S:
        completo = ''.join(texto)
        if url is None and (m := re.search(r'https://accounts\.google\.com/\S+', completo)):
            url = m.group(0)
            (trabajo / 'url.txt').write_text(url, encoding='utf-8')
            webbrowser.open(url)
        if url and (trabajo / 'continuar').exists():  # el usuario confirmó que aceptó los permisos
            proceso.stdin.write(b'\n')
            proceso.stdin.flush()
            break
        time.sleep(1)
    try:
        codigo = proceso.wait(timeout=300)
    except subprocess.TimeoutExpired:
        proceso.kill()
        codigo = 'timeout'
    lector.join(timeout=5)
    log.close()
    (trabajo / 'resultado.txt').write_text(f'codigo_salida={codigo}\n', encoding='utf-8')
    print(f'codigo_salida={codigo}')


if __name__ == '__main__':
    main()
