"""
api.py - Flask API wrapper for the BDU RAG Chat system.
Serves the frontend and exposes a /chat endpoint for queries.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from query import RAGChat

app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)

# --- RAG initialization ---
print("========================================")
print("  BDU RAG - API Server                  ")
print("========================================")
print()
print("[INIT] Loading RAG model and vector store...")
rag = RAGChat()
print("[READY] RAG system loaded. Server starting.\n")


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    query = body.get("query", "").strip()

    if not query:
        return jsonify({"error": "Missing 'query' in request body."}), 400

    try:
        result = rag.ask(query)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
