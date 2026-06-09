import sqlite3
import json
from datetime import date, datetime
from werkzeug.security import generate_password_hash

DB_PATH = "attendance.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Users table (admin accounts)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin'
        )
    """)

    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_number TEXT UNIQUE NOT NULL,
            photo_path TEXT,
            face_encoding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'Present',
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, date)
        )
    """)

    # Insert default admin if not exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


# ---------- USER FUNCTIONS ----------

def get_user_by_username(username):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


# ---------- STUDENT FUNCTIONS ----------

def add_student(name, roll_number, photo_path, face_encoding):
    """face_encoding is a list (numpy array converted to list)"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO students (name, roll_number, photo_path, face_encoding) VALUES (?, ?, ?, ?)",
            (name, roll_number, photo_path, json.dumps(face_encoding))
        )
        conn.commit()
        return True, "Student enrolled successfully."
    except sqlite3.IntegrityError:
        return False, "Roll number already exists."
    finally:
        conn.close()


def get_all_students():
    conn = get_connection()
    students = conn.execute(
        "SELECT id, name, roll_number, photo_path, created_at FROM students ORDER BY name"
    ).fetchall()
    conn.close()
    return students


def get_student_by_id(student_id):
    conn = get_connection()
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", (student_id,)
    ).fetchone()
    conn.close()
    return student


def delete_student(student_id):
    conn = get_connection()
    conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()


def get_all_face_encodings():
    """Returns list of (student_id, name, encoding_list)"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, face_encoding FROM students WHERE face_encoding IS NOT NULL"
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        encoding = json.loads(row["face_encoding"])
        result.append((row["id"], row["name"], encoding))
    return result


# ---------- ATTENDANCE FUNCTIONS ----------

def mark_attendance(student_id):
    """Marks a student present for today. Returns (success, message)."""
    today = date.today().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO attendance (student_id, date, time, status) VALUES (?, ?, ?, ?)",
            (student_id, today, now, "Present")
        )
        conn.commit()
        return True, "Marked present"
    except sqlite3.IntegrityError:
        return False, "Already marked today"
    finally:
        conn.close()


def get_attendance_by_date(filter_date=None):
    if filter_date is None:
        filter_date = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    records = conn.execute("""
        SELECT s.name, s.roll_number, a.date, a.time, a.status
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ?
        ORDER BY a.time DESC
    """, (filter_date,)).fetchall()
    conn.close()
    return records


def get_attendance_range(start_date, end_date):
    conn = get_connection()
    records = conn.execute("""
        SELECT s.name, s.roll_number, a.date, a.time, a.status
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date BETWEEN ? AND ?
        ORDER BY a.date DESC, a.time DESC
    """, (start_date, end_date)).fetchall()
    conn.close()
    return records


def get_dashboard_stats():
    today = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present_today = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE date = ?", (today,)
    ).fetchone()[0]
    absent_today = total_students - present_today
    recent = conn.execute("""
        SELECT s.name, s.roll_number, a.time
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ?
        ORDER BY a.time DESC LIMIT 5
    """, (today,)).fetchall()
    conn.close()
    return {
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": absent_today,
        "recent_activity": recent,
        "today": today
    }
