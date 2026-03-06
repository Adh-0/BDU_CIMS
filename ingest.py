"""
ingest.py - Document ingestion pipeline for BDU RAG Chatbot
Extracts text from PDFs (with smart table handling), chunks it,
and builds a FAISS vector index for similarity search.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

import pdfplumber
from langchain_community.document_loaders import TextLoader, UnstructuredWordDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

DOCS_DIR = Path(r"D:\RAG_CHAT\PDF")
INDEX_DIR = Path(r"D:\RAG_CHAT\index")

# --- Vertical text cleanup patterns ---
# These are rotated 90° cells in the PDF tables
VERTICAL_TEXT_MAP = {
    "r\na\ne\ny\n-\n2": "2 years",
    "r\na\ne\ny\n-\n3": "3 years",
    "r\na\ne\ny\n-\n5": "5 years",
    "r\na\ne\ny\n-\n6": "6 years",
    "r\na\ne\nY\n-\n2": "2 years",
    "s\nr\ne\nh\ntO": "Others",
    "s\nr\ne\nh\nt\nO": "Others",
    "T\nS\n/\nC\nS": "SC/ST",
}

# Table column headers (positions in the 15-column table)
COL_SNO = 0
COL_PROGRAMME = 1
COL_SUBJECT = 2
COL_DEPARTMENT = 3
COL_ELIGIBILITY = 4
COL_DURATION = 5
COL_CATEGORY = 6
COL_TUITION_FEE = 7
COL_OTHER_FEE_1 = 8
COL_OTHER_FEE_2 = 9


def clean_cell(text):
    """Clean a single table cell — fix vertical text, strip whitespace."""
    if not text or text == "EMPTY":
        return ""
    text = text.strip()
    # Check if it's a known vertical text pattern
    if text in VERTICAL_TEXT_MAP:
        return VERTICAL_TEXT_MAP[text]
    # Remove newlines within cell content and collapse whitespace
    text = " ".join(text.split())
    return text


def is_data_row(row):
    """Check if a table row contains actual programme data (not headers or empty rows)."""
    if not row or len(row) < 5:
        return False
    sno = clean_cell(str(row[COL_SNO])) if row[COL_SNO] else ""
    programme = clean_cell(str(row[COL_PROGRAMME])) if row[COL_PROGRAMME] else ""
    # Data rows have a serial number (digit) and a programme name
    return sno.isdigit() and programme != ""


def detect_programme_type(title):
    """Detect UG/PG/Integrated type from the table title."""
    t = title.upper()
    if "UNDER GRADUATE" in t or "UNDERGRADUATE" in t:
        return "Undergraduate (UG) Programme (after 12th / Plus Two / 10+2)"
    elif "FIVE - YEAR" in t or "FIVE YEAR" in t or "5 YEAR" in t:
        return "Five-Year Integrated Programme (after 12th / Plus Two / 10+2)"
    elif "SIX - YEAR" in t or "SIX YEAR" in t or "6 YEAR" in t:
        return "Six-Year Integrated Programme (after 12th / Plus Two / 10+2)"
    elif "DIPLOMA" in t:
        return "PG Diploma / Diploma / Certificate Programme"
    elif "CERTIFICATE" in t:
        return "Certificate Programme"
    elif "KAUSHAL" in t:
        return "Undergraduate (UG) Vocational Programme (B.Voc.) (after 12th / Plus Two / 10+2)"
    elif "POST GRADUATE" in t or "POSTGRADUATE" in t:
        return "Postgraduate (PG) Programme (after completing a degree / graduation)"
    return ""


def parse_table_row(row, programme_type=""):
    """Parse a single table row into structured course and fee data."""
    cells = [clean_cell(str(c)) if c else "" for c in row]

    sno = cells[COL_SNO] if len(cells) > COL_SNO else ""
    programme = cells[COL_PROGRAMME] if len(cells) > COL_PROGRAMME else ""
    subject = cells[COL_SUBJECT] if len(cells) > COL_SUBJECT else ""
    department = cells[COL_DEPARTMENT] if len(cells) > COL_DEPARTMENT else ""
    eligibility = cells[COL_ELIGIBILITY] if len(cells) > COL_ELIGIBILITY else ""
    duration = cells[COL_DURATION] if len(cells) > COL_DURATION else ""
    tuition_fee = cells[COL_TUITION_FEE] if len(cells) > COL_TUITION_FEE else ""

    # Build course info (no fees)
    course_info = ""
    if programme_type:
        course_info += f"Type: {programme_type}\n"
    course_info += f"Programme: {programme}"
    if subject:
        course_info += f" in {subject}"
    if department:
        course_info += f"\nDepartment/School: {department}"
    if eligibility:
        course_info += f"\nEligibility: {eligibility}"
    if duration:
        course_info += f"\nDuration: {duration}"

    # Build fee info separately
    fee_info = ""
    if tuition_fee and tuition_fee.replace(",", "").isdigit():
        fee_info = f"Fees for {programme}"
        if subject:
            fee_info += f" in {subject}"
        fee_info += f": Tuition Fee Rs.{tuition_fee} per semester"

    return course_info, fee_info


def extract_table_title(table):
    """Try to get the table title from the first row."""
    if not table or len(table) < 1:
        return ""
    first_cell = clean_cell(str(table[0][0])) if table[0][0] else ""
    # Title rows have long text in the first cell and EMPTY in others
    if any(keyword in first_cell.upper() for keyword in ["PROGRAMME", "GRADUATE", "KAUSHAL", "DIPLOMA"]):
        return first_cell
    return ""


def load_pdf_with_pdfplumber(filepath: Path) -> list[Document]:
    """Extract text from PDF using pdfplumber with smart table handling."""
    docs = []
    source = str(filepath)

    with pdfplumber.open(filepath) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()

            if tables:
                # --- TABLE PAGE: use structured table data only ---
                for table in tables:
                    title = extract_table_title(table)
                    prog_type = detect_programme_type(title)
                    course_entries = []
                    fee_entries = []

                    for row in table:
                        if is_data_row(row):
                            course_info, fee_info = parse_table_row(row, prog_type)
                            if course_info:
                                course_entries.append(course_info)
                            if fee_info:
                                fee_entries.append(fee_info)

                    # Create COURSE chunk
                    if course_entries:
                        header = f"{title}\n\n" if title else ""
                        course_text = header + "\n\n".join(course_entries)
                        docs.append(Document(
                            page_content=course_text,
                            metadata={
                                "source": source,
                                "page": page_idx,
                                "topic": "courses",
                                "total_pages": len(pdf.pages),
                            }
                        ))

                    # Create FEE chunk (separate)
                    if fee_entries:
                        header = f"Fee Structure - {title}\n\n" if title else "Fee Structure\n\n"
                        fee_text = header + "\n".join(fee_entries)
                        docs.append(Document(
                            page_content=fee_text,
                            metadata={
                                "source": source,
                                "page": page_idx,
                                "topic": "fees",
                                "total_pages": len(pdf.pages),
                            }
                        ))
            else:
                # --- TEXT PAGE: use extract_text() as normal ---
                text = page.extract_text() or ""
                if text.strip():
                    docs.append(Document(
                        page_content=text.strip(),
                        metadata={
                            "source": source,
                            "page": page_idx,
                            "topic": "general",
                            "total_pages": len(pdf.pages),
                        }
                    ))

    return docs


def load_documents(docs_dir: Path):
    docs = []
    for p in docs_dir.rglob("*"):
        if p.is_dir():
            continue
        ext = p.suffix.lower()
        try:
            if ext == ".pdf":
                docs.extend(load_pdf_with_pdfplumber(p))
            elif ext in [".txt", ".md"]:
                docs.extend(TextLoader(str(p), encoding="utf-8").load())
            elif ext in [".docx", ".doc"]:
                docs.extend(UnstructuredWordDocumentLoader(str(p)).load())
        except Exception as e:
            print(f"[WARN] Skipped {p.name}: {e}")
    return docs


def main():
    load_dotenv()

    if not DOCS_DIR.exists():
        raise SystemExit(f"Docs folder not found: {DOCS_DIR}")

    print("========================================")
    print("  BDU RAG - Document Ingestion Pipeline ")
    print("========================================")
    print()

    print(f"[LOAD] Reading docs from: {DOCS_DIR}")
    raw_docs = load_documents(DOCS_DIR)
    print(f"[DONE] Loaded {len(raw_docs)} documents")

    # Show topic breakdown
    topics = {}
    for d in raw_docs:
        t = d.metadata.get("topic", "unknown")
        topics[t] = topics.get(t, 0) + 1
    for t, c in topics.items():
        print(f"       - {t}: {c} chunks")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
    chunks = splitter.split_documents(raw_docs)
    print(f"[DONE] Split into {len(chunks)} chunks")

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print("[BUILD] Creating FAISS index...")
    db = FAISS.from_documents(chunks, embeddings)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    db.save_local(str(INDEX_DIR))
    print(f"[DONE] Index saved to: {INDEX_DIR}")
    print()

if __name__ == "__main__":
    main()