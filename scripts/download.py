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


def historical_search(data_path: Path, dataset: str, prefix: str, query: str, since, until,
                       frequency: str, sleep_time: int = 5, n: int = 900, product: str = "Top",
                       log=print) -> Path:
    _log_handler = _start_forwarding_twscrape_logs(log)
    try:
        output = Path(data_path) / dataset
        output.mkdir(parents=True, exist_ok=True)
        output_file = output / f"{prefix}.csv"
        output_raw_file = output / f"{prefix}_raw.csv"

        existing_range = context.get_context_search_range(output, prefix)
        original_since, original_until = existing_range if existing_range else (since, until)

        last_date = context.get_context_search(output, prefix)
        append = output_file.exists()
        if last_date is not None:
            since = last_date
            log(f"Reanudando desde el contexto guardado: {since} (rango original: {original_since} -> {original_until})")

        sequence = date_sequence(since, until, frequency)

        for i in range(len(sequence) - 1):
            min_date, max_date = sequence[i], sequence[i + 1]
            log(f"Desde {min_date} hasta {max_date}")
            query_date = f"{query} since:{min_date:%Y-%m-%d_%H:%M:%S} until:{max_date:%Y-%m-%d_%H:%M:%S}"
            log(f"--> Descargando {query_date} ......")

            tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
            log(f"Descargados {len(tweets)} tweets")
            if tweets:
                df = _to_dataframe(tweets)
                df = clean_text(df)
                _write_csv(df, output_raw_file, append)
                df = clean_tweets(df, min_date, max_date)
                _write_csv(df, output_file, append)
                append = True

            context.put_context_search(
                output, prefix, max_date, original_since, original_until,
                query=query, product=product, frequency=frequency,
            )
            if i < len(sequence) - 2:
                log(f"Esperando {sleep_time} segundos antes de la próxima iteración...")
                time.sleep(sleep_time)

        if output_file.exists():
            df = pd.read_csv(output_file, encoding="utf-8")
            df = clean_tweets(df, original_since, original_until)
            df.to_csv(output_file, index=False, encoding="utf-8")

        log("Descarga 'Historical Search' completada")
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

        existing_range = context.get_context_user_range(output, prefix)
        original_since, original_until = existing_range if existing_range else (since, until)

        ctx = context.get_context_user(output, prefix)
        append = output_file.exists()

        for order, user in enumerate(list_users):
            since_partial = _to_utc_timestamp(since)
            if ctx is not None:
                row = ctx[ctx["username"] == user]
                if not row.empty:
                    since_partial = _to_utc_timestamp(row["last_date"].iloc[0])
                    log(f"Reanudando @{user} desde el contexto guardado: {since_partial} (rango original: {original_since} -> {original_until})")

            log(f"--> download user {user}")
            sequence = date_sequence(since_partial, until, frequency)

            for i in range(len(sequence) - 1):
                min_date, max_date = sequence[i], sequence[i + 1]
                log(f"Desde {min_date} hasta {max_date}")
                query_date = f"from:{user} since:{min_date:%Y-%m-%d_%H:%M:%S} until:{max_date:%Y-%m-%d_%H:%M:%S}"

                tweets = run_async(scraping.search_tweets(query_date, n=n, product=product))
                log(f"Descargados {len(tweets)} tweets")
                if tweets:
                    df = _to_dataframe(tweets)
                    df = df[df["username"].str.lower() == user.lower()]
                    df = clean_text(df)
                    _write_csv(df, output_raw_file, append)
                    df = clean_tweets(df, min_date, max_date)
                    _write_csv(df, output_file, append)
                    append = True

                context.put_context_user(
                    output, prefix, max_date, order, user, original_since, original_until,
                    product=product, frequency=frequency,
                )
                if i < len(sequence) - 2:
                    log(f"Esperando {sleep_time} segundos antes de la próxima iteración...")
                    time.sleep(sleep_time)

        if output_file.exists():
            df = pd.read_csv(output_file, encoding="utf-8")
            df = clean_tweets(df, original_since, original_until)
            df.to_csv(output_file, index=False, encoding="utf-8")

        log("Descarga 'Historical Timeline' completada")
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
            log(f"Descargados {len(users)} retweeters")
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
                log(f"Esperando {sleep_time} segundos antes de la próxima iteración...")
                time.sleep(sleep_time)

        log("Descarga 'Retweets' completada")
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
            log(f"Descargadas {len(replies)} respuestas")
            if replies:
                df = _to_dataframe(replies)
                df = clean_text(df)
                _write_csv(df, output_raw_file, append)
                _write_csv(df, output_file, append)
                context.put_context_replies(output, prefix, tweet_id)
                append = True

            log(f"Esperando {sleep_time} segundos antes de la próxima iteración...")
            time.sleep(sleep_time)

        log("Descarga 'Replies' completada")
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

        for i, tweet_id in enumerate(tweet_ids):
            if int(tweet_id) <= last_tweet_id:
                continue

            log(f"Download replies from {tweet_urls[i]} {i + 1}/{len(tweet_ids)}")
            since = pd.Timestamp(tweet_dates[i], tz="UTC")
            until = since + pd.Timedelta(days=last_days)
            sequence = date_sequence(since, until, frequency)

            for j in range(len(sequence) - 1):
                min_date, max_date = sequence[j], sequence[j + 1]
                query = (
                    f"conversation_id:{tweet_id} filter:replies "
                    f"since:{min_date:%Y-%m-%d_%H:%M:%S} until:{max_date:%Y-%m-%d_%H:%M:%S}"
                )
                log(f"--> Descargando {query} ......")
                replies = run_async(scraping.search_tweets(query, n=n, product=product))
                log(f"Descargadas {len(replies)} respuestas")
                if replies:
                    df = _to_dataframe(replies)
                    df["url_replied"] = tweet_urls[i]
                    df = clean_text(df)
                    _write_csv(df, output_raw_file, append)
                    df = clean_tweets(df, min_date, max_date)
                    _write_csv(df, output_file, append)
                    context.put_context_replies(output, prefix, tweet_id, kind="replies_advanced")
                    append = True

                if j < len(sequence) - 2:
                    log(f"Esperando {sleep_time} segundos antes de la próxima iteración...")
                    time.sleep(sleep_time)

        log("Descarga 'Replies avanzadas' completada")
        return output_file
    finally:
        logger.remove(_log_handler)
