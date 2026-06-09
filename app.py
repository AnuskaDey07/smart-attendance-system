import os
import csv
import io
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, jsonify, Response)
from werkzeug.security import check_password_hash

import database as db
import face_utils as fu

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret_key_in_production"

# ---------- SIMPLE SESSION-BASED AUTH ----------

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------- AUTH ROUTES ----------

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------- DASHBOARD ----------

@app.route("/dashboard")
@login_required
def dashboard():
    stats = db.get_dashboard_stats()
    return render_template("dashboard.html", stats=stats, username=session.get("username"))


# ---------- STUDENTS ----------

@app.route("/students")
@login_required
def students():
    all_students = db.get_all_students()
    return render_template("students.html", students=all_students, username=session.get("username"))


@app.route("/students/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    student = db.get_student_by_id(student_id)
    if student:
        # Remove photo file if it exists
        if student["photo_path"] and os.path.exists(student["photo_path"]):
            os.remove(student["photo_path"])
        db.delete_student(student_id)
        flash("Student removed successfully.", "success")
    return redirect(url_for("students"))


# ---------- ENROLL ----------

@app.route("/enroll", methods=["GET", "POST"])
@login_required
def enroll():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        photo = request.files.get("photo")

        if not name or not roll_number:
            flash("Name and Roll Number are required.", "danger")
            return render_template("enroll.html", username=session.get("username"))

        if not photo or photo.filename == "":
            flash("Please capture or upload a photo.", "danger")
            return render_template("enroll.html", username=session.get("username"))

        # Save photo
        photo_path = fu.save_student_photo(photo, roll_number)

        # Encode face
        encoding, error = fu.encode_face_from_file(photo_path)
        if error:
            os.remove(photo_path)   # Clean up bad photo
            flash(f"Face detection failed: {error}", "danger")
            return render_template("enroll.html", username=session.get("username"))

        # Save to database
        success, message = db.add_student(name, roll_number, photo_path, encoding)
        if success:
            flash(f"✓ {name} enrolled successfully!", "success")
            return redirect(url_for("students"))
        else:
            os.remove(photo_path)
            flash(f"Error: {message}", "danger")

    return render_template("enroll.html", username=session.get("username"))


# ---------- ATTENDANCE / SCAN ----------

@app.route("/attendance")
@login_required
def attendance():
    return render_template("attendance.html", username=session.get("username"))


@app.route("/scan", methods=["POST"])
@login_required
def scan():
    """
    Receives: JSON { "image": "data:image/jpeg;base64,..." }
    Returns:  JSON { "matched": bool, "student_name": str, "confidence": float, "message": str, "already_marked": bool }
    """
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"matched": False, "message": "No image received."}), 400

    # Load all known face encodings from the database
    known_data = db.get_all_face_encodings()

    # Identify the face
    result = fu.identify_face_from_base64(data["image"], known_data)

    if result["matched"]:
        success, msg = db.mark_attendance(result["student_id"])
        result["already_marked"] = not success
        result["message"] = msg
    else:
        result["already_marked"] = False

    return jsonify(result)


# ---------- REPORTS ----------

@app.route("/reports")
@login_required
def reports():
    from datetime import date
    filter_date = request.args.get("date", date.today().strftime("%Y-%m-%d"))
    records = db.get_attendance_by_date(filter_date)
    return render_template("reports.html",
                           records=records,
                           filter_date=filter_date,
                           username=session.get("username"))


@app.route("/reports/download")
@login_required
def download_report():
    from datetime import date
    start = request.args.get("start", date.today().strftime("%Y-%m-%d"))
    end = request.args.get("end", date.today().strftime("%Y-%m-%d"))
    records = db.get_attendance_range(start, end)

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Roll Number", "Date", "Time", "Status"])
        for r in records:
            writer.writerow([r["name"], r["roll_number"], r["date"], r["time"], r["status"]])
        return output.getvalue()

    csv_data = generate()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{start}_to_{end}.csv"}
    )


# ---------- ENTRY POINT ----------

if __name__ == "__main__":
    db.init_db()
    print("\n" + "="*50)
    print("  Smart Attendance System")
    print("  URL : http://127.0.0.1:5000")
    print("  Login: admin / admin123")
    print("="*50 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
