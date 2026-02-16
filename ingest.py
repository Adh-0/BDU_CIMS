import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

DOCS_DIR = Path(r"D:\RAG_CHAT\PDF")
INDEX_DIR = Path(r"D:\RAG_CHAT\index")

def load_documents(docs_dir: Path):
    docs = []
    for p in docs_dir.rglob("*"):
        if p.is_dir():
            continue
        ext = p.suffix.lower()
        try:
            if ext == ".pdf":
                docs.extend(PyPDFLoader(str(p)).load())
            elif ext in [".txt", ".md"]:
                docs.extend(TextLoader(str(p), encoding="utf-8").load())
            elif ext in [".docx", ".doc"]:
                docs.extend(UnstructuredWordDocumentLoader(str(p)).load())
        except Exception as e:
            print(f"⚠️ Skipped {p.name}: {e}")
    return docs

def main():
    load_dotenv()

    if not DOCS_DIR.exists():
        raise SystemExit(f"Docs folder not found: {DOCS_DIR}")

    print(f"📄 Loading docs from: {DOCS_DIR}")
    raw_docs = load_documents(DOCS_DIR)
    print(f"✅ Loaded {len(raw_docs)} documents")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)
    chunks = splitter.split_documents(raw_docs)
    print(f"✅ Split into {len(chunks)} chunks")

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print("📌 Building FAISS index...")
    db = FAISS.from_documents(chunks, embeddings)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    db.save_local(str(INDEX_DIR))
    print(f"✅ Saved index to: {INDEX_DIR}")

if __name__ == "__main__":
    main()