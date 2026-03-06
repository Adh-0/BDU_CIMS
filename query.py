"""
query.py - RAG Query Engine for BDU Chatbot
Loads the FAISS index and answers student questions using
HuggingFace Inference API with Mistral-7B.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from huggingface_hub import InferenceClient
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

INDEX_DIR = Path(r"D:\RAG_CHAT\index")

SYSTEM_PROMPT = """You are the virtual assistant for Bharathidasan University (BDU), Tiruchirappalli.
You help students understand everything about BDU's programmes, admissions, and campus life.

RULES:
1. Give detailed, comprehensive answers. List ALL relevant programmes, departments, or details from the context — do not summarize or skip items.
2. When listing courses or departments, include the specific names, subjects, and schools/departments they belong to.
3. NEVER include fee details unless the student specifically asks about fees or costs.
4. NEVER add filler phrases like "I hope this helps", "Feel free to ask", or "Don't hesitate to contact us".
5. If the answer is not in the context, say: "I don't have that information. Please contact the BDU admission office."
6. Use bullet points and numbered lists to organize information clearly.
7. Answer in English only.
8. Only answer with answers that are relavent to the question asked, do not include any other information.
9. You do not need to answer the question to max token limit, you can answer the question to a certain extent and suggest the user to visit neccesary sources.

IMPORTANT - Understanding student language:
- "all the departments at bdu" = student wants to know about all the departments at BDU = show some major departments and suggest the user to visit neccesary sources.
- "after 12th" / "after 12th grade" / "after plus two" = student completed 10+2 schooling = show UNDERGRADUATE (UG) programmes and Five Year Integrated courses
- "after graduation" / "after degree" / "after UG" = student completed a degree = show POSTGRADUATE (PG) programmes
- Do NOT suggest PG programmes (M.Sc., M.A., MBA) to a student asking about courses after 12th grade.
- Do NOT suggest UG programmes (B.Sc., B.A., B.Voc.) to a student asking about courses after graduation.
"""


def build_prompt(question: str, contexts: list[str]) -> str:
    """Build the user prompt with retrieved context and student question."""
    context_text = "\n\n---\n\n".join(contexts)
    return f"""Context:
{context_text}

Question: {question}

Answer the question using the context above. Be specific and directly relevant to what was asked. Only include details that answer the student's question — do not add unrelated information. If there are many items, show the most relevant ones and suggest contacting BDU for the full list."""


class RAGChat:
    """Loads the FAISS index and HuggingFace model once, then answers questions."""

    def __init__(
        self,
        index_dir: Path = INDEX_DIR,
        model_id: str = "mistralai/Mistral-7B-Instruct-v0.2",
    ):
        load_dotenv()
        hf_token = os.getenv("HF_TOKEN")
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

    def ask(self, question: str, k: int = 5) -> dict:
        """Return {"answer": str, "sources": list[str]}."""
        docs = self.db.similarity_search(question, k=k)
        contexts = [
            f"[Source {i+1}] {d.page_content}" for i, d in enumerate(docs)
        ]
        prompt = build_prompt(question, contexts)

        resp = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=700,
            temperature=0.2,
        )

        # Collect unique source metadata
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
    print("========================================")
    print("  BDU RAG - Interactive Query Console   ")
    print("========================================")
    print()

    rag = RAGChat()
    print("[READY] System loaded. Type your question.\n")

    while True:
        q = input("Ask a question (or 'exit'): ").strip()
        if q.lower() in ["exit", "quit"]:
            break
        try:
            result = rag.ask(q)
            print("\n--- Answer ---\n")
            print(result["answer"])
            if result["sources"]:
                print("\nSources:", ", ".join(result["sources"]))
            print()
        except Exception as e:
            print(f"\n[ERROR] HF chat error: {e}\n")


if __name__ == "__main__":
    main()