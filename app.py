"""Flask app: operator screen, admin panel and JSON routes (guide section 2.4)."""
import functools
import re

import click
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db
import logic
import mock

UID_RE = re.compile(r"^(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RESULTS = {"ASSIGNED", "MATCH", "MISMATCH"}

PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">'
    '<rect width="640" height="480" fill="#000"/>'
    '<text x="320" y="240" fill="#9aa7b4" font-family="sans-serif" font-size="28" '
    'text-anchor="middle">Camera preview (mock)</text></svg>'
)


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    db.init_db()
    dummy_hash = generate_password_hash("not-a-real-password")

    @app.after_request
    def add_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def admin_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("admin"):
                if request.path.startswith("/api/"):
                    return jsonify(error="Sign in required."), 401
                return redirect(url_for("admin_login"))
            return view(*args, **kwargs)
        return wrapped

    # ---- operator routes (no login: the kiosk is the gateman's device) ----

    @app.get("/")
    def operator():
        return render_template("operator.html")

    @app.get("/video_feed")
    def video_feed():
        if not config.USE_MOCK:
            # Step 7: stream camera.stream_frames() as multipart/x-mixed-replace.
            return jsonify(error="Camera is not connected yet."), 501
        return Response(PLACEHOLDER_SVG, mimetype="image/svg+xml")

    @app.post("/capture")
    def capture():
        data = json_body()
        if data is None or data.get("mode") not in ("entry", "exit"):
            return jsonify(error="mode must be 'entry' or 'exit'."), 400
        mode = data["mode"]
        if not config.USE_MOCK:
            # Step 7: camera.capture_still() -> anpr.read_plate(), then
            # nfc.read_uid(config.CARD_TIMEOUT_SECONDS). Wait for the card in a
            # background thread so Flask is never blocked.
            return jsonify(error="Hardware is not connected yet."), 501

        plate, uid = mock.fake_reading(mode)
        if "plate" in data:  # Lets you test a scenario: {"mode":"exit","plate":"","uid":"A1B2C3D4"}
            plate = data["plate"]
        if "uid" in data:
            uid = data["uid"]
        if not isinstance(plate, str) or len(plate) > 12 or not isinstance(uid, str):
            return jsonify(error="plate must be text up to 12 characters; uid must be text."), 400
        uid = uid.strip().upper()
        if uid and not UID_RE.match(uid):
            return jsonify(error="uid must be 8, 14 or 20 hex characters."), 400

        handler = logic.handle_entry if mode == "entry" else logic.handle_exit
        return jsonify(handler(plate, uid))

    @app.post("/override")
    def override():
        data = json_body() or {}
        tx_id, note = data.get("transaction_id"), data.get("note")
        if (not isinstance(tx_id, int) or isinstance(tx_id, bool)
                or not isinstance(note, str) or len(note) > 200):
            return jsonify(error="transaction_id and a note (max 200 characters) are required."), 400
        try:
            return jsonify(logic.override(tx_id, note))
        except ValueError as err:
            return jsonify(error=str(err)), 400

    # ---- admin pages ----

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            row = db.get_admin(username)
            # Always check a hash so a wrong username takes as long as a wrong password.
            password_ok = check_password_hash(row["password_hash"] if row else dummy_hash, password)
            if row and password_ok:
                session.clear()
                session["admin"] = username
                return redirect(url_for("admin_page"))
            error = "Wrong username or password."
        return render_template("login.html", error=error), (401 if error else 200)

    @app.post("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    @app.get("/admin")
    @admin_required
    def admin_page():
        return render_template("admin.html", username=session["admin"])

    # ---- admin JSON API ----

    @app.get("/api/tags")
    @admin_required
    def api_tags_list():
        return jsonify(db.list_tags())

    @app.post("/api/tags")
    @admin_required
    def api_tags_add():
        data = json_body() or {}
        uid = str(data.get("uid", "")).strip().upper()
        if not UID_RE.match(uid):
            return jsonify(error="uid must be 8, 14 or 20 hex characters."), 400
        if not logic.register_tag(uid):
            return jsonify(error="That card is already registered."), 409
        return jsonify(db.get_tag(uid)), 201

    @app.patch("/api/tags/<uid>")
    @admin_required
    def api_tags_update(uid):
        uid = uid.upper()
        if not UID_RE.match(uid):
            return jsonify(error="Invalid card UID."), 400
        data = json_body() or {}
        try:
            return jsonify(logic.admin_set_status(uid, data.get("status")))
        except ValueError as err:
            return jsonify(error=str(err)), 400
        except LookupError:
            return jsonify(error="Card not found."), 404

    @app.get("/api/transactions")
    @admin_required
    def api_transactions():
        date_from, date_to = request.args.get("from", ""), request.args.get("to", "")
        if any(d and not DATE_RE.match(d) for d in (date_from, date_to)):
            return jsonify(error="Dates must look like 2026-11-11."), 400
        result = request.args.get("result", "").upper()
        if result and result not in RESULTS:
            return jsonify(error="result must be ASSIGNED, MATCH or MISMATCH."), 400
        rows = db.list_transactions(
            date_from or None, date_to or None,
            request.args.get("plate", "")[:20] or None,
            request.args.get("uid", "")[:20] or None,
            result or None,
        )
        return jsonify(rows)

    # ---- command line helpers ----

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.password_option()
    def create_admin(username, password):
        """Create an admin (or reset a password). There is no default login."""
        if len(password) < 8:
            raise click.UsageError("Use a password of at least 8 characters.")
        db.add_admin(username, generate_password_hash(password))
        click.echo(f"Admin '{username}' saved.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Register a few fake cards so the mock flow works."""
        for uid in mock.DEMO_UIDS:
            logic.register_tag(uid)
        click.echo(f"Registered {len(mock.DEMO_UIDS)} demo cards.")

    return app


if __name__ == "__main__":
    create_app().run(host=config.HOST, port=config.PORT)
