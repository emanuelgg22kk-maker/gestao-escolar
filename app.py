import os
import math
import secrets
import sqlite3
import uuid
from functools import wraps
from pathlib import Path
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    g,
    Response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from database import (
    create_direct_message,
    create_class,
    create_learning_material,
    create_school,
    create_student,
    create_teacher,
    create_user,
    get_class_subject_assignment,
    get_dashboard_data,
    get_alerts_page_data,
    get_communication_detail_data,
    get_communications_page_data,
    get_management_form_data,
    get_message_recipients,
    get_subject_assignments,
    get_user_by_id,
    get_user_by_username,
    get_users_page_data,
    get_learning_materials,
    get_learning_material,
    get_student_by_id,
    get_students_available_for_class,
    get_student_profile_data,
    record_student_attendance,
    record_student_grade,
    get_students_page_data,
    get_school_detail_data,
    get_schools_page_data,
    get_class_detail_data,
    get_classes_page_data,
    get_teacher_detail_data,
    get_teachers_page_data,
    get_student_monitoring_page_data,
    get_reports_page_data,
    initialize_database,
    mark_communication_read,
    assign_student_to_class,
    save_class_subject,
    update_school,
    update_student,
    update_subject,
    update_teacher,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
UPLOAD_FOLDER = Path(app.root_path) / "uploads"
ALLOWED_UPLOADS = {
    "mp4": "video",
    "webm": "video",
    "mov": "video",
    "jpg": "image",
    "jpeg": "image",
    "png": "image",
    "gif": "image",
    "webp": "image",
    "mp3": "audio",
    "wav": "audio",
    "ogg": "audio",
    "m4a": "audio",
    "pdf": "file",
    "doc": "file",
    "docx": "file",
    "ppt": "file",
    "pptx": "file",
}

initialize_database()
LOGIN_REPORT_PATH = Path(app.root_path) / "logins_disponiveis.txt"
USER_ROLE_LABELS = {
    "admin": "Administrador",
    "diretor": "Diretor de escola",
    "professor": "Professor",
    "aluno": "Aluno",
    "responsavel": "Responsável",
}


def update_login_report():
    users = get_users_page_data()
    lines = [
        "LOGINS CADASTRADOS - GESTAO ESCOLAR",
        "Atualizado em: {}".format(
            datetime.now().astimezone().isoformat(timespec="seconds")
        ),
        "Este arquivo lista usuarios e perfis. Senhas nao sao exibidas.",
        "",
        "Usuario | Tipo de usuario",
        "--------|----------------",
    ]
    lines.extend(
        "{} | {}".format(user["username"], USER_ROLE_LABELS[user["role"]])
        for user in users
    )
    content = "\n".join(lines) + "\n"
    LOGIN_REPORT_PATH.write_text(content, encoding="utf-8")
    return content


update_login_report()


def require_role(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None or user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _permitted_school_id(user, requested_id):
    if user["role"] == "admin":
        try:
            return int(requested_id)
        except (TypeError, ValueError):
            return None
    if user["role"] == "diretor":
        if requested_id and str(user["school_id"]) != str(requested_id):
            return None
        return user["school_id"]
    return None


def _school_scope(user, requested_id=""):
    if user["role"] == "admin":
        return requested_id or None
    return user["school_id"]


def _management_view_data(user):
    data = get_management_form_data()
    if user["role"] == "admin":
        return data

    assignments = get_subject_assignments(user)
    class_ids = {assignment["class_id"] for assignment in assignments}
    subject_ids = {assignment["subject_id"] for assignment in assignments}
    if user["role"] == "diretor":
        data["schools"] = [
            item for item in data["schools"] if item["id"] == user["school_id"]
        ]
        data["classes"] = [
            item for item in data["classes"] if item["school_id"] == user["school_id"]
        ]
        data["teachers"] = [
            item
            for item in data["teachers"]
            if item["school_id"] == user["school_id"]
        ]
        data["students"] = [
            item
            for item in data["students"]
            if item["school_id"] == user["school_id"]
        ]
    else:
        data["schools"] = []
        data["classes"] = [
            item for item in data["classes"] if item["id"] in class_ids
        ]
        data["teachers"] = [
            item for item in data["teachers"] if item["id"] == user["teacher_id"]
        ]
        data["students"] = [
            item for item in data["students"] if item["class_id"] in class_ids
        ]
    data["subjects"] = [
        item for item in data["subjects"] if item["id"] in subject_ids
    ]
    return data


def _class_is_accessible(user, class_id, form_data):
    class_record = next(
        (item for item in form_data["classes"] if item["id"] == class_id), None
    )
    if class_record is None:
        return False
    if user["role"] == "admin":
        return True
    if user["role"] == "diretor":
        return class_record["school_id"] == user["school_id"]
    if user["role"] == "professor":
        return any(
            assignment["class_id"] == class_id
            for assignment in get_subject_assignments(user)
        )
    return False


@app.context_processor
def inject_current_user():
    return {"current_user": getattr(g, "current_user", None)}


@app.before_request
def require_login():
    if request.endpoint in {"login", "logout", "static"}:
        return None
    user_id = session.get("user_id")
    if not user_id:
        session.clear()
        return redirect(url_for("login"))
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))
    g.current_user = user


@app.route("/")
def index():
    if session.get("user_id"):
        user = get_user_by_id(session["user_id"])
        if user and user["role"] in ("aluno", "responsavel"):
            return redirect(url_for("disciplinas"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["logged_in"] = True
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        error = "Usuário ou senha inválidos."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if g.current_user["role"] in ("aluno", "responsavel"):
        return redirect(url_for("disciplinas"))
    return render_template("dashboard.html", **get_dashboard_data())


@app.route("/comunicacao")
def comunicacao():
    page_data = get_communications_page_data(
        message_type=request.args.get("tipo", ""),
        status=request.args.get("status", ""),
        school_id=request.args.get("escola", ""),
        message_date=request.args.get("data", ""),
        user_id=g.current_user["id"],
        is_admin=g.current_user["role"] == "admin",
    )
    return render_template("comunicacao.html", **page_data)


@app.route("/comunicacao/nova", methods=["GET", "POST"])
@require_role("admin", "diretor", "professor")
def nova_comunicacao():
    recipients = get_message_recipients(g.current_user)
    form_data = {
        "recipient_user_id": "",
        "subject": "",
        "message": "",
    }
    errors = []

    if request.method == "POST":
        for field in form_data:
            form_data[field] = request.form.get(field, "").strip()

        for field, label in (("subject", "assunto"), ("message", "mensagem")):
            if not form_data[field]:
                errors.append("Informe {}.".format(label))

        try:
            recipient_user_id = int(form_data["recipient_user_id"])
        except ValueError:
            recipient_user_id = None
        recipient = next(
            (item for item in recipients if item["id"] == recipient_user_id), None
        )
        if recipient is None:
            errors.append("Selecione um professor ou diretor válido.")
        if len(form_data["subject"]) > 200:
            errors.append("O assunto deve ter no máximo 200 caracteres.")

        if not errors:
            communication_id = create_direct_message(
                sender_user_id=g.current_user["id"],
                recipient_user_id=recipient["id"],
                school_id=recipient["school_id"] or g.current_user["school_id"],
                subject=form_data["subject"],
                message=form_data["message"],
            )
            return redirect(
                url_for("comunicacao_detalhes", communication_id=communication_id)
            )

    return render_template(
        "comunicacao_nova.html",
        recipients=recipients,
        form_data=form_data,
        errors=errors,
    ), (400 if errors else 200)


@app.route("/comunicacao/<int:communication_id>")
def comunicacao_detalhes(communication_id):
    communication_data = get_communication_detail_data(
        communication_id,
        user_id=g.current_user["id"],
        is_admin=g.current_user["role"] == "admin",
    )
    if communication_data is None:
        abort(404)
    return render_template("comunicacao_detalhes.html", **communication_data)


@app.route("/comunicacao/<int:communication_id>/marcar-lida", methods=["POST"])
def marcar_comunicacao_lida(communication_id):
    if not mark_communication_read(
        communication_id,
        user_id=g.current_user["id"],
        is_admin=g.current_user["role"] == "admin",
    ):
        abort(404)
    return redirect(url_for("comunicacao_detalhes", communication_id=communication_id))


@app.route("/cadastros", methods=["GET", "POST"])
@require_role("admin", "diretor", "professor")
def cadastros():
    user = g.current_user
    data = _management_view_data(user)
    errors = []

    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "escola":
                if user["role"] != "admin":
                    abort(403)
                name = request.form.get("name", "").strip()
                city = request.form.get("city", "").strip()
                state = request.form.get("state", "").strip().upper()
                if not name or not city or len(state) != 2:
                    errors.append("Informe nome, cidade e estado (UF).")
                else:
                    create_school(name, city, state)
            elif action == "turma":
                if user["role"] != "admin":
                    abort(403)
                name = request.form.get("name", "").strip()
                school_id = int(request.form.get("school_id", ""))
                school_year = int(request.form.get("school_year", ""))
                shift = request.form.get("shift", "")
                if (
                    not name
                    or not any(item["id"] == school_id for item in data["schools"])
                    or school_year < 2000
                    or school_year > 2100
                ):
                    errors.append("Informe nome, escola e ano letivo válidos.")
                else:
                    create_class(school_id, name, school_year, shift)
            elif action == "professor":
                if user["role"] not in ("admin", "diretor"):
                    abort(403)
                full_name = request.form.get("full_name", "").strip()
                email = request.form.get("email", "").strip()
                school_id = _permitted_school_id(user, request.form.get("school_id"))
                if not full_name or not email or school_id is None:
                    errors.append("Informe nome, e-mail e uma escola permitida.")
                elif not any(item["id"] == school_id for item in data["schools"]):
                    errors.append("A escola selecionada não existe.")
                else:
                    create_teacher(school_id, full_name, email)
            elif action == "aluno":
                full_name = request.form.get("full_name", "").strip()
                enrollment_number = request.form.get("enrollment_number", "").strip()
                birth_date = request.form.get("birth_date", "").strip()
                class_id = int(request.form.get("class_id", ""))
                if not full_name or not enrollment_number:
                    errors.append("Informe nome e número de matrícula.")
                elif not _class_is_accessible(user, class_id, data):
                    errors.append("Selecione uma turma à qual você tenha acesso.")
                else:
                    create_student(class_id, full_name, enrollment_number, birth_date)
            elif action == "disciplina":
                class_id = int(request.form.get("class_id", ""))
                subject_name = request.form.get("subject_name", "").strip()
                teacher_value = request.form.get("teacher_id", "").strip()
                if user["role"] == "professor":
                    teacher_id = user["teacher_id"]
                else:
                    teacher_id = int(teacher_value)
                teacher = next(
                    (item for item in data["teachers"] if item["id"] == teacher_id),
                    None,
                )
                if not subject_name or teacher is None:
                    errors.append("Informe uma disciplina e selecione um professor.")
                elif not _class_is_accessible(user, class_id, data):
                    errors.append("Selecione uma turma à qual você tenha acesso.")
                elif user["role"] == "professor" and teacher_id != user["teacher_id"]:
                    abort(403)
                elif (
                    user["role"] == "diretor"
                    and teacher["school_id"] != user["school_id"]
                ):
                    abort(403)
                elif (
                    user["role"] == "admin"
                    and not any(
                        item["id"] == teacher_id for item in data["teachers"]
                    )
                ):
                    errors.append("O professor selecionado não existe.")
                else:
                    save_class_subject(class_id, subject_name, teacher_id)
            else:
                errors.append("Selecione uma operação de cadastro válida.")
        except ValueError:
            errors.append("Revise os campos numéricos e os dados informados.")
        except sqlite3.IntegrityError:
            errors.append(
                "Já existe um registro com esses dados ou uma relação incompatível."
            )

        if not errors:
            flash("Cadastro salvo com sucesso.", "success")
            return_to = request.form.get("return_to", "")
            if return_to in {"alunos", "professores", "turmas"}:
                return redirect(url_for(return_to))
            return redirect(url_for("cadastros"))
        data = _management_view_data(user)

    return render_template("cadastros.html", data=data, errors=errors), (
        400 if errors else 200
    )


@app.route("/cadastros/editar/<entity>/<int:record_id>", methods=["GET", "POST"])
@require_role("admin", "diretor", "professor")
def editar_cadastro(entity, record_id):
    user = g.current_user
    records = _management_view_data(user)
    entity_key = {
        "escola": "schools",
        "professor": "teachers",
        "aluno": "students",
        "disciplina": "subjects",
    }.get(entity)
    if entity_key is None:
        abort(404)
    permissions = {
        "escola": ("admin",),
        "professor": ("admin", "diretor"),
        "aluno": ("admin", "diretor", "professor"),
        "disciplina": ("admin", "diretor", "professor"),
    }
    if user["role"] not in permissions[entity]:
        abort(403)
    record = next(
        (item for item in records[entity_key] if item["id"] == record_id), None
    )
    if record is None:
        abort(404)
    if entity == "escola" and user["role"] != "admin":
        abort(403)
    if entity == "professor" and user["role"] == "diretor":
        if record["school_id"] != user["school_id"]:
            abort(403)
    if entity == "aluno":
        class_record = next(
            (item for item in records["classes"] if item["id"] == record["class_id"]),
            None,
        )
        if class_record is None or (
            user["role"] == "diretor"
            and class_record["school_id"] != user["school_id"]
        ):
            abort(403)
        if user["role"] == "professor" and not _class_is_accessible(
            user, record["class_id"], records
        ):
            abort(403)
    if entity == "disciplina" and user["role"] != "admin":
        permitted_subjects = {
            assignment["subject_id"] for assignment in get_subject_assignments(user)
        }
        if record_id not in permitted_subjects:
            abort(403)

    errors = []
    if request.method == "POST":
        try:
            if entity == "escola":
                name = request.form.get("name", "").strip()
                city = request.form.get("city", "").strip()
                state = request.form.get("state", "").strip().upper()
                if not name or not city or len(state) != 2:
                    errors.append("Informe nome, cidade e estado (UF).")
                else:
                    update_school(record_id, name, city, state)
            elif entity == "professor":
                full_name = request.form.get("full_name", "").strip()
                email = request.form.get("email", "").strip()
                school_id = _permitted_school_id(user, request.form.get("school_id"))
                if not full_name or not email or school_id is None:
                    errors.append("Informe nome, e-mail e uma escola permitida.")
                elif user["role"] == "diretor" and school_id != record["school_id"]:
                    abort(403)
                else:
                    update_teacher(record_id, full_name, email, school_id)
            elif entity == "aluno":
                class_id = int(request.form.get("class_id", ""))
                full_name = request.form.get("full_name", "").strip()
                enrollment_number = request.form.get("enrollment_number", "").strip()
                birth_date = request.form.get("birth_date", "").strip()
                if not full_name or not enrollment_number:
                    errors.append("Informe nome e número de matrícula.")
                elif not _class_is_accessible(user, class_id, records):
                    errors.append("Selecione uma turma à qual você tenha acesso.")
                else:
                    update_student(
                        record_id, class_id, full_name, enrollment_number, birth_date
                    )
            else:
                name = request.form.get("name", "").strip()
                if not name:
                    errors.append("Informe o nome da disciplina.")
                else:
                    update_subject(record_id, name)
        except ValueError:
            errors.append("Revise os campos numéricos e os dados informados.")
        except sqlite3.IntegrityError:
            errors.append("Já existe um registro com esses dados.")

        if not errors:
            flash("Alterações salvas com sucesso.", "success")
            return redirect(url_for("cadastros"))

    return render_template(
        "cadastro_editar.html",
        entity=entity,
        record=record,
        data=records,
        errors=errors,
    ), (400 if errors else 200)


@app.route("/usuarios", methods=["GET", "POST"])
@require_role("admin")
def usuarios():
    data = get_management_form_data()
    errors = []
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        school_id = teacher_id = student_id = None
        if len(username) < 3 or len(password) < 8:
            errors.append("Usuário deve ter 3 caracteres e senha no mínimo 8.")
        if role not in ("admin", "diretor", "professor", "aluno", "responsavel"):
            errors.append("Selecione um perfil válido.")
        if role == "admin":
            pass
        elif role == "diretor":
            school_id = _permitted_school_id(g.current_user, request.form.get("school_id"))
            if school_id is None:
                errors.append("Selecione uma escola válida.")
        elif role == "professor":
            try:
                teacher_id = int(request.form.get("teacher_id", ""))
            except ValueError:
                teacher_id = None
            teacher = next(
                (item for item in data["teachers"] if item["id"] == teacher_id), None
            )
            if teacher is None:
                errors.append("Selecione um professor cadastrado.")
            else:
                school_id = teacher["school_id"]
        else:
            try:
                student_id = int(request.form.get("student_id", ""))
            except ValueError:
                student_id = None
            student = next(
                (item for item in data["students"] if item["id"] == student_id), None
            )
            if student is None:
                errors.append("Selecione um aluno cadastrado.")
            else:
                school_id = student["school_id"]
        if not errors:
            try:
                create_user(
                    username,
                    password,
                    role,
                    school_id=school_id,
                    teacher_id=teacher_id,
                    student_id=student_id,
                )
            except sqlite3.IntegrityError:
                errors.append("Esse nome de usuário já está em uso.")
            else:
                update_login_report()
                flash("Acesso criado com sucesso.", "success")
                endpoint = (
                    "cadastro_contas"
                    if request.path == url_for("cadastro_contas")
                    else "usuarios"
                )
                return redirect(url_for(endpoint))

    return render_template(
        "usuarios.html",
        data=data,
        users=get_users_page_data(),
        errors=errors,
    ), (400 if errors else 200)


@app.route("/cadastro", methods=["GET", "POST"])
@require_role("admin")
def cadastro_contas():
    return usuarios()


@app.route("/usuarios/logins.txt")
@require_role("admin")
def baixar_logins():
    content = update_login_report()
    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="logins_disponiveis.txt"'
        },
    )


@app.route("/disciplinas", methods=["GET"])
@require_role("admin", "diretor", "professor", "aluno", "responsavel")
def disciplinas():
    assignments = get_subject_assignments(g.current_user)
    for assignment in assignments:
        assignment["materials"] = get_learning_materials(assignment["id"])
    return render_template(
        "disciplinas.html",
        assignments=assignments,
        can_upload=g.current_user["role"] == "professor",
    )


@app.route("/disciplinas/<int:assignment_id>/materiais", methods=["POST"])
@require_role("professor")
def enviar_material(assignment_id):
    assignment = get_class_subject_assignment(assignment_id)
    if (
        assignment is None
        or assignment["teacher_id"] != g.current_user["teacher_id"]
    ):
        abort(403)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    media_type = request.form.get("media_type", "").strip()
    upload = request.files.get("file")
    if not title or media_type not in (
        "message",
        "activity",
        "video",
        "image",
        "audio",
        "file",
    ):
        abort(400, description="Informe um título e um tipo de conteúdo válido.")

    storage_name = original_name = None
    if upload and upload.filename:
        safe_name = secure_filename(upload.filename)
        extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
        if not safe_name or extension not in ALLOWED_UPLOADS:
            abort(400, description="Formato de arquivo não permitido.")
        if (
            ALLOWED_UPLOADS[extension] != media_type
            and media_type not in ("file", "activity")
        ):
            abort(400, description="O arquivo não corresponde ao tipo selecionado.")
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        storage_name = "{}_{}".format(uuid.uuid4().hex, safe_name)
        original_name = safe_name
        upload.save(str(UPLOAD_FOLDER / storage_name))
    elif media_type not in ("message", "activity"):
        abort(400, description="Anexe um arquivo para esse tipo de conteúdo.")
    if media_type in ("message", "activity") and not description:
        abort(400, description="Escreva a mensagem ou as instruções da atividade.")

    try:
        create_learning_material(
            assignment_id,
            g.current_user["teacher_id"],
            title,
            description,
            media_type,
            storage_name,
            original_name,
        )
    except sqlite3.Error:
        if storage_name:
            saved_file = UPLOAD_FOLDER / storage_name
            if saved_file.exists():
                saved_file.unlink()
        raise
    flash("Conteúdo publicado para a turma.", "success")
    return redirect(url_for("disciplinas"))


@app.route("/materiais/<int:material_id>/arquivo")
@require_role("admin", "diretor", "professor", "aluno", "responsavel")
def baixar_material(material_id):
    material = get_learning_material(material_id)
    if material is None or not material["storage_name"]:
        abort(404)
    assignments = {
        assignment["id"] for assignment in get_subject_assignments(g.current_user)
    }
    if material["class_subject_id"] not in assignments:
        abort(403)
    return send_from_directory(UPLOAD_FOLDER, material["storage_name"])


@app.route("/relatorios")
@require_role("admin", "diretor", "professor")
def relatorios():
    page_data = get_reports_page_data(
        school_id=_school_scope(g.current_user, request.args.get("escola", "")),
        class_id=request.args.get("turma", ""),
    )
    return render_template("relatorios.html", **page_data)


@app.route("/acompanhamento")
@require_role("admin", "diretor", "professor")
def acompanhamento():
    return _render_student_monitoring_page("Acompanhamento")


@app.route("/frequencia-desempenho")
@require_role("admin", "diretor", "professor")
def frequencia_desempenho():
    return _render_student_monitoring_page("Frequência e Desempenho")


def _render_student_monitoring_page(page_title):
    page_data = get_student_monitoring_page_data(
        search=request.args.get("busca", ""),
        school_id=_school_scope(g.current_user, request.args.get("escola", "")),
        class_id=request.args.get("turma", ""),
        situation=request.args.get("situacao", ""),
        subject_id=request.args.get("disciplina", ""),
    )
    page_data["page_title"] = page_title
    page_data["form_action"] = request.path
    return render_template("acompanhamento.html", **page_data)





@app.route("/alertas")
@require_role("admin", "diretor", "professor")
def alertas():
    page_data = get_alerts_page_data(
        category=request.args.get("categoria", ""),
        priority=request.args.get("prioridade", ""),
        school_id=_school_scope(g.current_user, request.args.get("escola", "")),
        class_id=request.args.get("turma", ""),
        student_name=request.args.get("aluno", ""),
    )
    return render_template("alertas.html", **page_data)


@app.route("/alunos")
@require_role("admin", "diretor", "professor")
def alunos():
    page_data = get_students_page_data(
        search=request.args.get("busca", ""),
        school_id=_school_scope(g.current_user, request.args.get("escola", "")),
        class_id=request.args.get("turma", ""),
        situation=request.args.get("situacao", ""),
    )
    return render_template(
        "alunos.html",
        **page_data,
        management_data=_management_view_data(g.current_user),
    )


@app.route("/professores")
@require_role("admin", "diretor", "professor")
def professores():
    page_data = get_teachers_page_data(
        school_id=_school_scope(g.current_user, request.args.get("escola", "")),
        teacher_name=request.args.get("nome", ""),
    )
    return render_template(
        "professores.html",
        **page_data,
        management_data=_management_view_data(g.current_user),
    )


@app.route("/professores/<int:teacher_id>")
@require_role("admin", "diretor", "professor")
def professor_detalhes(teacher_id):
    teacher_data = get_teacher_detail_data(teacher_id)
    if teacher_data is None:
        abort(404)
    if g.current_user["role"] != "admin" and (
        teacher_data["teacher"]["school_id"] != g.current_user["school_id"]
    ):
        abort(403)
    return render_template("professor_detalhes.html", **teacher_data)


@app.route("/escolas", methods=["GET", "POST"])
@require_role("admin", "diretor")
def escolas():
    errors = []
    if request.method == "POST":
        if g.current_user["role"] != "admin":
            abort(403)
        name = request.form.get("name", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip().upper()
        if not name or not city or len(state) != 2:
            errors.append("Informe nome, cidade e estado (UF).")
        else:
            try:
                create_school(name, city, state)
            except sqlite3.IntegrityError:
                errors.append("Já existe uma escola com esse nome.")
            else:
                flash("Escola adicionada com sucesso.", "success")
                return redirect(url_for("escolas"))

    return render_template(
        "escolas.html",
        **get_schools_page_data(_school_scope(g.current_user)),
        errors=errors,
    ), (400 if errors else 200)


@app.route("/escolas/<int:school_id>")
@require_role("admin", "diretor", "professor")
def escola_detalhes(school_id):
    if g.current_user["role"] != "admin" and (
        g.current_user["school_id"] != school_id
    ):
        abort(403)
    school_data = get_school_detail_data(school_id)
    if school_data is None:
        abort(404)
    return render_template("escola_detalhes.html", **school_data)


@app.route("/turmas")
@require_role("admin", "diretor", "professor")
def turmas():
    page_data = get_classes_page_data(
        school_id=_school_scope(g.current_user, request.args.get("escola", "")),
        class_name=request.args.get("nome", ""),
    )
    return render_template(
        "turmas.html",
        **page_data,
        management_data=_management_view_data(g.current_user),
    )


@app.route("/turmas/<int:class_id>")
@require_role("admin", "diretor", "professor")
def turma_detalhes(class_id):
    class_data = get_class_detail_data(class_id)
    if class_data is None:
        abort(404)
    if g.current_user["role"] != "admin" and (
        class_data["class_detail"]["school_id"] != g.current_user["school_id"]
    ):
        abort(403)
    class_is_accessible = _class_is_accessible(
        g.current_user, class_id, get_management_form_data()
    )
    class_data["can_assign_students"] = class_is_accessible
    class_data["available_students"] = (
        get_students_available_for_class(class_id) if class_is_accessible else []
    )
    return render_template("turma_detalhes.html", **class_data)


@app.route("/turmas/<int:class_id>/adicionar-aluno", methods=["POST"])
@require_role("admin", "diretor", "professor")
def adicionar_aluno_a_turma(class_id):
    user = g.current_user
    class_data = get_class_detail_data(class_id)
    if class_data is None:
        abort(404)
    if not _class_is_accessible(user, class_id, get_management_form_data()):
        abort(403)

    try:
        student_id = int(request.form.get("student_id", ""))
    except ValueError:
        flash("Selecione um aluno cadastrado.", "error")
        return redirect(url_for("turma_detalhes", class_id=class_id))

    if not assign_student_to_class(student_id, class_id):
        flash(
            "O aluno não foi encontrado ou não pertence à escola desta turma.",
            "error",
        )
    else:
        flash("Aluno vinculado à turma com sucesso.", "success")
    return redirect(url_for("turma_detalhes", class_id=class_id))


@app.route("/alunos/<int:student_id>")
@require_role("admin", "diretor", "professor", "aluno", "responsavel")
def aluno_perfil(student_id):
    student_record = get_student_by_id(student_id)
    if student_record is None:
        abort(404)
    user = g.current_user
    if user["role"] in ("aluno", "responsavel") and user["student_id"] != student_id:
        abort(403)
    if user["role"] == "diretor" and user["school_id"] != student_record["school_id"]:
        abort(403)
    if user["role"] == "professor" and not _class_is_accessible(
        user, student_record["class_id"], get_management_form_data()
    ):
        abort(403)
    profile_data = get_student_profile_data(student_id)
    if profile_data is None:
        abort(404)
    if user["role"] in ("diretor", "professor"):
        profile_data["can_record_metrics"] = True
        profile_data["record_date"] = datetime.now().date().isoformat()
        profile_data["recording_assignments"] = [
            assignment
            for assignment in get_subject_assignments(user)
            if assignment["class_id"] == student_record["class_id"]
        ]
    else:
        profile_data["can_record_metrics"] = False
        profile_data["recording_assignments"] = []
    return render_template("aluno_perfil.html", **profile_data)


@app.route("/alunos/<int:student_id>/registros", methods=["POST"])
@require_role("diretor", "professor")
def registrar_dados_aluno(student_id):
    user = g.current_user
    student_record = get_student_by_id(student_id)
    if student_record is None:
        abort(404)
    management_data = get_management_form_data()
    if not _class_is_accessible(user, student_record["class_id"], management_data):
        abort(403)

    record_type = request.form.get("record_type", "")
    try:
        if record_type == "attendance":
            attendance_date = request.form.get("attendance_date", "").strip()
            status = request.form.get("status", "").strip()
            notes = request.form.get("notes", "").strip()
            datetime.strptime(attendance_date, "%Y-%m-%d")
            if status not in ("present", "absent", "late", "excused"):
                raise ValueError("Selecione uma situação de frequência válida.")
            if len(notes) > 500:
                raise ValueError("As observações devem ter até 500 caracteres.")
            record_student_attendance(student_id, attendance_date, status, notes)
            flash("Frequência registrada com sucesso.", "success")
        elif record_type == "grade":
            try:
                class_subject_id = int(request.form.get("class_subject_id", ""))
                score = float(request.form.get("score", ""))
            except ValueError:
                raise ValueError("Informe uma disciplina e uma nota válidas.")
            assessment_name = request.form.get("assessment_name", "").strip()
            assessment_date = request.form.get("assessment_date", "").strip()
            datetime.strptime(assessment_date, "%Y-%m-%d")
            permitted_assignments = {
                assignment["id"]: assignment
                for assignment in get_subject_assignments(user)
                if assignment["class_id"] == student_record["class_id"]
            }
            if class_subject_id not in permitted_assignments:
                abort(403)
            if not assessment_name or len(assessment_name) > 120:
                raise ValueError("Informe o nome da avaliação (até 120 caracteres).")
            if not math.isfinite(score) or not 0 <= score <= 10:
                raise ValueError("A nota deve estar entre 0 e 10.")
            if not record_student_grade(
                student_id,
                class_subject_id,
                assessment_name,
                score,
                assessment_date,
            ):
                abort(400, description="A disciplina não pertence à turma do aluno.")
            flash("Desempenho registrado com sucesso.", "success")
        else:
            abort(400, description="Tipo de registro inválido.")
    except ValueError as error:
        flash(str(error) or "Revise os dados informados.", "error")

    return redirect(url_for("aluno_perfil", student_id=student_id))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
