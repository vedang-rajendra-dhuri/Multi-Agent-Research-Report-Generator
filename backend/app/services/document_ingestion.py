import io
import re
import zipfile
from pathlib import PurePath

from docx import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 750_000
MAX_PDF_PAGES = 100
CHUNK_CHARACTERS = 1_800
CHUNK_OVERLAP = 200
MAX_DOCUMENT_CHUNKS = 500
MAX_DOCX_UNCOMPRESSED_BYTES = 30 * 1024 * 1024

SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class DocumentIngestionError(ValueError):
    pass


def sanitize_file_name(file_name: str) -> str:
    safe_name = PurePath(file_name.replace("\\", "/")).name.strip()
    safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name)
    if not safe_name or safe_name in {".", ".."}:
        raise DocumentIngestionError("The uploaded file must have a valid file name.")
    return safe_name[:255]


def _extract_pdf(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        raise DocumentIngestionError("The PDF file signature is invalid.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise DocumentIngestionError("Encrypted PDF files are not supported.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentIngestionError(f"PDF files are limited to {MAX_PDF_PAGES} pages.")
        paragraphs = []
        extracted_characters = 0
        for page in reader.pages:
            text = page.extract_text()
            if text:
                paragraphs.append(text)
                extracted_characters += len(text)
                if extracted_characters > MAX_EXTRACTED_CHARACTERS:
                    raise DocumentIngestionError("Extracted text exceeds the document size limit.")
        return "\n\n".join(paragraphs)
    except DocumentIngestionError:
        raise
    except (PdfReadError, ValueError, OSError) as error:
        raise DocumentIngestionError("The PDF could not be read.") from error


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise DocumentIngestionError("The Word document structure is invalid.")
            if sum(item.file_size for item in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise DocumentIngestionError("The Word document expands beyond the allowed size.")
        document = Document(io.BytesIO(data))
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    paragraphs.append(" | ".join(cells))
        return "\n\n".join(paragraphs)
    except DocumentIngestionError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as error:
        raise DocumentIngestionError("The Word document could not be read.") from error


def extract_text(file_name: str, data: bytes) -> str:
    safe_name = sanitize_file_name(file_name)
    suffix = PurePath(safe_name).suffix.lower()
    if suffix not in SUPPORTED_TYPES:
        raise DocumentIngestionError("Upload a PDF, DOCX, TXT, or Markdown file.")
    if not data:
        raise DocumentIngestionError("The uploaded document is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentIngestionError("Documents are limited to 10 MB.")

    if suffix == ".pdf":
        extracted = _extract_pdf(data)
    elif suffix == ".docx":
        extracted = _extract_docx(data)
    else:
        if b"\x00" in data:
            raise DocumentIngestionError("The text document contains binary data.")
        try:
            extracted = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DocumentIngestionError("Text documents must use UTF-8 encoding.") from error

    normalized = extracted.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        character
        for character in normalized
        if character in "\n\t" or ord(character) >= 32
    )
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        raise DocumentIngestionError("No readable text was found in the document.")
    if len(normalized) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentIngestionError("Extracted text exceeds the document size limit.")
    return normalized


def chunk_text(text: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARACTERS, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start + CHUNK_CHARACTERS // 2, end),
                           text.rfind(" ", start + CHUNK_CHARACTERS // 2, end))
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
            if len(chunks) > MAX_DOCUMENT_CHUNKS:
                raise DocumentIngestionError("The document has too many text sections to index.")
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks
