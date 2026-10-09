import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as appmod  # noqa: E402
from recommender import match_score, normalize_skills, recommend  # noqa: E402


class RecommenderTests(unittest.TestCase):
    def test_case_study_example_is_60_percent(self):
        score, matched, missing = match_score(
            ["Python", "SQL", "Machine Learning"],
            ["Python", "SQL", "Machine Learning", "Pandas", "Statistics"])
        self.assertEqual(score, 60)
        self.assertEqual(missing, ["Pandas", "Statistics"])

    def test_case_insensitive_and_normalize(self):
        self.assertEqual(normalize_skills(" python,SQL ,, python "), ["python", "SQL"])
        self.assertEqual(match_score(["python"], ["Python"])[0], 100)

    def test_ranking_prefers_domain_on_tie(self):
        its = [
            {"id": 1, "title": "A", "domain": "Web", "location": "Pune", "duration": 3, "skills": ["x"]},
            {"id": 2, "title": "B", "domain": "Data", "location": "Pune", "duration": 3, "skills": ["x"]},
        ]
        recs = recommend(["x"], its, preferred_domain="Data")
        self.assertEqual(recs[0]["id"], 2)


class AppTests(unittest.TestCase):
    def setUp(self):
        appmod.app.config["TESTING"] = True
        self.c = appmod.app.test_client()

    def token(self, path="/login"):
        html = self.c.get(path).get_data(as_text=True)
        return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)

    def post(self, path, data, form_page="/login"):
        data["_csrf"] = self.token(form_page)
        return self.c.post(path, data=data, follow_redirects=True)

    def test_full_student_flow(self):
        r = self.post("/register", {"name": "Rahul", "email": "rahul@test.com",
                                    "password": "secret1", "education": "B.Tech"}, "/register")
        self.assertIn("Account created", r.get_data(as_text=True))
        r = self.post("/profile", {"name": "Rahul", "skills": "python, sql, machine learning",
                                   "preferred_domain": "Data Science"}, "/profile")
        html = r.get_data(as_text=True)
        self.assertIn("Data Science Intern", html)
        self.assertIn("60%", html)
        self.assertIn("Statistics", self.c.get("/skill-gap").get_data(as_text=True))
        self.assertIn("Full Stack", self.c.get("/internships?q=flask").get_data(as_text=True))
        self.assertEqual(self.c.get("/admin").status_code, 403)

    def test_duplicate_and_bad_login(self):
        self.post("/register", {"name": "A", "email": "dup@test.com", "password": "secret1"}, "/register")
        self.c.post("/logout", data={"_csrf": self.token("/dashboard")})
        r = self.post("/register", {"name": "B", "email": "dup@test.com", "password": "secret1"}, "/register")
        self.assertIn("already exists", r.get_data(as_text=True))
        r = self.post("/login", {"email": "dup@test.com", "password": "wrong"})
        self.assertIn("Invalid email or password", r.get_data(as_text=True))

    def test_csrf_enforced(self):
        self.assertEqual(self.c.post("/login", data={"email": "a", "password": "b"}).status_code, 400)

    def test_admin_crud(self):
        r = self.post("/login", {"email": "admin@example.com", "password": "admin123"})
        self.assertIn("Admin panel", r.get_data(as_text=True))
        r = self.post("/admin/internship/new", {
            "title": "QA Intern", "company": "TestCo", "domain": "Testing", "location": "Remote",
            "duration": "2", "stipend": "5000", "skills": "Selenium, Python", "description": ""},
            "/admin/internship/new")
        self.assertIn("QA Intern", r.get_data(as_text=True))
        r = self.post("/admin/internship/new", {"title": "", "company": "x", "domain": "x",
                                                "location": "x", "duration": "2", "skills": "a"},
                      "/admin/internship/new")
        self.assertIn("required", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
