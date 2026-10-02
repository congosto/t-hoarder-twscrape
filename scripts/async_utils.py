import asyncio
import threading

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def get_loop() -> asyncio.AbstractEventLoop:
    """Event loop único del proceso, corriendo para siempre en un hilo propio."""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, name="twscrape-loop", daemon=True).start()
        return _loop


def run_async(coro):
    """Ejecuta una corrutina en el event loop único del proceso y espera su resultado.

    twscrape crea locks asyncio a nivel de módulo (p.ej. el de su BD de cuentas)
    que quedan atados al primer loop que los usa con contención. Por eso:
    - asyncio.run() repetido no vale: cada llamada crea un loop nuevo y la
      segunda rompe ("is bound to a different event loop").
    - un loop por hilo tampoco: cada sesión de Streamlit corre en su propio hilo
      y, si dos sesiones tocan la BD a la vez (una descarga larga en una pestaña
      y Settings en otra), el lock está atado al loop de la otra sesión.
    - compartir un loop con run_until_complete desde varios hilos falla con
      "event loop is already running".
    La solución es un solo loop en un hilo dedicado (run_forever) al que cada
    sesión envía su corrutina con run_coroutine_threadsafe: todo twscrape vive
    en el mismo loop y las corrutinas de distintas sesiones se intercalan.
    """
    return asyncio.run_coroutine_threadsafe(coro, get_loop()).result()
