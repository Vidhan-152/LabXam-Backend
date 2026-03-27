from flask import Blueprint, request, jsonify
from db import get_db
from db_auth import require_auth
from activity_helper import log_action
import psycopg2.extras

questions_bp = Blueprint("questions", __name__)


# ------------------------------------------------------------------
# GET /api/questions/
# Public – returns all question sets with their questions
# Supports optional filters: ?semester=4&subject=osl&evaluation=Midsem
# ------------------------------------------------------------------
@questions_bp.get("/")
def get_sets():
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    filters = []
    params  = []

    if request.args.get("semester"):
        filters.append("semester = %s")
        params.append(request.args["semester"])
    if request.args.get("subject"):
        filters.append("subject = %s")
        params.append(request.args["subject"])
    if request.args.get("evaluation"):
        filters.append("evaluation = %s")
        params.append(request.args["evaluation"])
    if request.args.get("section"):
        filters.append("section = %s")
        params.append(request.args["section"])
    if request.args.get("year"):
        filters.append("year = %s")
        params.append(request.args["year"])

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    cur.execute(
        f"SELECT * FROM question_sets {where} ORDER BY created_at DESC",
        params
    )
    sets = cur.fetchall()

    for s in sets:
        cur.execute(
            "SELECT id, question_text, order_index FROM questions "
            "WHERE set_id=%s ORDER BY order_index",
            (s["id"],)
        )
        s["questions"] = cur.fetchall()
        s["created_at"] = str(s["created_at"])

    return jsonify(sets)


# ------------------------------------------------------------------
# GET /api/questions/<set_id>
# Public – returns a single question set with its questions
# ------------------------------------------------------------------
@questions_bp.get("/<int:set_id>")
def get_set(set_id):
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM question_sets WHERE id=%s", (set_id,))
    qset = cur.fetchone()

    if not qset:
        return jsonify({"error": "Not found"}), 404

    cur.execute(
        "SELECT id, question_text, order_index FROM questions "
        "WHERE set_id=%s ORDER BY order_index",
        (set_id,)
    )
    qset["questions"] = cur.fetchall()
    qset["created_at"] = str(qset["created_at"])
    return jsonify(qset)


# ------------------------------------------------------------------
# GET /api/questions/meta/filters
# Public – returns distinct semesters / subjects / evaluations / sections
# so the frontend can populate dropdowns dynamically
# ------------------------------------------------------------------
@questions_bp.get("/meta/filters")
def get_filters():
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def distinct(col):
        cur.execute(f"SELECT DISTINCT {col} FROM question_sets ORDER BY {col}")
        return [r[col] for r in cur.fetchall()]

    return jsonify({
        "semesters":   distinct("semester"),
        "subjects":    distinct("subject"),
        "evaluations": distinct("evaluation"),
        "sections":    distinct("section"),
        "years":       distinct("year"),
    })


# ------------------------------------------------------------------
# POST /api/questions/
# Protected – create a new question set with questions
# Body: { semester, subject, evaluation, section, year, questions: [...] }
# ------------------------------------------------------------------
@questions_bp.post("/")
@require_auth
def create_set():
    body = request.get_json()

    required = ["semester", "subject", "evaluation", "section", "year", "questions"]
    missing  = [f for f in required if f not in body]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    if not isinstance(body["questions"], list) or len(body["questions"]) == 0:
        return jsonify({"error": "questions must be a non-empty list"}), 400

    db  = get_db()
    cur = db.cursor()

    cur.execute(
        """INSERT INTO question_sets (semester, subject, evaluation, section, year)
        VALUES (%s,%s,%s,%s,%s)
        RETURNING id""",
        (body["semester"], body["subject"], body["evaluation"],
        body["section"], body["year"])
    )

    set_id = cur.fetchone()[0]

    for idx, q_text in enumerate(body["questions"]):
        cur.execute(
            "INSERT INTO questions (set_id, question_text, order_index) VALUES (%s,%s,%s)",
            (set_id, q_text, idx)
        )

    db.commit()

    # update counter
    cur.execute(
        "UPDATE counters SET value = value + %s WHERE name='total_questions'",
        (len(body["questions"]),)
    )
    db.commit()

    log_action(
        int(request.admin["sub"]),
        f"added a question in Semester {body['semester']} — {body['subject']} "
        f"({body['evaluation']}, {body['section']})"
    )

    return jsonify({"id": set_id, "message": "Created"}), 201


# ------------------------------------------------------------------
# PUT /api/questions/<set_id>
# Protected – replace questions in an existing set (full update)
# Body: { questions: [...] }   (set metadata is immutable after creation)
# ------------------------------------------------------------------
@questions_bp.put("/<int:set_id>")
@require_auth
def update_set(set_id):
    body = request.get_json()

    if "questions" not in body or not isinstance(body["questions"], list):
        return jsonify({"error": "questions list required"}), 400

    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM question_sets WHERE id=%s", (set_id,))
    qset = cur.fetchone()
    if not qset:
        return jsonify({"error": "Not found"}), 404

    cur = db.cursor()
    # count old questions for counter delta
    cur.execute("SELECT COUNT(*) AS c FROM questions WHERE set_id=%s", (set_id,))
    old_count = cur.fetchone()[0]

    cur.execute("DELETE FROM questions WHERE set_id=%s", (set_id,))
    for idx, q_text in enumerate(body["questions"]):
        cur.execute(
            "INSERT INTO questions (set_id, question_text, order_index) VALUES (%s,%s,%s)",
            (set_id, q_text, idx)
        )
    db.commit()

    delta = len(body["questions"]) - old_count
    if delta != 0:
        cur.execute(
            "UPDATE counters SET value = GREATEST(0, value + %s) WHERE name='total_questions'",
            (delta,)
        )
        db.commit()

    log_action(
        int(request.admin["sub"]),
        f"updated questions in set #{set_id} — {qset['subject']} (Sem {qset['semester']})"
    )

    return jsonify({"message": "Updated", "id": set_id})


# ------------------------------------------------------------------
# DELETE /api/questions/<set_id>
# Protected – delete a question set (cascades to questions)
# ------------------------------------------------------------------
@questions_bp.delete("/<int:set_id>")
@require_auth
def delete_set(set_id):
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM question_sets WHERE id=%s", (set_id,))
    qset = cur.fetchone()
    if not qset:
        return jsonify({"error": "Not found"}), 404

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM questions WHERE set_id=%s", (set_id,))
    q_count = cur.fetchone()[0]

    cur.execute("DELETE FROM question_sets WHERE id=%s", (set_id,))
    db.commit()

    cur.execute(
        "UPDATE counters SET value = GREATEST(0, value - %s) WHERE name='total_questions'",
        (q_count,)
    )
    db.commit()

    log_action(
        int(request.admin["sub"]),
        f"deleted a question from Semester {qset['semester']}_{qset['subject']}"
        f"_{qset['year']}_{qset['evaluation']}_{qset['section']}"
    )

    return jsonify({"message": "Deleted"})