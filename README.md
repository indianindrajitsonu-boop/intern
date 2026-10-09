# Student Skill & Internship Recommendation System

A Flask web application that recommends internships to students by matching their skills against internship requirements, and shows which skills to improve.

**Match Score = (Matched Skills ÷ Required Skills) × 100**

## Features
- Student registration, login, logout (hashed passwords, CSRF protection)
- Profile: education, experience, projects, certifications, interests, skills, preferred domain / location / duration
- Skill-matching recommendation engine with matched / missing skill chips
- Search & filter internships (keyword, domain, location, duration)
- Skill-gap analysis with course suggestions
- Admin panel: add / edit / delete internships, see top student skills and domain interest
- Recommendation table persisted per student

## Run
```bash
pip install -r requirements.txt
python app.py          # http://127.0.0.1:5000
```
The SQLite database (`internship.db`) is created and seeded with 12 sample internships on first run.

**Admin login:** `admin@example.com` / `admin123` (override with `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and set `SECRET_KEY` for any real deployment).

## Project structure
```
app.py            routes, auth, DB helpers
recommender.py    matching, scoring, skill-gap logic
schema.sql        database schema (students, skills, student_skills,
                  internships, internship_skills, recommendations)
seed_data.py      sample internships, domains, course suggestions
templates/        Jinja2 pages (student + admin)
static/style.css  styling
tests/            automated tests (python -m unittest)
```

## Using MySQL (as in the case study)
The schema is standard SQL; to move to MySQL swap `sqlite3` for `mysql-connector-python` / SQLAlchemy in `app.py`, change `AUTOINCREMENT` to `AUTO_INCREMENT`, and `?` placeholders to `%s`.

## Future scope
ML-based recommendations, resume parsing, job recommendations, chatbot career assistant, college placement portal integration, live internship feeds.
