"""Hook SessionStart del proyecto U2: inyecta .claude/PROGRESO.md en el contexto.

Se ejecuta al iniciar, reanudar o tras compactar, para que el trabajo por bloques siga
siendo coherente entre ventanas de contexto.
"""
import json
import os
import sys
from pathlib import Path

PROYECTO = Path(os.environ.get('CLAUDE_PROJECT_DIR') or Path(__file__).resolve().parents[2])
PROGRESO = PROYECTO / '.claude' / 'PROGRESO.md'


def main():
    if not PROGRESO.exists():
        sys.exit(0)
    texto = PROGRESO.read_text(encoding='utf-8')
    contexto = ('Bitácora del proyecto U2 (.claude/PROGRESO.md). Retoma desde el primer bloque '
                'que no esté COMPLETADO y actualiza este archivo al cerrar cada bloque:\n\n' + texto)
    sys.stdout.buffer.write(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': contexto,
    }}, ensure_ascii=False).encode('utf-8'))


if __name__ == '__main__':
    main()
