"""Muestreo de memoria durante la ejecución (el pico es el máximo de las muestras, no una lectura final).

Se registran dos magnitudes distintas:
- `mem_sis_pct`: psutil.virtual_memory().percent, el % de RAM ocupada en TODO el sistema
  (lo que pide la guía). Incluye otros procesos de Colab, así que no es memoria exclusiva de la herramienta.
- `rss_mb`: RSS del proceso Python más sus hijos recursivos (incluye la JVM de Spark, lanzada por py4j).
  RSS cuenta páginas compartidas, así que la suma puede sobrestimar algo la memoria privada.
Limitación: un pico más corto que el intervalo de muestreo puede no quedar registrado.
"""
import threading
import time

import psutil


def rss_arbol_mb(proceso):
    total = 0
    for p in [proceso, *proceso.children(recursive=True)]:
        try:
            total += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total / 2 ** 20


class MemorySampler:
    """Hilo que muestrea memoria cada `intervalo` segundos y lleva el pico del tramo en curso."""

    def __init__(self, intervalo=0.02):
        self.intervalo = intervalo
        self._proceso = psutil.Process()
        self._bloqueo = threading.Lock()
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._tramo = None

    def _muestra(self):
        return psutil.virtual_memory().percent, rss_arbol_mb(self._proceso)

    def _registrar(self, sis, rss):
        with self._bloqueo:
            if self._tramo is not None:
                t = self._tramo
                t['mem_sis_pico_pct'] = max(t['mem_sis_pico_pct'], sis)
                t['rss_pico_mb'] = max(t['rss_pico_mb'], rss)
                t['n_muestras'] += 1

    def _bucle(self):
        while not self._parar.is_set():
            self._registrar(*self._muestra())
            self._parar.wait(self.intervalo)

    def __enter__(self):
        self._hilo.start()
        return self

    def __exit__(self, *exc):
        self._parar.set()
        self._hilo.join()

    def iniciar_tramo(self):
        sis, rss = self._muestra()
        with self._bloqueo:
            self._tramo = {'mem_sis_base_pct': sis, 'mem_sis_pico_pct': sis,
                           'rss_base_mb': rss, 'rss_pico_mb': rss, 'n_muestras': 1}

    def cerrar_tramo(self):
        self._registrar(*self._muestra())
        with self._bloqueo:
            tramo, self._tramo = self._tramo, None
        return {k: round(v, 3) if isinstance(v, float) else v for k, v in tramo.items()}


def medir(sampler, funcion, *args, **kwargs):
    """Ejecuta `funcion` midiendo tiempo (reloj monotónico) y memoria muestreada."""
    sampler.iniciar_tramo()
    t0 = time.perf_counter_ns()
    resultado = funcion(*args, **kwargs)
    segundos = (time.perf_counter_ns() - t0) / 1e9
    return resultado, segundos, sampler.cerrar_tramo()
