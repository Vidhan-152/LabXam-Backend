from db import get_db

def log_action(admin_id: int, action: str) -> None:
    try:
        db  = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO activity_log (admin_id, action) VALUES (%s, %s)",
            (admin_id, action)
        )
        db.commit()
    except Exception as exc:
        print(f"[activity_helper] logging failed: {exc}")