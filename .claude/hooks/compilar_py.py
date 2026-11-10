"""Hook PostToolUse del proyecto U2: compila cada .py editado y devuelve los errores de sintaxis.

Sale con código 2 (el mensaje vuelve a Claude) solo si el archivo no compila.
"""
import json
import py_compile
import sys
from pathlib import Path


def main():
    try:
        evento = json.loads(sys.stdin.buffer.read().decode('utf-8') or '{}')
    except json.JSONDecodeError:
        sys.exit(0)
    entrada = evento.get('tool_input') or {}
    ruta = Path(entrada.get('file_path') or '')
    if ruta.suffix != '.py' or not ruta.exists():
        sys.exit(0)
    try:
        py_compile.compile(str(ruta), doraise=True, cfile=None, optimize=-1)
    except py_compile.PyCompileError as error:
        sys.stderr.write(f'Error de sintaxis en {ruta.name}: {error.msg}\n')
        sys.exit(2)
    finally:
        cache = ruta.parent / '__pycache__'
        for archivo in cache.glob(f'{ruta.stem}.*.pyc') if cache.exists() else []:
            try:
                archivo.unlink()
            except OSError:
                pass


if __name__ == '__main__':
    main()
