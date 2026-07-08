import time
from pathlib import Path

import pandas as pd
from loguru import logger

from async_utils import run_async
import context
import scraping
from utils import clean_text, clean_tweets


def _start_forwarding_twscrape_logs(log):
    """Reenvía a la consola de la app los avisos de rate-limit/cuentas que twscrape
    emite por su propio logger (loguru) y que de otro modo solo se ven en la terminal."""
    def sink(message):
        record = message.record
        if record["name"].startswith("twscrape"):
            log(f"[twscrape] {record['message']}")

    return logger.add(sink, level="INFO")

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


def _record_overflow(path: Path, source: str, since, until, product: str,
                     frequency: str, tweets: int, n: int, log) -> None:
    """Anota un tramo que alcanzó el límite n de la paginación (len(tweets) >= n):
    señal de que Twitter tenía más y se cortó, así que ese rango puede estar
    incompleto. Se guarda en {prefix}_overflow.csv como log (append) para que el
    usuario re-descargue esos rangos con una frecuencia más fina y luego haga merge.
    No se subdivide nada: la descarga usa el product y la frecuencia del formulario."""
    log(f"OVERFLOW: {tweets} tweets in [{since:%Y-%m-%d %H:%M} .. {until:%Y-%m-%d %H:%M}] "
        f"reached the limit n={n}; range may be incomplete (see {path.name})")
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
            query_date = f"{query} since:{a:%Y-%m-%d_%H:%M:%S} until:{b:%Y-%m-%d_%H:%M:%S}"
            log(f"--> Downloading {query_date} (product={product}) ......")
            tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
            log(f"Downloaded {len(tweets)} tweets")
            if len(tweets) >= n:
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
            log(f"WARNING: {overflow_count} interval(s) reached the n={n} limit and may be "
                f"incomplete — see {overflow_file.name}; re-download those ranges at a finer "
                f"frequency and merge.")
        context.log_end_download(output, prefix, "search", total)

        log("'Historical Search' download completed")
        return output_file
    finally:
        logger.remove(_log_handler)


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
                query_date = f"from:{_user} since:{a:%Y-%m-%d_%H:%M:%S} until:{b:%Y-%m-%d_%H:%M:%S}"
                log(f"--> Downloading {query_date} (product={product}) ......")
                tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
                log(f"Downloaded {len(tweets)} tweets")
                if len(tweets) >= n:
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
            log(f"WARNING: {overflow_count} interval(s) reached the n={n} limit and may be "
                f"incomplete — see {overflow_file.name}; re-download those ranges at a finer "
                f"frequency and merge.")
        context.log_end_download(output, prefix, "users", total)

        log("'Historical Timeline' download completed")
        return output_file
    finally:
        logger.remove(_log_handler)


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
        logger.remove(_log_handler)


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
        logger.remove(_log_handler)


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
                if len(replies) >= n:
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
            log(f"WARNING: {overflow_count} interval(s) reached the n={n} limit and may be "
                f"incomplete — see {overflow_file.name}.")
        log("'Advanced Replies' download completed")
        return output_file
    finally:
        logger.remove(_log_handler)
