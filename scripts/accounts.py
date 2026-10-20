import sqlite3

from twscrape import API

from config import ACCOUNTS_DB as DEFAULT_DB_FILE


async def add_account(username: str, password: str, email: str, email_password: str,
                       cookies: str, db_file: str = DEFAULT_DB_FILE) -> dict:
    if not cookies:
        raise ValueError("cookies es obligatorio. Formato: 'auth_token=...; ct0=...'")

    conn = sqlite3.connect(db_file)
    conn.close()
    api = API(db_file)

    try:
        # pool.add_account solo avisa si la cuenta ya existe y no toca nada:
        # en ese caso se actualizan las cookies y se limpian sus bloqueos.
        existing = await api.pool.get_account(username)
        if existing:
            await api.pool.add_account_cookies(username, cookies)
            acc = await api.pool.get_account(username)
            acc.locks = {}
            await api.pool.save(acc)
        else:
            await api.pool.add_account(username, password, email, email_password, cookies=cookies)
    except Exception as e:
        return {"success": False, "message": str(e)}

    target = await api.pool.get_account(username)
    active = bool(target.active) if target else False

    return {"success": True, "active": active, "updated": existing is not None}


async def list_accounts(db_file: str = DEFAULT_DB_FILE) -> list[dict]:
    api = API(db_file)
    accounts = await api.pool.get_all()
    return [
        {"username": acc.username, "email": acc.email, "active": acc.active, "locks": acc.locks}
        for acc in accounts
    ]


async def delete_account(username: str, db_file: str = DEFAULT_DB_FILE) -> dict:
    api = API(db_file)
    try:
        await api.pool.delete_accounts(username)
    except Exception as e:
        return {"success": False, "message": str(e)}
    return {"success": True}
