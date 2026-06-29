from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_file
)
from werkzeug.utils import secure_filename
from datetime import datetime
from fpdf import FPDF
import csv
import io
import os

app = Flask(__name__)
app.secret_key = 'student_management_secret_key_2026'

# ============================================================
# CONFIGURATION
# ============================================================
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB max
STUDENTS_PER_PAGE = 10

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================
# IN-MEMORY DATA STORAGE
# ============================================================
students = []
next_id = 1

# Dynamic subjects list (can be modified via Settings)
subjects = [
    {'key': 'math', 'name': 'Mathematics', 'icon': 'fa-calculator'},
    {'key': 'science', 'name': 'Science', 'icon': 'fa-flask'},
    {'key': 'english', 'name': 'English', 'icon': 'fa-language'},
    {'key': 'urdu', 'name': 'Urdu', 'icon': 'fa-pen-fancy'},
    {'key': 'computer', 'name': 'Computer', 'icon': 'fa-laptop-code'},
]

# Attendance records: list of {date, student_id, status}
attendance_records = []


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def calculate_grade(marks):
    """Calculate grade based on average marks."""
    if marks >= 90:
        return 'A+'
    elif marks >= 80:
        return 'A'
    elif marks >= 70:
        return 'B+'
    elif marks >= 60:
        return 'B'
    elif marks >= 50:
        return 'C'
    elif marks >= 40:
        return 'D'
    else:
        return 'F'


def get_grade_color(grade):
    """Return a CSS class based on the grade for styling."""
    grade_colors = {
        'A+': 'grade-aplus',
        'A': 'grade-a',
        'B+': 'grade-bplus',
        'B': 'grade-b',
        'C': 'grade-c',
        'D': 'grade-d',
        'F': 'grade-f',
    }
    return grade_colors.get(grade, 'grade-default')


def get_grade_remark(grade):
    """Return a motivational remark based on grade."""
    remarks = {
        'A+': 'Outstanding! Keep up the excellent work! 🌟',
        'A': 'Excellent performance! Very impressive! 🎯',
        'B+': 'Very good! You are doing great! 💪',
        'B': 'Good job! Keep pushing forward! 👍',
        'C': 'Average. There is room for improvement. 📚',
        'D': 'Below average. Needs to work harder. ⚠️',
        'F': 'Failed. Immediate attention required. 🚨',
    }
    return remarks.get(grade, '')


def get_subject_status(mark):
    """Return pass/fail status for a subject."""
    return 'Pass' if mark >= 40 else 'Fail'


def get_subject_keys():
    """Get list of subject keys."""
    return [s['key'] for s in subjects]


def get_subject_name(key):
    """Get display name for a subject key."""
    for s in subjects:
        if s['key'] == key:
            return s['name']
    return key.title()


def get_subject_icon(key):
    """Get icon class for a subject key."""
    for s in subjects:
        if s['key'] == key:
            return s['icon']
    return 'fa-book'


def build_student_marks(form_data):
    """Extract and validate marks from form data for all subjects."""
    marks = {}
    for subj in subjects:
        val = form_data.get(subj['key'], '0')
        try:
            mark = float(val)
        except ValueError:
            return None, f"Marks should only contain numbers for {subj['name']}!"
        if mark < 0 or mark > 100:
            return None, f"{subj['name']} marks must be between 0 and 100!"
        marks[subj['key']] = mark
    return marks, None


def compute_student_stats(marks):
    """Compute total, average, grade from marks dict."""
    if not marks:
        return 0, 0, 'F', get_grade_color('F'), get_grade_remark('F')
    total = sum(marks.values())
    average = total / len(marks) if marks else 0
    grade = calculate_grade(average)
    return total, round(average, 2), grade, get_grade_color(grade), get_grade_remark(grade)


def get_student_attendance(student_id):
    """Get attendance summary for a student."""
    records = [r for r in attendance_records if r['student_id'] == student_id]
    total = len(records)
    present = sum(1 for r in records if r['status'] == 'Present')
    absent = sum(1 for r in records if r['status'] == 'Absent')
    late = sum(1 for r in records if r['status'] == 'Late')
    percentage = round((present + late * 0.5) / total * 100, 1) if total > 0 else 0
    return {
        'total': total,
        'present': present,
        'absent': absent,
        'late': late,
        'percentage': percentage,
    }


# Make helpers available in templates
@app.context_processor
def inject_helpers():
    return {
        'subjects': subjects,
        'get_subject_name': get_subject_name,
        'get_subject_icon': get_subject_icon,
    }


# ============================================================
# ROUTES — DASHBOARD
# ============================================================

@app.route('/')
def index():
    """Home page with dashboard summary."""
    total_students = len(students)
    if total_students > 0:
        avg_marks = sum(s['average'] for s in students) / total_students
        top_student = max(students, key=lambda s: s['average'])
        pass_count = sum(1 for s in students if s['average'] >= 40)
        fail_count = total_students - pass_count
        highest_marks = max(s['average'] for s in students)
        lowest_marks = min(s['average'] for s in students)
    else:
        avg_marks = 0
        top_student = None
        pass_count = 0
        fail_count = 0
        highest_marks = 0
        lowest_marks = 0

    recent_students = students[-5:][::-1] if students else []

    return render_template(
        'index.html',
        total=total_students,
        avg_marks=round(avg_marks, 2),
        top_student=top_student,
        pass_count=pass_count,
        fail_count=fail_count,
        highest_marks=highest_marks,
        lowest_marks=lowest_marks,
        recent_students=recent_students,
    )


# ============================================================
# ROUTES — ADD STUDENT
# ============================================================

@app.route('/add', methods=['GET', 'POST'])
def add_student():
    """Add a new student."""
    global next_id

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll_no = request.form.get('roll_no', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        course = request.form.get('course', '').strip()
        gender = request.form.get('gender', '').strip()
        address = request.form.get('address', '').strip()

        # Validation
        if not name or not roll_no:
            flash('Name and Roll Number are required!', 'error')
            return redirect(url_for('add_student'))

        # Check duplicate roll number
        for s in students:
            if s['roll_no'] == roll_no:
                flash(f'Roll Number "{roll_no}" already exists!', 'error')
                return redirect(url_for('add_student'))

        # Build marks
        marks, error = build_student_marks(request.form)
        if error:
            flash(error, 'error')
            return redirect(url_for('add_student'))

        total, average, grade, grade_color, remark = compute_student_stats(marks)

        # Handle photo upload
        photo_filename = ''
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and photo.filename and allowed_file(photo.filename):
                filename = secure_filename(f"{roll_no}_{photo.filename}")
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_filename = filename

        student = {
            'id': next_id,
            'name': name,
            'roll_no': roll_no,
            'email': email,
            'phone': phone,
            'course': course,
            'gender': gender,
            'address': address,
            'marks': marks,
            'total': total,
            'average': average,
            'grade': grade,
            'grade_color': grade_color,
            'remark': remark,
            'photo': photo_filename,
            'date_added': datetime.now().strftime('%d %b %Y, %I:%M %p'),
        }

        students.append(student)
        next_id += 1
        flash(f'Student "{name}" has been added successfully!', 'success')
        return redirect(url_for('view_students'))

    return render_template('add_student.html')


# ============================================================
# ROUTES — VIEW ALL STUDENTS (with Pagination, Sort, Filter)
# ============================================================

@app.route('/students')
def view_students():
    """View all students with sorting, filtering, and pagination."""
    sort_by = request.args.get('sort', 'id')
    order = request.args.get('order', 'asc')
    filter_grade = request.args.get('grade', '')
    filter_course = request.args.get('course', '')
    page = request.args.get('page', 1, type=int)

    filtered = students[:]

    if filter_grade:
        filtered = [s for s in filtered if s['grade'] == filter_grade]
    if filter_course:
        filtered = [s for s in filtered if s['course'].lower() == filter_course.lower()]

    sort_keys = {
        'id': lambda s: s['id'],
        'name': lambda s: s['name'].lower(),
        'roll_no': lambda s: s['roll_no'].lower(),
        'average': lambda s: s['average'],
        'total': lambda s: s['total'],
        'grade': lambda s: s['average'],
    }
    sort_func = sort_keys.get(sort_by, sort_keys['id'])
    filtered.sort(key=sort_func, reverse=(order == 'desc'))

    # Pagination
    total_filtered = len(filtered)
    total_pages = max(1, (total_filtered + STUDENTS_PER_PAGE - 1) // STUDENTS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * STUDENTS_PER_PAGE
    end = start + STUDENTS_PER_PAGE
    paginated = filtered[start:end]

    courses = sorted(set(s['course'] for s in students if s['course']))
    grades = ['A+', 'A', 'B+', 'B', 'C', 'D', 'F']

    return render_template(
        'students.html',
        students=paginated,
        sort_by=sort_by,
        order=order,
        filter_grade=filter_grade,
        filter_course=filter_course,
        courses=courses,
        grades=grades,
        total_count=len(students),
        filtered_count=total_filtered,
        page=page,
        total_pages=total_pages,
        per_page=STUDENTS_PER_PAGE,
    )


# ============================================================
# ROUTES — STUDENT PROFILE
# ============================================================

@app.route('/profile/<int:student_id>')
def student_profile(student_id):
    """View detailed student profile."""
    student = next((s for s in students if s['id'] == student_id), None)
    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('view_students'))

    sorted_students = sorted(students, key=lambda s: s['average'], reverse=True)
    rank = next((i + 1 for i, s in enumerate(sorted_students) if s['id'] == student_id), 0)

    subject_status = {subj: get_subject_status(mark) for subj, mark in student['marks'].items()}

    if student['marks']:
        strongest = max(student['marks'], key=student['marks'].get)
        weakest = min(student['marks'], key=student['marks'].get)
    else:
        strongest = weakest = 'N/A'

    attendance = get_student_attendance(student_id)

    return render_template(
        'profile.html',
        student=student,
        rank=rank,
        total_students=len(students),
        subject_status=subject_status,
        strongest=strongest,
        weakest=weakest,
        attendance=attendance,
    )


# ============================================================
# ROUTES — UPDATE STUDENT
# ============================================================

@app.route('/update/<int:student_id>', methods=['GET', 'POST'])
def update_student(student_id):
    """Update an existing student's information."""
    student = next((s for s in students if s['id'] == student_id), None)
    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('view_students'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll_no = request.form.get('roll_no', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        course = request.form.get('course', '').strip()
        gender = request.form.get('gender', '').strip()
        address = request.form.get('address', '').strip()

        if not name or not roll_no:
            flash('Name and Roll Number are required!', 'error')
            return redirect(url_for('update_student', student_id=student_id))

        for s in students:
            if s['roll_no'] == roll_no and s['id'] != student_id:
                flash(f'Roll Number "{roll_no}" belongs to another student!', 'error')
                return redirect(url_for('update_student', student_id=student_id))

        marks, error = build_student_marks(request.form)
        if error:
            flash(error, 'error')
            return redirect(url_for('update_student', student_id=student_id))

        total, average, grade, grade_color, remark = compute_student_stats(marks)

        # Handle photo upload
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and photo.filename and allowed_file(photo.filename):
                # Delete old photo if exists
                if student.get('photo'):
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], student['photo'])
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(f"{roll_no}_{photo.filename}")
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                student['photo'] = filename

        student['name'] = name
        student['roll_no'] = roll_no
        student['email'] = email
        student['phone'] = phone
        student['course'] = course
        student['gender'] = gender
        student['address'] = address
        student['marks'] = marks
        student['total'] = total
        student['average'] = average
        student['grade'] = grade
        student['grade_color'] = grade_color
        student['remark'] = remark

        flash(f'Student "{name}" has been updated successfully!', 'success')
        return redirect(url_for('view_students'))

    return render_template('update_student.html', student=student)


# ============================================================
# ROUTES — DELETE STUDENT
# ============================================================

@app.route('/delete/<int:student_id>')
def delete_student(student_id):
    """Delete a student by ID."""
    global students
    student = next((s for s in students if s['id'] == student_id), None)

    if student:
        # Delete photo file
        if student.get('photo'):
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], student['photo'])
            if os.path.exists(photo_path):
                os.remove(photo_path)
        students = [s for s in students if s['id'] != student_id]
        flash(f'Student "{student["name"]}" has been deleted successfully!', 'success')
    else:
        flash('Student not found!', 'error')

    return redirect(url_for('view_students'))


# ============================================================
# ROUTES — SEARCH
# ============================================================

@app.route('/search', methods=['GET', 'POST'])
def search_student():
    """Search students by name, roll number, course, or email."""
    results = []
    query = ''

    if request.method == 'POST':
        query = request.form.get('query', '').strip().lower()
        if query:
            results = [
                s for s in students
                if query in s['name'].lower()
                or query in s['roll_no'].lower()
                or query in s['course'].lower()
                or query in s.get('email', '').lower()
            ]
        else:
            flash('Search field is empty! Please enter a keyword.', 'error')

    return render_template('search.html', results=results, query=query)


# ============================================================
# ROUTES — ANALYTICS
# ============================================================

@app.route('/analytics')
def analytics():
    """Analytics and Reports page."""
    total_students = len(students)

    if total_students == 0:
        return render_template('analytics.html',
                               total=0, stats=None, grade_dist={},
                               subject_avg={}, top_performers=[], courses_data={})

    grade_dist = {'A+': 0, 'A': 0, 'B+': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    for s in students:
        grade_dist[s['grade']] = grade_dist.get(s['grade'], 0) + 1

    subject_avg = {}
    subject_stats = {}
    for subj in subjects:
        key = subj['key']
        all_marks = [s['marks'].get(key, 0) for s in students if key in s['marks']]
        if all_marks:
            avg = sum(all_marks) / len(all_marks)
            subject_avg[key] = round(avg, 2)
            subject_stats[key] = {
                'avg': round(avg, 2),
                'highest': max(all_marks),
                'lowest': min(all_marks),
            }

    top_performers = sorted(students, key=lambda s: s['average'], reverse=True)[:5]
    bottom_performers = sorted(students, key=lambda s: s['average'])[:5]

    courses_data = {}
    for s in students:
        course = s['course'] or 'Unassigned'
        if course not in courses_data:
            courses_data[course] = {'count': 0, 'total_avg': 0}
        courses_data[course]['count'] += 1
        courses_data[course]['total_avg'] += s['average']
    for course in courses_data:
        courses_data[course]['avg'] = round(
            courses_data[course]['total_avg'] / courses_data[course]['count'], 2
        )

    all_averages = [s['average'] for s in students]
    stats = {
        'total': total_students,
        'class_avg': round(sum(all_averages) / total_students, 2),
        'highest': max(all_averages),
        'lowest': min(all_averages),
        'pass_count': sum(1 for a in all_averages if a >= 40),
        'fail_count': sum(1 for a in all_averages if a < 40),
        'pass_rate': round(sum(1 for a in all_averages if a >= 40) / total_students * 100, 1),
    }

    return render_template(
        'analytics.html',
        total=total_students,
        stats=stats,
        grade_dist=grade_dist,
        subject_avg=subject_avg,
        subject_stats=subject_stats,
        top_performers=top_performers,
        bottom_performers=bottom_performers,
        courses_data=courses_data,
    )


# ============================================================
# ROUTES — ATTENDANCE
# ============================================================

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    """Mark attendance for students."""
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

    if request.method == 'POST':
        date = request.form.get('date', selected_date)
        # Remove existing records for this date
        global attendance_records
        attendance_records = [r for r in attendance_records if r['date'] != date]

        for s in students:
            status = request.form.get(f'status_{s["id"]}', 'Absent')
            attendance_records.append({
                'date': date,
                'student_id': s['id'],
                'status': status,
            })

        flash(f'Attendance for {date} has been saved successfully!', 'success')
        return redirect(url_for('attendance', date=date))

    # Get existing records for selected date
    existing = {}
    for r in attendance_records:
        if r['date'] == selected_date:
            existing[r['student_id']] = r['status']

    return render_template(
        'attendance.html',
        students=students,
        selected_date=selected_date,
        existing=existing,
    )


@app.route('/attendance/report')
def attendance_report():
    """View attendance report."""
    student_attendance = []
    for s in students:
        att = get_student_attendance(s['id'])
        student_attendance.append({
            'student': s,
            'attendance': att,
        })

    # Get all unique dates
    dates = sorted(set(r['date'] for r in attendance_records), reverse=True)

    return render_template(
        'attendance_report.html',
        student_attendance=student_attendance,
        dates=dates,
        total_students=len(students),
    )


# ============================================================
# ROUTES — SETTINGS (Custom Subjects)
# ============================================================

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page — manage subjects."""
    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'add_subject':
            name = request.form.get('subject_name', '').strip()
            icon = request.form.get('subject_icon', 'fa-book').strip()
            if not name:
                flash('Subject name is required!', 'error')
                return redirect(url_for('settings'))

            key = name.lower().replace(' ', '_')
            # Check duplicate
            if any(s['key'] == key for s in subjects):
                flash(f'Subject "{name}" already exists!', 'error')
                return redirect(url_for('settings'))

            subjects.append({'key': key, 'name': name, 'icon': icon})
            flash(f'Subject "{name}" has been added successfully!', 'success')

        elif action == 'delete_subject':
            key = request.form.get('subject_key', '')
            if len(subjects) <= 1:
                flash('Cannot delete! At least one subject is required.', 'error')
                return redirect(url_for('settings'))

            subjects[:] = [s for s in subjects if s['key'] != key]
            # Remove this subject from all students' marks
            for s in students:
                s['marks'].pop(key, None)
                total, average, grade, grade_color, remark = compute_student_stats(s['marks'])
                s['total'] = total
                s['average'] = average
                s['grade'] = grade
                s['grade_color'] = grade_color
                s['remark'] = remark

            flash('Subject has been removed successfully!', 'success')

        return redirect(url_for('settings'))

    return render_template('settings.html')


# ============================================================
# ROUTES — EXPORT CSV
# ============================================================

@app.route('/export/csv')
def export_csv():
    """Export all students to CSV file."""
    if not students:
        flash('No students to export!', 'error')
        return redirect(url_for('view_students'))

    output = io.StringIO()
    subject_keys = get_subject_keys()
    fieldnames = ['ID', 'Name', 'Roll No', 'Email', 'Phone', 'Gender',
                  'Course', 'Address'] + [get_subject_name(k) for k in subject_keys] + [
                  'Total', 'Average', 'Grade', 'Date Added']

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for s in students:
        row = {
            'ID': s['id'],
            'Name': s['name'],
            'Roll No': s['roll_no'],
            'Email': s['email'],
            'Phone': s['phone'],
            'Gender': s.get('gender', ''),
            'Course': s['course'],
            'Address': s.get('address', ''),
            'Total': s['total'],
            'Average': s['average'],
            'Grade': s['grade'],
            'Date Added': s.get('date_added', ''),
        }
        for key in subject_keys:
            row[get_subject_name(key)] = s['marks'].get(key, 0)
        writer.writerow(row)

    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'students_export_{timestamp}.csv',
    )


# ============================================================
# ROUTES — IMPORT CSV
# ============================================================

@app.route('/import/csv', methods=['POST'])
def import_csv():
    """Import students from a CSV file."""
    global next_id

    if 'csv_file' not in request.files:
        flash('No file selected!', 'error')
        return redirect(url_for('view_students'))

    file = request.files['csv_file']
    if not file.filename or not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file!', 'error')
        return redirect(url_for('view_students'))

    try:
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))

        imported_count = 0
        skipped_count = 0

        for row in reader:
            name = row.get('Name', '').strip()
            roll_no = row.get('Roll No', '').strip()

            if not name or not roll_no:
                skipped_count += 1
                continue

            # Skip if roll number already exists
            if any(s['roll_no'] == roll_no for s in students):
                skipped_count += 1
                continue

            marks = {}
            for subj in subjects:
                val = row.get(subj['name'], row.get(subj['key'], '0'))
                try:
                    mark = float(val) if val else 0
                    marks[subj['key']] = max(0, min(100, mark))
                except (ValueError, TypeError):
                    marks[subj['key']] = 0

            total, average, grade, grade_color, remark = compute_student_stats(marks)

            student = {
                'id': next_id,
                'name': name,
                'roll_no': roll_no,
                'email': row.get('Email', '').strip(),
                'phone': row.get('Phone', '').strip(),
                'course': row.get('Course', '').strip(),
                'gender': row.get('Gender', '').strip(),
                'address': row.get('Address', '').strip(),
                'marks': marks,
                'total': total,
                'average': average,
                'grade': grade,
                'grade_color': grade_color,
                'remark': remark,
                'photo': '',
                'date_added': datetime.now().strftime('%d %b %Y, %I:%M %p'),
            }
            students.append(student)
            next_id += 1
            imported_count += 1

        flash(f'Successfully imported {imported_count} student(s). Skipped: {skipped_count}.', 'success')
    except Exception as e:
        flash(f'Error reading CSV file: {str(e)}', 'error')

    return redirect(url_for('view_students'))


# ============================================================
# ROUTES — PHOTO UPLOAD
# ============================================================

@app.route('/upload-photo/<int:student_id>', methods=['POST'])
def upload_photo(student_id):
    """Upload or change student photo."""
    student = next((s for s in students if s['id'] == student_id), None)
    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('view_students'))

    if 'photo' not in request.files:
        flash('No photo selected!', 'error')
        return redirect(url_for('student_profile', student_id=student_id))

    photo = request.files['photo']
    if not photo.filename:
        flash('No photo selected!', 'error')
        return redirect(url_for('student_profile', student_id=student_id))

    if not allowed_file(photo.filename):
        flash('Invalid file type! Only JPG, PNG, and GIF are allowed.', 'error')
        return redirect(url_for('student_profile', student_id=student_id))

    # Delete old photo
    if student.get('photo'):
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], student['photo'])
        if os.path.exists(old_path):
            os.remove(old_path)

    filename = secure_filename(f"{student['roll_no']}_{photo.filename}")
    photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    student['photo'] = filename

    flash('Photo has been uploaded successfully!', 'success')
    return redirect(url_for('student_profile', student_id=student_id))


# ============================================================
# ROUTES — PDF REPORT CARD
# ============================================================

@app.route('/report-card/<int:student_id>')
def report_card(student_id):
    """Generate and download PDF report card."""
    student = next((s for s in students if s['id'] == student_id), None)
    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('view_students'))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_fill_color(108, 99, 255)
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_y(10)
    pdf.cell(0, 12, 'REPORT CARD', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 8, 'Student Management System', align='C', new_x='LMARGIN', new_y='NEXT')

    pdf.ln(15)
    pdf.set_text_color(0, 0, 0)

    # Student Info
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Student Information', new_x='LMARGIN', new_y='NEXT')
    pdf.set_draw_color(108, 99, 255)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    pdf.set_font('Helvetica', '', 11)
    info_fields = [
        ('Name', student['name']),
        ('Roll Number', student['roll_no']),
        ('Course', student['course'] or 'N/A'),
        ('Gender', student.get('gender', 'N/A') or 'N/A'),
        ('Email', student['email'] or 'N/A'),
        ('Phone', student['phone'] or 'N/A'),
    ]
    for label, value in info_fields:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(50, 8, f'{label}:', new_x='RIGHT')
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, str(value), new_x='LMARGIN', new_y='NEXT')

    pdf.ln(8)

    # Marks Table
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Subject-wise Marks', new_x='LMARGIN', new_y='NEXT')
    pdf.set_draw_color(108, 99, 255)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # Table header
    pdf.set_fill_color(108, 99, 255)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(15, 10, '#', border=1, fill=True, align='C')
    pdf.cell(70, 10, 'Subject', border=1, fill=True, align='C')
    pdf.cell(40, 10, 'Marks', border=1, fill=True, align='C')
    pdf.cell(30, 10, 'Out Of', border=1, fill=True, align='C')
    pdf.cell(35, 10, 'Status', border=1, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')

    # Table rows
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 11)
    for i, subj in enumerate(subjects):
        key = subj['key']
        mark = student['marks'].get(key, 0)
        status = 'Pass' if mark >= 40 else 'Fail'
        bg = (i % 2 == 0)
        if bg:
            pdf.set_fill_color(240, 240, 255)
        pdf.cell(15, 9, str(i + 1), border=1, fill=bg, align='C')
        pdf.cell(70, 9, subj['name'], border=1, fill=bg)
        pdf.cell(40, 9, str(mark), border=1, fill=bg, align='C')
        pdf.cell(30, 9, '100', border=1, fill=bg, align='C')

        if status == 'Fail':
            pdf.set_text_color(231, 76, 60)
        else:
            pdf.set_text_color(46, 204, 113)
        pdf.cell(35, 9, status, border=1, fill=bg, align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)

    pdf.ln(5)

    # Summary
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Result Summary', new_x='LMARGIN', new_y='NEXT')
    pdf.set_draw_color(108, 99, 255)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    max_total = len(subjects) * 100
    pdf.set_font('Helvetica', '', 12)
    summary = [
        ('Total Marks', f'{student["total"]} / {max_total}'),
        ('Average', f'{student["average"]}%'),
        ('Grade', student['grade']),
        ('Result', 'PASS' if student['average'] >= 40 else 'FAIL'),
    ]
    for label, value in summary:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(50, 9, f'{label}:', new_x='RIGHT')
        pdf.set_font('Helvetica', '', 12)
        if value == 'FAIL':
            pdf.set_text_color(231, 76, 60)
        elif value == 'PASS':
            pdf.set_text_color(46, 204, 113)
        pdf.cell(0, 9, str(value), new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)

    # Remark
    pdf.ln(5)
    pdf.set_font('Helvetica', 'I', 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f'Remark: {student.get("remark", "")}', new_x='LMARGIN', new_y='NEXT')

    # Footer
    pdf.ln(15)
    pdf.set_text_color(150, 150, 150)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 6, f'Generated on {datetime.now().strftime("%d %b %Y at %I:%M %p")}',
             align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 6, 'Student Management System - Powered by SMS', align='C')

    # Save to bytes
    pdf_bytes = pdf.output()
    safe_name = student['name'].replace(' ', '_')
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Report_Card_{safe_name}_{student["roll_no"]}.pdf',
    )


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/grade-distribution')
def api_grade_distribution():
    """Return grade distribution data for charts."""
    grade_dist = {'A+': 0, 'A': 0, 'B+': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    for s in students:
        grade_dist[s['grade']] = grade_dist.get(s['grade'], 0) + 1
    return jsonify(grade_dist)


@app.route('/api/subject-averages')
def api_subject_averages():
    """Return subject-wise average for charts."""
    if not students:
        return jsonify({})
    result = {}
    for subj in subjects:
        key = subj['key']
        marks_list = [s['marks'].get(key, 0) for s in students if key in s['marks']]
        if marks_list:
            avg = sum(marks_list) / len(marks_list)
            result[subj['name']] = round(avg, 2)
    return jsonify(result)


# ============================================================
# RUN THE APP
# ============================================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)
