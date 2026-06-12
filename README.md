# Result Management System

A full-stack student result management system built with FastAPI, SQLite, and vanilla HTML/JS.

## Features
- Add & manage students
- Enter grades per subject & exam type
- Auto-calculate GPA and letter grades
- Generate & print report cards
- SQLite database (no setup required)

## Project Structure
```
result-system/
├── main.py            # FastAPI backend
├── requirements.txt   # Python dependencies
├── results.db         # SQLite database (auto-created)
└── static/
    └── index.html     # Frontend
```

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the server
```bash
uvicorn main:app --reload
```

### 3. Open in browser
```
http://localhost:8000
```

## Grading Scale
| Score | Letter | GPA |
|-------|--------|-----|
| 80–100 | A | 4.0 |
| 70–79  | B | 3.0 |
| 60–69  | C | 2.0 |
| 50–59  | D | 1.0 |
| 0–49   | F | 0.0 |

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /students | List all students |
| POST | /students | Add student |
| DELETE | /students/{id} | Delete student |
| GET | /subjects | List subjects |
| POST | /subjects | Add subject |
| GET | /grades/{student_id} | Get student grades |
| POST | /grades | Save/update grade |
| DELETE | /grades/{id} | Remove grade |
| GET | /report/{student_id} | Generate report card |
