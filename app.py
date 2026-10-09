"""Student Skill & Internship Recommendation System - Flask application."""
import os
import re
import secrets
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import seed_data
from recommender import normalize_skills, recommend, skill_gap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "internship.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_or_create_skill(db, name):
    row = db.execute("SELECT skill_id FROM skills WHERE skill_name = ?", (name,)).fetchone()
    if row:
        return row["skill_id"]
    display = name.title() if name.islower() else name
    return db.execute("INSERT INTO skills (skill_name) VALUES (?)", (display,)).lastrowid


def set_links(db, link_table, owner_col, owner_id, skill_names):
    """Replace the skills attached to a student or an internship."""
    db.execute(f"DELETE FROM {link_table} WHERE {owner_col} = ?", (owner_id,))
    for name in skill_names:
        sid = get_or_create_skill(db, name)
        db.execute(f"INSERT OR IGNORE INTO {link_table} ({owner_col}, skill_id) VALUES (?, ?)",
                   (owner_id, sid))


def student_skill_names(db, student_id):
    rows = db.execute(
        "SELECT s.skill_name FROM skills s JOIN student_skills ss ON ss.skill_id = s.skill_id "
        "WHERE ss.student_id = ? ORDER BY s.skill_name", (student_id,)).fetchall()
    return [r["skill_name"] for r in rows]


def load_internships(db, where="", params=()):
    rows = db.execute(f"SELECT * FROM internships {where} ORDER BY title", params).fetchall()
    skill_rows = db.execute(
        "SELECT i.internship_id, s.skill_name FROM internship_skills i "
        "JOIN skills s ON s.skill_id = i.skill_id ORDER BY s.skill_name").fetchall()
    by_id = {}
    for r in skill_rows:
        by_id.setdefault(r["internship_id"], []).append(r["skill_name"])
    out = []
    for r in rows:
        d = dict(r)
        d["id"] = d.pop("internship_id")
        d["skills"] = by_id.get(d["id"], [])
        out.append(d)
    return out


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    if db.execute("SELECT COUNT(*) FROM internships").fetchone()[0] == 0:
        for title, company, domain, loc, dur, stipend, desc, skills in seed_data.INTERNSHIPS:
            iid = db.execute(
                "INSERT INTO internships (title, company, domain, location, duration, stipend, description) "
                "VALUES (?,?,?,?,?,?,?)", (title, company, domain, loc, dur, stipend, desc)).lastrowid
            for name in skills:
                row = db.execute("SELECT skill_id FROM skills WHERE skill_name = ?", (name,)).fetchone()
                sid = row["skill_id"] if row else db.execute(
                    "INSERT INTO skills (skill_name) VALUES (?)", (name,)).lastrowid
                db.execute("INSERT OR IGNORE INTO internship_skills VALUES (?,?)", (iid, sid))
    if not db.execute("SELECT 1 FROM students WHERE is_admin = 1").fetchone():
        db.execute("INSERT INTO students (name, email, password_hash, is_admin, created_at) "
                   "VALUES (?,?,?,1,?)",
                   ("Administrator", ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), now()))
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Auth, CSRF
# --------------------------------------------------------------------------
@app.before_request
def load_user_and_check_csrf():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_db().execute("SELECT * FROM students WHERE student_id = ?", (uid,)).fetchone()
        if g.user is None:
            session.clear()
    if request.method == "POST":
        token = session.get("_csrf")
        if not token or token != request.form.get("_csrf"):
            abort(400, "Invalid or missing CSRF token")


@app.context_processor
def inject_globals():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return {"csrf_token": session["_csrf"], "current_user": g.get("user")}


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            flash("Please log in first.", "warn")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if not g.user["is_admin"]:
            abort(403)
        return view(*a, **kw)
    return wrapped


# --------------------------------------------------------------------------
# Public + auth routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    stats = {
        "internships": db.execute("SELECT COUNT(*) FROM internships").fetchone()[0],
        "students": db.execute("SELECT COUNT(*) FROM students WHERE is_admin = 0").fetchone()[0],
        "skills": db.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
    }
    return render_template("index.html", stats=stats)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        education = request.form.get("education", "").strip()
        error = None
        if not name:
            error = "Name is required."
        elif not EMAIL_RE.match(email):
            error = "Enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        db = get_db()
        if not error and db.execute("SELECT 1 FROM students WHERE email = ?", (email,)).fetchone():
            error = "An account with this email already exists."
        if error:
            flash(error, "error")
            return render_template("register.html", form=request.form)
        cur = db.execute(
            "INSERT INTO students (name, email, password_hash, education, created_at) VALUES (?,?,?,?,?)",
            (name, email, generate_password_hash(password), education, now()))
        db.commit()
        session.clear()
        session["uid"] = cur.lastrowid
        flash("Account created! Add your skills to get recommendations.", "ok")
        return redirect(url_for("profile"))
    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = user["student_id"]
            flash(f"Welcome back, {user['name']}!", "ok")
            return redirect(url_for("admin_panel" if user["is_admin"] else "dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "ok")
    return redirect(url_for("index"))


# --------------------------------------------------------------------------
# Student routes
# --------------------------------------------------------------------------
def compute_recommendations(db, student, **filters):
    skills = student_skill_names(db, student["student_id"])
    recs = recommend(
        skills, load_internships(db),
        preferred_domain=student["preferred_domain"],
        location=student["preferred_location"],
        duration=student["preferred_duration"],
        **filters)
    return skills, recs


def save_recommendations(db, student_id, recs):
    db.execute("DELETE FROM recommendations WHERE student_id = ?", (student_id,))
    db.executemany(
        "INSERT INTO recommendations VALUES (?,?,?,?)",
        [(student_id, r["id"], r["score"], now()) for r in recs if r["score"] > 0])
    db.commit()


@app.route("/dashboard")
@login_required
def dashboard():
    if g.user["is_admin"]:
        return redirect(url_for("admin_panel"))
    db = get_db()
    skills, recs = compute_recommendations(db, g.user)
    save_recommendations(db, g.user["student_id"], recs)
    fields = ["education", "preferred_domain", "preferred_location", "preferred_duration", "interests"]
    filled = sum(1 for f in fields if g.user[f]) + (1 if skills else 0)
    completion = round(filled / (len(fields) + 1) * 100)
    return render_template("dashboard.html", skills=skills, recs=recs[:3], completion=completion,
                           total_good=sum(1 for r in recs if r["score"] >= 60))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    if request.method == "POST":
        f = request.form
        duration = f.get("preferred_duration", "")
        db.execute(
            "UPDATE students SET name=?, education=?, experience=?, projects=?, certifications=?, "
            "interests=?, preferred_domain=?, preferred_location=?, preferred_duration=? "
            "WHERE student_id=?",
            (f.get("name", "").strip() or g.user["name"], f.get("education", "").strip(),
             f.get("experience", "Fresher"), f.get("projects", "").strip(),
             f.get("certifications", "").strip(), f.get("interests", "").strip(),
             f.get("preferred_domain", ""), f.get("preferred_location", ""),
             int(duration) if duration.isdigit() else None, g.user["student_id"]))
        set_links(db, "student_skills", "student_id", g.user["student_id"],
                  normalize_skills(f.get("skills", "")))
        db.commit()
        flash("Profile updated.", "ok")
        return redirect(url_for("recommendations"))
    return render_template("profile.html", skills=", ".join(student_skill_names(db, g.user["student_id"])),
                           domains=seed_data.DOMAINS, locations=seed_data.LOCATIONS,
                           durations=seed_data.DURATIONS,
                           all_skills=[r["skill_name"] for r in db.execute(
                               "SELECT skill_name FROM skills ORDER BY skill_name")])


@app.route("/internships")
@login_required
def internships():
    db = get_db()
    q = request.args.get("q", "").strip()
    domain = request.args.get("domain", "")
    location = request.args.get("location", "")
    duration = request.args.get("duration", "")
    items = load_internships(db)
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i["title"].lower() or ql in i["company"].lower()
                 or any(ql in s.lower() for s in i["skills"])]
    if domain:
        items = [i for i in items if i["domain"] == domain]
    if location:
        items = [i for i in items if i["location"] == location]
    if duration.isdigit():
        items = [i for i in items if i["duration"] == int(duration)]
    return render_template("internships.html", items=items, q=q, domain=domain, location=location,
                           duration=duration, domains=seed_data.DOMAINS,
                           locations=seed_data.LOCATIONS, durations=seed_data.DURATIONS)


@app.route("/recommendations")
@login_required
def recommendations():
    if g.user["is_admin"]:
        return redirect(url_for("admin_panel"))
    db = get_db()
    try:
        min_score = max(0, min(100, int(request.args.get("min_score", 0))))
    except ValueError:
        min_score = 0
    skills, recs = compute_recommendations(db, g.user, min_score=min_score)
    recs = [r for r in recs if r["score"] > 0]
    save_recommendations(db, g.user["student_id"], recs)
    return render_template("recommendations.html", skills=skills, recs=recs, min_score=min_score)


@app.route("/skill-gap")
@login_required
def skill_gap_view():
    db = get_db()
    skills = student_skill_names(db, g.user["student_id"])
    domain = request.args.get("domain") or g.user["preferred_domain"] or ""
    gaps, pool_size = skill_gap(skills, load_internships(db), domain)
    courses = {s: seed_data.COURSES.get(s.lower()) for s, _ in gaps}
    return render_template("skill_gap.html", skills=skills, gaps=gaps, pool_size=pool_size,
                           domain=domain, domains=seed_data.DOMAINS, courses=courses)


# --------------------------------------------------------------------------
# Admin routes
# --------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_panel():
    db = get_db()
    stats = {
        "students": db.execute("SELECT COUNT(*) FROM students WHERE is_admin = 0").fetchone()[0],
        "internships": db.execute("SELECT COUNT(*) FROM internships").fetchone()[0],
    }
    top_skills = db.execute(
        "SELECT s.skill_name, COUNT(*) c FROM student_skills ss JOIN skills s ON s.skill_id = ss.skill_id "
        "GROUP BY s.skill_id ORDER BY c DESC LIMIT 5").fetchall()
    domain_interest = db.execute(
        "SELECT preferred_domain d, COUNT(*) c FROM students WHERE preferred_domain != '' AND is_admin = 0 "
        "GROUP BY preferred_domain ORDER BY c DESC").fetchall()
    return render_template("admin.html", items=load_internships(db), stats=stats,
                           top_skills=top_skills, domain_interest=domain_interest)


def read_internship_form():
    f = request.form
    data = {
        "title": f.get("title", "").strip(), "company": f.get("company", "").strip(),
        "domain": f.get("domain", "").strip(), "location": f.get("location", "").strip(),
        "duration": f.get("duration", "").strip(), "stipend": f.get("stipend", "0").strip(),
        "description": f.get("description", "").strip(),
    }
    skills = normalize_skills(f.get("skills", ""))
    error = None
    if not (data["title"] and data["company"] and data["domain"] and data["location"]):
        error = "Title, company, domain and location are required."
    elif not data["duration"].isdigit() or int(data["duration"]) < 1:
        error = "Duration must be a number of months."
    elif not skills:
        error = "Add at least one required skill."
    return data, skills, error


@app.route("/admin/internship/new", methods=["GET", "POST"])
@app.route("/admin/internship/<int:iid>/edit", methods=["GET", "POST"])
@admin_required
def admin_internship_form(iid=None):
    db = get_db()
    item = None
    if iid:
        found = load_internships(db, "WHERE internship_id = ?", (iid,))
        if not found:
            abort(404)
        item = found[0]
    if request.method == "POST":
        data, skills, error = read_internship_form()
        if error:
            flash(error, "error")
            item = {**data, "skills": skills, "id": iid}
        else:
            vals = (data["title"], data["company"], data["domain"], data["location"],
                    int(data["duration"]), int(data["stipend"]) if data["stipend"].isdigit() else 0,
                    data["description"])
            if iid:
                db.execute("UPDATE internships SET title=?, company=?, domain=?, location=?, "
                           "duration=?, stipend=?, description=? WHERE internship_id=?", vals + (iid,))
            else:
                iid = db.execute("INSERT INTO internships (title, company, domain, location, duration, "
                                 "stipend, description) VALUES (?,?,?,?,?,?,?)", vals).lastrowid
            set_links(db, "internship_skills", "internship_id", iid, skills)
            db.commit()
            flash("Internship saved.", "ok")
            return redirect(url_for("admin_panel"))
    return render_template("admin_form.html", item=item, domains=seed_data.DOMAINS,
                           locations=seed_data.LOCATIONS)


@app.route("/admin/internship/<int:iid>/delete", methods=["POST"])
@admin_required
def admin_delete(iid):
    db = get_db()
    db.execute("DELETE FROM internships WHERE internship_id = ?", (iid,))
    db.commit()
    flash("Internship deleted.", "ok")
    return redirect(url_for("admin_panel"))


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
