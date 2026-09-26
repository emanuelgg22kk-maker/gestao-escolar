import hmac
import os

from flask import Flask, abort, redirect, render_template, request, session, url_for

from database import (
    get_dashboard_data,
    get_alerts_page_data,
    get_student_by_id,
    get_student_profile_data,
    get_students_page_data,
    get_school_detail_data,
    get_schools_page_data,
    get_class_detail_data,
    get_classes_page_data,
    get_teacher_detail_data,
    get_teachers_page_data,
    get_student_monitoring_page_data,
    get_pedagogical_plan_detail_data,
    get_pedagogical_plans_page_data,
    get_reports_page_data,
    create_communication,
    get_communication_detail_data,
    get_communication_school_options,
    get_communications_page_data,
    mark_communication_read,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or "gestao-escolar-local-prototype-key"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "admin123"


@app.before_request
def require_login():
    if request.endpoint in {"login", "logout", "static"}:
        return None
    if not session.get("logged_in"):
        return redirect(url_for("login"))


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        valid_username = hmac.compare_digest(
            username.encode("utf-8"), DEMO_USERNAME.encode("utf-8")
        )
        valid_password = hmac.compare_digest(
            password.encode("utf-8"), DEMO_PASSWORD.encode("utf-8")
        )
        if valid_username and valid_password:
            session.clear()
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "Usuário ou senha inválidos."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", **get_dashboard_data())


@app.route("/comunicacao")
def comunicacao():
    page_data = get_communications_page_data(
        message_type=request.args.get("tipo", ""),
        status=request.args.get("status", ""),
        school_id=request.args.get("escola", ""),
        message_date=request.args.get("data", ""),
    )
    return render_template("comunicacao.html", **page_data)


@app.route("/comunicacao/nova", methods=["GET", "POST"])
def nova_comunicacao():
    schools = get_communication_school_options()
    school_ids = {school["id"] for school in schools}
    form_data = {
        "recipient": "",
        "subject": "",
        "message": "",
        "message_type": "family",
        "direction": "sent",
        "school_id": "",
    }
    errors = []

    if request.method == "POST":
        for field in form_data:
            form_data[field] = request.form.get(field, "").strip()

        for field, label in (
            ("recipient", "destinatário"),
            ("subject", "assunto"),
            ("message", "mensagem"),
        ):
            if not form_data[field]:
                errors.append("Informe {}.".format(label))

        if form_data["message_type"] not in ("family", "school", "management"):
            errors.append("Selecione um tipo de comunicação válido.")
        if form_data["direction"] not in ("sent", "received"):
            errors.append("Selecione uma direção válida.")

        school_id = None
        if form_data["school_id"]:
            try:
                school_id = int(form_data["school_id"])
            except ValueError:
                errors.append("Selecione uma escola válida.")
            else:
                if school_id not in school_ids:
                    errors.append("A escola selecionada não existe.")

        if not errors:
            communication_id = create_communication(
                school_id=school_id,
                recipient=form_data["recipient"],
                subject=form_data["subject"],
                message=form_data["message"],
                message_type=form_data["message_type"],
                direction=form_data["direction"],
            )
            return redirect(
                url_for("comunicacao_detalhes", communication_id=communication_id)
            )

    return render_template(
        "comunicacao_nova.html",
        schools=schools,
        form_data=form_data,
        errors=errors,
    ), (400 if errors else 200)


@app.route("/comunicacao/<int:communication_id>")
def comunicacao_detalhes(communication_id):
    communication_data = get_communication_detail_data(communication_id)
    if communication_data is None:
        abort(404)
    return render_template("comunicacao_detalhes.html", **communication_data)


@app.route("/comunicacao/<int:communication_id>/marcar-lida", methods=["POST"])
def marcar_comunicacao_lida(communication_id):
    if not mark_communication_read(communication_id):
        abort(404)
    return redirect(url_for("comunicacao_detalhes", communication_id=communication_id))


@app.route("/relatorios")
def relatorios():
    page_data = get_reports_page_data(
        school_id=request.args.get("escola", ""),
        class_id=request.args.get("turma", ""),
    )
    return render_template("relatorios.html", **page_data)


@app.route("/acompanhamento")
def acompanhamento():
    return _render_student_monitoring_page("Acompanhamento")


@app.route("/frequencia-desempenho")
def frequencia_desempenho():
    return _render_student_monitoring_page("Frequência e Desempenho")


def _render_student_monitoring_page(page_title):
    page_data = get_student_monitoring_page_data(
        search=request.args.get("busca", ""),
        school_id=request.args.get("escola", ""),
        class_id=request.args.get("turma", ""),
        situation=request.args.get("situacao", ""),
        subject_id=request.args.get("disciplina", ""),
    )
    page_data["page_title"] = page_title
    page_data["form_action"] = request.path
    return render_template("acompanhamento.html", **page_data)


@app.route("/planejamento")
def planejamento():
    page_data = get_pedagogical_plans_page_data(
        school_id=request.args.get("escola", ""),
        teacher_id=request.args.get("professor", ""),
        class_id=request.args.get("turma", ""),
        subject_id=request.args.get("disciplina", ""),
    )
    return render_template("planejamento.html", **page_data)


@app.route("/planejamento/<int:plan_id>")
def planejamento_detalhes(plan_id):
    plan_data = get_pedagogical_plan_detail_data(plan_id)
    if plan_data is None:
        abort(404)
    return render_template("planejamento_detalhes.html", **plan_data)


@app.route("/alertas")
def alertas():
    page_data = get_alerts_page_data(
        category=request.args.get("categoria", ""),
        priority=request.args.get("prioridade", ""),
        school_id=request.args.get("escola", ""),
        class_id=request.args.get("turma", ""),
        student_name=request.args.get("aluno", ""),
    )
    return render_template("alertas.html", **page_data)


@app.route("/alunos")
def alunos():
    page_data = get_students_page_data(
        search=request.args.get("busca", ""),
        school_id=request.args.get("escola", ""),
        class_id=request.args.get("turma", ""),
        situation=request.args.get("situacao", ""),
    )
    return render_template("alunos.html", **page_data)


@app.route("/professores")
def professores():
    page_data = get_teachers_page_data(
        school_id=request.args.get("escola", ""),
        teacher_name=request.args.get("nome", ""),
    )
    return render_template("professores.html", **page_data)


@app.route("/professores/<int:teacher_id>")
def professor_detalhes(teacher_id):
    teacher_data = get_teacher_detail_data(teacher_id)
    if teacher_data is None:
        abort(404)
    return render_template("professor_detalhes.html", **teacher_data)


@app.route("/escolas")
def escolas():
    return render_template("escolas.html", **get_schools_page_data())


@app.route("/escolas/<int:school_id>")
def escola_detalhes(school_id):
    school_data = get_school_detail_data(school_id)
    if school_data is None:
        abort(404)
    return render_template("escola_detalhes.html", **school_data)


@app.route("/turmas")
def turmas():
    page_data = get_classes_page_data(
        school_id=request.args.get("escola", ""),
        class_name=request.args.get("nome", ""),
    )
    return render_template("turmas.html", **page_data)


@app.route("/turmas/<int:class_id>")
def turma_detalhes(class_id):
    class_data = get_class_detail_data(class_id)
    if class_data is None:
        abort(404)
    return render_template("turma_detalhes.html", **class_data)


@app.route("/alunos/<int:student_id>")
def aluno_perfil(student_id):
    profile_data = get_student_profile_data(student_id)
    if profile_data is None:
        abort(404)
    return render_template("aluno_perfil.html", **profile_data)


if __name__ == "__main__":
    app.run(debug=True)
