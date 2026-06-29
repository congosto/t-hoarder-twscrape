import asyncio
import threading

_state = threading.local()


def get_loop() -> asyncio.AbstractEventLoop:
    loop = getattr(_state, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _state.loop = loop
    return loop


def run_async(coro):
    """Ejecuta una corrutina en un event loop persistente por hilo.

    twscrape crea locks asyncio a nivel de módulo en el primer uso; usar
    asyncio.run() repetidamente crea un loop nuevo cada vez y esos locks
    quedan atados al loop antiguo, rompiendo en la segunda llamada. Un loop
    global compartido entre hilos también falla ("event loop is already
    running") cuando dos sesiones/reruns de Streamlit lo usan a la vez, por
    eso el loop es local a cada hilo (cada sesión de Streamlit corre en su
    propio hilo de script).
    """
    return get_loop().run_until_complete(coro)
