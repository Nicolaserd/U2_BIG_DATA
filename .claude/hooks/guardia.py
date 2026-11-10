"""Hook PreToolUse del proyecto U2: bloquea acciones que violan las reglas del proyecto.

Lee el evento JSON por stdin y responde con permissionDecision (deny/ask) cuando corresponde.
Solo usa la biblioteca estándar.
"""
import json
import os
import re
import sys
from pathlib import Path

PROYECTO = Path(os.environ.get('CLAUDE_PROJECT_DIR') or Path(__file__).resolve().parents[2]).resolve()
DATOS_CRUDOS = (PROYECTO / 'BigData_Emergencias_123').resolve()
U1 = (PROYECTO.parent / 'U1_Guia_Actividades').resolve()

VERBOS_DESTRUCTIVOS = re.compile(
    r'(^|[\s;&|(])(rm|mv|del|erase|rmdir|truncate|Remove-Item|Move-Item|Rename-Item|Set-Content|'
    r'Clear-Content|Add-Content|Out-File|Copy-Item\s+\S+\s+\S*BigData_Emergencias_123)\b|sed\s+-i',
    re.IGNORECASE)
REDIRECCION_A_CRUDOS = re.compile(r'>{1,2}\s*["\']?[^\s&|;]*BigData_Emergencias_123', re.IGNORECASE)
PIP_DIRECTO = re.compile(r'(^|[\s;&|(])(?<!-m )pip3?(\.exe)?\s+install\b', re.IGNORECASE)
PIP_MODULO = re.compile(r'(\S*?)(python3?|py)(\.exe)?["\']?\s+(-\S+\s+)*-m\s+pip\s+install\b', re.IGNORECASE)
UV_SISTEMA = re.compile(r'\buv\s+pip\s+install\b.*--system', re.IGNORECASE)
COLAB_PAGO = re.compile(r'\bcolab(\.exe)?\s+(\S+\s+)*?(new|run)\b.*(--gpu|--tpu|--high-mem)|\bcolab(\.exe)?\s+pay\b',
                        re.IGNORECASE)
COLAB_INTERACTIVO = re.compile(r'\bcolab(\.exe)?\s+(--\S+\s+)*(drivemount|auth)\b', re.IGNORECASE)
COLAB_EXEC = re.compile(r'\bcolab(\.exe)?\s+(--\S+\s+)*(exec|run)\b', re.IGNORECASE)
GIT_PUBLICAR = re.compile(r'\bgit\s+(commit|push)\b', re.IGNORECASE)
# Subcomando que ejecuta colab: opcionalmente precedido de variables VAR=valor, `export ...;` o `timeout N`.
INVOCA_COLAB = re.compile(r'^(?:\w+=\S+\s+)*(?:timeout\s+\d+\s+)?colab(?:\.exe)?(?:\s|$)', re.IGNORECASE)


def responder(decision, motivo):
    sys.stdout.buffer.write(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': decision,
        'permissionDecisionReason': motivo,
    }}, ensure_ascii=False).encode('utf-8'))
    sys.exit(0)


def dentro_de(ruta, base):
    try:
        Path(ruta).resolve().relative_to(base)
        return True
    except (ValueError, OSError):
        return False


def revisar_archivo(entrada):
    ruta = entrada.get('file_path') or entrada.get('notebook_path') or ''
    if not ruta:
        return
    if dentro_de(ruta, DATOS_CRUDOS):
        responder('deny', 'Los CSV originales de BigData_Emergencias_123/ son de solo lectura (regla 4 del proyecto).')
    if dentro_de(ruta, U1):
        responder('deny', 'U1_Guia_Actividades es de solo lectura: lo útil se copia dentro de U2, no se edita en U1.')


def revisar_comando(comando):
    for segmento in re.split(r'&&|\|\||[;|\n]', comando):
        # U1 se puede LEER y COPIAR hacia U2 (decisión del usuario, 2026-11-10), pero nunca modificar.
        if 'U1_Guia_Actividades' in segmento and (VERBOS_DESTRUCTIVOS.search(segmento)
                                                  or re.search(r'>{1,2}\s*["\']?[^\s&|;]*U1_Guia_Actividades', segmento)):
            responder('deny', 'U1_Guia_Actividades es de solo lectura: se puede leer o copiar hacia U2, no modificar.')
    for segmento in re.split(r'&&|\|\||[;|\n]', comando):
        if 'BigData_Emergencias_123' in segmento and (VERBOS_DESTRUCTIVOS.search(segmento)
                                                      or REDIRECCION_A_CRUDOS.search(segmento)):
            responder('deny', 'Comando que podría modificar los CSV originales (solo lectura). '
                              'Copia los archivos a otra ruta si necesitas transformarlos.')
    if PIP_DIRECTO.search(comando) and not COLAB_EXEC.search(comando):
        responder('deny', 'No uses `pip install` directo: usa `.venv/Scripts/python.exe -m pip install ...` '
                          '(regla global de entornos virtuales).')
    for m in PIP_MODULO.finditer(comando):
        if '.venv' not in m.group(1).replace('\\', '/'):
            responder('deny', 'pip solo con el Python del entorno: `.venv/Scripts/python.exe -m pip install ...`.')
    if UV_SISTEMA.search(comando) and not COLAB_EXEC.search(comando):
        responder('deny', '`uv pip install --system` instala en el Python global; usa el .venv del proyecto.')
    # Las reglas de Colab solo aplican a los subcomandos que REALMENTE invocan `colab` (no a texto que lo mencione,
    # p. ej. un heredoc que escribe documentación).
    for segmento in re.split(r'&&|\|\||[;|\n]', comando):
        s = segmento.strip()
        if not INVOCA_COLAB.match(s):
            continue
        if COLAB_PAGO.search(s):
            responder('deny', 'Solo runtime CPU de Colab: sin --gpu, --tpu, --high-mem ni `colab pay` (sin recursos de pago).')
        if COLAB_INTERACTIVO.search(s):
            responder('deny', '`colab drivemount` / `colab auth` son interactivos. Para Drive usa '
                              '`python -I .claude/scripts/montar_drive.py <dir>` (abre el consentimiento en el navegador '
                              'del usuario y solo envía Enter cuando el agente crea <dir>/continuar tras su confirmación).')
        if COLAB_EXEC.search(s) and '--timeout' not in s and re.search(r'\bexec\b', s):
            responder('deny', '`colab exec` usa 30 s de timeout por defecto: añade `--timeout <segundos>` explícito.')
    if GIT_PUBLICAR.search(comando):
        responder('ask', 'Commit/push solo si el usuario lo pidió explícitamente en esta conversación.')


def main():
    try:
        evento = json.loads(sys.stdin.buffer.read().decode('utf-8') or '{}')
    except json.JSONDecodeError:
        sys.exit(0)
    herramienta = evento.get('tool_name', '')
    entrada = evento.get('tool_input') or {}
    if herramienta in ('Edit', 'Write', 'NotebookEdit'):
        revisar_archivo(entrada)
    elif herramienta in ('Bash', 'PowerShell'):
        revisar_comando(entrada.get('command', ''))
    sys.exit(0)


if __name__ == '__main__':
    main()
