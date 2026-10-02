import asyncio
import concurrent.futures
import threading

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()

# Funciones que cada hilo llamante quiere ejecutar mientras espera a run_async
# (p.ej. volcar a la consola de Streamlit los avisos de twscrape), por id de hilo
_waiters: dict[int, list] = {}


def get_loop() -> asyncio.AbstractEventLoop:
    """Event loop único del proceso, corriendo para siempre en un hilo propio."""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, name="twscrape-loop", daemon=True).start()
        return _loop


def add_waiter(fn) -> None:
    """Registra fn para que run_async la llame (en el hilo actual) mientras espera."""
    _waiters.setdefault(threading.get_ident(), []).append(fn)


def remove_waiter(fn) -> None:
    fns = _waiters.get(threading.get_ident(), [])
    if fn in fns:
        fns.remove(fn)


def _call_waiters() -> None:
    for fn in list(_waiters.get(threading.get_ident(), [])):
        fn()


def run_async(coro, poll: float = 0.5):
    """Ejecuta una corrutina en el event loop único del proceso y espera su resultado.

    twscrape crea locks asyncio a nivel de módulo (p.ej. el de su BD de cuentas)
    que quedan atados al primer loop que los usa con contención. Por eso:
    - asyncio.run() repetido no vale: cada llamada crea un loop nuevo y la
      segunda rompe ("is bound to a different event loop").
    - un loop por hilo tampoco: Streamlit ejecuta las sesiones (y a veces cada
      rerun) en hilos distintos y el lock acaba atado al loop de otro hilo.
    - compartir un loop con run_until_complete desde varios hilos falla con
      "event loop is already running".
    La solución es un solo loop en un hilo dedicado (run_forever) al que cada
    sesión envía su corrutina con run_coroutine_threadsafe.

    Mientras espera, cada `poll` segundos llama en el hilo llamante a las funciones
    registradas con add_waiter: el código de twscrape corre en el hilo del loop, y
    nada de ahí debe tocar Streamlit (solo admite llamadas desde el hilo de su
    sesión), así que los avisos se encolan allí y se pintan desde aquí.
    """
    future = asyncio.run_coroutine_threadsafe(coro, get_loop())
    try:
        while True:
            try:
                return future.result(timeout=poll)
            except concurrent.futures.TimeoutError:
                _call_waiters()
    finally:
        _call_waiters()
