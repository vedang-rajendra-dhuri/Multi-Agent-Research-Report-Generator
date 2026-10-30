from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.services.document_retrieval import retrieve_project_evidence


class RetrievalResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class RetrievalSessionStub:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return RetrievalResult(self.rows)


def test_project_evidence_uses_project_scoped_postgres_full_text_query():
    project_id = uuid4()
    session = RetrievalSessionStub([])

    assert retrieve_project_evidence(
        session,
        project_id,
        "  battery storage cost trends  ",
    ) == []

    compiled = session.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "project_documents.project_id" in sql
    assert "document_chunks.text @@ plainto_tsquery" in sql
    assert "ts_rank_cd" in sql
    assert project_id in compiled.params.values()


def test_empty_document_query_skips_database_lookup():
    class NoQuerySession:
        def execute(self, statement):
            raise AssertionError("Empty search query should not hit the database.")

    assert retrieve_project_evidence(NoQuerySession(), uuid4(), "   ") == []
