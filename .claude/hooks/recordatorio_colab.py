"""Hook Stop del proyecto U2: recuerda detener la sesión de Colab `u2bd` si sigue registrada.

Solo lee el estado local del CLI (~/.config/colab-cli/sessions.json); no hace llamadas de red
ni bloquea el cierre del turno.
"""
import json
import sys
from pathlib import Path

ESTADO = Path.home() / '.config' / 'colab-cli' / 'sessions.json'


def main():
    try:
        activa = 'u2bd' in ESTADO.read_text(encoding='utf-8')
    except OSError:
        activa = False
    if activa:
        sys.stdout.buffer.write(json.dumps({
            'systemMessage': 'Sesión de Colab "u2bd" registrada como activa. Si ya no se usa, '
                             'deténla con `colab stop -s u2bd` (consume unidades de cómputo).',
        }, ensure_ascii=False).encode('utf-8'))


if __name__ == '__main__':
    main()
