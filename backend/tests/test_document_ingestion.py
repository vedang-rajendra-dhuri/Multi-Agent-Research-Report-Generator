import io

import pytest
from docx import Document

from app.services.document_ingestion import (
    CHUNK_CHARACTERS,
    MAX_UPLOAD_BYTES,
    DocumentIngestionError,
    chunk_text,
    extract_text,
    sanitize_file_name,
)


def create_docx(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def test_plain_text_extraction_normalizes_line_endings_and_controls():
    extracted = extract_text("notes.txt", b"First line\r\n\r\nSecond line\x01")

    assert extracted == "First line\n\nSecond line"


def test_docx_extraction_reads_paragraphs_and_tables():
    document = Document()
    document.add_paragraph("A report paragraph")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Cost"
    table.cell(0, 1).text = "Value"
    output = io.BytesIO()
    document.save(output)

    extracted = extract_text("research.docx", output.getvalue())

    assert "A report paragraph" in extracted
    assert "Cost | Value" in extracted


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("report.exe", b"plain text", "Upload a PDF"),
        ("report.txt", b"\xff", "UTF-8"),
        ("report.txt", b"\x00", "binary data"),
        ("report.pdf", b"not a pdf", "signature"),
        ("empty.md", b" \n\t ", "No readable text"),
    ],
)
def test_unsupported_or_malformed_uploads_fail_explicitly(name, data, message):
    with pytest.raises(DocumentIngestionError, match=message):
        extract_text(name, data)


def test_oversized_upload_fails_explicitly():
    with pytest.raises(DocumentIngestionError, match="10 MB"):
        extract_text("oversized.txt", b"a" * (MAX_UPLOAD_BYTES + 1))


def test_docx_extension_does_not_allow_arbitrary_zip_files():
    with pytest.raises(DocumentIngestionError, match="Word document could not be read"):
        extract_text("not-a-document.docx", b"PK\x03\x04")


def test_file_name_strips_client_supplied_path_components():
    assert sanitize_file_name(r"C:\private\report.txt") == "report.txt"


def test_chunk_text_bounds_chunk_size_and_keeps_context_overlap():
    text = "A research sentence. " * 300

    chunks = chunk_text(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= CHUNK_CHARACTERS for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)
