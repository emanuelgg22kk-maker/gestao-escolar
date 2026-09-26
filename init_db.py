from database import DATABASE_PATH, get_connection, initialize_database


DEMO_DATA = {
    "schools": [
        (1, "Escola Ficticia Horizonte", "Campinas", "SP"),
        (2, "Escola Ficticia Vale Verde", "Jundiai", "SP"),
    ],
    "classes": [
        (1, 1, "6A", 2026, "morning"),
        (2, 1, "6B", 2026, "afternoon"),
        (3, 2, "7A", 2026, "morning"),
    ],
    "students": [
        (1, 1, "Estudante Demonstracao 01", "DEMO-001", "2014-03-12"),
        (2, 1, "Estudante Demonstracao 02", "DEMO-002", "2014-08-25"),
        (3, 2, "Estudante Demonstracao 03", "DEMO-003", "2013-11-04"),
        (4, 2, "Estudante Demonstracao 04", "DEMO-004", "2013-06-19"),
        (5, 3, "Estudante Demonstracao 05", "DEMO-005", "2013-02-10"),
        (6, 3, "Estudante Demonstracao 06", "DEMO-006", "2013-09-30"),
    ],
    "teachers": [
        (1, 1, "Professor Exemplo 01", "professor01@example.test"),
        (2, 1, "Professora Exemplo 02", "professora02@example.test"),
        (3, 2, "Professor Exemplo 03", "professor03@example.test"),
    ],
    "subjects": [
        (1, "Matematica"),
        (2, "Lingua Portuguesa"),
        (3, "Ciencias"),
        (4, "Historia"),
    ],
    "class_subjects": [
        (1, 1, 1, 1),
        (2, 1, 2, 2),
        (3, 1, 3, 1),
        (4, 2, 1, 1),
        (5, 2, 2, 2),
        (6, 3, 1, 3),
        (7, 3, 3, 3),
        (8, 3, 4, 3),
    ],
    "grades": [
        (1, 1, 1, "Avaliacao 1", 8.5, "2026-03-10"),
        (2, 2, 1, "Avaliacao 1", 7.0, "2026-03-10"),
        (3, 1, 2, "Atividade 1", 9.0, "2026-03-12"),
        (4, 2, 2, "Atividade 1", 8.0, "2026-03-12"),
        (5, 3, 4, "Avaliacao 1", 6.5, "2026-03-15"),
        (6, 4, 4, "Avaliacao 1", 8.0, "2026-03-15"),
        (7, 5, 6, "Avaliacao 1", 7.5, "2026-03-18"),
        (8, 6, 6, "Avaliacao 1", 9.0, "2026-03-18"),
    ],
    "attendance": [
        (1, 1, "2026-03-02", "present", None),
        (2, 2, "2026-03-02", "present", None),
        (3, 3, "2026-03-02", "absent", "Registro de demonstracao"),
        (4, 4, "2026-03-02", "present", None),
        (5, 5, "2026-03-02", "late", "Registro de demonstracao"),
        (6, 6, "2026-03-02", "present", None),
        (7, 1, "2026-03-03", "present", None),
        (8, 2, "2026-03-03", "excused", "Registro de demonstracao"),
        (9, 3, "2026-03-03", "present", None),
        (10, 4, "2026-03-03", "present", None),
        (11, 5, "2026-03-03", "present", None),
        (12, 6, "2026-03-03", "absent", "Registro de demonstracao"),
    ],
    "participation": [
        (1, 1, 1, "Resolucao de exercicios", 8.0, "2026-03-05"),
        (2, 2, 1, "Trabalho em grupo", 7.5, "2026-03-05"),
        (3, 3, 4, "Discussao em aula", 6.0, "2026-03-06"),
        (4, 4, 5, "Trabalho em grupo", 8.5, "2026-03-06"),
        (5, 5, 6, "Resolucao de exercicios", 9.0, "2026-03-07"),
        (6, 6, 7, "Experimento demonstrativo", 8.0, "2026-03-07"),
    ],
    "alerts": [
        (1, 3, "attendance", "Frequencia baixa para acompanhamento.", "warning", "2026-03-04", 0),
        (2, 6, "performance", "Acompanhar desempenho nas avaliacoes.", "info", "2026-03-19", 0),
    ],
    "pedagogical_plans": [
        (1, 1, "Operacoes matematicas", "Praticar operacoes basicas.", "2026-04-01", "planned"),
        (2, 3, "Introducao a ciencias", "Observar e registrar resultados de experiencias.", "2026-04-03", "planned"),
        (3, 6, "Resolucao de problemas", "Desenvolver estrategias de resolucao.", "2026-04-05", "planned"),
    ],
}


INSERT_STATEMENTS = {
    "schools": "INSERT OR IGNORE INTO schools VALUES (?, ?, ?, ?)",
    "classes": "INSERT OR IGNORE INTO classes VALUES (?, ?, ?, ?, ?)",
    "students": "INSERT OR IGNORE INTO students VALUES (?, ?, ?, ?, ?)",
    "teachers": "INSERT OR IGNORE INTO teachers VALUES (?, ?, ?, ?)",
    "subjects": "INSERT OR IGNORE INTO subjects VALUES (?, ?)",
    "class_subjects": "INSERT OR IGNORE INTO class_subjects VALUES (?, ?, ?, ?)",
    "grades": "INSERT OR IGNORE INTO grades VALUES (?, ?, ?, ?, ?, ?)",
    "attendance": "INSERT OR IGNORE INTO attendance VALUES (?, ?, ?, ?, ?)",
    "participation": "INSERT OR IGNORE INTO participation VALUES (?, ?, ?, ?, ?, ?)",
    "alerts": "INSERT OR IGNORE INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?)",
    "pedagogical_plans": "INSERT OR IGNORE INTO pedagogical_plans VALUES (?, ?, ?, ?, ?, ?)",
}


def seed_database():
    initialize_database()
    connection = get_connection()
    try:
        with connection:
            for table, rows in DEMO_DATA.items():
                connection.executemany(INSERT_STATEMENTS[table], rows)
    finally:
        connection.close()

    print("Banco inicializado em: {}".format(DATABASE_PATH))
    print("Dados ficticios de demonstracao inseridos (ou ja existentes).")


if __name__ == "__main__":
    seed_database()