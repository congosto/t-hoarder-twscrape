import queue
import time
from pathlib import Path

import pandas as pd
from loguru import logger

from async_utils import add_waiter, remove_waiter, run_async
import context
import scraping
from utils import clean_text, clean_tweets


_forwarders: dict[int, tuple] = {}


def _start_forwarding_twscrape_logs(log):
    """Reenvía a la consola de la app los avisos de rate-limit/cuentas que twscrape
    emite por su propio logger (loguru) y que de otro modo solo se ven en la terminal.

    twscrape corre en el hilo del event loop (async_utils), y desde ahí no se puede
    tocar Streamlit: el sink solo encola, y el hilo de la sesión vuelca la cola
    mientras espera en run_async (add_waiter) y al terminar."""
    pending = queue.Queue()

    def sink(message):
        record = message.record
        if record["name"].startswith("twscrape"):
            pending.put(f"[twscrape] {record['message']}")

    def drain():
        while True:
            try:
                log(pending.get_nowait())
            except queue.Empty:
                return

    handler = logger.add(sink, level="INFO")
    add_waiter(drain)
    _forwarders[handler] = drain
    return handler


def _stop_forwarding_twscrape_logs(handler) -> None:
    logger.remove(handler)
    drain = _forwarders.pop(handler, None)
    if drain:
        remove_waiter(drain)
        drain()

_FREQ_UNITS = {
    "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
    "hour": "hours", "hours": "hours",
    "day": "days", "days": "days",
    "week": "weeks", "weeks": "weeks",
    "month": "months", "months": "months",
    "year": "years", "years": "years",
}


def _parse_frequency(frequency: str) -> pd.DateOffset:
    parts = frequency.strip().split()
    if len(parts) == 1:
        n, unit = 1, parts[0]
    else:
        n, unit = int(parts[0]), parts[1]
    kwarg = _FREQ_UNITS[unit.lower()]
    return pd.DateOffset(**{kwarg: n})


def _to_utc_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def date_sequence(since, until, frequency: str) -> list[pd.Timestamp]:
    since = _to_utc_timestamp(since)
    until = _to_utc_timestamp(until)
    offset = _parse_frequency(frequency)

    dates = [since]
    current = since
    while current < until:
        current = min(current + offset, until)
        dates.append(current)

    return dates


def _to_dataframe(tweets: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(tweets)


def _write_csv(df: pd.DataFrame, path: Path, append: bool) -> None:
    df.to_csv(path, mode="a" if append else "w", header=not append, index=False, encoding="utf-8")


def _time_operators(a: pd.Timestamp, b: pd.Timestamp, product: str) -> str:
    """Operadores temporales de la query según ventana y product.

    Latest ignora la parte horaria de since:/until: (trunca el until al día),
    así que sus ventanas de menos de un día usan since_time:/until_time: en
    epoch (mecanismo validado por barri en probe_window_size_recall.py). X
    trata el epoch de forma difusa —puede devolver tweets fuera del rango—,
    pero el recorte fino lo hace clean_tweets en local, y el raw lo guarda
    todo. Top respeta el formato con hora y se mantiene tal cual."""
    if product == "Latest" and (b - a) < pd.Timedelta(days=1):
        return f"since_time:{int(a.timestamp())} until_time:{int(b.timestamp())}"
    return f"since:{a:%Y-%m-%d_%H:%M:%S} until:{b:%Y-%m-%d_%H:%M:%S}"


# Memoria del índice denso de Top: cubre exactamente los últimos N días
# naturales (UTC). El día D-N se recupera completo a cualquier hora y el D-(N+1)
# cae a 0 con ventanas horarias (verificado con las baterías "cintora" de
# data/prueba_descarga_2, jul-2026, replicado en dos descargas independientes).
# Más allá solo queda un residuo de lo más viral, accesible con ventanas de
# >= 1 día (~decenas de tweets/día); Latest no tiene acantilado pero en datos
# viejos devuelve un subconjunto de ese residuo.
_TOP_MEMORY_DAYS = 7


def _top_cutoff() -> pd.Timestamp:
    """Primer día natural (UTC) aún dentro del índice denso de Top. El corte
    avanza a las 00:00 UTC, por eso se recalcula en cada ventana."""
    return pd.Timestamp.now(tz="UTC").floor("D") - pd.Timedelta(days=_TOP_MEMORY_DAYS)


# Umbral de aviso de desbordamiento: si una ventana devuelve >= este nº de tweets
# se considera que topó con el techo del buscador y puede estar incompleta. Es un
# umbral fijo porque el techo real de Latest queda por debajo de n (~700-950, y
# variable), así que un criterio >= n casi nunca dispararía. Se usa min(n, ESTE),
# por si se pide n < 500 (ahí topar con n ya es la señal).
_OVERFLOW_WARN = 500


def _overflow_threshold(n: int) -> int:
    return min(n, _OVERFLOW_WARN)


def _record_overflow(path: Path, source: str, since, until, product: str,
                     frequency: str, tweets: int, n: int, log) -> None:
    """Anota un tramo que superó el umbral de desbordamiento (len(tweets) >=
    min(n, _OVERFLOW_WARN)): señal de que topó con el techo del buscador y ese
    rango puede estar incompleto. Se guarda en {prefix}_overflow.csv como log
    (append) para que el usuario re-descargue esos rangos con una frecuencia más
    fina y luego haga merge. No se subdivide nada: la descarga usa el product y
    la frecuencia del formulario."""
    log(f"OVERFLOW: {tweets} tweets in [{since:%Y-%m-%d %H:%M} .. {until:%Y-%m-%d %H:%M}] "
        f"(>= {_overflow_threshold(n)}); range may be incomplete (see {path.name})")
    row = pd.DataFrame([{
        "detected_at": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "since": f"{since:%Y-%m-%d %H:%M:%S}",
        "until": f"{until:%Y-%m-%d %H:%M:%S}",
        "product": product,
        "frequency": frequency,
        "tweets": tweets,
        "n": n,
    }])
    _write_csv(row, path, append=path.exists())


def historical_search(data_path: Path, dataset: str, prefix: str, query: str, since, until,
                       frequency: str, sleep_time: int = 5, n: int = 900, product: str = "Top",
                       log=print) -> Path:
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        output.mkdir(parents=True, exist_ok=True)
        output_file = output / f"{prefix}.csv"
        output_raw_file = output / f"{prefix}_raw.csv"
        overflow_file = output / f"{prefix}_overflow.csv"

        existing_range = context.get_context_search_range(output, prefix)
        original_since, original_until = existing_range if existing_range else (since, until)

        last_date = context.get_context_search(output, prefix)
        append = output_file.exists()
        if last_date is not None:
            since = last_date
            log(f"Resuming from saved context: {since} (original range: {original_since} -> {original_until})")

        sequence = date_sequence(since, until, frequency)

        if product == "Top" and _to_utc_timestamp(since) < _top_cutoff():
            log(f"WARNING: Top's dense index only covers the last {_TOP_MEMORY_DAYS} calendar days "
                f"(UTC); days before {_top_cutoff():%Y-%m-%d} will return only a residue of the most "
                f"viral tweets (or nothing with sub-day windows). Consider Latest or the optimized "
                f"download for old ranges.")

        _pacer = {"first": True}
        overflow_count = 0

        def pace():
            if _pacer["first"]:
                _pacer["first"] = False
            elif sleep_time:
                log(f"Waiting {sleep_time} seconds before the next iteration...")
                time.sleep(sleep_time)

        def slot(a, b):
            nonlocal append, overflow_count
            pace()
            log(f"From {a} to {b}")
            query_date = f"{query} {_time_operators(a, b, product)}"
            log(f"--> Downloading {query_date} (product={product}) ......")
            tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
            log(f"Downloaded {len(tweets)} tweets")
            if len(tweets) >= _overflow_threshold(n):
                _record_overflow(overflow_file, query, a, b, product, frequency, len(tweets), n, log)
                overflow_count += 1
            if tweets:
                df = _to_dataframe(tweets)
                df = clean_text(df)
                _write_csv(df, output_raw_file, append)
                df = clean_tweets(df, a, b)
                _write_csv(df, output_file, append)
                append = True

        for i in range(len(sequence) - 1):
            slot(sequence[i], sequence[i + 1])
            context.log_download_tweets(
                output, prefix, sequence[i + 1], original_since, original_until,
                query=query, product=product, frequency=frequency,
            )

        total = 0
        if output_file.exists():
            df = clean_tweets(pd.read_csv(output_file, encoding="utf-8"),
                              original_since, original_until)
            df.to_csv(output_file, index=False, encoding="utf-8")
            total = len(df)
        if overflow_count:
            log(f"WARNING: {overflow_count} interval(s) reached >= {_overflow_threshold(n)} tweets "
                f"and may be incomplete — see {overflow_file.name}; re-download those ranges at a "
                f"finer frequency and merge.")
        context.log_end_download(output, prefix, "search", total)

        log("'Historical Search' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)


# ── Descarga optimizada ──────────────────────────────────────────────────────
# Elige sola la frecuencia: empieza por la que corresponde al periodo pedido y,
# cuando una ventana desborda (>= _OPT_OVERFLOW), la re-descarga subdividida con
# la siguiente frecuencia de la escalera, recursivamente. Las ventanas de >= 1
# día van alineadas a medianoche, porque Latest trunca la hora del until al día;
# las intradía usan operadores epoch (_time_operators).
#
# El producto es SIEMPRE Latest (2026-09-03). Antes la escalera usaba Top en las
# ventanas intradía recientes y añadía una pasada Top de "residuo viral" en las
# ventanas viejas de >= 1 día. Se han quitado las dos: pasados unos días, Top se
# comporta de forma errática y lo que devuelve es basura (tweets fuera de rango
# o irrelevantes) que no compensa ni la cuota gastada ni el ruido en el raw.
# Top sigue disponible en las descargas manuales, donde lo elige el usuario.

_OPT_LADDER = ["1 month", "1 week", "1 day", "6 hour", "3 hour", "1 hour", "30 min"]
_OPT_OVERFLOW = 500


def _initial_frequency(since, until) -> str:
    days = (_to_utc_timestamp(until) - _to_utc_timestamp(since)).total_seconds() / 86400
    if days <= 31:
        return "1 day"
    if days <= 183:
        return "1 week"
    return "1 month"


def _record_overflow_opt(path: Path, source: str, since, until, product: str,
                         frequency: str, tweets: int, n: int, action: str, log) -> None:
    log(f"OVERFLOW: {tweets} tweets in [{since:%Y-%m-%d %H:%M} .. {until:%Y-%m-%d %H:%M}] "
        f"({action}; see {path.name})")
    row = pd.DataFrame([{
        "detected_at": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "since": f"{since:%Y-%m-%d %H:%M:%S}",
        "until": f"{until:%Y-%m-%d %H:%M:%S}",
        "product": product,
        "frequency": frequency,
        "tweets": tweets,
        "n": n,
        "action": action,
    }])
    _write_csv(row, path, append=path.exists())


def optimized_search(data_path: Path, dataset: str, prefix: str, query: str, since, until,
                     sleep_time: int = 5, n: int = 900, log=print) -> Path:
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        output.mkdir(parents=True, exist_ok=True)
        output_file = output / f"{prefix}.csv"
        output_raw_file = output / f"{prefix}_raw.csv"
        overflow_file = output / f"{prefix}_overflow.csv"

        existing_range = context.get_context_search_range(output, prefix)
        original_since, original_until = existing_range if existing_range else (since, until)

        last_date = context.get_context_search(output, prefix)
        append = output_file.exists()
        if last_date is not None:
            since = last_date
            log(f"Resuming from saved context: {since} (original range: {original_since} -> {original_until})")

        frequency = _initial_frequency(original_since, original_until)
        level0 = _OPT_LADDER.index(frequency)
        threshold = min(n, _OPT_OVERFLOW)
        # ventanas Latest alineadas a frontera de día; el final se recorta luego
        start = _to_utc_timestamp(since).floor("D")
        end = _to_utc_timestamp(until).ceil("D")
        log(f"Optimized download: full period {pd.Timestamp(original_since):%Y-%m-%d %H:%M} -> "
            f"{pd.Timestamp(original_until):%Y-%m-%d %H:%M}, starting at Latest / {frequency} "
            f"(overflow threshold {threshold})")

        _pacer = {"first": True}
        overflow_count = 0

        def pace():
            if _pacer["first"]:
                _pacer["first"] = False
            elif sleep_time:
                log(f"Waiting {sleep_time} seconds before the next iteration...")
                time.sleep(sleep_time)

        def store(tweets, a, b):
            nonlocal append
            df = _to_dataframe(tweets)
            df = clean_text(df)
            _write_csv(df, output_raw_file, output_raw_file.exists())
            df = clean_tweets(df, a, b)
            if len(df):
                _write_csv(df, output_file, append)
                append = True

        def window(a, b, level):
            nonlocal overflow_count
            pace()
            freq = _OPT_LADDER[level]
            product = "Latest"
            query_date = f"{query} {_time_operators(a, b, product)}"
            log(f"--> Downloading {query_date} (product={product}, frequency={freq}) ......")
            tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
            log(f"Downloaded {len(tweets)} tweets")
            if tweets:
                store(tweets, a, b)
            if len(tweets) >= threshold:
                overflow_count += 1
                if level + 1 < len(_OPT_LADDER):
                    finer = _OPT_LADDER[level + 1]
                    _record_overflow_opt(overflow_file, query, a, b, product, freq,
                                         len(tweets), n, f"overflow -> retry at {finer}", log)
                    sub = date_sequence(a, b, finer)
                    for j in range(len(sub) - 1):
                        window(sub[j], sub[j + 1], level + 1)
                else:
                    _record_overflow_opt(overflow_file, query, a, b, product, freq,
                                         len(tweets), n, "overflow (min frequency reached)", log)

        sequence = date_sequence(start, end, frequency)
        for i in range(len(sequence) - 1):
            window(sequence[i], sequence[i + 1], level0)
            context.log_download_tweets(
                output, prefix, sequence[i + 1], original_since, original_until,
                query=query, product="Optimized", frequency="auto",
            )

        total = 0
        if output_file.exists():
            df = clean_tweets(pd.read_csv(output_file, encoding="utf-8"),
                              original_since, original_until)
            df.to_csv(output_file, index=False, encoding="utf-8")
            total = len(df)
        if overflow_count:
            log(f"{overflow_count} interval(s) overflowed and were re-downloaded at finer "
                f"frequencies — see {overflow_file.name} for every range change.")
        context.log_end_download(output, prefix, "search", total)

        log("'Optimized Search' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)


def historical_timeline(data_path: Path, dataset: str, prefix: str, list_users: list[str],
                         since, until, frequency: str, sleep_time: int = 5, n: int = 900,
                         product: str = "Top", log=print) -> Path:
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        output.mkdir(parents=True, exist_ok=True)
        output_file = output / f"{prefix}.csv"
        output_raw_file = output / f"{prefix}_raw.csv"
        overflow_file = output / f"{prefix}_overflow.csv"

        existing_range = context.get_context_user_range(output, prefix)
        original_since, original_until = existing_range if existing_range else (since, until)

        ctx = context.get_context_user(output, prefix)
        append = output_file.exists()

        if product == "Top" and _to_utc_timestamp(since) < _top_cutoff():
            log(f"WARNING: Top's dense index only covers the last {_TOP_MEMORY_DAYS} calendar days "
                f"(UTC); days before {_top_cutoff():%Y-%m-%d} will return only a residue of the most "
                f"viral tweets (or nothing with sub-day windows). Consider Latest or the optimized "
                f"download for old ranges.")

        _pacer = {"first": True}
        overflow_count = 0

        def pace():
            if _pacer["first"]:
                _pacer["first"] = False
            elif sleep_time:
                log(f"Waiting {sleep_time} seconds before the next iteration...")
                time.sleep(sleep_time)

        for order, user in enumerate(list_users):
            since_partial = _to_utc_timestamp(since)
            if ctx is not None:
                row = ctx[ctx["username"] == user]
                if not row.empty:
                    since_partial = _to_utc_timestamp(row["last_date"].iloc[0])
                    log(f"Resuming @{user} from saved context: {since_partial} (original range: {original_since} -> {original_until})")

            log(f"--> download user {user}")
            sequence = date_sequence(since_partial, until, frequency)

            def slot(a, b, _user=user):
                nonlocal append, overflow_count
                pace()
                log(f"From {a} to {b}")
                query_date = f"from:{_user} {_time_operators(a, b, product)}"
                log(f"--> Downloading {query_date} (product={product}) ......")
                tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
                log(f"Downloaded {len(tweets)} tweets")
                if len(tweets) >= _overflow_threshold(n):
                    _record_overflow(overflow_file, f"from:{_user}", a, b, product, frequency, len(tweets), n, log)
                    overflow_count += 1
                if tweets:
                    df = _to_dataframe(tweets)
                    df = df[df["username"].str.lower() == _user.lower()]
                    df = clean_text(df)
                    _write_csv(df, output_raw_file, append)
                    df = clean_tweets(df, a, b)
                    _write_csv(df, output_file, append)
                    append = True

            for i in range(len(sequence) - 1):
                slot(sequence[i], sequence[i + 1])
                context.log_download_users(
                    output, prefix, sequence[i + 1], order, user, original_since, original_until,
                    product=product, frequency=frequency,
                )

        total = 0
        if output_file.exists():
            df = clean_tweets(pd.read_csv(output_file, encoding="utf-8"),
                              original_since, original_until)
            df.to_csv(output_file, index=False, encoding="utf-8")
            total = len(df)
        if overflow_count:
            log(f"WARNING: {overflow_count} interval(s) reached >= {_overflow_threshold(n)} tweets "
                f"and may be incomplete — see {overflow_file.name}; re-download those ranges at a "
                f"finer frequency and merge.")
        context.log_end_download(output, prefix, "users", total)

        log("'Historical Timeline' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)


def optimized_timeline(data_path: Path, dataset: str, prefix: str, list_users: list[str],
                       since, until, sleep_time: int = 5, n: int = 900, log=print) -> Path:
    """Descarga optimizada de timelines: mismo criterio que optimized_search
    (frecuencia inicial según el periodo, siempre Latest —ventanas de >= 1 día
    alineadas a medianoche y epoch en las intradía—, subdivisión recursiva al
    desbordar), aplicado usuario a usuario con consultas from:{user}."""
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        output.mkdir(parents=True, exist_ok=True)
        output_file = output / f"{prefix}.csv"
        output_raw_file = output / f"{prefix}_raw.csv"
        overflow_file = output / f"{prefix}_overflow.csv"

        existing_range = context.get_context_user_range(output, prefix)
        original_since, original_until = existing_range if existing_range else (since, until)

        ctx = context.get_context_user(output, prefix)
        append = output_file.exists()

        frequency = _initial_frequency(original_since, original_until)
        level0 = _OPT_LADDER.index(frequency)
        threshold = min(n, _OPT_OVERFLOW)
        log(f"Optimized download: full period {pd.Timestamp(original_since):%Y-%m-%d %H:%M} -> "
            f"{pd.Timestamp(original_until):%Y-%m-%d %H:%M}, starting at Latest / {frequency} "
            f"(overflow threshold {threshold})")

        _pacer = {"first": True}
        overflow_count = 0

        def pace():
            if _pacer["first"]:
                _pacer["first"] = False
            elif sleep_time:
                log(f"Waiting {sleep_time} seconds before the next iteration...")
                time.sleep(sleep_time)

        def store(tweets, a, b, _user):
            nonlocal append
            df = _to_dataframe(tweets)
            df = df[df["username"].str.lower() == _user.lower()]
            df = clean_text(df)
            _write_csv(df, output_raw_file, output_raw_file.exists())
            df = clean_tweets(df, a, b)
            if len(df):
                _write_csv(df, output_file, append)
                append = True

        def window(a, b, level, _user):
            nonlocal overflow_count
            pace()
            freq = _OPT_LADDER[level]
            product = "Latest"
            query_date = f"from:{_user} {_time_operators(a, b, product)}"
            log(f"--> Downloading {query_date} (product={product}, frequency={freq}) ......")
            tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
            log(f"Downloaded {len(tweets)} tweets")
            if tweets:
                store(tweets, a, b, _user)
            if len(tweets) >= threshold:
                overflow_count += 1
                if level + 1 < len(_OPT_LADDER):
                    finer = _OPT_LADDER[level + 1]
                    _record_overflow_opt(overflow_file, f"from:{_user}", a, b, product, freq,
                                         len(tweets), n, f"overflow -> retry at {finer}", log)
                    sub = date_sequence(a, b, finer)
                    for j in range(len(sub) - 1):
                        window(sub[j], sub[j + 1], level + 1, _user)
                else:
                    _record_overflow_opt(overflow_file, f"from:{_user}", a, b, product, freq,
                                         len(tweets), n, "overflow (min frequency reached)", log)

        for order, user in enumerate(list_users):
            since_partial = _to_utc_timestamp(since)
            if ctx is not None:
                row = ctx[ctx["username"] == user]
                if not row.empty:
                    since_partial = _to_utc_timestamp(row["last_date"].iloc[0])
                    log(f"Resuming @{user} from saved context: {since_partial} "
                        f"(original range: {original_since} -> {original_until})")

            log(f"--> download user {user}")
            # ventanas Latest alineadas a frontera de día; el final se recorta luego
            sequence = date_sequence(since_partial.floor("D"), _to_utc_timestamp(until).ceil("D"), frequency)
            for i in range(len(sequence) - 1):
                window(sequence[i], sequence[i + 1], level0, user)
                context.log_download_users(
                    output, prefix, sequence[i + 1], order, user, original_since, original_until,
                    product="Optimized", frequency="auto",
                )

        total = 0
        if output_file.exists():
            df = clean_tweets(pd.read_csv(output_file, encoding="utf-8"),
                              original_since, original_until)
            df.to_csv(output_file, index=False, encoding="utf-8")
            total = len(df)
        if overflow_count:
            log(f"{overflow_count} interval(s) overflowed and were re-downloaded at finer "
                f"frequencies — see {overflow_file.name} for every range change.")
        context.log_end_download(output, prefix, "users", total)

        log("'Optimized Timeline' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)


def get_retweets(data_path: Path, dataset: str, prefix: str, min_rts: int = 1,
                  sleep_time: int = 5, n: int = 10000, log=print) -> Path:
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        file_in = output / f"{prefix}.csv"
        output_file = output / f"{prefix}_RTs.csv"

        tweets = pd.read_csv(file_in, encoding="utf-8")
        tweets = tweets[tweets["retweet_count"] >= min_rts]
        tweets["tweet_id"] = tweets["url"].str.extract(r"(\d+)$")
        tweets = tweets.dropna(subset=["id"]).sort_values("tweet_id")

        last_tweet_id = context.get_context_RTs(output, prefix)
        append = output_file.exists()
        last_tweet_id = int(last_tweet_id) if last_tweet_id else 0

        tweet_ids = tweets["tweet_id"].tolist()
        tweet_urls = tweets["url"].tolist()

        for i, tweet_id in enumerate(tweet_ids):
            if int(tweet_id) <= last_tweet_id:
                continue

            log(f"Download RTs from {tweet_urls[i]} {i + 1}/{len(tweet_ids)}")
            users = run_async(scraping.get_retweeters(tweet_id, n=n))
            log(f"Downloaded {len(users)} retweeters")
            if users:
                df = pd.DataFrame(users)
                df["user_retweeted"] = tweet_urls[i].split("/")[-3]
                df["url_rt"] = tweet_urls[i]
                df = df.rename(columns={"id": "user_id", "displayname": "user_displayname"})
                df = df[[
                    "username", "user_retweeted", "user_id", "user_displayname",
                    "followers_count", "friends_count", "statuses_count", "favourites_count",
                    "listed_count", "location", "created_at", "user_verified",
                    "is_blue_verified", "verified_type", "url_rt",
                ]]
                _write_csv(df, output_file, append)
                append = True

            context.put_context_RTs(output, prefix, tweet_id)
            if i < len(tweet_ids) - 1:
                log(f"Waiting {sleep_time} seconds before the next iteration...")
                time.sleep(sleep_time)

        log("'Retweets' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)


def get_replies(data_path: Path, dataset: str, prefix: str, min_replies: int = 1,
                 sleep_time: int = 5, n: int = 10000, log=print) -> Path:
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        file_in = output / f"{prefix}.csv"
        output_file = output / f"{prefix}_replies.csv"
        output_raw_file = output / f"{prefix}_replies_raw.csv"

        tweets = pd.read_csv(file_in, encoding="utf-8")
        tweets = tweets[tweets["reply_count"] >= min_replies]
        tweets["tweet_id"] = tweets["url"].str.extract(r"(\d+)$")
        tweets = tweets.sort_values("tweet_id")

        last_tweet_id = context.get_context_replies(output, prefix)
        append = output_file.exists()
        last_tweet_id = int(last_tweet_id) if last_tweet_id else 0

        tweet_ids = tweets["tweet_id"].tolist()
        tweet_urls = tweets["url"].tolist()

        for i, tweet_id in enumerate(tweet_ids):
            if int(tweet_id) <= last_tweet_id:
                continue

            log(f"Download replies from {tweet_urls[i]} {i + 1}/{len(tweet_ids)}")
            replies = run_async(scraping.tweet_replies(tweet_id, n=n))
            log(f"Downloaded {len(replies)} replies")
            if replies:
                df = _to_dataframe(replies)
                df = clean_text(df)
                _write_csv(df, output_raw_file, append)
                _write_csv(df, output_file, append)
                context.put_context_replies(output, prefix, tweet_id)
                append = True

            log(f"Waiting {sleep_time} seconds before the next iteration...")
            time.sleep(sleep_time)

        log("'Replies' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)


def get_replies_advanced(data_path: Path, dataset: str, prefix: str, min_replies: int = 1,
                          last_days: int = 4, frequency: str = "1 day", sleep_time: int = 5,
                          n: int = 900, product: str = "Top", log=print) -> Path:
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        file_in = output / f"{prefix}.csv"
        output_file = output / f"{prefix}_replies_advanced.csv"
        output_raw_file = output / f"{prefix}_replies_advanced_raw.csv"
        overflow_file = output / f"{prefix}_replies_advanced_overflow.csv"

        tweets = pd.read_csv(file_in, encoding="utf-8")
        tweets = tweets[tweets["reply_count"] >= min_replies]
        tweets["tweet_id"] = tweets["url"].str.extract(r"(\d+)$")
        tweets = tweets.sort_values("tweet_id")

        last_tweet_id = context.get_context_replies(output, prefix, kind="replies_advanced")
        append = output_file.exists()
        last_tweet_id = int(last_tweet_id) if last_tweet_id else 0

        tweet_ids = tweets["tweet_id"].tolist()
        tweet_urls = tweets["url"].tolist()
        tweet_dates = tweets["date"].tolist()

        _pacer = {"first": True}
        overflow_count = 0

        def pace():
            if _pacer["first"]:
                _pacer["first"] = False
            elif sleep_time:
                log(f"Waiting {sleep_time} seconds before the next iteration...")
                time.sleep(sleep_time)

        for i, tweet_id in enumerate(tweet_ids):
            if int(tweet_id) <= last_tweet_id:
                continue

            log(f"Download replies from {tweet_urls[i]} {i + 1}/{len(tweet_ids)}")
            since_t = pd.Timestamp(tweet_dates[i], tz="UTC")
            until_t = since_t + pd.Timedelta(days=last_days)

            def slot(a, b, _tid=tweet_id, _url=tweet_urls[i]):
                nonlocal append, overflow_count
                pace()
                query = (f"conversation_id:{_tid} filter:replies "
                         f"since:{a:%Y-%m-%d_%H:%M:%S} until:{b:%Y-%m-%d_%H:%M:%S}")
                log(f"--> Downloading {query} (product={product}) ......")
                replies = run_async(scraping.search_tweets(query, n=n, product=product))
                log(f"Downloaded {len(replies)} replies")
                if len(replies) >= _overflow_threshold(n):
                    _record_overflow(overflow_file, _url, a, b, product, frequency, len(replies), n, log)
                    overflow_count += 1
                if replies:
                    df = _to_dataframe(replies)
                    df["url_replied"] = _url
                    df = clean_text(df)
                    _write_csv(df, output_raw_file, append)
                    df = clean_tweets(df, a, b)
                    _write_csv(df, output_file, append)
                    append = True

            seq = date_sequence(since_t, until_t, frequency)
            for j in range(len(seq) - 1):
                slot(seq[j], seq[j + 1])
            context.put_context_replies(output, prefix, tweet_id, kind="replies_advanced")

        if overflow_count:
            log(f"WARNING: {overflow_count} interval(s) reached >= {_overflow_threshold(n)} tweets "
                f"and may be incomplete — see {overflow_file.name}.")
        log("'Advanced Replies' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)


# ── About (x.com/{user}/about) ───────────────────────────────────────────────

ABOUT_FILE_COLS = [
    "user_id", "username", "about_account_based_in", "about_location_accurate",
    "about_created_country_accurate", "about_source", "about_affiliate_username",
    "about_username_changes", "about_username_last_changed", "about_identity_verified",
    "about_verified_since", "about_status", "about_checked_at",
]


def get_about(data_path: Path, dataset: str, prefix: str, sleep_time: float = 1,
              retries: int = 3, retry_wait: int = 60, log=print) -> Path:
    """Descarga la página "About this account" de cada autor de {prefix}.csv en
    {prefix}_about.csv (una fila por usuario, en orden de user_id).

    Solo autores de los tweets originales: se probó también con los retuiteadores
    (2-10-2026) y se quitó por coste: una petición por usuario y ~50 por cuenta
    cada 15 min hacen que los ~40.000 retuiteadores de un dataset mediano lleven
    ~35 h con 5 cuentas.

    Reanudación: el cursor (último user_id procesado) va en {prefix}_about_context.csv
    como en RTs/replies, y además se saltan los user_id que ya están en la salida, así
    que tras una descarga nueva solo se piden los autores nuevos. Si X no responde
    (petición abortada por twscrape) se reintenta el mismo usuario; si sigue sin
    responder se para SIN avanzar el cursor, para no anotar cuentas como not_found
    por error.

    sleep_time espacia las peticiones. Sin pausa, al liberarse las cuentas salían
    ~250 peticiones en ráfaga desde la misma IP y Cloudflare respondía 429 (bloqueo
    por IP, que no se arregla rotando cuentas). El ritmo total lo marca el límite de
    X (~50 por cuenta cada 15 min): medido ~790 usuarios/h con 4-5 cuentas tanto
    con 4 s como con 1 s, y con 1 s sin ningún 429."""
    from datetime import datetime, timezone

    from twscrape import API
    from config import ACCOUNTS_DB

    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        file_in = output / f"{prefix}.csv"
        output_file = output / f"{prefix}_about.csv"

        tweets = pd.read_csv(file_in, encoding="utf-8", dtype={"user_id": str},
                             usecols=["user_id", "username"])
        users = (tweets.dropna()
                       .drop_duplicates(subset="user_id", keep="last")
                       .assign(_uid=lambda d: d["user_id"].astype(int))
                       .sort_values("_uid"))
        done = (set(pd.read_csv(output_file, encoding="utf-8", dtype={"user_id": str},
                                usecols=["user_id"])["user_id"])
                if output_file.exists() else set())
        last_user_id = context.get_context_about(output, prefix)
        pending = users[~users["user_id"].isin(done)]
        log(f"Authors in {file_in.name}: {len(users)} — already downloaded: {len(users) - len(pending)} "
            f"— to download: {len(pending)}"
            + (f" (resuming after user_id {last_user_id})" if last_user_id else ""))

        api = API(ACCOUNTS_DB)
        append = output_file.exists()
        for i, (user_id, username) in enumerate(pending[["user_id", "username"]].itertuples(index=False), 1):
            for attempt in range(1, retries + 1):
                try:
                    about = run_async(scraping.user_about(username, api=api))
                    break
                except RuntimeError as e:
                    if attempt == retries:
                        raise RuntimeError(
                            f"@{username}: {e} after {retries} attempts; stopped at {i}/{len(pending)}. "
                            f"Progress saved in {output_file.name}: launch it again later to resume."
                        )
                    log(f"@{username}: {e}; retrying in {retry_wait} seconds ({attempt}/{retries})...")
                    time.sleep(retry_wait)

            row = {**about, "user_id": user_id, "username": username,
                   "about_checked_at": str(datetime.now(timezone.utc).replace(microsecond=0))}
            # si la cuenta cambió de nombre, el screen_name puede ser ya de otra cuenta
            if about["about_status"] == "ok" and about["user_id"] != user_id:
                row = {"user_id": user_id, "username": username, "about_status": "renamed",
                       "about_checked_at": row["about_checked_at"]}
            _write_csv(pd.DataFrame([row]).reindex(columns=ABOUT_FILE_COLS), output_file, append)
            append = True
            context.put_context_about(output, prefix, user_id)
            if i % 25 == 0 or i == len(pending):
                log(f"Downloaded about of {i}/{len(pending)} users")
            if i < len(pending):
                time.sleep(sleep_time)

        if output_file.exists():
            status = pd.read_csv(output_file, encoding="utf-8")["about_status"].value_counts().to_dict()
            log("About status: " + ", ".join(f"{k}={v}" for k, v in status.items()))
        log("'About' download completed")
        return output_file
    finally:
        _stop_forwarding_twscrape_logs(_log_handler)
