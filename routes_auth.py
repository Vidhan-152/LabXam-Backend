import bcrypt
from flask import Blueprint, request, jsonify
from db import get_db
from db_auth import create_token, require_auth
import psycopg2.extras

auth_bp = Blueprint("auth", __name__)

@auth_bp.post("/login")
def login():
    body  = request.get_json()
    email = body.get("email", "").strip()
    pwd   = body.get("password", "").encode()

    if not email or not pwd:
        return jsonify({"error": "Email and password required"}), 400

    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM admins WHERE email = %s", (email,))
    admin = cur.fetchone()

    if not admin or not bcrypt.checkpw(pwd, admin["password_hash"].encode()):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(admin["id"], admin["role"])
    return jsonify({
        "token": token,
        "role":  admin["role"],
        "name":  admin["name"],
        "id":    admin["id"],
    })

@auth_bp.get("/me")
@require_auth
def me():
    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, name, email, role, created_at FROM admins WHERE id=%s",
        (int(request.admin["sub"]),)
    )
    admin = cur.fetchone()
    if not admin:
        return jsonify({"error": "Admin not found"}), 404
    admin["created_at"] = str(admin["created_at"])
    return jsonify(admin)

@auth_bp.post("/change-password")
@require_auth
def change_password():
    body = request.get_json()
    if not body.get("current_password") or not body.get("new_password"):
        return jsonify({"error": "current_password and new_password required"}), 400

    db  = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM admins WHERE id=%s", (int(request.admin["sub"]),))
    admin = cur.fetchone()

    if not bcrypt.checkpw(body["current_password"].encode(), admin["password_hash"].encode()):
        return jsonify({"error": "Current password is incorrect"}), 401

    new_hash = bcrypt.hashpw(body["new_password"].encode(), bcrypt.gensalt()).decode()
    cur = db.cursor()
    cur.execute("UPDATE admins SET password_hash=%s WHERE id=%s",
                (new_hash, int(request.admin["sub"])))
    db.commit()

    return jsonify({"message": "Password changed"})