import os
from pathlib import Path
from dotenv import load_dotenv

from huggingface_hub import InferenceClient
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings  # pip install -U langchain-huggingface

INDEX_DIR = Path(r"D:\RAG_CHAT\index")


def build_prompt(question: str, contexts: list[str]) -> str:
    context_text = "\n\n---\n\n".join(contexts)
    return f"""Answer ONLY using the context.
If the answer is not in the context, say: "I don't know from the provided documents."

Context:
{context_text}

Question: {question}
Answer:"""


class RAGChat:
    """Loads the FAISS index and HuggingFace model once, then answers questions."""

    def __init__(
        self,
        index_dir: Path = INDEX_DIR,
        model_id: str = "mistralai/Mistral-7B-Instruct-v0.2",
    ):
        load_dotenv()
        hf_token = "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"  # os.getenv("HF_TOKEN")
        if not hf_token:
            raise RuntimeError("HF_TOKEN not found. Put it in .env as HF_TOKEN=...")

        if not index_dir.exists():
            raise RuntimeError(f"Index not found: {index_dir}. Run ingest.py first.")

        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.db = FAISS.load_local(
            str(index_dir), embeddings, allow_dangerous_deserialization=True
        )
        self.client = InferenceClient(model=model_id, token=hf_token)

    def ask(self, question: str, k: int = 12) -> dict:
        """Return {"answer": str, "sources": list[str]}."""
        docs = self.db.similarity_search(question, k=k)
        contexts = [
            f"[Source {i+1}] {d.page_content[:1500]}" for i, d in enumerate(docs)
        ]
        prompt = build_prompt(question, contexts)

        resp = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant for document Q&A.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.2,
        )

        # Collect unique source metadata (if available)
        sources = []
        for d in docs:
            src = d.metadata.get("source", "")
            if src and src not in sources:
                sources.append(src)

        return {
            "answer": resp.choices[0].message.content,
            "sources": sources,
        }


def main():
    rag = RAGChat()
    while True:
        q = input("\nAsk a question (or 'exit'): ").strip()
        if q.lower() in ["exit", "quit"]:
            break
        try:
            result = rag.ask(q)
            print("\n--- Answer ---\n")
            print(result["answer"])
            if result["sources"]:
                print("\nSources:", ", ".join(result["sources"]))
        except Exception as e:
            print(f"\n❌ HF chat error: {e}")


if __name__ == "__main__":
    main()