from flask import Blueprint, request, jsonify
from db import get_db
from db_auth import require_auth
import psycopg2.extras

counters_bp = Blueprint("counters", __name__)

@counters_bp.get("/")
def get_counters():
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT COUNT(*) AS total FROM questions")
    total_questions = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(DISTINCT evaluation) AS c FROM question_sets")
    active_evaluators = cur.fetchone()["c"]

    cur.execute(
        "SELECT name, value FROM counters WHERE name IN ('pending_submissions','open_reports')"
    )
    rows = {r["name"]: r["value"] for r in cur.fetchall()}

    return jsonify({
        "total_questions":     total_questions,
        "active_evaluators":   active_evaluators,
        "pending_submissions": rows.get("pending_submissions", 0),
        "open_reports":        rows.get("open_reports", 0),
    })