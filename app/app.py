"""ShadowFind - campus lost and found, matched by shadow silhouette."""

from __future__ import annotations

import io
import os
import secrets
from pathlib import Path

import cv2
import numpy as np
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.utils import secure_filename

import db
import vision

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("SHADOWFIND_DATA", BASE.parent / "instance"))
UPLOADS = DATA / "uploads"
PHOTOS = UPLOADS
DATA.mkdir(parents=True, exist_ok=True)
UPLOADS.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA / "shadowfind.sqlite3"

CATEGORIES = ["Bag", "Bottle", "Watch", "Umbrella", "Helmet", "Electronics",
              "Books", "Keys", "ID card", "Other"]
DEPARTMENTS = ["CSE", "ECE", "EEE", "MECH", "CIVIL", "IT", "AI&DS", "Other"]
MAX_BYTES = 6 * 1024 * 1024

app = Flask(__name__)
app.secret_key = os.environ.get("SHADOWFIND_SECRET", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


# ---------------------------------------------------------------------------
# per-request database handle
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        # self-healing: a fresh clone or a wiped instance/ must not 500
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        PHOTOS.mkdir(parents=True, exist_ok=True)
        if not DB_PATH.exists():
            db.init_db(DB_PATH)
        g.db = db.connect(DB_PATH)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.context_processor
def inject_globals():
    return {"current_student": current_student(), "MAX_BYTES": MAX_BYTES}


def current_student():
    sid = session.get("student_id")
    if not sid:
        return None
    return db.get_student(get_db(), sid)


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------
def save_image(file_storage) -> tuple[str, str, np.ndarray]:
    """Store the upload, return (photo_name, overlay_name, BGR array)."""
    raw = file_storage.read()
    if not raw:
        raise ValueError("The uploaded file is empty.")

    arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("That file is not a readable image.")

    token = secrets.token_hex(8)
    photo_name = f"{token}.jpg"
    cv2.imwrite(str(PHOTOS / photo_name), img, [cv2.IMWRITE_JPEG_QUALITY, 88])

    # the silhouette overlay is generated once and stored, so the detail page
    # does not have to re-run the pipeline on every view
    sil = vision.extract_shadow(img)
    tinted = img.copy()
    tinted[sil.mask > 0] = (0.45 * tinted[sil.mask > 0] + 0.55 * np.array([40, 90, 170])).astype(np.uint8)
    overlay_name = f"{token}_shadow.jpg"
    cv2.imwrite(str(PHOTOS / overlay_name), tinted, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return photo_name, overlay_name, img


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    conn = get_db()
    recent = db.list_items(conn, limit=6)
    return render_template("index.html", recent=recent, stats=db.stats(conn))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        department = request.form.get("department") or ""

        errors = []
        if len(name) < 3:
            errors.append("Enter your full name.")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Enter a valid e-mail address.")
        if len(password) < 6:
            errors.append("The password must be at least 6 characters.")
        if department not in DEPARTMENTS:
            errors.append("Choose your department.")

        conn = get_db()
        if not errors and db.find_student_by_email(conn, email):
            errors.append("That e-mail address is already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", departments=DEPARTMENTS,
                                   form=request.form)

        sid = db.create_student(conn, name, email, password, department)
        session.clear()
        session["student_id"] = sid
        flash("Account created. Welcome to ShadowFind.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html", departments=DEPARTMENTS, form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email") or ""
        password = request.form.get("password") or ""
        student = db.verify_student(get_db(), email, password)
        if student:
            session.clear()
            session["student_id"] = int(student["id"])
            flash(f"Signed in as {student['name']}.", "success")
            nxt = request.args.get("next")
            return redirect(nxt if nxt and nxt.startswith("/") else url_for("dashboard"))
        flash("Wrong e-mail address or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out safely.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    student = current_student()
    mine = conn.execute(
        "SELECT * FROM items WHERE student_id = ? ORDER BY created_at DESC, id DESC",
        (student["id"],),
    ).fetchall()
    return render_template("dashboard.html", mine=mine, stats=db.stats(conn),
                           incoming=db.incoming_claims(conn, student["id"]))


@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
    if request.method == "POST":
        type_ = request.form.get("type") or ""
        title = (request.form.get("title") or "").strip()
        category = request.form.get("category") or ""
        description = (request.form.get("description") or "").strip()
        place = (request.form.get("place") or "").strip()
        seen_on = request.form.get("seen_on") or ""
        upload = request.files.get("photo")

        errors = []
        if type_ not in ("lost", "found"):
            errors.append("Choose whether you lost or found the item.")
        if len(title) < 3:
            errors.append("Give the item a short title.")
        if category not in CATEGORIES:
            errors.append("Choose a category.")
        if not upload or not upload.filename:
            errors.append("Attach a photograph of the item.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("report.html", categories=CATEGORIES,
                                   form=request.form), 400

        try:
            photo, overlay, img = save_image(upload)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("report.html", categories=CATEGORIES,
                                   form=request.form), 400

        sil = vision.extract_shadow(img)
        item_id = db.create_item(
            get_db(),
            student_id=current_student()["id"], title=title, type_=type_,
            category=category, description=description, place=place,
            seen_on=seen_on, photo=photo, overlay=overlay,
            descriptor=sil.descriptor, shadow_iou=sil.iou,
        )
        flash("Item reported. Shadow signature stored.", "success")
        return redirect(url_for("item_detail", item_id=item_id))

    return render_template("report.html", categories=CATEGORIES, form={})


@app.route("/browse")
def browse():
    conn = get_db()
    type_ = request.args.get("type") if request.args.get("type") in ("lost", "found") else None
    category = request.args.get("category") if request.args.get("category") in CATEGORIES else None
    exclude = session.get("student_id")
    items = db.list_items(conn, exclude_student=exclude, type_=type_, category=category)
    return render_template("browse.html", items=items, categories=CATEGORIES,
                           active_type=type_, active_category=category)


@app.route("/item/<int:item_id>")
def item_detail(item_id):
    conn = get_db()
    item = db.get_item(conn, item_id)
    if item is None:
        abort(404)

    ranked = []
    query = db.descriptor_of(item)
    if query is not None:
        cands = db.candidates_for(conn, item)
        pairs = [(c["id"], db.descriptor_of(c)) for c in cands if c["descriptor"]]
        scored = vision.rank(query, [(i, d) for i, d in pairs if d is not None])
        by_id = {c["id"]: c for c in cands}
        for cid, score in scored[:10]:
            ranked.append({"item": by_id[cid], "score": score})

    mine = session.get("student_id") == item["student_id"]
    return render_template("item.html", item=item, ranked=ranked, mine=mine)


@app.route("/claim/<int:lost_id>/<int:found_id>", methods=["POST"])
@login_required
def claim(lost_id, found_id):
    conn = get_db()
    lost = db.get_item(conn, lost_id)
    found = db.get_item(conn, found_id)
    if lost is None or found is None:
        abort(404)

    student = current_student()
    # the claim runs from the owner of the lost item to the finder
    sender, receiver = lost, found
    if student["id"] not in (sender["student_id"], receiver["student_id"]):
        abort(403)
    if sender["student_id"] == receiver["student_id"]:
        flash("You cannot claim your own report.", "warning")
        return redirect(url_for("item_detail", item_id=lost_id))

    q = db.descriptor_of(lost)
    c = db.descriptor_of(found)
    score = vision.similarity(q, c) if q is not None and c is not None else 0.0
    match_id = db.save_match(conn, lost_id, found_id, score)
    _claim_id, created = db.create_claim(conn, match_id, sender["student_id"], receiver["student_id"])
    flash("Claim sent to the finder." if created else "You already have an open claim on this item.",
          "success" if created else "info")
    return redirect(url_for("dashboard"))


@app.route("/claims")
@login_required
def claims():
    conn = get_db()
    student = current_student()
    return render_template("claims.html",
                           incoming=db.incoming_claims(conn, student["id"]),
                           sent=db.sent_claims(conn, student["id"]))


@app.route("/claims/<int:claim_id>/<action>", methods=["POST"])
@login_required
def claim_action(claim_id, action):
    if action not in ("accept", "reject", "return"):
        abort(404)
    conn = get_db()
    row = db.get_claim(conn, claim_id)
    if row is None:
        abort(404)

    student = current_student()["id"]
    if action in ("accept", "reject") and row["receiver_id"] != student:
        abort(403)
    if action == "return" and row["sender_id"] != student:
        abort(403)
    if action in ("accept", "reject") and row["status"] != "pending":
        flash("That claim has already been answered.", "info")
        return redirect(url_for("claims"))
    if action == "return" and row["status"] != "accepted":
        flash("Only an accepted claim can be marked as returned.", "warning")
        return redirect(url_for("claims"))

    db.set_claim_status(conn, claim_id, {"accept": "accepted", "reject": "rejected",
                                        "return": "returned"}[action])
    flash({"accept": "Claim accepted.", "reject": "Claim rejected.",
           "return": "Handover confirmed. The item is marked returned."}[action], "success")
    return redirect(url_for("claims"))


@app.route("/media/<path:name>")
def media(name):
    from flask import send_from_directory

    name = secure_filename(name)
    target = PHOTOS / name
    if not target.exists():
        abort(404)
    return send_from_directory(PHOTOS, name, max_age=3600)


@app.errorhandler(413)
def too_large(_e):
    flash("That image is larger than 6 MB.", "danger")
    return redirect(url_for("report")), 303


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    db.init_db(DB_PATH)
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
