import os
import re
import pickle
import argparse
import sys
import json
import time
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
DEFAULT_BACKEND = os.environ.get("RETRIEVER_BACKEND", "auto")
DEFAULT_LLAMA_MODEL = os.environ.get("LLAMA_EMBED_MODEL", "")
DEFAULT_LLAMA_GPU_LAYERS = int(os.environ.get("LLAMA_GPU_LAYERS", "-1"))


def cuda_runtime_works():
    """Return True only when CUDA is usable for real tensor ops."""
    if not torch.cuda.is_available():
        return False
    try:
        probe = torch.tensor([1.0], device="cuda")
        _ = (probe + 1).cpu().item()
        return True
    except Exception as exc:
        print(f"CUDA probe failed, falling back from CUDA: {exc}")
        return False


def mps_runtime_works():
    """Return True only when MPS is usable for real tensor ops."""
    mps_backend = getattr(torch.backends, "mps", None)
    if not (mps_backend and mps_backend.is_available()):
        return False
    try:
        probe = torch.tensor([1.0], device="mps")
        _ = (probe + 1).cpu().item()
        return True
    except Exception as exc:
        print(f"MPS probe failed, falling back from MPS: {exc}")
        return False


def optimize_gpu_memory(device="cpu"):
    """Clear CUDA cache when CUDA is active."""
    if device == "cuda":
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass


def resolve_device(device_preference="auto", cpu_only=False):
    """
    Select acceleration-first device.
    Priority for auto: CUDA -> MPS -> CPU.
    """
    if cpu_only:
        return "cpu"

    cuda_ok = cuda_runtime_works()
    mps_ok = mps_runtime_works()

    if device_preference and device_preference != "auto":
        if device_preference == "cuda" and cuda_ok:
            return "cuda"
        if device_preference == "mps" and mps_ok:
            return "mps"
        if device_preference == "cpu":
            return "cpu"
        print(f"Requested device '{device_preference}' unavailable; falling back to auto")

    if cuda_ok:
        return "cuda"
    if mps_ok:
        return "mps"
    return "cpu"

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
    def __init__(self, cross_encoder_model=CROSS_ENCODER_MODEL, retriever_model=RETRIEVER_MODEL, device_preference="auto", cpu_only=False):
        self.cross_encoder_model_name = cross_encoder_model
        self.retriever_model_name = retriever_model
        
        self.cross_encoder = None
        self.retriever = None
        
        self.device_preference = device_preference
        self.cpu_only = cpu_only
        self.device = resolve_device(device_preference=device_preference, cpu_only=cpu_only)
        optimize_gpu_memory(self.device)
        print(f"Using device: {self.device} (preference={self.device_preference}, cpu_only={self.cpu_only})")
        self.faiss_index = None
        self.doc_ids = []
        self.doc_texts = {}
        
        self._load_index()

    def _init_models(self):
        if self.cross_encoder is None:
            print(f"Loading Cross-Encoder: {self.cross_encoder_model_name}")
            use_fp16 = self.device == "cuda"
            try:
                self.cross_encoder = FlagReranker(
                    self.cross_encoder_model_name,
                    use_fp16=use_fp16,
                    devices=self.device,
                )
            except TypeError:
                # Older FlagEmbedding versions do not accept `devices`.
                self.cross_encoder = FlagReranker(self.cross_encoder_model_name, use_fp16=use_fp16)

        if self.retriever is None:
            print(f"Loading Qwen Embedding Model: {self.retriever_model_name}")
            self.retriever = SentenceTransformer(
                self.retriever_model_name,
                trust_remote_code=True,
                device=self.device,
            )
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
        build_start = time.perf_counter()
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
        print(f"Index build time: {(time.perf_counter() - build_start):.2f}s")
    

    def find_match(self, query, retrieve_k=10, rerank_k=5):

        if self.faiss_index is None:
            raise RuntimeError("Index not found. Please build it first.")

        self._init_models()
        self._load_doc_texts()

        search_start = time.perf_counter()

        # Stage 1: Fast FAISS retrieval with large pool
        retrieval_start = time.perf_counter()
        query_emb = self.get_embedding(query, is_query=True).reshape(1, -1)
        scores, idxs = self.faiss_index.search(query_emb, min(retrieve_k, len(self.doc_ids)))
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        candidates = []
        for j, idx in enumerate(idxs[0]):
            doc_id = self.doc_ids[idx]
            candidates.append({
                "id": doc_id,
                "text": self.doc_texts.get(doc_id, ""),
                "retrieval_score": float(scores[0][j])
            })

        # Stage 2: Cross-Encoder reranking on full candidate pool
        rerank_start = time.perf_counter()
        pairs = [[query, self.prepare_for_reranking(c["text"])] for c in candidates]
        batch_size = 16 if self.device == "cuda" else 8
        ce_scores = self.cross_encoder.compute_score(pairs, batch_size=batch_size)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000

        results = []
        for i, ce_score in enumerate(ce_scores):
            results.append({
                "id": candidates[i]["id"],
                "name": candidates[i]["id"].replace("-", " ").title(),
                "score": float(ce_score),
                "retrieval_score": candidates[i]["retrieval_score"]
            })

        results_sorted = sorted(results, key=lambda x: x["score"], reverse=True)
        total_ms = (time.perf_counter() - search_start) * 1000

        if self.device == "cuda":
            torch.cuda.empty_cache()

        print(f"Timing: retrieval={retrieval_ms:.1f}ms | rerank={rerank_ms:.1f}ms | total={total_ms:.1f}ms")
        return results_sorted[:rerank_k]


class LlamaVulkanRanker:
    def __init__(self, model_path, gpu_layers=-1, cross_encoder_model=CROSS_ENCODER_MODEL, device_preference="auto", cpu_only=False):
        if not model_path:
            raise ValueError("Vulkan backend requires --llama-model or LLAMA_EMBED_MODEL")

        from llama_cpp import Llama

        self.cross_encoder_model_name = cross_encoder_model
        self.retriever_model_name = f"llama.cpp embedding ({Path(model_path).name})"
        self.model_path = model_path
        self.gpu_layers = gpu_layers
        self.device = "vulkan"
        self.device_preference = device_preference
        self.cpu_only = cpu_only
        self.rerank_device = resolve_device(device_preference=device_preference, cpu_only=cpu_only)

        self.llm = Llama(
            model_path=self.model_path,
            embedding=True,
            n_gpu_layers=self.gpu_layers,
            verbose=False,
        )

        self.faiss_index = None
        self.doc_ids = []
        self.doc_texts = {}
        self.cross_encoder = None

        print(
            f"Using backend: vulkan (model={self.model_path}, n_gpu_layers={self.gpu_layers}, "
            f"reranker={self.cross_encoder_model_name}, rerank_device={self.rerank_device})"
        )
        self._load_index()
        self._init_models()

    def _init_models(self):
        if self.cross_encoder is not None:
            return
        use_fp16 = self.rerank_device == "cuda"
        try:
            self.cross_encoder = FlagReranker(
                self.cross_encoder_model_name,
                use_fp16=use_fp16,
                devices=self.rerank_device,
            )
        except TypeError:
            self.cross_encoder = FlagReranker(self.cross_encoder_model_name, use_fp16=use_fp16)

    @staticmethod
    def _extract_embedding(resp):
        if isinstance(resp, dict):
            if "data" in resp and isinstance(resp["data"], list) and resp["data"]:
                emb = resp["data"][0].get("embedding")
                if emb is not None:
                    return emb
            if "embedding" in resp:
                return resp["embedding"]
        if isinstance(resp, list) and resp and isinstance(resp[0], (float, int)):
            return resp
        raise RuntimeError("Could not parse embedding response from llama.cpp")

    def _embed(self, text):
        resp = self.llm.create_embedding(text)
        emb = self._extract_embedding(resp)
        arr = np.array(emb, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr

    def _load_index(self):
        if Path(INDEX_PATH).exists() and Path(META_PATH).exists():
            self.faiss_index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, "rb") as f:
                self.doc_ids = pickle.load(f)
            print(f"Loaded FAISS index with {len(self.doc_ids)} documents")
        else:
            print("Warning: FAISS index not found. Run with 'index' command first.")

    def _load_doc_texts(self, docs_dir=DOCS_DIR):
        if self.doc_texts:
            return
        docs_path = Path(docs_dir)
        for md_file in sorted(docs_path.glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS:
                continue
            self.doc_texts[md_file.stem] = md_file.read_text(encoding="utf-8").strip()

    @staticmethod
    def prepare_for_reranking(text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)

    def build_index(self, docs_dir=DOCS_DIR):
        build_start = time.perf_counter()
        texts, ids = [], []
        docs_path = Path(docs_dir)

        for md_file in sorted(docs_path.glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS:
                continue
            text = md_file.read_text(encoding="utf-8").strip()
            texts.append(text)
            ids.append(md_file.stem)
            self.doc_texts[md_file.stem] = text

        print(f"Building FAISS index for {len(texts)} documents (vulkan backend)...")
        embeddings = np.vstack([self._embed(t) for t in texts]).astype(np.float32)

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        Path(INDEX_DIR).mkdir(exist_ok=True, parents=True)
        faiss.write_index(index, INDEX_PATH)
        with open(META_PATH, "wb") as f:
            pickle.dump(ids, f)
        print(f"Indexed {len(ids)} scenarios")
        print(f"Index build time: {(time.perf_counter() - build_start):.2f}s")

    def find_match(self, query, retrieve_k=10, rerank_k=5):
        if self.faiss_index is None:
            raise RuntimeError("Index not found. Please build it first.")

        self._init_models()
        self._load_doc_texts()
        search_start = time.perf_counter()

        retrieval_start = time.perf_counter()
        query_emb = self._embed(query).reshape(1, -1)
        scores, idxs = self.faiss_index.search(query_emb, min(retrieve_k, len(self.doc_ids)))
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        candidates = []
        for j, idx in enumerate(idxs[0]):
            doc_id = self.doc_ids[idx]
            retrieval_score = float(scores[0][j])
            candidates.append({
                "id": doc_id,
                "name": doc_id.replace("-", " ").title(),
                "text": self.doc_texts.get(doc_id, ""),
                "score": retrieval_score,
                "retrieval_score": retrieval_score,
            })

        rerank_start = time.perf_counter()
        pairs = [[query, self.prepare_for_reranking(c["text"])] for c in candidates]
        batch_size = 16 if self.rerank_device == "cuda" else 8

        try:
            ce_scores = self.cross_encoder.compute_score(pairs, batch_size=batch_size)
            results = []
            for i, ce_score in enumerate(ce_scores):
                results.append({
                    "id": candidates[i]["id"],
                    "name": candidates[i]["name"],
                    "score": float(ce_score),
                    "retrieval_score": candidates[i]["retrieval_score"],
                })
            results = sorted(results, key=lambda x: x["score"], reverse=True)
        except Exception as exc:
            print(f"Reranker failed on backend={self.rerank_device}, falling back to cosine scores: {exc}")
            results = sorted(candidates, key=lambda x: x["retrieval_score"], reverse=True)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000

        total_ms = (time.perf_counter() - search_start) * 1000
        print(f"Timing: retrieval={retrieval_ms:.1f}ms | rerank={rerank_ms:.1f}ms | total={total_ms:.1f}ms")
        return results[:rerank_k]

_ranker_instance = None
_ranker_config = None

def reset_ranker():
    global _ranker_instance
    _ranker_instance = None

def resolve_backend(backend, llama_model_path):
    if backend in ("torch", "vulkan"):
        return backend
    if llama_model_path:
        return "vulkan"
    return "torch"


def get_ranker(device_preference="auto", cpu_only=False, backend=DEFAULT_BACKEND, llama_model_path=DEFAULT_LLAMA_MODEL, llama_gpu_layers=DEFAULT_LLAMA_GPU_LAYERS):
    global _ranker_instance, _ranker_config

    resolved_backend = resolve_backend(backend, llama_model_path)
    desired_config = (resolved_backend, device_preference, cpu_only, llama_model_path, int(llama_gpu_layers))

    if _ranker_instance is None or _ranker_config != desired_config:
        if resolved_backend == "vulkan":
            _ranker_instance = LlamaVulkanRanker(
                model_path=llama_model_path,
                gpu_layers=int(llama_gpu_layers),
                cross_encoder_model=CROSS_ENCODER_MODEL,
                device_preference=device_preference,
                cpu_only=cpu_only,
            )
        else:
            _ranker_instance = CrossEncoderRanker(
                device_preference=device_preference,
                cpu_only=cpu_only,
            )
        _ranker_config = desired_config

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
    parser.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default=os.environ.get("RETRIEVER_DEVICE", "auto"), help="Device policy: acceleration-first by default (auto)")
    parser.add_argument("--cpu-only", action="store_true", default=os.environ.get("RETRIEVER_CPU_ONLY", "0") == "1", help="Force CPU execution")
    parser.add_argument("--backend", choices=["auto", "torch", "vulkan"], default=DEFAULT_BACKEND, help="Retrieval backend. auto picks vulkan when LLAMA_EMBED_MODEL is set, otherwise torch")
    parser.add_argument("--llama-model", default=DEFAULT_LLAMA_MODEL, help="Path to GGUF embedding model for vulkan backend")
    parser.add_argument("--llama-gpu-layers", type=int, default=DEFAULT_LLAMA_GPU_LAYERS, help="llama.cpp n_gpu_layers for vulkan backend")
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

    ranker = get_ranker(
        device_preference=args.device,
        cpu_only=args.cpu_only,
        backend=args.backend,
        llama_model_path=args.llama_model,
        llama_gpu_layers=args.llama_gpu_layers,
    )

    if args.cmd == "index":
        ranker.build_index(args.docs)
    elif args.cmd == "query":
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