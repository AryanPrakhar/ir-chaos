import os
import re
import pickle
import argparse
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import faiss
import torch
from FlagEmbedding import FlagReranker
from sentence_transformers import SentenceTransformer

# SOTA Performance
# CROSS_ENCODER_MODEL = "BAAI/bge-reranker-v2-m3"
CROSS_ENCODER_MODEL = "BAAI/bge-reranker-base"
RETRIEVER_MODEL = "Qwen/Qwen3-Embedding-0.6B"

def optimize_gpu_memory():
    """Clear GPU cache and configure for optimal performance."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

DOCS_DIR = os.environ.get("DOCS_DIR", "../docs")

INDEX_DIR = "faiss-index"
INDEX_PATH = f"{INDEX_DIR}/krkn-scenarios.index"
META_PATH = f"{INDEX_DIR}/krkn-scenarios.meta"

NON_SCENARIO_DOCS = {
    "all_scenarios_env.md", "contribute.md", "test_your_changes.md",
    "error_cases.md", "cerberus.md", "chaos-recommender.md",
    "aggregated_docs.md",
}

class CrossEncoderRanker:
    def __init__(self, cross_encoder_model=CROSS_ENCODER_MODEL, retriever_model=RETRIEVER_MODEL):
        optimize_gpu_memory()
        self.cross_encoder_model_name = cross_encoder_model
        self.retriever_model_name = retriever_model
        
        self.cross_encoder = None
        self.retriever = None
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        self.faiss_index = None
        self.doc_ids = []
        self.doc_texts = {}
        
        self._load_index()

    def _init_models(self):
        if self.cross_encoder is None:
            print(f"Loading Cross-Encoder: {self.cross_encoder_model_name}")
            self.cross_encoder = FlagReranker(self.cross_encoder_model_name, use_fp16=True)

        if self.retriever is None:
            print(f"Loading Qwen Embedding Model: {self.retriever_model_name}")
            self.retriever = SentenceTransformer(self.retriever_model_name, trust_remote_code=True)
            print("Retriever loaded successfully")

    def get_embedding(self, text, is_query=False):
            if is_query:
                embedding = self.retriever.encode(
                    text, 
                    prompt_name="query", 
                    normalize_embeddings=True
                )
            else:
                embedding = self.retriever.encode(
                    text, 
                    normalize_embeddings=True
                )
                
            return embedding.astype(np.float32)

    def _load_index(self):
        if Path(INDEX_PATH).exists() and Path(META_PATH).exists():
            self.faiss_index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, "rb") as f:
                self.doc_ids = pickle.load(f)
            print(f"Loaded FAISS index with {len(self.doc_ids)} documents")
        else:
            print(f"Warning: FAISS index not found. Run with 'index' command first.")

    def _load_doc_texts(self, docs_dir=DOCS_DIR):
        if self.doc_texts: return
        docs_path = Path(docs_dir)
        for md_file in sorted(docs_path.glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS: continue
            self.doc_texts[md_file.stem] = md_file.read_text(encoding="utf-8").strip()

    def prepare_for_reranking(self, text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)

    def build_index(self, docs_dir=DOCS_DIR):
        self._init_models()
        texts, ids = [], []
        docs_path = Path(docs_dir)

        for md_file in sorted(docs_path.glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS: continue
            text = md_file.read_text(encoding="utf-8").strip()
            texts.append(text)
            ids.append(md_file.stem)
            self.doc_texts[md_file.stem] = text

        print(f"Building FAISS index for {len(texts)} documents...")
        
        embeddings = self.retriever.encode(
            texts, 
            batch_size=16, 
            normalize_embeddings=True,
            show_progress_bar=True
        ).astype(np.float32)
        
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        Path(INDEX_DIR).mkdir(exist_ok=True, parents=True)
        faiss.write_index(index, INDEX_PATH)
        with open(META_PATH, "wb") as f:
            pickle.dump(ids, f)
        print(f"Indexed {len(ids)} scenarios")
    

    def find_match(self, query, retrieve_k=10, rerank_k=5):

        if self.faiss_index is None:
            raise RuntimeError("Index not found. Please build it first.")

        self._init_models()
        self._load_doc_texts()

        # Stage 1: Fast FAISS retrieval with large pool
        query_emb = self.get_embedding(query, is_query=True).reshape(1, -1)
        scores, idxs = self.faiss_index.search(query_emb, min(retrieve_k, len(self.doc_ids)))

        candidates = []
        for j, idx in enumerate(idxs[0]):
            doc_id = self.doc_ids[idx]
            candidates.append({
                "id": doc_id,
                "text": self.doc_texts.get(doc_id, ""),
                "retrieval_score": float(scores[0][j])
            })

        # Stage 2: Cross-Encoder reranking on full candidate pool
        pairs = [[query, self.prepare_for_reranking(c["text"])] for c in candidates]
        batch_size = 16 if self.device == "cuda" else 8
        ce_scores = self.cross_encoder.compute_score(pairs, batch_size=batch_size)

        results = []
        for i, ce_score in enumerate(ce_scores):
            results.append({
                "id": candidates[i]["id"],
                "name": candidates[i]["id"].replace("-", " ").title(),
                "score": float(ce_score),
                "retrieval_score": candidates[i]["retrieval_score"]
            })

        results_sorted = sorted(results, key=lambda x: x["score"], reverse=True)
        
        torch.cuda.empty_cache()
        return results_sorted[:rerank_k]

_ranker_instance = None

def get_ranker():
    global _ranker_instance
    if _ranker_instance is None:
        _ranker_instance = CrossEncoderRanker()
    return _ranker_instance

def display_results(result):
    if not result:
        print("\nNo results found.")
        return
    
    print("\n" + "=" * 95)
    print("RERANKED RESULTS (Top-K)")
    print("=" * 95)
    for i, r in enumerate(result, 1):
        print(f"  [{i}] {r['name']:<40} | Cross-Encoder: {r['score']:>7.4f} | FAISS: {r['retrieval_score']:>7.4f}")
    print("=" * 95)

def export_results(query, results, output_path, ranker, include_text=False):
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "results": [],
    }

    for r in results:
        row = {
            "id": r["id"],
            "name": r["name"],
            "score": r["score"],
            "retrieval_score": r["retrieval_score"],
        }
        if include_text:
            row["text"] = ranker.doc_texts.get(r["id"], "")
        payload["results"].append(row)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported retrieval payload to: {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Two-stage retrieval (SentenceTransformers + Reranker)")
    subparsers = parser.add_subparsers(dest="cmd")

    index_parser = subparsers.add_parser("index")
    index_parser.add_argument("--docs", default=DOCS_DIR)

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("query", nargs="?")
    query_parser.add_argument("--retrieve-k", type=int, default=10, help="FAISS candidate pool size (default: 10)")
    query_parser.add_argument("--rerank-k", type=int, default=5, help="Top results after Cross-Encoder reranking (default: 5)")
    query_parser.add_argument("--interactive", "-i", action="store_true")
    query_parser.add_argument("--export", default=None, help="Write query + top results to JSON (for inference handoff)")
    query_parser.add_argument("--include-text", action="store_true", help="Include full scenario text in exported JSON")

    args = parser.parse_args()

    if args.cmd == "index":
        get_ranker().build_index(args.docs)
    elif args.cmd == "query":
        ranker = get_ranker()
        if args.interactive:
            print("\nInteractive Query Mode (type 'exit' or 'quit' to end)\n")
            while True:
                q = input("Query: ").strip()
                if not q:
                    print("Empty query. Please try again.")
                    continue
                if q.lower() in ("exit", "quit"):
                    print("\nGoodbye!")
                    break
                print(f"\nSearching for: {q}")
                res = ranker.find_match(q, args.retrieve_k, args.rerank_k)
                display_results(res[:5])
        elif args.query:
            print(f"\nSearching for: {args.query}")
            res = ranker.find_match(args.query, args.retrieve_k, args.rerank_k)
            display_results(res[:5])
            if args.export:
                export_results(args.query, res, args.export, ranker, include_text=args.include_text)

if __name__ == "__main__":
    main()