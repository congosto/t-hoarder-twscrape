"""Parche para twscrape: XClIdGen con sesión autenticada (issue #320).

Desde julio de 2026, X sirve a las peticiones ANÓNIMAS el bundle web
"logged-out", que ya no incluye el script de índices (sign.o-*.js /
ondemand.s-*.js) necesario para calcular el header x-client-transaction-id que
X exige en cada petición a su API. Resultado: `XClIdGen.create()` falla con
"Couldn't get XClientTxId indices script" y no se puede descargar nada.

La misma página cargada CON las cookies de sesión de una cuenta (auth_token +
ct0, y user-agent de navegador, sin el bearer de la API) devuelve el bundle
"logged-in", que sí enlaza ese script. Este parche hace que `XClIdGen.create`
reciba las cookies de la cuenta activa y las use para cargar la página.

El material de clave del transaction-id es global de la página (bytes de
verificación del <meta> + animación del SVG), NO depende de la cuenta, así que
valen las cookies de cualquier cuenta activa; se mantiene la caché por usuario
que ya trae twscrape.

Se importa desde scripts/scraping.py, así que se activa en cuanto la app usa
twscrape. Es idempotente. QUITAR cuando twscrape publique el fix de
https://github.com/vladkens/twscrape/issues/320 (comprobar si sus funciones
siguen coincidiendo con las que aquí se reemplazan).

Ref. issue: https://github.com/vladkens/twscrape/issues/320
"""

import asyncio
from urllib.parse import urlparse

import bs4

import twscrape.queue_client as _qc
import twscrape.xclid as _xclid
from twscrape.http import make_client as _make_http_client
from twscrape.logger import logger

_MARK = "_thoarder_xclid_cookies_patch"


async def _create(cookies=None):
    """Como XClIdGen.create original, pero cargando la página con las cookies de
    sesión de la cuenta (bundle logged-in, que sí trae el script de índices)."""
    clt = _make_http_client(headers={"user-agent": "@chrome"}, cookies=cookies or {})
    try:
        text = await _xclid.get_tw_page_text("https://x.com/tesla", clt)
        soup = bs4.BeautifulSoup(text, "html.parser")
        vk_bytes, anim_key = await _xclid.load_keys(soup, clt)
        return _xclid.XClIdGen(vk_bytes, anim_key)
    finally:
        await clt.aclose()


async def _store_get(cls, username, cookies=None, fresh=False):
    """XClIdGenStore.get que además propaga las cookies a create()."""
    if username in cls.items and not fresh:
        return cls.items[username]

    tries = 0
    while tries < 3:
        try:
            gen = await _xclid.XClIdGen.create(cookies=cookies)
            cls.items[username] = gen
            return gen
        except Exception as e:
            tries += 1
            logger.warning(f"XClIdGen creation attempt {tries}/3 failed: {type(e).__name__}: {e}")
            await asyncio.sleep(1)

    raise _qc.AbortReqError(
        "Failed to create XClIdGen. See: https://github.com/vladkens/twscrape/issues/248"
    )


async def _ctx_req(self, method, url, params=None):
    """Ctx.req que pasa las cookies de la cuenta (self.acc.cookies) al store.
    Idéntico al original salvo ese argumento (conserva el retry por 404)."""
    path = urlparse(url).path or "/"

    tries = 0
    while tries < 3:
        gen = await _qc.XClIdGenStore.get(
            self.acc.username, cookies=self.acc.cookies, fresh=tries > 0
        )
        hdr = {"x-client-transaction-id": gen.calc(method, path)}
        rep = await self.clt.request(method, url, params=params, headers=hdr)
        if rep.status_code != 404:
            return rep

        tries += 1
        logger.debug(f"Retrying request with new x-client-transaction-id: {url}")
        await asyncio.sleep(1)

    raise _qc.AbortReqError(
        "Faield to get XClIdGen. See: https://github.com/vladkens/twscrape/issues/248"
    )


def apply():
    """Aplica el parche una sola vez (idempotente)."""
    if getattr(_qc.XClIdGenStore, _MARK, False):
        return
    _xclid.XClIdGen.create = staticmethod(_create)
    _qc.XClIdGenStore.get = classmethod(_store_get)
    _qc.Ctx.req = _ctx_req
    setattr(_qc.XClIdGenStore, _MARK, True)
    logger.debug("twscrape XClIdGen patch aplicado (issue #320)")


apply()
