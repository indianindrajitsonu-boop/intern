PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    student_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    education       TEXT DEFAULT '',
    experience      TEXT DEFAULT 'Fresher',
    projects        TEXT DEFAULT '',
    certifications  TEXT DEFAULT '',
    interests       TEXT DEFAULT '',
    preferred_domain TEXT DEFAULT '',
    preferred_location TEXT DEFAULT '',
    preferred_duration INTEGER,
    is_admin        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS student_skills (
    student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    skill_id   INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (student_id, skill_id)
);

CREATE TABLE IF NOT EXISTS internships (
    internship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    domain      TEXT NOT NULL,
    location    TEXT NOT NULL,
    duration    INTEGER NOT NULL,          -- months
    stipend     INTEGER DEFAULT 0,         -- INR per month
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS internship_skills (
    internship_id INTEGER NOT NULL REFERENCES internships(internship_id) ON DELETE CASCADE,
    skill_id      INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (internship_id, skill_id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    student_id    INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    internship_id INTEGER NOT NULL REFERENCES internships(internship_id) ON DELETE CASCADE,
    match_score   INTEGER NOT NULL,
    generated_at  TEXT NOT NULL,
    PRIMARY KEY (student_id, internship_id)
);
