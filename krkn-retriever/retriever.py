import os
import re
import pickle
import argparse
import sys
import json
import time
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import faiss

# ── optional heavy deps (imported lazily) ──────────────────────────────────
# torch / sentence-transformers: used only by CrossEncoderRanker
# llama-cpp-python: used only by LlamaVulkanRanker (embedding only)
# onnxruntime / transformers: used by OnnxCrossEncoder (reranker, both paths)

# ── constants ───────────────────────────────────────────────────────────────
CROSS_ENCODER_MODEL = os.environ.get(
    "CROSS_ENCODER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
)
RETRIEVER_MODEL     = "Qwen/Qwen3-Embedding-0.6B"

MIN_FAISS_SCORE          = 0.23
FAISS_TOP2_GAP_THRESHOLD = 0.07
CE_TOP2_GAP_THRESHOLD    = 1.0
FINAL_CE_WEIGHT          = 0.8
FINAL_FAISS_WEIGHT       = 0.2
MIN_QUERY_WORDS          = 4
MIN_CE_SCORE             = -9.0
MIN_MATCH_SCORE          = float(os.environ.get("MIN_MATCH_SCORE", "0.10"))
RERANK_MAX_LENGTH        = int(os.environ.get("RERANK_MAX_LENGTH", "192"))
RERANK_BATCH_SIZE        = int(os.environ.get("RERANK_BATCH_SIZE", "16"))
RERANK_DOC_CHARS         = int(os.environ.get("RERANK_DOC_CHARS", "1800"))
RERANK_THREADS           = int(os.environ.get("RERANK_THREADS", str(min(4, os.cpu_count() or 4))))
RERANK_CANDIDATE_K       = int(os.environ.get("RERANK_CANDIDATE_K", "0"))
RERANK_ONNX_QUANTIZE     = os.environ.get("RERANK_ONNX_QUANTIZE", "1") == "1"

DEFAULT_BACKEND              = os.environ.get("RETRIEVER_BACKEND", "auto")
DEFAULT_LLAMA_MODEL          = os.environ.get("LLAMA_EMBED_MODEL", "")
DEFAULT_LLAMA_GPU_LAYERS     = int(os.environ.get("LLAMA_GPU_LAYERS", "-1"))
DEFAULT_LLAMA_RERANKER_MODEL = os.environ.get("LLAMA_RERANKER_MODEL", "")

DOCS_DIR   = os.environ.get("DOCS_DIR", "../docs")
INDEX_DIR  = "faiss-index"
INDEX_PATH = f"{INDEX_DIR}/krkn-scenarios.index"
META_PATH  = f"{INDEX_DIR}/krkn-scenarios.meta"

NON_SCENARIO_DOCS = {
    "all_scenarios_env.md", "contribute.md", "test_your_changes.md",
    "error_cases.md", "cerberus.md", "chaos-recommender.md",
    "aggregated_docs.md",
}


# ── helpers ─────────────────────────────────────────────────────────────────

def score_to_match(ce_score: float, faiss_score: float) -> float:
    ce_sigmoid = 1.0 / (1.0 + np.exp(-float(ce_score)))
    faiss = max(0.0, min(1.0, float(faiss_score)))
    return (FINAL_CE_WEIGHT * ce_sigmoid) + (FINAL_FAISS_WEIGHT * faiss)


def cuda_runtime_works() -> bool:
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        probe = torch.tensor([1.0], device="cuda")
        _ = (probe + 1).cpu().item()
        return True
    except Exception as exc:
        print(f"CUDA probe failed: {exc}")
        return False


def mps_runtime_works() -> bool:
    try:
        import torch
        mps_backend = getattr(torch.backends, "mps", None)
        if not (mps_backend and mps_backend.is_available()):
            return False
        probe = torch.tensor([1.0], device="mps")
        _ = (probe + 1).cpu().item()
        return True
    except Exception as exc:
        print(f"MPS probe failed: {exc}")
        return False


def resolve_device(device_preference="auto", cpu_only=False) -> str:
    """CUDA -> MPS -> CPU priority. Vulkan is handled separately by llama.cpp."""
    if cpu_only:
        return "cpu"
    cuda_ok = cuda_runtime_works()
    mps_ok  = mps_runtime_works()
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


# ── ONNX cross-encoder reranker ──────────────────────────────────────────────
#
# Replaces the broken LlamaCppReranker entirely.
#
# Why ONNX instead of llama.cpp reranking:
#   - llama.cpp rerank() / reranking=True is unstable across versions.
#     The relevance_score field is not reliably present in the response dict.
#   - ONNX Runtime has no GPU dependency for 20-doc workloads, exports cleanly
#     from any HuggingFace cross-encoder, and runs ~80-200 ms on CPU for 20 pairs.
#   - When onnxruntime ships a stable Vulkan EP it can be added to `providers`
#     here with no other changes.
#
# Export strategy (tried in order):
#   1. optimum[onnxruntime]  — cleanest, handles dynamic shapes automatically
#   2. torch.onnx.export     — fallback when optimum is not installed
#   3. raw transformers      — final fallback, no ONNX file needed

class OnnxCrossEncoder:
    """
    Cross-encoder backed by ONNX Runtime with a transformers fallback.
    Drop-in replacement for FlagReranker: exposes compute_score(pairs).
    """

    def __init__(self, model_name: str = CROSS_ENCODER_MODEL, cache_dir: str = None):
        self.model_name = model_name
        self.cache_dir  = cache_dir or os.environ.get(
            "HF_HOME", os.path.expanduser("~/.cache/huggingface")
        )
        self._session   = None   # onnxruntime.InferenceSession
        self._tokenizer = None
        self._hf_model  = None   # transformers fallback
        self._backend   = None   # "onnx" | "transformers"
        self._input_names = set()
        self._init()

    def _onnx_model_dir(self) -> Path:
        slug = self.model_name.replace("/", "__")
        return Path(self.cache_dir) / "onnx_rerankers" / slug

    def _init(self):
        from transformers import AutoTokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        # ── Try ONNX Runtime ──────────────────────────────────────────────────
        try:
            import onnxruntime as ort

            onnx_dir  = self._onnx_model_dir()
            onnx_file = onnx_dir / "model.onnx"
            runtime_file = onnx_dir / "model-int8.onnx"

            if not onnx_file.exists():
                print(f"Exporting {self.model_name} to ONNX (one-time)…")
                self._export_to_onnx(onnx_dir)

            if onnx_file.exists():
                if RERANK_ONNX_QUANTIZE:
                    runtime_file = self._quantize_onnx(onnx_file, runtime_file)
                else:
                    runtime_file = onnx_file

                opts = ort.SessionOptions()
                opts.intra_op_num_threads    = max(1, RERANK_THREADS)
                opts.inter_op_num_threads    = 1
                opts.graph_optimization_level = (
                    ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                )
                self._session = ort.InferenceSession(
                    str(runtime_file),
                    sess_options=opts,
                    providers=["CPUExecutionProvider"],
                )
                self._input_names = {inp.name for inp in self._session.get_inputs()}
                self._backend = "onnx"
                print(
                    f"Reranker: ONNX Runtime CPU ({self.model_name}, "
                    f"max_len={RERANK_MAX_LENGTH}, threads={RERANK_THREADS}, "
                    f"int8={runtime_file.name.endswith('int8.onnx')})"
                )
                return
        except Exception as exc:
            print(f"ONNX path failed ({exc}); using transformers fallback")

        # ── Transformers fallback ─────────────────────────────────────────────
        self._load_transformers_model()

    def _export_to_onnx(self, out_dir: Path):
        # Try optimum first
        try:
            from optimum.onnxruntime import ORTModelForSequenceClassification
            m = ORTModelForSequenceClassification.from_pretrained(
                self.model_name, export=True
            )
            m.save_pretrained(str(out_dir))
            print("ONNX export: optimum succeeded")
            return
        except Exception as exc:
            print(f"optimum export failed ({exc}); trying torch.onnx")

        # Try torch.onnx
        try:
            import torch
            from transformers import AutoModelForSequenceClassification

            hf = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            ).eval()
            dummy = self._tokenizer(
                "query", "document",
                return_tensors="pt", truncation=True, max_length=RERANK_MAX_LENGTH,
            )
            input_names = ["input_ids", "attention_mask"]
            model_args = [dummy["input_ids"], dummy["attention_mask"]]
            dynamic_axes = {
                "input_ids":      {0: "batch", 1: "seq"},
                "attention_mask": {0: "batch", 1: "seq"},
                "logits":         {0: "batch"},
            }
            if "token_type_ids" in dummy:
                input_names.append("token_type_ids")
                model_args.append(dummy["token_type_ids"])
                dynamic_axes["token_type_ids"] = {0: "batch", 1: "seq"}
            out_dir.mkdir(parents=True, exist_ok=True)
            torch.onnx.export(
                hf,
                tuple(model_args),
                str(out_dir / "model.onnx"),
                input_names=input_names,
                output_names=["logits"],
                dynamic_axes=dynamic_axes,
                opset_version=14,
            )
            print("ONNX export: torch.onnx succeeded")
        except Exception as exc:
            print(f"torch.onnx export failed ({exc}); ONNX unavailable")

    def _quantize_onnx(self, src: Path, dst: Path) -> Path:
        if dst.exists():
            return dst
        try:
            from onnxruntime.quantization import QuantType, quantize_dynamic
            quantize_dynamic(str(src), str(dst), weight_type=QuantType.QInt8)
            print("ONNX quantization: dynamic int8 succeeded")
            return dst
        except Exception as exc:
            print(f"ONNX quantization failed ({exc}); using fp32 model")
            return src

    def _load_transformers_model(self):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification
            dev = resolve_device()
            self._hf_model = (
                AutoModelForSequenceClassification.from_pretrained(self.model_name)
                .to(dev).eval()
            )
            self._backend = "transformers"
            print(f"Reranker: transformers on {dev} ({self.model_name})")
        except Exception as exc:
            raise RuntimeError(f"Could not load reranker: {exc}") from exc

    # public API ────────────────────────────────────────────────────────────

    def compute_score(self, pairs: list, batch_size: int = None) -> list:
        batch_size = batch_size or RERANK_BATCH_SIZE
        if self._backend == "onnx":
            return self._score_onnx(pairs, batch_size)
        return self._score_transformers(pairs, batch_size)

    def _score_onnx(self, pairs: list, batch_size: int) -> list:
        all_scores = []
        for i in range(0, len(pairs), batch_size):
            batch   = pairs[i : i + batch_size]
            queries = [p[0] for p in batch]
            docs    = [p[1] for p in batch]
            enc = self._tokenizer(
                queries, docs,
                padding=True, truncation=True, max_length=RERANK_MAX_LENGTH,
                return_tensors="np",
            )
            ort_in = {}
            for name in self._input_names:
                if name in enc:
                    ort_in[name] = enc[name].astype(np.int64)
            logits = self._session.run(None, ort_in)[0]  # (batch, labels)
            if logits.ndim == 2 and logits.shape[1] == 2:
                # [irrelevant, relevant] -> relevance logit
                scores = (logits[:, 1] - logits[:, 0]).tolist()
            else:
                scores = logits[:, 0].tolist()
            all_scores.extend(scores)
        return all_scores

    def _score_transformers(self, pairs: list, batch_size: int) -> list:
        import torch
        dev = next(self._hf_model.parameters()).device
        all_scores = []
        with torch.no_grad():
            for i in range(0, len(pairs), batch_size):
                batch   = pairs[i : i + batch_size]
                queries = [p[0] for p in batch]
                docs    = [p[1] for p in batch]
                enc = self._tokenizer(
                    queries, docs,
                    padding=True, truncation=True, max_length=RERANK_MAX_LENGTH,
                    return_tensors="pt",
                ).to(dev)
                logits = self._hf_model(**enc).logits
                if logits.shape[-1] == 2:
                    scores = (logits[:, 1] - logits[:, 0]).cpu().tolist()
                else:
                    scores = logits[:, 0].cpu().tolist()
                all_scores.extend(scores)
        return all_scores


# ── torch-based ranker (CUDA / MPS / CPU) ────────────────────────────────────

class CrossEncoderRanker:
    """
    Two-stage ranker:
      embed:  SentenceTransformer (Qwen3-Embedding) on CUDA/MPS/CPU
      rerank: OnnxCrossEncoder
    """

    def __init__(
        self,
        cross_encoder_model=CROSS_ENCODER_MODEL,
        retriever_model=RETRIEVER_MODEL,
        device_preference="auto",
        cpu_only=False,
    ):
        self.cross_encoder_model_name = cross_encoder_model
        self.retriever_model_name     = retriever_model
        self.cross_encoder = None
        self.retriever     = None
        self.device_preference = device_preference
        self.cpu_only          = cpu_only
        self.device            = resolve_device(device_preference, cpu_only)
        print(f"CrossEncoderRanker device: {self.device}")
        self.faiss_index = None
        self.doc_ids     = []
        self.doc_texts   = {}
        self._load_index()

    def _init_models(self):
        if self.cross_encoder is None:
            print(f"Loading OnnxCrossEncoder: {self.cross_encoder_model_name}")
            self.cross_encoder = OnnxCrossEncoder(self.cross_encoder_model_name)

        if self.retriever is None:
            from sentence_transformers import SentenceTransformer
            print(f"Loading retriever: {self.retriever_model_name}")
            self.retriever = SentenceTransformer(
                self.retriever_model_name,
                trust_remote_code=True,
                device=self.device,
            )

    def get_embedding(self, text, is_query=False):
        kwargs = dict(normalize_embeddings=True)
        if is_query:
            kwargs["prompt_name"] = "query"
        return self.retriever.encode(text, **kwargs).astype(np.float32)

    def _load_index(self):
        if Path(INDEX_PATH).exists() and Path(META_PATH).exists():
            self.faiss_index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, "rb") as f:
                self.doc_ids = pickle.load(f)
            print(f"Loaded FAISS index: {len(self.doc_ids)} docs")
        else:
            print("Warning: FAISS index not found. Run 'index' first.")

    def _load_doc_texts(self, docs_dir=DOCS_DIR):
        if self.doc_texts:
            return
        for md_file in sorted(Path(docs_dir).glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS:
                continue
            self.doc_texts[md_file.stem] = md_file.read_text(encoding="utf-8").strip()

    @staticmethod
    def prepare_for_reranking(text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)

    def build_index(self, docs_dir=DOCS_DIR):
        t0 = time.perf_counter()
        self._init_models()
        texts, ids = [], []
        for md_file in sorted(Path(docs_dir).glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS:
                continue
            text = md_file.read_text(encoding="utf-8").strip()
            texts.append(text)
            ids.append(md_file.stem)
            self.doc_texts[md_file.stem] = text

        print(f"Building FAISS index: {len(texts)} docs…")
        embeddings = self.retriever.encode(
            texts, batch_size=16, normalize_embeddings=True, show_progress_bar=True
        ).astype(np.float32)
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        Path(INDEX_DIR).mkdir(exist_ok=True, parents=True)
        faiss.write_index(index, INDEX_PATH)
        with open(META_PATH, "wb") as f:
            pickle.dump(ids, f)
        print(f"Indexed {len(ids)} docs in {time.perf_counter()-t0:.2f}s")

    def find_match(self, query: str, retrieve_k=10, rerank_k=5):
        if self.faiss_index is None:
            raise RuntimeError("Index not found. Build it first.")
        if len(query.split()) < MIN_QUERY_WORDS:
            print(f"Query rejected: need >= {MIN_QUERY_WORDS} words.")
            return []
        self._init_models()
        self._load_doc_texts()
        return _find_match_impl(
            query, retrieve_k, rerank_k,
            self.faiss_index, self.doc_ids, self.doc_texts,
            embed_fn=lambda q: self.get_embedding(q, is_query=True),
            reranker=self.cross_encoder,
        )


# ── llama.cpp Vulkan ranker ──────────────────────────────────────────────────
#
# llama.cpp is used ONLY for embedding (Vulkan compute shaders via GGML).
# Reranking always goes through OnnxCrossEncoder — the llama.cpp rerank() API
# and reranking=True flag have been removed from this codebase.
#
# The LLAMA_RERANKER_MODEL env var is accepted for backward compatibility but
# is silently ignored; no GGUF reranker model is needed.

class LlamaVulkanRanker:
    """
    Two-stage ranker:
      embed:  llama.cpp (Vulkan GGML) -> FAISS
      rerank: OnnxCrossEncoder (CPU ONNX Runtime)
    """

    def __init__(
        self,
        model_path: str,
        gpu_layers: int = -1,
        cross_encoder_model=CROSS_ENCODER_MODEL,
        device_preference="auto",
        cpu_only=False,
        reranker_model_path=DEFAULT_LLAMA_RERANKER_MODEL,
    ):
        if not model_path:
            raise ValueError(
                "Vulkan backend requires --llama-model or LLAMA_EMBED_MODEL"
            )

        from llama_cpp import Llama

        self.model_path           = model_path
        self.gpu_layers           = gpu_layers
        self.cross_encoder_model_name = cross_encoder_model
        self.device               = "vulkan"
        self.device_preference    = device_preference
        self.cpu_only             = cpu_only
        self.reranker_model_path  = reranker_model_path  # compat only, not used
        self.retriever_model_name = (
            f"llama.cpp ({Path(model_path).name}, n_gpu_layers={gpu_layers})"
        )

        print(
            f"LlamaVulkanRanker: loading embedding model "
            f"{Path(model_path).name} (n_gpu_layers={gpu_layers})"
        )
        self.llm = Llama(
            model_path=model_path,
            embedding=True,
            n_gpu_layers=gpu_layers,
            verbose=False,
            n_batch=512,
        )

        self.faiss_index   = None
        self.doc_ids       = []
        self.doc_texts     = {}
        self.cross_encoder = None  # loaded lazily

        print(
            f"LlamaVulkanRanker ready "
            f"(embed=llama.cpp/vulkan, rerank=OnnxCrossEncoder/{cross_encoder_model})"
        )
        self._load_index()
        self._init_models()

    def _init_models(self):
        if self.cross_encoder is not None:
            return
        print(f"Loading OnnxCrossEncoder: {self.cross_encoder_model_name}")
        self.cross_encoder = OnnxCrossEncoder(self.cross_encoder_model_name)

    @staticmethod
    def _extract_embedding(resp):
        if isinstance(resp, dict):
            if "data" in resp and resp["data"]:
                emb = resp["data"][0].get("embedding")
                if emb is not None:
                    return emb
            if "embedding" in resp:
                return resp["embedding"]
        if isinstance(resp, list) and resp and isinstance(resp[0], (float, int)):
            return resp
        raise RuntimeError("Cannot parse embedding from llama.cpp response")

    def _embed(self, text: str) -> np.ndarray:
        resp = self.llm.create_embedding(text)
        arr  = np.array(self._extract_embedding(resp), dtype=np.float32)
        norm = np.linalg.norm(arr)
        return arr / norm if norm > 0 else arr

    def _load_index(self):
        if Path(INDEX_PATH).exists() and Path(META_PATH).exists():
            self.faiss_index = faiss.read_index(INDEX_PATH)
            with open(META_PATH, "rb") as f:
                self.doc_ids = pickle.load(f)
            print(f"Loaded FAISS index: {len(self.doc_ids)} docs")
        else:
            print("Warning: FAISS index not found. Run 'index' first.")

    def _load_doc_texts(self, docs_dir=DOCS_DIR):
        if self.doc_texts:
            return
        for md_file in sorted(Path(docs_dir).glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS:
                continue
            self.doc_texts[md_file.stem] = md_file.read_text(encoding="utf-8").strip()

    @staticmethod
    def prepare_for_reranking(text: str) -> str:
        return re.sub(r"\n{3,}", "\n\n", text)

    def build_index(self, docs_dir=DOCS_DIR):
        t0 = time.perf_counter()
        texts, ids = [], []
        for md_file in sorted(Path(docs_dir).glob("*.md")):
            if md_file.name in NON_SCENARIO_DOCS:
                continue
            text = md_file.read_text(encoding="utf-8").strip()
            texts.append(text)
            ids.append(md_file.stem)
            self.doc_texts[md_file.stem] = text

        print(f"Building FAISS index: {len(texts)} docs (llama.cpp/vulkan)…")
        embeddings = np.vstack([self._embed(t) for t in texts]).astype(np.float32)
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        Path(INDEX_DIR).mkdir(exist_ok=True, parents=True)
        faiss.write_index(index, INDEX_PATH)
        with open(META_PATH, "wb") as f:
            pickle.dump(ids, f)
        print(f"Indexed {len(ids)} docs in {time.perf_counter()-t0:.2f}s")

    def find_match(self, query: str, retrieve_k=10, rerank_k=5):
        if self.faiss_index is None:
            raise RuntimeError("Index not found. Build it first.")
        if len(query.split()) < MIN_QUERY_WORDS:
            print(f"Query rejected: need >= {MIN_QUERY_WORDS} words.")
            return []
        self._init_models()
        self._load_doc_texts()
        return _find_match_impl(
            query, retrieve_k, rerank_k,
            self.faiss_index, self.doc_ids, self.doc_texts,
            embed_fn=self._embed,
            reranker=self.cross_encoder,
        )


# ── shared retrieval + reranking core ────────────────────────────────────────

def _compact_for_reranking(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if RERANK_DOC_CHARS > 0 and len(text) > RERANK_DOC_CHARS:
        head = text[:RERANK_DOC_CHARS]
        last_break = max(head.rfind("\n"), head.rfind(". "), head.rfind(" "))
        if last_break > 300:
            head = head[:last_break]
        return head
    return text


def _find_match_impl(
    query: str,
    retrieve_k: int,
    rerank_k: int,
    faiss_index,
    doc_ids: list,
    doc_texts: dict,
    embed_fn,
    reranker,
) -> list:
    """
    Stage 1: FAISS inner-product search
    Stage 2: OnnxCrossEncoder relevance scoring
    """
    t_search = time.perf_counter()

    # Stage 1 ─────────────────────────────────────────────────────────────────
    t_ret     = time.perf_counter()
    query_emb = embed_fn(query).reshape(1, -1)
    scores, idxs = faiss_index.search(query_emb, min(retrieve_k, len(doc_ids)))
    ret_ms    = (time.perf_counter() - t_ret) * 1000

    candidates = [
        {
            "id":              doc_ids[idx],
            "text":            doc_texts.get(doc_ids[idx], ""),
            "retrieval_score": float(scores[0][j]),
        }
        for j, idx in enumerate(idxs[0])
    ]

    if not candidates or candidates[0]["retrieval_score"] < MIN_FAISS_SCORE:
        top = candidates[0]["retrieval_score"] if candidates else float("-inf")
        print(
            f"No match: top FAISS {top:.4f} < {MIN_FAISS_SCORE:.2f}  "
            f"[ret={ret_ms:.0f}ms]"
        )
        return []

    # Stage 2 ─────────────────────────────────────────────────────────────────
    expensive_k = RERANK_CANDIDATE_K if RERANK_CANDIDATE_K > 0 else rerank_k
    expensive_k = max(1, min(len(candidates), expensive_k))
    candidates = candidates[:expensive_k]

    t_rerank = time.perf_counter()
    pairs = [
        [query, _compact_for_reranking(c["text"])]
        for c in candidates
    ]
    try:
        ce_scores = reranker.compute_score(pairs, batch_size=RERANK_BATCH_SIZE)
    except Exception as exc:
        raise RuntimeError(f"Reranker failed: {exc}") from exc
    rerank_ms = (time.perf_counter() - t_rerank) * 1000

    top_ce = max((float(s) for s in ce_scores), default=float("-inf"))
    if top_ce < MIN_CE_SCORE:
        total_ms = (time.perf_counter() - t_search) * 1000
        print(
            f"No match: top CE {top_ce:.4f} < {MIN_CE_SCORE:.1f}  "
            f"[ret={ret_ms:.0f}ms rerank={rerank_ms:.0f}ms total={total_ms:.0f}ms]"
        )
        return []

    results = []
    for i, ce_score in enumerate(ce_scores):
        results.append({
            "id":              candidates[i]["id"],
            "name":            candidates[i]["id"].replace("-", " ").title(),
            "score":           float(ce_score),
            "retrieval_score": candidates[i]["retrieval_score"],
        })
    for row in results:
        row["final_score"] = score_to_match(row["score"], row["retrieval_score"])

    results.sort(key=lambda x: x["final_score"], reverse=True)

    top_final = results[0]["final_score"]
    if top_final < MIN_MATCH_SCORE:
        total_ms = (time.perf_counter() - t_search) * 1000
        print(
            f"No match: top hybrid {top_final:.3f} < {MIN_MATCH_SCORE:.2f}  "
            f"[ret={ret_ms:.0f}ms rerank={rerank_ms:.0f}ms total={total_ms:.0f}ms]"
        )
        return []

    # Widen window when top-2 are close
    if len(results) >= 2:
        faiss_gap = abs(results[0]["retrieval_score"] - results[1]["retrieval_score"])
        ce_gap    = abs(results[0]["score"] - results[1]["score"])
        if faiss_gap < FAISS_TOP2_GAP_THRESHOLD or ce_gap < CE_TOP2_GAP_THRESHOLD:
            rerank_k = max(rerank_k, 2)

    total_ms = (time.perf_counter() - t_search) * 1000
    print(
        f"Timing: ret={ret_ms:.0f}ms  rerank={rerank_ms:.0f}ms  "
        f"total={total_ms:.0f}ms  reranked={len(candidates)}  top={top_final:.3f}"
    )
    final = results[:rerank_k]
    for row in final:
        row["timing_ms"] = {
            "retrieve": int(round(ret_ms)),
            "rerank": int(round(rerank_ms)),
            "total": int(round(total_ms)),
            "reranked": len(candidates),
        }
    return final


# ── ranker singleton ──────────────────────────────────────────────────────────

_ranker_instance = None
_ranker_config   = None


def reset_ranker():
    global _ranker_instance
    _ranker_instance = None


def resolve_backend(backend: str, llama_model_path: str) -> str:
    if backend in ("torch", "vulkan"):
        return backend
    return "vulkan" if llama_model_path else "torch"


def get_ranker(
    device_preference="auto",
    cpu_only=False,
    backend=DEFAULT_BACKEND,
    llama_model_path=DEFAULT_LLAMA_MODEL,
    llama_gpu_layers=DEFAULT_LLAMA_GPU_LAYERS,
    llama_reranker_model_path=DEFAULT_LLAMA_RERANKER_MODEL,
):
    global _ranker_instance, _ranker_config

    resolved = resolve_backend(backend, llama_model_path)
    cfg = (
        resolved, device_preference, cpu_only,
        llama_model_path, int(llama_gpu_layers), llama_reranker_model_path,
    )

    if _ranker_instance is None or _ranker_config != cfg:
        if resolved == "vulkan":
            _ranker_instance = LlamaVulkanRanker(
                model_path=llama_model_path,
                gpu_layers=int(llama_gpu_layers),
                cross_encoder_model=CROSS_ENCODER_MODEL,
                device_preference=device_preference,
                cpu_only=cpu_only,
                reranker_model_path=llama_reranker_model_path,
            )
        else:
            _ranker_instance = CrossEncoderRanker(
                device_preference=device_preference,
                cpu_only=cpu_only,
            )
        _ranker_config = cfg

    return _ranker_instance


# ── display / export (CLI) ────────────────────────────────────────────────────

def display_results(result: list):
    if not result:
        print("\nNo results found.")
        return

    clear = result[:1]
    if len(result) >= 2:
        faiss_gap = abs(result[0]["retrieval_score"] - result[1]["retrieval_score"])
        ce_gap    = abs(result[0]["score"] - result[1]["score"])
        if faiss_gap < FAISS_TOP2_GAP_THRESHOLD or ce_gap < CE_TOP2_GAP_THRESHOLD:
            clear = result[:2]

    print("\n" + "=" * 95)
    print("Clear answer" if len(clear) == 1 else "Clear answers")
    print("=" * 95)
    for i, r in enumerate(clear, 1):
        print(
            f"  [{i}] {r['name']:<40}"
            f" | CE: {r['score']:>7.4f}"
            f" | FAISS: {r['retrieval_score']:>7.4f}"
            f" | hybrid: {r['final_score']:>7.4f}"
        )

    print("\n" + "=" * 95)
    print("Most relevant scenarios")
    print("=" * 95)
    for i, r in enumerate(result, 1):
        print(
            f"  [{i}] {r['name']:<40}"
            f" | CE: {r['score']:>7.4f}"
            f" | FAISS: {r['retrieval_score']:>7.4f}"
            f" | hybrid: {r['final_score']:>7.4f}"
        )
    print("=" * 95)


def export_results(query, results, output_path, ranker, include_text=False):
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query":     query,
        "results":   [],
    }
    for r in results:
        row = {
            "id":              r["id"],
            "name":            r["name"],
            "score":           r["score"],
            "retrieval_score": r["retrieval_score"],
        }
        if include_text:
            row["text"] = ranker.doc_texts.get(r["id"], "")
        payload["results"].append(row)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported to: {out}")


def run_single_query(
    ranker, query, retrieve_k, rerank_k,
    export_path=None, include_text=False, display=True,
):
    if display:
        print(f"\nSearching: {query}")
    res = ranker.find_match(query, retrieve_k, rerank_k)
    if display:
        display_results(res[:5])
    if export_path:
        export_results(query, res, export_path, ranker, include_text=include_text)
    return res


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Two-stage retrieval: embed (llama.cpp/torch) + rerank (ONNX)"
    )
    parser.add_argument(
        "--device", choices=["auto", "cuda", "mps", "cpu"],
        default=os.environ.get("RETRIEVER_DEVICE", "auto"),
    )
    parser.add_argument(
        "--cpu-only", action="store_true",
        default=os.environ.get("RETRIEVER_CPU_ONLY", "0") == "1",
    )
    parser.add_argument(
        "--backend", choices=["auto", "torch", "vulkan"],
        default=DEFAULT_BACKEND,
        help="auto: vulkan when LLAMA_EMBED_MODEL set, else torch",
    )
    parser.add_argument("--llama-model",          default=DEFAULT_LLAMA_MODEL)
    parser.add_argument("--llama-gpu-layers",     type=int, default=DEFAULT_LLAMA_GPU_LAYERS)
    parser.add_argument(
        "--llama-reranker-model", default=DEFAULT_LLAMA_RERANKER_MODEL,
        help="Kept for backward compat; ONNX reranker is always used now",
    )

    sub = parser.add_subparsers(dest="cmd")

    idx_p = sub.add_parser("index")
    idx_p.add_argument("--docs", default=DOCS_DIR)

    qry_p = sub.add_parser("query")
    qry_p.add_argument("query", nargs="?")
    qry_p.add_argument("--retrieve-k",   type=int, default=10)
    qry_p.add_argument("--rerank-k",     type=int, default=5)
    qry_p.add_argument("--interactive",  "-i", action="store_true", default=True)
    qry_p.add_argument("--non-interactive",    action="store_false", dest="interactive")
    qry_p.add_argument("--jsonl-stdin",  action="store_true")
    qry_p.add_argument("--export",       default=None)
    qry_p.add_argument("--include-text", action="store_true")

    args   = parser.parse_args()
    ranker = get_ranker(
        device_preference=args.device,
        cpu_only=args.cpu_only,
        backend=args.backend,
        llama_model_path=args.llama_model,
        llama_gpu_layers=args.llama_gpu_layers,
        llama_reranker_model_path=args.llama_reranker_model,
    )

    if args.cmd == "index":
        ranker.build_index(args.docs)

    elif args.cmd == "query":
        if args.jsonl_stdin:
            for raw in sys.stdin:
                raw = raw.strip()
                if not raw:
                    continue
                req = json.loads(raw)
                q   = str(req.get("query", "")).strip()
                if not q:
                    print(json.dumps({"ok": False, "error": "empty_query"}), flush=True)
                    continue
                if q.lower() in ("exit", "quit"):
                    print(json.dumps({"ok": True, "done": True}), flush=True)
                    break
                run_single_query(
                    ranker, q,
                    int(req.get("retrieve_k", args.retrieve_k)),
                    int(req.get("rerank_k",   args.rerank_k)),
                    export_path=req.get("export"),
                    include_text=bool(req.get("include_text", args.include_text)),
                    display=False,
                )
                print(json.dumps({"ok": True, "done": False}), flush=True)
        elif args.interactive and not args.query:
            print("\nInteractive mode (type 'exit' to quit)\n")
            while True:
                q = input("Query: ").strip()
                if not q:
                    continue
                if q.lower() in ("exit", "quit"):
                    break
                run_single_query(ranker, q, args.retrieve_k, args.rerank_k)
        elif args.query:
            run_single_query(
                ranker, args.query, args.retrieve_k, args.rerank_k,
                export_path=args.export,
                include_text=args.include_text,
            )
        else:
            print("\nNo query provided.")
            parser.print_help()


if __name__ == "__main__":
    main()
