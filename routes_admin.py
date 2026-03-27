import bcrypt
from flask import Blueprint, request, jsonify
from db import get_db
from db_auth import require_auth
from activity_helper import log_action
import psycopg2.extras

admins_bp = Blueprint("admins", __name__)


def _require_superadmin():
    if request.admin.get("role") != "superadmin":
        return jsonify({"error": "Superadmin access required"}), 403
    return None


# ------------------------------------------------------------------
# GET /api/admins/
# Protected – list all admins (any authenticated admin can view)
# ------------------------------------------------------------------
@admins_bp.get("/")
@require_auth
def list_admins():
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, name, email, role, created_at FROM admins ORDER BY created_at")
    admins = cur.fetchall()
    for a in admins:
        a["created_at"] = str(a["created_at"])
    return jsonify(admins)


# ------------------------------------------------------------------
# POST /api/admins/
# Protected (superadmin only) – create a new admin
# Body: { name, email, password, role? }
# ------------------------------------------------------------------
@admins_bp.post("/")
@require_auth
def create_admin():
    err = _require_superadmin()
    if err:
        return err

    body = request.get_json()
    required = ["name", "email", "password"]
    missing  = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    pw_hash = bcrypt.hashpw(body["password"].encode(), bcrypt.gensalt()).decode()

    db  = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO admins (name, email, password_hash, role) VALUES (%s,%s,%s,%s)",
            (body["name"], body["email"], pw_hash, body.get("role", "admin"))
        )
        db.commit()
    except Exception:
        return jsonify({"error": "Email already exists"}), 409

    log_action(request.admin["sub"], f"created admin account for {body['email']}")
    return jsonify({"id": cur.lastrowid, "message": "Admin created"}), 201


# ------------------------------------------------------------------
# PATCH /api/admins/<admin_id>/password
# Protected (superadmin only) – reset another admin's password
# Body: { new_password }
# ------------------------------------------------------------------
@admins_bp.patch("/<int:admin_id>/password")
@require_auth
def reset_password(admin_id):
    err = _require_superadmin()
    if err:
        return err

    body = request.get_json()
    if not body.get("new_password"):
        return jsonify({"error": "new_password required"}), 400

    pw_hash = bcrypt.hashpw(body["new_password"].encode(), bcrypt.gensalt()).decode()

    db  = get_db()
    cur = db.cursor()
    cur.execute("UPDATE admins SET password_hash=%s WHERE id=%s", (pw_hash, admin_id))
    if cur.rowcount == 0:
        return jsonify({"error": "Admin not found"}), 404
    db.commit()

    log_action(request.admin["sub"], f"reset password for admin id={admin_id}")
    return jsonify({"message": "Password updated"})


# ------------------------------------------------------------------
# DELETE /api/admins/<admin_id>
# Protected (superadmin only) – remove an admin account
# ------------------------------------------------------------------
@admins_bp.delete("/<int:admin_id>")
@require_auth
def delete_admin(admin_id):
    err = _require_superadmin()
    if err:
        return err

    # Prevent self-deletion
    if request.admin["sub"] == admin_id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    db  = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM admins WHERE id=%s", (admin_id,))
    if cur.rowcount == 0:
        return jsonify({"error": "Admin not found"}), 404
    db.commit()

    log_action(request.admin["sub"], f"deleted admin id={admin_id}")
    return jsonify({"message": "Admin deleted"})