import sqlite3

from twscrape import API

DEFAULT_DB_FILE = "accounts.db"


async def add_account(username: str, password: str, email: str, email_password: str,
                       cookies: str, db_file: str = DEFAULT_DB_FILE) -> dict:
    if not cookies:
        raise ValueError("cookies es obligatorio. Formato: 'auth_token=...; ct0=...'")

    conn = sqlite3.connect(db_file)
    conn.close()
    api = API(db_file)

    try:
        await api.pool.add_account(username, password, email, email_password, cookies=cookies)
    except Exception as e:
        return {"success": False, "message": str(e)}

    accounts = await api.pool.get_all()
    target = next((acc for acc in accounts if acc.username == username), None)
    active = bool(target.active) if target else False

    return {"success": True, "active": active}


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
