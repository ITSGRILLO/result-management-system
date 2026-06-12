from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import sqlite3
import secrets
import hashlib

app = FastAPI(title="University Result Management System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "results.db"

# ── Auth config ──────────────────────────────────────────────
USERS = {
    "admin":   {"password": "admin123",   "role": "admin"},
    "teacher": {"password": "teacher123", "role": "teacher"},
}

# In-memory token store {token: {username, role}}
active_tokens: dict = {}

security = HTTPBearer()

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token not in active_tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in.")
    return active_tokens[token]["username"]

# ── Database ─────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            reg_number TEXT UNIQUE NOT NULL,
            class TEXT NOT NULL,
            course TEXT DEFAULT '',
            year_of_study TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            score REAL NOT NULL,
            exam_type TEXT DEFAULT 'Final Exam',
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id),
            UNIQUE(student_id, subject_id, exam_type)
        )
    """)
    default_subjects = [
        "Calculus", "Programming Fundamentals", "Database Systems",
        "Discrete Mathematics", "Computer Networks", "Software Engineering"
    ]
    for sub in default_subjects:
        c.execute("INSERT OR IGNORE INTO subjects (name) VALUES (?)", (sub,))
    conn.commit()
    conn.close()

init_db()

# ── Models ───────────────────────────────────────────────────

class LoginIn(BaseModel):
    username: str
    password: str

class StudentIn(BaseModel):
    name: str
    reg_number: str
    class_name: str
    course: str = ""
    year_of_study: str = ""

class GradeIn(BaseModel):
    student_id: int
    subject_id: int
    score: float
    exam_type: Optional[str] = "Final Exam"

class GradeEdit(BaseModel):
    score: float

class SubjectIn(BaseModel):
    name: str

# ── Auth endpoints ────────────────────────────────────────────

@app.post("/auth/login")
def login(data: LoginIn):
    user = USERS.get(data.username)
    if not user or user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_hex(32)
    active_tokens[token] = {"username": data.username, "role": user["role"]}
    return {"token": token, "username": data.username, "role": user["role"]}

@app.post("/auth/logout")
def logout(user: str = Depends(require_auth), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    active_tokens.pop(token, None)
    return {"message": "Logged out"}

@app.get("/auth/me")
def me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token not in active_tokens:
        raise HTTPException(status_code=401, detail="Not authenticated")
    info = active_tokens[token]
    return {"username": info["username"], "role": info["role"]}

# ── Students ─────────────────────────────────────────────────

@app.get("/students")
def get_students(user: str = Depends(require_auth)):
    conn = get_db()
    students = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
    conn.close()
    return [dict(s) for s in students]

@app.post("/students")
def add_student(data: StudentIn, user: str = Depends(require_auth)):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO students (name, reg_number, class, course, year_of_study) VALUES (?, ?, ?, ?, ?)",
            (data.name, data.reg_number, data.class_name, data.course, data.year_of_study)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Student ID already exists")
    finally:
        conn.close()
    return {"message": "Student added"}

@app.delete("/students/{student_id}")
def delete_student(student_id: int, user: str = Depends(require_auth)):
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    return {"message": "Student deleted"}

# ── Subjects ─────────────────────────────────────────────────

@app.get("/subjects")
def get_subjects(user: str = Depends(require_auth)):
    conn = get_db()
    subjects = conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    conn.close()
    return [dict(s) for s in subjects]

@app.post("/subjects")
def add_subject(data: SubjectIn, user: str = Depends(require_auth)):
    conn = get_db()
    try:
        conn.execute("INSERT INTO subjects (name) VALUES (?)", (data.name,))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Unit/module already exists")
    finally:
        conn.close()
    return {"message": "Subject added"}

# ── Grades ───────────────────────────────────────────────────

@app.get("/grades/{student_id}")
def get_grades(student_id: int, user: str = Depends(require_auth)):
    conn = get_db()
    grades = conn.execute("""
        SELECT g.id, g.score, g.exam_type, s.name as subject, s.id as subject_id
        FROM grades g
        JOIN subjects s ON g.subject_id = s.id
        WHERE g.student_id = ?
        ORDER BY s.name
    """, (student_id,)).fetchall()
    conn.close()
    return [dict(g) for g in grades]

@app.post("/grades")
def save_grade(data: GradeIn, user: str = Depends(require_auth)):
    if not (0 <= data.score <= 100):
        raise HTTPException(400, "Score must be between 0 and 100")
    conn = get_db()
    conn.execute("""
        INSERT INTO grades (student_id, subject_id, score, exam_type)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_id, subject_id, exam_type)
        DO UPDATE SET score = excluded.score
    """, (data.student_id, data.subject_id, data.score, data.exam_type))
    conn.commit()
    conn.close()
    return {"message": "Grade saved"}

@app.patch("/grades/edit/{grade_id}")
def edit_grade(grade_id: int, data: GradeEdit, user: str = Depends(require_auth)):
    if not (0 <= data.score <= 100):
        raise HTTPException(400, "Score must be between 0 and 100")
    conn = get_db()
    conn.execute("UPDATE grades SET score = ? WHERE id = ?", (data.score, grade_id))
    conn.commit()
    conn.close()
    return {"message": "Grade updated"}

@app.delete("/grades/{grade_id}")
def delete_grade(grade_id: int, user: str = Depends(require_auth)):
    conn = get_db()
    conn.execute("DELETE FROM grades WHERE id = ?", (grade_id,))
    conn.commit()
    conn.close()
    return {"message": "Grade deleted"}

# ── Report Card ──────────────────────────────────────────────

@app.get("/report/{student_id}")
def get_report(student_id: int, user: str = Depends(require_auth)):
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        raise HTTPException(404, "Student not found")
    grades = conn.execute("""
        SELECT g.score, g.exam_type, s.name as subject
        FROM grades g
        JOIN subjects s ON g.subject_id = s.id
        WHERE g.student_id = ?
        ORDER BY s.name
    """, (student_id,)).fetchall()
    conn.close()

    grade_list = [dict(g) for g in grades]
    scores = [g["score"] for g in grade_list]
    average = round(sum(scores) / len(scores), 2) if scores else 0
    total = sum(scores)

    def letter_grade(score):
        if score >= 70: return "A"
        if score >= 60: return "B"
        if score >= 50: return "C"
        if score >= 40: return "D"
        return "F"

    def gpa(score):
        if score >= 70: return 4.0
        if score >= 60: return 3.0
        if score >= 50: return 2.0
        if score >= 40: return 1.0
        return 0.0

    def remarks(score):
        if score >= 70: return "Distinction"
        if score >= 60: return "Credit"
        if score >= 50: return "Pass"
        if score >= 40: return "Marginal Pass"
        return "Fail"

    for g in grade_list:
        g["letter"] = letter_grade(g["score"])
        g["gpa_points"] = gpa(g["score"])
        g["remarks"] = remarks(g["score"])

    gpa_avg = round(sum(g["gpa_points"] for g in grade_list) / len(grade_list), 2) if grade_list else 0

    def overall_remarks(gpa_val):
        if gpa_val >= 3.6: return "First Class Honours"
        if gpa_val >= 3.0: return "Second Class Upper"
        if gpa_val >= 2.0: return "Second Class Lower"
        if gpa_val >= 1.0: return "Pass"
        return "Fail"

    return {
        "student": dict(student),
        "grades": grade_list,
        "summary": {
            "total": total,
            "average": average,
            "gpa": gpa_avg,
            "letter_grade": letter_grade(average),
            "subjects_count": len(grade_list),
            "overall_remarks": overall_remarks(gpa_avg)
        }
    }

# ── Ranking ──────────────────────────────────────────────────

@app.get("/rank/{student_id}")
def get_rank(student_id: int, user: str = Depends(require_auth)):
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        raise HTTPException(404, "Student not found")

    classmates = conn.execute(
        "SELECT id FROM students WHERE class = ?", (student["class"],)
    ).fetchall()

    averages = []
    for c in classmates:
        row = conn.execute(
            "SELECT AVG(score) as avg FROM grades WHERE student_id = ?", (c["id"],)
        ).fetchone()
        averages.append({"id": c["id"], "average": row["avg"] or 0})

    conn.close()

    averages.sort(key=lambda x: x["average"], reverse=True)
    position = next((i + 1 for i, s in enumerate(averages) if s["id"] == student_id), None)

    return {"position": position, "out_of": len(averages), "class": student["class"]}

# ── Serve Frontend ───────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")