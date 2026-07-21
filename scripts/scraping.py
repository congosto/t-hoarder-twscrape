import twscrape_patch  # noqa: F401  parche XClIdGen issue #320 (se aplica al importar)
from twscrape import API


def _tweet_to_dict(tweet) -> dict:
    user = tweet.user
    media_urls = (
        [p.url for p in tweet.media.photos]
        + [v.thumbnailUrl for v in tweet.media.videos]
        + [a.thumbnailUrl for a in tweet.media.animated]
    )
    expanded_url = tweet.links[0].url if tweet.links else None
    quoted = tweet.quotedTweet

    return {
        # metadatos básicos del tweet
        "id": str(tweet.id),
        "date": str(tweet.date),
        "username": user.username,
        "text": tweet.rawContent,
        "source": tweet.sourceLabel,
        "lang": tweet.lang or "und",
        # metadatos de interacción
        "reply_count": tweet.replyCount or 0,
        "retweet_count": tweet.retweetCount or 0,
        "like_count": tweet.likeCount or 0,
        "quote_count": tweet.quoteCount or 0,
        "views_count": tweet.viewCount or 0,
        "in_reply_to_user_id_str": tweet.inReplyToUser.id_str if tweet.inReplyToUser else None,
        "in_reply_to_user_username": tweet.inReplyToUser.username if tweet.inReplyToUser else None,
        "in_reply_to_tweet_id_str": tweet.inReplyToTweetIdStr,
        "conversation_id_str": tweet.conversationIdStr,
        "is_quote_status": tweet.isQuoteStatus,
        "quoted_tweet_username": quoted.user.username if quoted else None,
        "quoted_tweet_url": quoted.url if quoted else None,
        # metadatos del autor del tweet
        "user_id": str(user.id),
        "user_displayname": user.displayname,
        "followers_count": getattr(user, "followersCount", 0) or 0,
        "friends_count": getattr(user, "friendsCount", 0) or 0,
        "statuses_count": getattr(user, "statusesCount", 0) or 0,
        "favourites_count": getattr(user, "favouritesCount", 0) or 0,
        "listed_count": getattr(user, "listedCount", 0) or 0,
        "location": getattr(user, "location", "") or "",
        "created_at": str(getattr(user, "created", "")),
        "user_verified": getattr(user, "verified", False) or False,
        "is_blue_verified": getattr(user, "blue", False) or False,
        "verified_type": getattr(user, "blueType", None),
        # metadatos del contenido
        "expanded_url": expanded_url,
        "media": ";".join(media_urls) if media_urls else None,
        # enlace del tweet
        "url": tweet.url,
    }


def _user_to_dict(user) -> dict:
    return {
        "id": str(user.id),
        "username": getattr(user, "username", ""),
        "displayname": getattr(user, "displayname", ""),
        "description": getattr(user, "rawDescription", "") or getattr(user, "description", ""),
        "followers_count": getattr(user, "followersCount", 0) or 0,
        "friends_count": getattr(user, "friendsCount", 0) or 0,
        "statuses_count": getattr(user, "statusesCount", 0) or 0,
        "favourites_count": getattr(user, "favouritesCount", 0) or 0,
        "listed_count": getattr(user, "listedCount", 0) or 0,
        "location": getattr(user, "location", "") or "",
        "created_at": str(getattr(user, "created", "")),
        "user_verified": getattr(user, "verified", False) or False,
        "is_blue_verified": getattr(user, "blue", False) or False,
        "verified_type": getattr(user, "blueType", None),
        "url": getattr(user, "url", "") or "",
        "profile_image_url": getattr(user, "profileImageUrl", "") or "",
    }


async def search_tweets(query: str, n: int = 100, product: str = "Top") -> list[dict]:
    api = API()
    tweets = []
    async for tweet in api.search(query, limit=n, kv={"product": product}):
        tweets.append(_tweet_to_dict(tweet))
    return tweets


async def user_tweets(username: str, n: int = 100) -> list[dict]:
    api = API()
    user = await api.user_by_login(username)
    tweets = []
    async for tweet in api.user_tweets(user.id, limit=n):
        tweets.append(_tweet_to_dict(tweet))
    return tweets


async def get_user(username: str) -> dict:
    api = API()
    user = await api.user_by_login(username)
    return _user_to_dict(user)


async def search_hashtag(hashtag: str, n: int = 100) -> list[dict]:
    hashtag = hashtag.lstrip("#")
    return await search_tweets(f"#{hashtag}", n=n)


async def search_mentions(username: str, n: int = 100) -> list[dict]:
    username = username.lstrip("@")
    return await search_tweets(f"@{username}", n=n)


async def tweet_replies(tweet_id: int | str, n: int = 100) -> list[dict]:
    api = API()
    replies = []
    async for tweet in api.tweet_replies(int(tweet_id), limit=n):
        replies.append(_tweet_to_dict(tweet))
    return replies


async def get_retweeters(tweet_id: int | str, n: int = 100) -> list[dict]:
    api = API()
    retweeters = []
    async for user in api.retweeters(int(tweet_id), limit=n):
        retweeters.append(_user_to_dict(user))
    return retweeters


async def tweet_details(tweet_id: int | str) -> dict | None:
    api = API()
    tweet = await api.tweet_details(int(tweet_id))
    if tweet is None:
        return None
    return _tweet_to_dict(tweet)


async def get_followers(username: str, n: int = 100) -> list[dict]:
    api = API()
    user = await api.user_by_login(username)
    followers = []
    async for follower in api.followers(user.id, limit=n):
        followers.append(_user_to_dict(follower))
    return followers


async def get_following(username: str, n: int = 100) -> list[dict]:
    api = API()
    user = await api.user_by_login(username)
    following = []
    async for followee in api.following(user.id, limit=n):
        following.append(_user_to_dict(followee))
    return following


async def get_retweeters_batch(
    tweet_ids: list[int | str], n: int = 100, flatten: bool = True
) -> list[dict] | dict[str, list[dict]]:
    tweet_ids = list(dict.fromkeys(str(tid) for tid in tweet_ids if str(tid).strip()))

    retweeters_by_tweet: dict[str, list[dict]] = {}
    for tweet_id in tweet_ids:
        users = await get_retweeters(tweet_id, n=n)
        for u in users:
            u["source_tweet_id"] = tweet_id
        retweeters_by_tweet[tweet_id] = users

    if flatten:
        return [u for users in retweeters_by_tweet.values() for u in users]
    return retweeters_by_tweet


async def user_tweets_and_replies(username: str, n: int = 100) -> list[dict]:
    api = API()
    user = await api.user_by_login(username)
    tweets = []
    async for tweet in api.user_tweets_and_replies(user.id, limit=n):
        tweets.append(_tweet_to_dict(tweet))
    return tweets


async def user_media(username: str, n: int = 100) -> list[dict]:
    api = API()
    user = await api.user_by_login(username)
    tweets = []
    async for tweet in api.user_media(user.id, limit=n):
        tweets.append(_tweet_to_dict(tweet))
    return tweets


async def verified_followers(username: str, n: int = 100) -> list[dict]:
    api = API()
    user = await api.user_by_login(username)
    followers = []
    async for follower in api.verified_followers(user.id, limit=n):
        followers.append(_user_to_dict(follower))
    return followers
