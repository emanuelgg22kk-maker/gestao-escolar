import sqlite3
from datetime import datetime
from pathlib import Path

from werkzeug.security import generate_password_hash

DATABASE_PATH = Path(__file__).resolve().parent / "gestao_escolar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS schools (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    school_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    school_year INTEGER NOT NULL,
    shift TEXT NOT NULL,
    FOREIGN KEY (school_id) REFERENCES schools(id),
    UNIQUE (school_id, name, school_year)
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    enrollment_number TEXT NOT NULL UNIQUE,
    birth_date TEXT,
    FOREIGN KEY (class_id) REFERENCES classes(id)
);

CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY,
    school_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    FOREIGN KEY (school_id) REFERENCES schools(id)
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS class_subjects (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    FOREIGN KEY (class_id) REFERENCES classes(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (teacher_id) REFERENCES teachers(id),
    UNIQUE (class_id, subject_id)
);

CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    class_subject_id INTEGER NOT NULL,
    assessment_name TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 10),
    assessment_date TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late', 'excused')),
    notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students(id),
    UNIQUE (student_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS participation (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    class_subject_id INTEGER NOT NULL,
    activity TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 10),
    recorded_on TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    created_at TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1)),
    FOREIGN KEY (student_id) REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (
        role IN ('admin', 'diretor', 'professor', 'aluno', 'responsavel')
    ),
    school_id INTEGER,
    teacher_id INTEGER,
    student_id INTEGER,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE SET NULL,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_case_insensitive
    ON users(lower(username));

CREATE TABLE IF NOT EXISTS communications (
    id INTEGER PRIMARY KEY,
    school_id INTEGER,
    sender_user_id INTEGER,
    recipient_user_id INTEGER,
    recipient_read INTEGER NOT NULL DEFAULT 0 CHECK (recipient_read IN (0, 1)),
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    message_type TEXT NOT NULL
        CHECK (message_type IN ('family', 'school', 'management')),
    direction TEXT NOT NULL CHECK (direction IN ('sent', 'received')),
    status TEXT NOT NULL CHECK (status IN ('sent', 'unread', 'read')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE SET NULL,
    CHECK (
        (direction = 'sent' AND status = 'sent')
        OR (direction = 'received' AND status IN ('unread', 'read'))
    ),
    FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS learning_materials (
    id INTEGER PRIMARY KEY,
    class_subject_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    media_type TEXT NOT NULL
        CHECK (media_type IN ('message', 'activity', 'video', 'image', 'audio', 'file')),
    storage_name TEXT,
    original_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_subject_id) REFERENCES class_subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_students_class_id ON students(class_id);
CREATE INDEX IF NOT EXISTS idx_grades_student_id ON grades(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student_date
    ON attendance(student_id, attendance_date);
CREATE INDEX IF NOT EXISTS idx_participation_student_id
    ON participation(student_id);
CREATE INDEX IF NOT EXISTS idx_alerts_student_resolved
    ON alerts(student_id, resolved);
CREATE INDEX IF NOT EXISTS idx_communications_school_type
    ON communications(school_id, message_type);
CREATE INDEX IF NOT EXISTS idx_communications_status_date
    ON communications(status, created_at);
CREATE INDEX IF NOT EXISTS idx_learning_materials_assignment
    ON learning_materials(class_subject_id, created_at);
"""


def get_connection(database_path=DATABASE_PATH):
    """Abre uma conexão SQLite com suporte a chaves estrangeiras."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path=DATABASE_PATH):
    """Cria as tabelas e os índices caso ainda não existam."""
    connection = get_connection(database_path)
    try:
        connection.executescript(SCHEMA)
        connection.execute("DROP TABLE IF EXISTS pedagogical_plans")
        communication_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(communications)")
        }
        for column, definition in (
            ("sender_user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
            ("recipient_user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
            ("recipient_read", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if column not in communication_columns:
                connection.execute(
                    "ALTER TABLE communications ADD COLUMN {} {}".format(
                        column, definition
                    )
                )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_communications_sender "
            "ON communications(sender_user_id, recipient_user_id, created_at)"
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role)
            VALUES (?, ?, 'admin')
            """,
            ("admin", generate_password_hash("admin123")),
        )
        connection.commit()
    finally:
        connection.close()


def get_user_by_username(username):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT users.id, users.username, users.password_hash, users.role,
                users.school_id, users.teacher_id, users.student_id
            FROM users
            WHERE users.username = ? AND users.active = 1
            """,
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_user_by_id(user_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT users.id, users.username, users.role, users.school_id,
                users.teacher_id, users.student_id
            FROM users
            WHERE users.id = ? AND users.active = 1
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def create_user(username, password, role, school_id=None, teacher_id=None, student_id=None):
    if role not in ("admin", "diretor", "professor", "aluno", "responsavel"):
        raise ValueError("Perfil de usuário inválido.")
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    username, password_hash, role, school_id, teacher_id, student_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    generate_password_hash(password),
                    role,
                    school_id,
                    teacher_id,
                    student_id,
                ),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def get_management_form_data():
    connection = get_connection()
    try:
        schools = connection.execute(
            "SELECT id, name, city, state FROM schools ORDER BY name"
        ).fetchall()
        classes = connection.execute(
            """
            SELECT classes.id, classes.name, classes.school_id,
                classes.school_year, schools.name AS school_name
            FROM classes
            JOIN schools ON schools.id = classes.school_id
            ORDER BY schools.name, classes.school_year, classes.name
            """
        ).fetchall()
        teachers = connection.execute(
            """
            SELECT teachers.id, teachers.full_name, teachers.email, teachers.school_id,
                schools.name AS school_name
            FROM teachers
            JOIN schools ON schools.id = teachers.school_id
            ORDER BY teachers.full_name
            """
        ).fetchall()
        students = connection.execute(
            """
            SELECT students.id, students.full_name, students.enrollment_number,
                students.birth_date, students.class_id,
                classes.school_id, schools.name AS school_name
            FROM students
            JOIN classes ON classes.id = students.class_id
            JOIN schools ON schools.id = classes.school_id
            ORDER BY students.full_name
            """
        ).fetchall()
        subjects = connection.execute(
            "SELECT id, name FROM subjects ORDER BY name"
        ).fetchall()
    finally:
        connection.close()
    return {
        "schools": [dict(row) for row in schools],
        "classes": [dict(row) for row in classes],
        "teachers": [dict(row) for row in teachers],
        "students": [dict(row) for row in students],
        "subjects": [dict(row) for row in subjects],
    }


def get_users_page_data():
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT users.id, users.username, users.role, users.school_id,
                users.teacher_id, users.student_id, schools.name AS school_name,
                COALESCE(teachers.full_name, students.full_name) AS person_name
            FROM users
            LEFT JOIN schools ON schools.id = users.school_id
            LEFT JOIN teachers ON teachers.id = users.teacher_id
            LEFT JOIN students ON students.id = users.student_id
            WHERE users.active = 1
            ORDER BY users.role, users.username
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def create_school(name, city, state):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO schools (name, city, state) VALUES (?, ?, ?)",
                (name, city, state),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def create_class(school_id, name, school_year, shift):
    if shift not in ("morning", "afternoon", "evening"):
        raise ValueError("Turno inválido.")
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO classes (school_id, name, school_year, shift)
                VALUES (?, ?, ?, ?)
                """,
                (school_id, name, school_year, shift),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def update_school(school_id, name, city, state):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                "UPDATE schools SET name = ?, city = ?, state = ? WHERE id = ?",
                (name, city, state, school_id),
            )
            return cursor.rowcount > 0
    finally:
        connection.close()


def create_teacher(school_id, full_name, email):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO teachers (school_id, full_name, email)
                VALUES (?, ?, ?)
                """,
                (school_id, full_name, email),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def update_teacher(teacher_id, full_name, email, school_id):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                UPDATE teachers SET full_name = ?, email = ?, school_id = ?
                WHERE id = ?
                """,
                (full_name, email, school_id, teacher_id),
            )
            return cursor.rowcount > 0
    finally:
        connection.close()


def create_student(class_id, full_name, enrollment_number, birth_date):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO students (class_id, full_name, enrollment_number, birth_date)
                VALUES (?, ?, ?, ?)
                """,
                (class_id, full_name, enrollment_number, birth_date or None),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def update_student(student_id, class_id, full_name, enrollment_number, birth_date):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                UPDATE students
                SET class_id = ?, full_name = ?, enrollment_number = ?, birth_date = ?
                WHERE id = ?
                """,
                (class_id, full_name, enrollment_number, birth_date or None, student_id),
            )
            return cursor.rowcount > 0
    finally:
        connection.close()


def get_students_available_for_class(class_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT students.id, students.full_name, students.enrollment_number
            FROM students
            JOIN classes AS current_classes
                ON current_classes.id = students.class_id
            JOIN classes AS target_class
                ON target_class.school_id = current_classes.school_id
            WHERE target_class.id = ? AND students.class_id != target_class.id
            ORDER BY students.full_name COLLATE NOCASE
            """,
            (class_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def assign_student_to_class(student_id, class_id):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                UPDATE students
                SET class_id = ?
                WHERE id = ?
                  AND EXISTS (
                      SELECT 1
                      FROM classes AS target_class
                      JOIN classes AS current_class
                          ON current_class.school_id = target_class.school_id
                      WHERE target_class.id = ?
                        AND current_class.id = students.class_id
                  )
                """,
                (class_id, student_id, class_id),
            )
            return cursor.rowcount > 0
    finally:
        connection.close()


def record_student_attendance(student_id, attendance_date, status, notes=""):
    if status not in ("present", "absent", "late", "excused"):
        raise ValueError("Situação de frequência inválida.")
    connection = get_connection()
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO attendance (
                    student_id, attendance_date, status, notes
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(student_id, attendance_date) DO UPDATE SET
                    status = excluded.status,
                    notes = excluded.notes
                """,
                (student_id, attendance_date, status, notes or None),
            )
        return True
    finally:
        connection.close()


def record_student_grade(
    student_id, class_subject_id, assessment_name, score, assessment_date
):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO grades (
                    student_id, class_subject_id, assessment_name, score,
                    assessment_date
                )
                SELECT ?, class_subjects.id, ?, ?, ?
                FROM class_subjects
                JOIN students ON students.class_id = class_subjects.class_id
                WHERE students.id = ? AND class_subjects.id = ?
                """,
                (
                    student_id,
                    assessment_name,
                    score,
                    assessment_date,
                    student_id,
                    class_subject_id,
                ),
            )
            return cursor.rowcount > 0
    finally:
        connection.close()


def save_class_subject(class_id, subject_name, teacher_id):
    connection = get_connection()
    try:
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO subjects (name) VALUES (?)", (subject_name,)
            )
            subject_id = connection.execute(
                "SELECT id FROM subjects WHERE name = ?", (subject_name,)
            ).fetchone()["id"]
            connection.execute(
                """
                INSERT INTO class_subjects (class_id, subject_id, teacher_id)
                VALUES (?, ?, ?)
                ON CONFLICT(class_id, subject_id) DO UPDATE SET teacher_id = excluded.teacher_id
                """,
                (class_id, subject_id, teacher_id),
            )
            return subject_id
    finally:
        connection.close()


def update_subject(subject_id, name):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                "UPDATE subjects SET name = ? WHERE id = ?", (name, subject_id)
            )
            return cursor.rowcount > 0
    finally:
        connection.close()


def get_subject_assignments(user=None):
    conditions = []
    values = []
    if user and user["role"] == "professor":
        conditions.append("class_subjects.teacher_id = ?")
        values.append(user["teacher_id"])
    elif user and user["role"] in ("diretor",):
        conditions.append("schools.id = ?")
        values.append(user["school_id"])
    elif user and user["role"] in ("aluno", "responsavel"):
        conditions.append("students.id = ?")
        values.append(user["student_id"])
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT class_subjects.id, class_subjects.class_id, class_subjects.teacher_id,
                class_subjects.subject_id,
                classes.name AS class_name, classes.school_year, schools.id AS school_id,
                schools.name AS school_name, subjects.name AS subject_name,
                teachers.full_name AS teacher_name
            FROM class_subjects
            JOIN classes ON classes.id = class_subjects.class_id
            JOIN schools ON schools.id = classes.school_id
            JOIN subjects ON subjects.id = class_subjects.subject_id
            JOIN teachers ON teachers.id = class_subjects.teacher_id
            LEFT JOIN students ON students.class_id = classes.id
            {}
            GROUP BY class_subjects.id
            ORDER BY schools.name, classes.name, subjects.name
            """.format(where_clause),
            values,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_class_subject_assignment(assignment_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT class_subjects.id, class_subjects.class_id,
                class_subjects.subject_id, class_subjects.teacher_id,
                classes.school_id
            FROM class_subjects
            JOIN classes ON classes.id = class_subjects.class_id
            WHERE class_subjects.id = ?
            """,
            (assignment_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def create_learning_material(
    class_subject_id, teacher_id, title, description, media_type, storage_name=None,
    original_name=None,
):
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO learning_materials (
                    class_subject_id, teacher_id, title, description, media_type,
                    storage_name, original_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    class_subject_id,
                    teacher_id,
                    title,
                    description,
                    media_type,
                    storage_name,
                    original_name,
                ),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def get_learning_materials(class_subject_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, title, description, media_type, storage_name,
                original_name, created_at
            FROM learning_materials
            WHERE class_subject_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (class_subject_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_learning_material(material_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT learning_materials.id, learning_materials.class_subject_id,
                learning_materials.storage_name, learning_materials.original_name,
                class_subjects.teacher_id
            FROM learning_materials
            JOIN class_subjects
                ON class_subjects.id = learning_materials.class_subject_id
            WHERE learning_materials.id = ?
            """,
            (material_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_dashboard_data():
    """Retorna os indicadores e as listas usadas pela tela de Dashboard."""
    connection = get_connection()
    try:
        summary = connection.execute(
            """
            WITH attendance_by_student AS (
                SELECT student_id,
                    100.0 * SUM(
                        CASE WHEN status IN ('present', 'late') THEN 1 ELSE 0 END
                    ) / COUNT(*) AS attendance_rate
                FROM attendance
                GROUP BY student_id
            ),
            grades_by_student AS (
                SELECT student_id, AVG(score) AS average_grade
                FROM grades
                GROUP BY student_id
            )
            SELECT
                (SELECT COUNT(*) FROM students) AS total_students,
                (SELECT COUNT(*) FROM teachers) AS total_teachers,
                (SELECT COUNT(*) FROM classes) AS total_classes,
                (SELECT COUNT(*) FROM schools) AS total_schools,
                (SELECT AVG(score) FROM grades) AS average_grade,
                (SELECT AVG(attendance_rate) FROM attendance_by_student)
                    AS average_attendance,
                (
                    SELECT COUNT(*)
                    FROM students
                    LEFT JOIN attendance_by_student
                        ON attendance_by_student.student_id = students.id
                    LEFT JOIN grades_by_student
                        ON grades_by_student.student_id = students.id
                    WHERE (attendance_by_student.attendance_rate IS NOT NULL
                           AND attendance_by_student.attendance_rate < 75)
                       OR (grades_by_student.average_grade IS NOT NULL
                           AND grades_by_student.average_grade < 6)
                ) AS attention_students
            """
        ).fetchone()

        attendance_cte = """
            WITH attendance_by_student AS (
                SELECT student_id,
                    100.0 * SUM(
                        CASE WHEN status IN ('present', 'late') THEN 1 ELSE 0 END
                    ) / COUNT(*) AS attendance_rate
                FROM attendance
                GROUP BY student_id
            )
        """

        schools = connection.execute(
            attendance_cte
            + """
            SELECT schools.name,
                (SELECT COUNT(*)
                 FROM students
                 JOIN classes ON classes.id = students.class_id
                 WHERE classes.school_id = schools.id) AS student_count,
                (SELECT COUNT(*) FROM classes
                 WHERE classes.school_id = schools.id) AS class_count,
                (SELECT AVG(attendance_by_student.attendance_rate)
                 FROM students
                 JOIN classes ON classes.id = students.class_id
                 JOIN attendance_by_student
                    ON attendance_by_student.student_id = students.id
                 WHERE classes.school_id = schools.id) AS attendance_rate
            FROM schools
            ORDER BY schools.name
            """
        ).fetchall()

        subject_performance = connection.execute(
            """
            SELECT subjects.name, AVG(grades.score) AS average_grade
            FROM subjects
            LEFT JOIN class_subjects
                ON class_subjects.subject_id = subjects.id
            LEFT JOIN grades
                ON grades.class_subject_id = class_subjects.id
            GROUP BY subjects.id, subjects.name
            ORDER BY subjects.name
            """
        ).fetchall()

        class_attendance = connection.execute(
            attendance_cte
            + """
            SELECT classes.name AS class_name, schools.name AS school_name,
                AVG(attendance_by_student.attendance_rate) AS attendance_rate
            FROM classes
            JOIN schools ON schools.id = classes.school_id
            LEFT JOIN students ON students.class_id = classes.id
            LEFT JOIN attendance_by_student
                ON attendance_by_student.student_id = students.id
            GROUP BY classes.id, classes.name, schools.name
            ORDER BY schools.name, classes.name
            """
        ).fetchall()

        alert_rows = connection.execute(
            """
            SELECT students.full_name, alerts.category, alerts.message,
                alerts.severity, alerts.created_at
            FROM alerts
            JOIN students ON students.id = alerts.student_id
            ORDER BY alerts.created_at DESC, alerts.id DESC
            LIMIT 5
            """
        ).fetchall()
    finally:
        connection.close()

    category_labels = {
        "attendance": "Frequência",
        "performance": "Desempenho",
    }
    severity_labels = {
        "info": "Informativa",
        "warning": "Atenção",
        "critical": "Crítica",
    }
    alerts = []
    for row in alert_rows:
        alert = dict(row)
        alert["category_label"] = category_labels.get(
            alert["category"], alert["category"].replace("_", " ").capitalize()
        )
        alert["priority_label"] = severity_labels.get(
            alert["severity"], alert["severity"].capitalize()
        )
        alerts.append(alert)

    return {
        "summary": dict(summary),
        "alerts": alerts,
        "schools": [dict(row) for row in schools],
        "subject_performance": [dict(row) for row in subject_performance],
        "class_attendance": [dict(row) for row in class_attendance],
    }


_STUDENT_METRICS_CTE = """
    WITH attendance_by_student AS (
        SELECT student_id,
            100.0 * SUM(
                CASE WHEN status IN ('present', 'late') THEN 1 ELSE 0 END
            ) / COUNT(*) AS attendance_rate
        FROM attendance
        GROUP BY student_id
    ),
    grades_by_student AS (
        SELECT student_id, AVG(score) AS average_grade
        FROM grades
        GROUP BY student_id
    ),
    student_metrics AS (
        SELECT students.id, students.full_name,
            schools.id AS school_id, schools.name AS school_name,
            classes.id AS class_id, classes.name AS class_name,
            classes.school_year,
            attendance_by_student.attendance_rate,
            grades_by_student.average_grade,
            CASE
                WHEN (attendance_by_student.attendance_rate IS NOT NULL
                      AND attendance_by_student.attendance_rate < 75)
                  OR (grades_by_student.average_grade IS NOT NULL
                      AND grades_by_student.average_grade < 6)
                THEN 'attention'
                ELSE 'regular'
            END AS situation
        FROM students
        JOIN classes ON classes.id = students.class_id
        JOIN schools ON schools.id = classes.school_id
        LEFT JOIN attendance_by_student
            ON attendance_by_student.student_id = students.id
        LEFT JOIN grades_by_student
            ON grades_by_student.student_id = students.id
    )
"""


def _positive_integer(value):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return None
    return parsed_value if parsed_value > 0 else None


def get_students_page_data(search="", school_id="", class_id="", situation=""):
    """Retorna os indicadores, filtros e alunos para a página de listagem."""
    search = (search or "").strip()
    school_id = _positive_integer(school_id)
    class_id = _positive_integer(class_id)
    if situation not in ("attention", "regular"):
        situation = ""

    connection = get_connection()
    try:
        summary = connection.execute(
            _STUDENT_METRICS_CTE
            + """
            SELECT COUNT(*) AS total_students,
                COALESCE(SUM(
                    CASE WHEN situation = 'attention' THEN 1 ELSE 0 END
                ), 0) AS attention_students,
                (SELECT AVG(attendance_rate) FROM student_metrics)
                    AS average_attendance,
                (SELECT AVG(score) FROM grades) AS average_grade
            FROM student_metrics
            """
        ).fetchone()

        students = connection.execute(
            _STUDENT_METRICS_CTE
            + """
            SELECT id, full_name, school_id, school_name, class_id,
                class_name, attendance_rate, average_grade, situation
            FROM student_metrics
            WHERE (? = '' OR full_name LIKE ? COLLATE NOCASE)
              AND (? IS NULL OR school_id = ?)
              AND (? IS NULL OR class_id = ?)
              AND (? = '' OR situation = ?)
            ORDER BY full_name COLLATE NOCASE
            """,
            (
                search,
                "%{}%".format(search),
                school_id,
                school_id,
                class_id,
                class_id,
                situation,
                situation,
            ),
        ).fetchall()

        schools = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
        classes = connection.execute(
            """
            SELECT classes.id, classes.name, schools.name AS school_name
            FROM classes
            JOIN schools ON schools.id = classes.school_id
            WHERE (? IS NULL OR classes.school_id = ?)
            ORDER BY schools.name, classes.name
            """,
            (school_id, school_id),
        ).fetchall()
    finally:
        connection.close()

    return {
        "summary": dict(summary),
        "students": [dict(row) for row in students],
        "schools": [dict(row) for row in schools],
        "classes": [dict(row) for row in classes],
        "filters": {
            "search": search,
            "school_id": str(school_id or ""),
            "class_id": str(class_id or ""),
            "situation": situation,
        },
    }


def get_student_by_id(student_id):
    """Busca os vínculos do aluno para validar o acesso ao perfil."""
    connection = get_connection()
    try:
        student = connection.execute(
            """
            SELECT students.id, students.full_name, students.class_id,
                classes.school_id
            FROM students
            JOIN classes ON classes.id = students.class_id
            WHERE students.id = ?
            """,
            (student_id,),
        ).fetchone()
        return dict(student) if student is not None else None
    finally:
        connection.close()


def get_student_profile_data(student_id):
    """Retorna somente dados existentes necessários ao perfil do aluno."""
    connection = get_connection()
    try:
        student_row = connection.execute(
            _STUDENT_METRICS_CTE
            + """
            SELECT student_metrics.*,
                (SELECT COUNT(*) FROM class_subjects
                 WHERE class_subjects.class_id = student_metrics.class_id)
                    AS subject_count
            FROM student_metrics
            WHERE student_metrics.id = ?
            """,
            (student_id,),
        ).fetchone()

        if student_row is None:
            return None

        attendance = connection.execute(
            """
            SELECT COUNT(*) AS total_records,
                COALESCE(SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END), 0)
                    AS present_count,
                COALESCE(SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END), 0)
                    AS late_count,
                COALESCE(SUM(
                    CASE WHEN status IN ('absent', 'excused') THEN 1 ELSE 0 END
                ), 0) AS absence_count,
                100.0 * SUM(
                    CASE WHEN status IN ('present', 'late') THEN 1 ELSE 0 END
                ) / NULLIF(COUNT(*), 0) AS attendance_rate
            FROM attendance
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()

        grade_rows = connection.execute(
            """
            SELECT subjects.name AS subject_name, teachers.full_name AS teacher_name,
                grades.assessment_name, grades.score, grades.assessment_date
            FROM grades
            JOIN class_subjects
                ON class_subjects.id = grades.class_subject_id
            JOIN subjects ON subjects.id = class_subjects.subject_id
            LEFT JOIN teachers ON teachers.id = class_subjects.teacher_id
            WHERE grades.student_id = ?
            ORDER BY grades.assessment_date DESC, grades.id DESC
            """,
            (student_id,),
        ).fetchall()

        participation_summary = connection.execute(
            """
            SELECT AVG(score) AS average_participation
            FROM participation
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        participation_rows = connection.execute(
            """
            SELECT participation.activity, participation.score,
                participation.recorded_on, subjects.name AS subject_name
            FROM participation
            LEFT JOIN class_subjects
                ON class_subjects.id = participation.class_subject_id
            LEFT JOIN subjects ON subjects.id = class_subjects.subject_id
            WHERE participation.student_id = ?
            ORDER BY participation.recorded_on DESC, participation.id DESC
            """,
            (student_id,),
        ).fetchall()

        alert_rows = connection.execute(
            """
            SELECT category, message, severity, created_at
            FROM alerts
            WHERE student_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (student_id,),
        ).fetchall()
    finally:
        connection.close()

    student = dict(student_row)
    student["situation_label"] = (
        "Acompanhamento" if student["situation"] == "attention" else "Regular"
    )
    attendance = dict(attendance)

    grade_statuses = []
    for row in grade_rows:
        grade = dict(row)
        grade["situation_label"] = (
            "Abaixo da referência" if grade["score"] < 6 else "Na referência"
        )
        grade_statuses.append(grade)

    category_labels = {
        "attendance": "Frequência",
        "performance": "Desempenho",
    }
    priority_labels = {
        "info": "Informativa",
        "warning": "Atenção",
        "critical": "Crítica",
    }
    alerts = []
    for row in alert_rows:
        alert = dict(row)
        alert["category_label"] = category_labels.get(
            alert["category"], alert["category"].replace("_", " ").capitalize()
        )
        alert["priority_label"] = priority_labels.get(
            alert["severity"], alert["severity"].capitalize()
        )
        alerts.append(alert)

    attendance_low = (
        student["attendance_rate"] is not None
        and student["attendance_rate"] < 75
    )
    grade_low = (
        student["average_grade"] is not None
        and student["average_grade"] < 6
    )
    if attendance_low and grade_low:
        pedagogical_message = "Aluno necessita de acompanhamento prioritário."
    elif attendance_low:
        pedagogical_message = "Frequência abaixo do nível de acompanhamento."
    elif grade_low:
        pedagogical_message = "Desempenho abaixo da média de referência."
    elif student["attendance_rate"] is None or student["average_grade"] is None:
        pedagogical_message = "Ainda não há dados suficientes para avaliar os dois indicadores."
    else:
        pedagogical_message = "Indicadores dentro dos parâmetros de acompanhamento."

    return {
        "student": student,
        "attendance": attendance,
        "grades": grade_statuses,
        "average_participation": participation_summary["average_participation"],
        "participation": [dict(row) for row in participation_rows],
        "alerts": alerts,
        "pedagogical_message": pedagogical_message,
    }


def get_alerts_page_data(
    category="", priority="", school_id="", class_id="", student_name=""
):
    """Retorna alertas e opções de filtro sem alterar os registros existentes."""
    category = (category or "").strip()
    if priority not in ("info", "warning", "critical"):
        priority = ""
    school_id = _positive_integer(school_id)
    class_id = _positive_integer(class_id)
    student_name = (student_name or "").strip()

    connection = get_connection()
    try:
        summary = connection.execute(
            """
            SELECT COUNT(*) AS total_alerts,
                COALESCE(SUM(CASE WHEN category = 'attendance' THEN 1 ELSE 0 END), 0)
                    AS attendance_alerts,
                COALESCE(SUM(CASE WHEN category = 'performance' THEN 1 ELSE 0 END), 0)
                    AS performance_alerts,
                COALESCE(SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END), 0)
                    AS high_priority_alerts
            FROM alerts
            """
        ).fetchone()

        alerts = connection.execute(
            """
            SELECT alerts.id, alerts.student_id, students.full_name,
                schools.name AS school_name, classes.name AS class_name,
                alerts.category, alerts.message, alerts.severity, alerts.created_at
            FROM alerts
            JOIN students ON students.id = alerts.student_id
            JOIN classes ON classes.id = students.class_id
            JOIN schools ON schools.id = classes.school_id
            WHERE (? = '' OR alerts.category = ?)
              AND (? = '' OR alerts.severity = ?)
              AND (? IS NULL OR schools.id = ?)
              AND (? IS NULL OR classes.id = ?)
              AND (? = '' OR students.full_name LIKE ? COLLATE NOCASE)
            ORDER BY alerts.created_at DESC, alerts.id DESC
            """,
            (
                category,
                category,
                priority,
                priority,
                school_id,
                school_id,
                class_id,
                class_id,
                student_name,
                "%{}%".format(student_name),
            ),
        ).fetchall()

        categories = connection.execute(
            "SELECT DISTINCT category FROM alerts ORDER BY category"
        ).fetchall()
        schools = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
        classes = connection.execute(
            """
            SELECT classes.id, classes.name, schools.name AS school_name
            FROM classes
            JOIN schools ON schools.id = classes.school_id
            WHERE (? IS NULL OR classes.school_id = ?)
            ORDER BY schools.name, classes.name
            """,
            (school_id, school_id),
        ).fetchall()
    finally:
        connection.close()

    category_labels = {
        "attendance": "Frequência",
        "performance": "Desempenho",
    }
    priority_labels = {
        "info": "Informativa",
        "warning": "Atenção",
        "critical": "Crítica",
    }
    alert_rows = []
    for row in alerts:
        alert = dict(row)
        alert["category_label"] = category_labels.get(
            alert["category"], alert["category"].replace("_", " ").capitalize()
        )
        alert["priority_label"] = priority_labels.get(
            alert["severity"], alert["severity"].capitalize()
        )
        alert_rows.append(alert)

    return {
        "summary": dict(summary),
        "alerts": alert_rows,
        "categories": [dict(row) for row in categories],
        "category_labels": category_labels,
        "schools": [dict(row) for row in schools],
        "classes": [dict(row) for row in classes],
        "filters": {
            "category": category,
            "priority": priority,
            "school_id": str(school_id or ""),
            "class_id": str(class_id or ""),
            "student_name": student_name,
        },
    }


_SCHOOL_ATTENDANCE_CTE = """
    WITH attendance_by_student AS (
        SELECT student_id,
            100.0 * SUM(
                CASE WHEN status IN ('present', 'late') THEN 1 ELSE 0 END
            ) / COUNT(*) AS attendance_rate
        FROM attendance
        GROUP BY student_id
    )
"""


def _get_school_rows(connection, school_id=None):
    return connection.execute(
        _SCHOOL_ATTENDANCE_CTE
        + """
        SELECT schools.id, schools.name, schools.city, schools.state,
            (SELECT COUNT(*)
             FROM students
             JOIN classes ON classes.id = students.class_id
             WHERE classes.school_id = schools.id) AS student_count,
            (SELECT COUNT(*) FROM classes
             WHERE classes.school_id = schools.id) AS class_count,
            (SELECT COUNT(*) FROM teachers
             WHERE teachers.school_id = schools.id) AS teacher_count,
            (SELECT AVG(grades.score)
             FROM grades
             JOIN students ON students.id = grades.student_id
             JOIN classes ON classes.id = students.class_id
             WHERE classes.school_id = schools.id) AS average_grade,
            (SELECT AVG(attendance_by_student.attendance_rate)
             FROM attendance_by_student
             JOIN students
                ON students.id = attendance_by_student.student_id
             JOIN classes ON classes.id = students.class_id
             WHERE classes.school_id = schools.id) AS average_attendance
        FROM schools
        WHERE (? IS NULL OR schools.id = ?)
        ORDER BY schools.name
        """,
        (school_id, school_id),
    ).fetchall()


def get_schools_page_data(school_id=None):
    """Retorna totais gerais e indicadores calculados para cada escola."""
    connection = get_connection()
    try:
        summary = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM schools
                 WHERE (? IS NULL OR id = ?)) AS total_schools,
                (SELECT COUNT(*) FROM students
                 JOIN classes ON classes.id = students.class_id
                 WHERE (? IS NULL OR classes.school_id = ?)) AS total_students,
                (SELECT COUNT(*) FROM classes
                 WHERE (? IS NULL OR school_id = ?)) AS total_classes,
                (SELECT COUNT(*) FROM teachers
                 WHERE (? IS NULL OR school_id = ?)) AS total_teachers
            """,
            (school_id, school_id, school_id, school_id, school_id, school_id,
             school_id, school_id),
        ).fetchone()
        schools = _get_school_rows(connection, school_id)
    finally:
        connection.close()

    return {
        "summary": dict(summary),
        "schools": [dict(row) for row in schools],
    }


def get_school_detail_data(school_id):
    """Retorna os indicadores e as turmas de uma escola existente."""
    connection = get_connection()
    try:
        school_rows = _get_school_rows(connection, school_id)
        if not school_rows:
            return None

        classes = connection.execute(
            """
            SELECT classes.id, classes.name, classes.school_year, classes.shift,
                COUNT(students.id) AS student_count
            FROM classes
            LEFT JOIN students ON students.class_id = classes.id
            WHERE classes.school_id = ?
            GROUP BY classes.id, classes.name, classes.school_year, classes.shift
            ORDER BY classes.school_year, classes.name
            """,
            (school_id,),
        ).fetchall()
    finally:
        connection.close()

    school = dict(school_rows[0])
    shift_labels = {
        "morning": "Manhã",
        "afternoon": "Tarde",
        "evening": "Noite",
    }
    class_rows = []
    for row in classes:
        class_data = dict(row)
        class_data["shift_label"] = shift_labels.get(
            class_data["shift"], class_data["shift"].capitalize()
        )
        class_rows.append(class_data)

    return {
        "school": school,
        "classes": class_rows,
    }


def _get_class_rows(connection, class_id=None, school_id=None, class_name=""):
    return connection.execute(
        _STUDENT_METRICS_CTE
        + """
        SELECT classes.id, classes.name, classes.school_id,
            schools.name AS school_name, classes.school_year, classes.shift,
            COUNT(student_metrics.id) AS student_count,
            AVG(student_metrics.average_grade) AS average_grade,
            AVG(student_metrics.attendance_rate) AS average_attendance
        FROM classes
        JOIN schools ON schools.id = classes.school_id
        LEFT JOIN student_metrics ON student_metrics.class_id = classes.id
        WHERE (? IS NULL OR classes.id = ?)
          AND (? IS NULL OR classes.school_id = ?)
          AND (? = '' OR classes.name LIKE ? COLLATE NOCASE)
        GROUP BY classes.id, classes.name, classes.school_id, schools.name,
            classes.school_year, classes.shift
        ORDER BY schools.name, classes.school_year, classes.name
        """,
        (
            class_id,
            class_id,
            school_id,
            school_id,
            class_name,
            "%{}%".format(class_name),
        ),
    ).fetchall()


def get_classes_page_data(school_id="", class_name=""):
    """Retorna resumo, filtros e métricas das turmas cadastradas."""
    school_id = _positive_integer(school_id)
    class_name = (class_name or "").strip()

    connection = get_connection()
    try:
        summary = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM classes) AS total_classes,
                (SELECT COUNT(*) FROM students) AS total_students,
                (SELECT COUNT(*) FROM schools) AS total_schools
            """
        ).fetchone()
        classes = _get_class_rows(
            connection, school_id=school_id, class_name=class_name
        )
        schools = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
    finally:
        connection.close()

    return {
        "summary": dict(summary),
        "classes": [dict(row) for row in classes],
        "schools": [dict(row) for row in schools],
        "filters": {
            "school_id": str(school_id or ""),
            "class_name": class_name,
        },
    }


def get_class_detail_data(class_id):
    """Retorna uma turma e os indicadores atuais de seus alunos."""
    connection = get_connection()
    try:
        class_rows = _get_class_rows(connection, class_id=class_id)
        if not class_rows:
            return None

        students = connection.execute(
            _STUDENT_METRICS_CTE
            + """
            SELECT id, full_name, average_grade, attendance_rate, situation
            FROM student_metrics
            WHERE class_id = ?
            ORDER BY full_name COLLATE NOCASE
            """,
            (class_id,),
        ).fetchall()
    finally:
        connection.close()

    class_detail = dict(class_rows[0])
    shift_labels = {
        "morning": "Manhã",
        "afternoon": "Tarde",
        "evening": "Noite",
    }
    class_detail["shift_label"] = shift_labels.get(
        class_detail["shift"], class_detail["shift"].capitalize()
    )

    student_rows = []
    for row in students:
        student = dict(row)
        student["situation_label"] = (
            "Acompanhamento" if student["situation"] == "attention" else "Regular"
        )
        student_rows.append(student)

    return {
        "class_detail": class_detail,
        "students": student_rows,
    }


def get_teachers_page_data(school_id="", teacher_name=""):
    """Retorna professores filtrados e suas relações existentes com turmas e disciplinas."""
    school_id = _positive_integer(school_id)
    teacher_name = (teacher_name or "").strip()

    connection = get_connection()
    try:
        summary = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM teachers) AS total_teachers,
                (SELECT COUNT(*) FROM schools) AS total_schools,
                (SELECT COUNT(DISTINCT class_id) FROM class_subjects)
                    AS related_classes
            """
        ).fetchone()

        teacher_rows = connection.execute(
            """
            SELECT teachers.id, teachers.full_name, teachers.school_id,
                schools.name AS school_name,
                (SELECT COUNT(DISTINCT class_id) FROM class_subjects
                 WHERE class_subjects.teacher_id = teachers.id) AS class_count,
                (SELECT COUNT(DISTINCT subject_id) FROM class_subjects
                 WHERE class_subjects.teacher_id = teachers.id) AS subject_count
            FROM teachers
            JOIN schools ON schools.id = teachers.school_id
            WHERE (? IS NULL OR teachers.school_id = ?)
              AND (? = '' OR teachers.full_name LIKE ? COLLATE NOCASE)
            ORDER BY teachers.full_name COLLATE NOCASE
            """,
            (
                school_id,
                school_id,
                teacher_name,
                "%{}%".format(teacher_name),
            ),
        ).fetchall()

        subject_rows = connection.execute(
            """
            SELECT DISTINCT class_subjects.teacher_id, subjects.name
            FROM class_subjects
            JOIN subjects ON subjects.id = class_subjects.subject_id
            ORDER BY subjects.name
            """
        ).fetchall()
        schools = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
    finally:
        connection.close()

    subjects_by_teacher = {}
    for row in subject_rows:
        subjects_by_teacher.setdefault(row["teacher_id"], []).append(row["name"])

    teachers = []
    for row in teacher_rows:
        teacher = dict(row)
        teacher["subjects"] = subjects_by_teacher.get(teacher["id"], [])
        teachers.append(teacher)

    return {
        "summary": dict(summary),
        "teachers": teachers,
        "schools": [dict(row) for row in schools],
        "filters": {
            "school_id": str(school_id or ""),
            "teacher_name": teacher_name,
        },
    }


def get_teacher_detail_data(teacher_id):
    """Retorna somente os dados e vínculos disponíveis de um professor."""
    connection = get_connection()
    try:
        teacher_row = connection.execute(
            """
            SELECT teachers.id, teachers.full_name, teachers.school_id,
                schools.name AS school_name
            FROM teachers
            JOIN schools ON schools.id = teachers.school_id
            WHERE teachers.id = ?
            """,
            (teacher_id,),
        ).fetchone()
        if teacher_row is None:
            return None

        classes = connection.execute(
            """
            SELECT classes.id, classes.name, classes.school_year, classes.shift,
                COUNT(DISTINCT students.id) AS student_count
            FROM class_subjects
            JOIN classes ON classes.id = class_subjects.class_id
            LEFT JOIN students ON students.class_id = classes.id
            WHERE class_subjects.teacher_id = ?
            GROUP BY classes.id, classes.name, classes.school_year, classes.shift
            ORDER BY classes.school_year, classes.name
            """,
            (teacher_id,),
        ).fetchall()
        subjects = connection.execute(
            """
            SELECT DISTINCT subjects.id, subjects.name
            FROM class_subjects
            JOIN subjects ON subjects.id = class_subjects.subject_id
            WHERE class_subjects.teacher_id = ?
            ORDER BY subjects.name
            """,
            (teacher_id,),
        ).fetchall()
    finally:
        connection.close()

    teacher = dict(teacher_row)
    shift_labels = {
        "morning": "Manhã",
        "afternoon": "Tarde",
        "evening": "Noite",
    }
    class_rows = []
    for row in classes:
        class_data = dict(row)
        class_data["shift_label"] = shift_labels.get(
            class_data["shift"], class_data["shift"].capitalize()
        )
        class_rows.append(class_data)

    return {
        "teacher": teacher,
        "classes": class_rows,
        "subjects": [dict(row) for row in subjects],
    }


_MONITORING_METRICS_CTE = _STUDENT_METRICS_CTE + """
    , participation_by_student AS (
        SELECT student_id, AVG(score) AS average_participation
        FROM participation
        GROUP BY student_id
    ),
    monitoring_metrics AS (
        SELECT student_metrics.*,
            participation_by_student.average_participation,
            CASE
                WHEN student_metrics.attendance_rate < 75
                 AND student_metrics.average_grade < 6 THEN 'both'
                WHEN student_metrics.attendance_rate < 75 THEN 'attendance'
                WHEN student_metrics.average_grade < 6 THEN 'performance'
                WHEN student_metrics.attendance_rate IS NULL
                  OR student_metrics.average_grade IS NULL THEN 'insufficient'
                ELSE 'regular'
            END AS reason
        FROM student_metrics
        LEFT JOIN participation_by_student
            ON participation_by_student.student_id = student_metrics.id
    )
"""


_SUBJECT_MONITORING_METRICS_CTE = """
    WITH selected_subject AS (
        SELECT ? AS subject_id
    ),
    attendance_by_student AS (
        SELECT student_id,
            100.0 * SUM(
                CASE WHEN status IN ('present', 'late') THEN 1 ELSE 0 END
            ) / COUNT(*) AS attendance_rate
        FROM attendance
        GROUP BY student_id
    ),
    grades_by_student AS (
        SELECT grades.student_id, AVG(grades.score) AS average_grade
        FROM grades
        JOIN class_subjects ON class_subjects.id = grades.class_subject_id
        JOIN selected_subject
            ON selected_subject.subject_id = class_subjects.subject_id
        GROUP BY grades.student_id
    ),
    participation_by_student AS (
        SELECT participation.student_id,
            AVG(participation.score) AS average_participation
        FROM participation
        JOIN class_subjects
            ON class_subjects.id = participation.class_subject_id
        JOIN selected_subject
            ON selected_subject.subject_id = class_subjects.subject_id
        GROUP BY participation.student_id
    ),
    student_metrics AS (
        SELECT students.id, students.full_name,
            schools.id AS school_id, schools.name AS school_name,
            classes.id AS class_id, classes.name AS class_name,
            classes.school_year,
            attendance_by_student.attendance_rate,
            grades_by_student.average_grade,
            CASE
                WHEN (attendance_by_student.attendance_rate IS NOT NULL
                      AND attendance_by_student.attendance_rate < 75)
                  OR (grades_by_student.average_grade IS NOT NULL
                      AND grades_by_student.average_grade < 6)
                THEN 'attention'
                ELSE 'regular'
            END AS situation,
            participation_by_student.average_participation
        FROM students
        JOIN classes ON classes.id = students.class_id
        JOIN schools ON schools.id = classes.school_id
        JOIN class_subjects ON class_subjects.class_id = classes.id
        JOIN selected_subject
            ON selected_subject.subject_id = class_subjects.subject_id
        LEFT JOIN attendance_by_student
            ON attendance_by_student.student_id = students.id
        LEFT JOIN grades_by_student
            ON grades_by_student.student_id = students.id
        LEFT JOIN participation_by_student
            ON participation_by_student.student_id = students.id
    ),
    monitoring_metrics AS (
        SELECT student_metrics.*,
            CASE
                WHEN student_metrics.attendance_rate < 75
                 AND student_metrics.average_grade < 6 THEN 'both'
                WHEN student_metrics.attendance_rate < 75 THEN 'attendance'
                WHEN student_metrics.average_grade < 6 THEN 'performance'
                WHEN student_metrics.attendance_rate IS NULL
                  OR student_metrics.average_grade IS NULL THEN 'insufficient'
                ELSE 'regular'
            END AS reason
        FROM student_metrics
    )
"""


def get_student_monitoring_page_data(
    search="", school_id="", class_id="", situation="", subject_id=""
):
    """Retorna indicadores integrados de frequência, desempenho e participação."""
    search = (search or "").strip()
    school_id = _positive_integer(school_id)
    class_id = _positive_integer(class_id)
    subject_id = _positive_integer(subject_id)
    if situation not in ("attention", "regular"):
        situation = ""

    if subject_id is None:
        metrics_cte = _MONITORING_METRICS_CTE
        cte_values = ()
    else:
        metrics_cte = _SUBJECT_MONITORING_METRICS_CTE
        cte_values = (subject_id,)

    filter_sql = """
        WHERE (? = '' OR monitoring_metrics.full_name LIKE ? COLLATE NOCASE)
          AND (? IS NULL OR monitoring_metrics.school_id = ?)
          AND (? IS NULL OR monitoring_metrics.class_id = ?)
          AND (? = '' OR monitoring_metrics.situation = ?)
    """
    filter_values = (
        search,
        "%{}%".format(search),
        school_id,
        school_id,
        class_id,
        class_id,
        situation,
        situation,
    )

    connection = get_connection()
    try:
        summary = connection.execute(
            metrics_cte
            + """
            SELECT COUNT(*) AS total_students_analyzed,
                COALESCE(SUM(CASE WHEN situation = 'attention' THEN 1 ELSE 0 END), 0)
                    AS attention_students,
                COALESCE(SUM(CASE WHEN situation = 'regular' THEN 1 ELSE 0 END), 0)
                    AS regular_students,
                AVG(average_grade) AS average_grade,
                AVG(attendance_rate) AS average_attendance,
                AVG(average_participation) AS average_participation,
                COALESCE(SUM(CASE WHEN attendance_rate < 75 THEN 1 ELSE 0 END), 0)
                    AS low_attendance_students,
                COALESCE(SUM(CASE WHEN average_grade < 6 THEN 1 ELSE 0 END), 0)
                    AS low_performance_students,
                COALESCE(SUM(
                    CASE WHEN attendance_rate < 75 AND average_grade < 6
                         THEN 1 ELSE 0 END
                ), 0) AS both_issues_students
            FROM monitoring_metrics
            """
            + filter_sql,
            cte_values + filter_values,
        ).fetchone()

        students = connection.execute(
            metrics_cte
            + """
            SELECT id, full_name, school_id, school_name, class_id, class_name,
                average_grade, attendance_rate, average_participation,
                situation, reason
            FROM monitoring_metrics
            """
            + filter_sql
            + """
            ORDER BY full_name COLLATE NOCASE
            """,
            cte_values + filter_values,
        ).fetchall()

        schools = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
        classes = connection.execute(
            """
            SELECT classes.id, classes.name, schools.name AS school_name
            FROM classes
            JOIN schools ON schools.id = classes.school_id
            WHERE (? IS NULL OR classes.school_id = ?)
            ORDER BY schools.name, classes.name
            """,
            (school_id, school_id),
        ).fetchall()
        subjects = connection.execute(
            "SELECT id, name FROM subjects ORDER BY name"
        ).fetchall()
        class_subjects = connection.execute(
            """
            SELECT class_subjects.class_id,
                GROUP_CONCAT(subjects.name, ', ') AS subject_names
            FROM class_subjects
            JOIN subjects ON subjects.id = class_subjects.subject_id
            WHERE (? IS NULL OR class_subjects.subject_id = ?)
            GROUP BY class_subjects.class_id
            """,
            (subject_id, subject_id),
        ).fetchall()
    finally:
        connection.close()

    summary_data = dict(summary)
    reason_labels = {
        "attendance": "Frequência baixa",
        "performance": "Desempenho baixo",
        "both": "Frequência e desempenho",
        "insufficient": "Sem dados suficientes",
        "regular": "Dentro dos parâmetros",
    }
    situation_labels = {
        "attention": "Acompanhamento",
        "regular": "Regular",
    }
    subject_names_by_class = {
        row["class_id"]: row["subject_names"] for row in class_subjects
    }
    student_rows = []
    for row in students:
        student = dict(row)
        student["situation_label"] = situation_labels[student["situation"]]
        student["reason_label"] = reason_labels[student["reason"]]
        student["subject_names"] = subject_names_by_class.get(student["class_id"])
        student_rows.append(student)

    analyzed = summary_data["total_students_analyzed"]
    analysis = [
        {
            "label": "Frequência baixa",
            "count": summary_data["low_attendance_students"],
            "percentage": 100.0 * summary_data["low_attendance_students"] / analyzed
            if analyzed
            else 0,
            "style": "attendance",
        },
        {
            "label": "Desempenho baixo",
            "count": summary_data["low_performance_students"],
            "percentage": 100.0 * summary_data["low_performance_students"] / analyzed
            if analyzed
            else 0,
            "style": "performance",
        },
        {
            "label": "Frequência e desempenho",
            "count": summary_data["both_issues_students"],
            "percentage": 100.0 * summary_data["both_issues_students"] / analyzed
            if analyzed
            else 0,
            "style": "combined",
        },
        {
            "label": "Alunos regulares",
            "count": summary_data["regular_students"],
            "percentage": 100.0 * summary_data["regular_students"] / analyzed
            if analyzed
            else 0,
            "style": "regular",
        },
    ]

    return {
        "summary": summary_data,
        "analysis": analysis,
        "students": student_rows,
        "schools": [dict(row) for row in schools],
        "classes": [dict(row) for row in classes],
        "subjects": [dict(row) for row in subjects],
        "filters": {
            "search": search,
            "school_id": str(school_id or ""),
            "class_id": str(class_id or ""),
            "situation": situation,
            "subject_id": str(subject_id or ""),
        },
    }


def get_reports_page_data(school_id="", class_id=""):
    """Retorna indicadores e distribuições para o recorte escolar selecionado."""
    school_id = _positive_integer(school_id)
    class_id = _positive_integer(class_id)
    filter_sql = """
        WHERE (? IS NULL OR monitoring_metrics.school_id = ?)
          AND (? IS NULL OR monitoring_metrics.class_id = ?)
    """
    filter_values = (school_id, school_id, class_id, class_id)

    connection = get_connection()
    try:
        summary = connection.execute(
            _MONITORING_METRICS_CTE
            + """
            SELECT COUNT(*) AS total_students,
                COALESCE(SUM(CASE WHEN situation = 'attention' THEN 1 ELSE 0 END), 0)
                    AS attention_students,
                COALESCE(SUM(CASE WHEN situation = 'regular' THEN 1 ELSE 0 END), 0)
                    AS regular_students,
                AVG(average_grade) AS average_grade,
                AVG(attendance_rate) AS average_attendance,
                COALESCE(SUM(CASE WHEN attendance_rate < 75 THEN 1 ELSE 0 END), 0)
                    AS low_attendance_students,
                COALESCE(SUM(CASE WHEN average_grade < 6 THEN 1 ELSE 0 END), 0)
                    AS low_performance_students,
                COALESCE(SUM(
                    CASE WHEN attendance_rate < 75 AND average_grade < 6
                         THEN 1 ELSE 0 END
                ), 0) AS both_problem_students,
                COALESCE(SUM(CASE WHEN reason = 'attendance' THEN 1 ELSE 0 END), 0)
                    AS frequency_only_students,
                COALESCE(SUM(CASE WHEN reason = 'performance' THEN 1 ELSE 0 END), 0)
                    AS performance_only_students,
                COALESCE(SUM(CASE WHEN reason = 'both' THEN 1 ELSE 0 END), 0)
                    AS both_issue_students
            FROM monitoring_metrics
            """
            + filter_sql,
            filter_values,
        ).fetchone()

        school_reports = connection.execute(
            _MONITORING_METRICS_CTE
            + """
            SELECT school_id, school_name, COUNT(*) AS student_count,
                AVG(average_grade) AS average_grade,
                AVG(attendance_rate) AS average_attendance,
                COALESCE(SUM(CASE WHEN situation = 'attention' THEN 1 ELSE 0 END), 0)
                    AS attention_students,
                COALESCE(SUM(CASE WHEN situation = 'regular' THEN 1 ELSE 0 END), 0)
                    AS regular_students,
                COALESCE(SUM(CASE WHEN attendance_rate < 75 THEN 1 ELSE 0 END), 0)
                    AS low_attendance_students
            FROM monitoring_metrics
            """
            + filter_sql
            + """
            GROUP BY school_id, school_name
            ORDER BY school_name
            """,
            filter_values,
        ).fetchall()

        class_reports = connection.execute(
            _MONITORING_METRICS_CTE
            + """
            SELECT school_id, school_name, class_id, class_name, school_year,
                COUNT(*) AS student_count,
                AVG(average_grade) AS average_grade,
                AVG(attendance_rate) AS average_attendance,
                COALESCE(SUM(CASE WHEN situation = 'attention' THEN 1 ELSE 0 END), 0)
                    AS attention_students,
                COALESCE(SUM(CASE WHEN situation = 'regular' THEN 1 ELSE 0 END), 0)
                    AS regular_students,
                COALESCE(SUM(CASE WHEN attendance_rate < 75 THEN 1 ELSE 0 END), 0)
                    AS low_attendance_students
            FROM monitoring_metrics
            """
            + filter_sql
            + """
            GROUP BY school_id, school_name, class_id, class_name, school_year
            ORDER BY school_name, school_year, class_name
            """,
            filter_values,
        ).fetchall()

        alert_count = connection.execute(
            """
            SELECT COUNT(*) AS total_alerts
            FROM alerts
            JOIN students ON students.id = alerts.student_id
            JOIN classes ON classes.id = students.class_id
            WHERE (? IS NULL OR classes.school_id = ?)
              AND (? IS NULL OR classes.id = ?)
            """,
            filter_values,
        ).fetchone()["total_alerts"]

        schools = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
        classes = connection.execute(
            """
            SELECT classes.id, classes.name, schools.name AS school_name
            FROM classes
            JOIN schools ON schools.id = classes.school_id
            WHERE (? IS NULL OR classes.school_id = ?)
            ORDER BY schools.name, classes.name
            """,
            (school_id, school_id),
        ).fetchall()
    finally:
        connection.close()

    summary_data = dict(summary)
    summary_data["total_alerts"] = alert_count
    return {
        "summary": summary_data,
        "school_reports": [dict(row) for row in school_reports],
        "class_reports": [dict(row) for row in class_reports],
        "schools": [dict(row) for row in schools],
        "classes": [dict(row) for row in classes],
        "filters": {
            "school_id": str(school_id or ""),
            "class_id": str(class_id or ""),
        },
    }


COMMUNICATION_TYPE_LABELS = {
    "family": "Família",
    "school": "Escola",
    "management": "Gestão",
}
COMMUNICATION_STATUS_LABELS = {
    "sent": "Enviada",
    "unread": "Não lida",
    "read": "Lida",
}
COMMUNICATION_DIRECTION_LABELS = {
    "sent": "Enviada",
    "received": "Recebida",
}


def get_communication_school_options():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_message_recipients(user):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT users.id, users.username, users.role, users.school_id,
                COALESCE(teachers.full_name, users.username) AS display_name
            FROM users
            LEFT JOIN teachers ON teachers.id = users.teacher_id
            WHERE users.active = 1
              AND users.role IN ('diretor', 'professor')
              AND users.id != ?
              AND (? = 'admin' OR users.school_id = ?)
            ORDER BY users.role, display_name
            """,
            (user["id"], user["role"], user.get("school_id")),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_communications_page_data(
    message_type="", status="", school_id="", message_date="",
    user_id=None, is_admin=False,
):
    """Retorna comunicações persistidas e os totais do recorte filtrado."""
    message_type = (message_type or "").strip()
    status = (status or "").strip()
    message_date = (message_date or "").strip()
    if message_type not in COMMUNICATION_TYPE_LABELS:
        message_type = ""
    if status not in COMMUNICATION_STATUS_LABELS:
        status = ""
    school_id = _positive_integer(school_id)
    try:
        message_date = datetime.strptime(message_date, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        message_date = ""

    filter_sql = """
        WHERE (? = '' OR communications.message_type = ?)
          AND (? = '' OR
              CASE WHEN communications.recipient_user_id = ?
                   THEN CASE WHEN communications.recipient_read = 1
                             THEN 'read' ELSE 'unread' END
                   ELSE communications.status END = ?)
          AND (? IS NULL OR communications.school_id = ?)
          AND (? = '' OR DATE(communications.created_at) = ?)
          AND (
              communications.sender_user_id = ?
              OR communications.recipient_user_id = ?
              OR (? = 1 AND communications.sender_user_id IS NULL
                         AND communications.recipient_user_id IS NULL)
          )
    """
    filter_values = (
        message_type,
        message_type,
        status,
        user_id,
        status,
        school_id,
        school_id,
        message_date,
        message_date,
        user_id,
        user_id,
        int(is_admin),
    )

    connection = get_connection()
    try:
        summary = connection.execute(
            """
            SELECT COUNT(*) AS total_messages,
                COALESCE(SUM(
                    CASE WHEN (
                        (recipient_user_id = ? AND recipient_read = 0)
                        OR (recipient_user_id IS NULL
                            AND direction = 'received' AND status = 'unread')
                    )
                         THEN 1 ELSE 0 END
                ), 0) AS unread_messages,
                COALESCE(SUM(
                    CASE WHEN sender_user_id = ? OR direction = 'sent'
                         THEN 1 ELSE 0 END
                ), 0)
                    AS sent_messages,
                COALESCE(SUM(
                    CASE WHEN recipient_user_id = ? OR direction = 'received'
                         THEN 1 ELSE 0 END
                ), 0)
                    AS received_messages
            FROM communications
            """
            + filter_sql,
            (user_id, user_id, user_id) + filter_values,
        ).fetchone()

        message_rows = connection.execute(
            """
            SELECT communications.id, communications.school_id,
                CASE WHEN communications.recipient_user_id = ?
                     THEN sender.username ELSE communications.recipient END
                    AS recipient,
                communications.message, communications.message_type,
                CASE WHEN communications.recipient_user_id = ?
                     THEN 'received' ELSE communications.direction END AS direction,
                CASE WHEN communications.recipient_user_id = ?
                     THEN CASE WHEN communications.recipient_read = 1
                               THEN 'read' ELSE 'unread' END
                     ELSE communications.status END AS status,
                communications.created_at, schools.name AS school_name,
                communications.subject
            FROM communications
            LEFT JOIN schools ON schools.id = communications.school_id
            LEFT JOIN users AS sender ON sender.id = communications.sender_user_id
            """
            + filter_sql
            + """
            ORDER BY communications.created_at DESC, communications.id DESC
            """,
            (user_id, user_id, user_id) + filter_values,
        ).fetchall()
        schools = connection.execute(
            "SELECT id, name FROM schools ORDER BY name"
        ).fetchall()
    finally:
        connection.close()

    messages = []
    for row in message_rows:
        communication = dict(row)
        communication["type_label"] = COMMUNICATION_TYPE_LABELS[
            communication["message_type"]
        ]
        communication["direction_label"] = COMMUNICATION_DIRECTION_LABELS[
            communication["direction"]
        ]
        communication["status_label"] = COMMUNICATION_STATUS_LABELS[
            communication["status"]
        ]
        messages.append(communication)

    return {
        "summary": dict(summary),
        "messages": messages,
        "schools": [dict(row) for row in schools],
        "type_options": [
            {"value": value, "label": label}
            for value, label in COMMUNICATION_TYPE_LABELS.items()
        ],
        "status_options": [
            {"value": value, "label": label}
            for value, label in COMMUNICATION_STATUS_LABELS.items()
        ],
        "filters": {
            "message_type": message_type,
            "status": status,
            "school_id": str(school_id or ""),
            "message_date": message_date,
        },
    }


def create_direct_message(sender_user_id, recipient_user_id, school_id, subject, message):
    connection = get_connection()
    try:
        with connection:
            recipient = connection.execute(
                "SELECT username FROM users WHERE id = ? AND active = 1",
                (recipient_user_id,),
            ).fetchone()
            if recipient is None:
                raise ValueError("Destinatário inválido.")
            cursor = connection.execute(
                """
                INSERT INTO communications (
                    school_id, sender_user_id, recipient_user_id, recipient_read,
                    recipient, subject, message, message_type, direction, status
                ) VALUES (?, ?, ?, 0, ?, ?, ?, 'management', 'sent', 'sent')
                """,
                (
                    school_id,
                    sender_user_id,
                    recipient_user_id,
                    recipient["username"],
                    subject,
                    message,
                ),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def create_communication(school_id, recipient, subject, message, message_type, direction):
    """Persiste uma comunicação enviada ou recebida pelo formulário."""
    if message_type not in COMMUNICATION_TYPE_LABELS:
        raise ValueError("Tipo de comunicação inválido.")
    if direction not in COMMUNICATION_DIRECTION_LABELS:
        raise ValueError("Direção de comunicação inválida.")

    status = "sent" if direction == "sent" else "unread"
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO communications (
                    school_id, recipient, subject, message,
                    message_type, direction, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (school_id, recipient, subject, message, message_type, direction, status),
            )
            return cursor.lastrowid
    finally:
        connection.close()


def get_communication_detail_data(communication_id, user_id=None, is_admin=False):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT communications.id, communications.school_id,
                CASE WHEN communications.recipient_user_id = ?
                     THEN sender.username ELSE communications.recipient END
                    AS recipient,
                communications.subject,
                communications.message, communications.message_type,
                CASE WHEN communications.recipient_user_id = ?
                     THEN 'received' ELSE communications.direction END AS direction,
                CASE WHEN communications.recipient_user_id = ?
                     THEN CASE WHEN communications.recipient_read = 1
                               THEN 'read' ELSE 'unread' END
                     ELSE communications.status END AS status,
                communications.created_at, schools.name AS school_name,
                communications.sender_user_id, communications.recipient_user_id,
                sender.username AS sender_username
            FROM communications
            LEFT JOIN schools ON schools.id = communications.school_id
            LEFT JOIN users AS sender ON sender.id = communications.sender_user_id
            WHERE communications.id = ?
              AND (
                  communications.sender_user_id = ?
                  OR communications.recipient_user_id = ?
                  OR (? = 1 AND communications.sender_user_id IS NULL
                             AND communications.recipient_user_id IS NULL)
              )
            """,
            (user_id, user_id, user_id, communication_id, user_id, user_id, int(is_admin)),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    communication = dict(row)
    communication["type_label"] = COMMUNICATION_TYPE_LABELS[
        communication["message_type"]
    ]
    communication["direction_label"] = COMMUNICATION_DIRECTION_LABELS[
        communication["direction"]
    ]
    communication["status_label"] = COMMUNICATION_STATUS_LABELS[
        communication["status"]
    ]
    return {"communication": communication}


def mark_communication_read(communication_id, user_id=None, is_admin=False):
    connection = get_connection()
    try:
        with connection:
            row = connection.execute(
                """
                SELECT direction, status, sender_user_id, recipient_user_id,
                    recipient_read
                FROM communications WHERE id = ?
                """,
                (communication_id,),
            ).fetchone()
            if row is None:
                return False
            if row["recipient_user_id"] is not None:
                if row["recipient_user_id"] != user_id:
                    return False
                if not row["recipient_read"]:
                    connection.execute(
                        "UPDATE communications SET recipient_read = 1 WHERE id = ?",
                        (communication_id,),
                    )
                return True
            if not is_admin:
                return False
            if row["direction"] == "received" and row["status"] == "unread":
                connection.execute(
                    "UPDATE communications SET status = 'read' WHERE id = ?",
                    (communication_id,),
                )
        return True
    finally:
        connection.close()