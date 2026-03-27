from flask import Blueprint, request, jsonify
from db import get_db
from db_auth import require_auth
import psycopg2.extras

activity_bp = Blueprint("activity", __name__)

@activity_bp.get("/")
@require_auth
def get_activity():
    limit = min(int(request.args.get("limit", 50)), 200)
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """SELECT al.*, a.name AS admin_name
           FROM activity_log al
           JOIN admins a ON al.admin_id = a.id
           ORDER BY al.created_at DESC
           LIMIT %s""",
        (limit,)
    )

    logs = cur.fetchall()

    for l in logs:
        l["created_at"] = str(l["created_at"])

    return jsonify(logs)