#!/usr/bin/env python3
"""
FastAPI service wrapper for krkn-retriever.
"""

import os
import time
import logging
import math
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from retriever import (
    DOCS_DIR,
    INDEX_PATH,
    META_PATH,
    DEFAULT_BACKEND,
    DEFAULT_LLAMA_MODEL,
    DEFAULT_LLAMA_GPU_LAYERS,
    DEFAULT_LLAMA_RERANKER_MODEL,
    FAISS_TOP2_GAP_THRESHOLD,
    CE_TOP2_GAP_THRESHOLD,
    FINAL_CE_WEIGHT,
    FINAL_FAISS_WEIGHT,
    get_ranker,
    reset_ranker,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEVICE = os.environ.get("RETRIEVER_DEVICE", "auto")
CPU_ONLY = os.environ.get("RETRIEVER_CPU_ONLY", "0") == "1"
BACKEND = os.environ.get("RETRIEVER_BACKEND", DEFAULT_BACKEND)
LLAMA_MODEL = os.environ.get("LLAMA_EMBED_MODEL", DEFAULT_LLAMA_MODEL)
LLAMA_GPU_LAYERS = int(os.environ.get("LLAMA_GPU_LAYERS", str(DEFAULT_LLAMA_GPU_LAYERS)))
LLAMA_RERANKER_MODEL = os.environ.get("LLAMA_RERANKER_MODEL", DEFAULT_LLAMA_RERANKER_MODEL)
RETRIEVE_K = int(os.environ.get("RETRIEVE_K", "10"))
RERANK_K = int(os.environ.get("RERANK_K", "5"))
FORCE_REINDEX = os.environ.get("FORCE_REINDEX", "false").lower() == "true"
QUERY_CACHE_SIZE = int(os.environ.get("RETRIEVER_QUERY_CACHE_SIZE", "256"))

ranker = None
query_cache: "OrderedDict[Tuple[str, int, int], List[dict]]" = OrderedDict()


class ChatMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    model: str = "krkn-retriever"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 512
    stream: Optional[bool] = False
    retrieve_k: Optional[int] = None
    rerank_k: Optional[int] = None


class QueryChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class QueryResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[QueryChoice]
    usage: Usage
    scenario_name: Optional[str] = None
    scenario_names: List[str] = []
    clear_answers: List[dict] = []
    results: List[dict] = []


class ScenarioQueryRequest(BaseModel):
    query: str
    retrieve_k: Optional[int] = None
    rerank_k: Optional[int] = None


class ScenarioQueryResponse(BaseModel):
    query: str
    scenario_name: Optional[str] = None
    scenario_names: List[str] = []
    clear_answers: List[dict] = []
    results: List[dict] = []


class CompactQueryResponse(BaseModel):
    answer: str
    scenario_names: List[str] = []
    clear_answers: List[dict] = []
    results: List[dict] = []


class RetrieveRequest(BaseModel):
    query: str
    k: Optional[int] = None
    retrieve_k: Optional[int] = None
    rerank_k: Optional[int] = None


class RetrieveResult(BaseModel):
    id: str
    name: str
    retrieval_score: float
    rerank_score: float
    final_score: float
    score_percent: float


class RetrieveResponse(BaseModel):
    query: str
    results: List[RetrieveResult]
    top_match: Optional[str] = None
    message: str


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _display_score(row: dict) -> float:
    if "final_score" in row:
        return max(0.0, min(1.0, float(row.get("final_score", 0.0))))
    # Back-compat for older payloads without final_score
    ce = float(row.get("score", 0.0))
    faiss = max(0.0, min(1.0, float(row.get("retrieval_score", 0.0))))
    ce_sigmoid = 1.0 / (1.0 + math.exp(-ce))
    return (FINAL_CE_WEIGHT * ce_sigmoid) + (FINAL_FAISS_WEIGHT * faiss)


def _with_display_scores(results: List[dict]) -> List[dict]:
    enriched = []
    for row in results:
        item = dict(row)
        score = _display_score(item)
        item["display_score"] = round(score, 4)
        item["display_score_pct"] = round(score * 100.0, 1)
        enriched.append(item)
    return enriched


def _clear_answers(results: List[dict]) -> List[dict]:
    if not results:
        return []
    clear = results[:1]
    if len(results) >= 2:
        faiss_gap = abs(results[0]["retrieval_score"] - results[1]["retrieval_score"])
        ce_gap = abs(results[0]["score"] - results[1]["score"])
        if faiss_gap < FAISS_TOP2_GAP_THRESHOLD or ce_gap < CE_TOP2_GAP_THRESHOLD:
            clear = results[:2]
    return clear


def _extract_user_query(messages: List[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content.strip()
    return ""


def _normalize_relevance(results: List[dict]) -> List[float]:
    if not results:
        return []

    raw_scores = [
        float(item.get("final_score", item.get("retrieval_score", 0.0)))
        for item in results
    ]
    low = min(raw_scores)
    high = max(raw_scores)

    if high == low:
        base = 1.0 if high > 0 else 0.0
        return [base for _ in raw_scores]

    return [(score - low) / (high - low) for score in raw_scores]


def _cache_get(cache_key: Tuple[str, int, int]) -> Optional[List[dict]]:
    cached = query_cache.get(cache_key)
    if cached is None:
        return None
    query_cache.move_to_end(cache_key)
    return [dict(row) for row in cached]


def _cache_put(cache_key: Tuple[str, int, int], results: List[dict]) -> None:
    query_cache[cache_key] = [dict(row) for row in results]
    query_cache.move_to_end(cache_key)
    while len(query_cache) > QUERY_CACHE_SIZE:
        query_cache.popitem(last=False)


def _rank_with_cache(query: str, retrieve_k: int, rerank_k: int) -> tuple[List[dict], int, bool]:
    cache_key = (query, retrieve_k, rerank_k)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached, 0, True

    started = time.perf_counter()
    results = ranker.find_match(query, retrieve_k=retrieve_k, rerank_k=rerank_k)
    elapsed_ms = int(round((time.perf_counter() - started) * 1000))
    _cache_put(cache_key, results)
    return results, elapsed_ms, False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ranker

    logger.info("Starting krkn-retriever FastAPI service")
    reset_ranker()
    query_cache.clear()
    ranker = get_ranker(
        device_preference=DEVICE,
        cpu_only=CPU_ONLY,
        backend=BACKEND,
        llama_model_path=LLAMA_MODEL,
        llama_gpu_layers=LLAMA_GPU_LAYERS,
        llama_reranker_model_path=LLAMA_RERANKER_MODEL,
    )

    if FORCE_REINDEX or not (os.path.exists(INDEX_PATH) and os.path.exists(META_PATH)):
        logger.info("Building FAISS index (startup)")
        ranker.build_index(DOCS_DIR)
        ranker._load_index()
    else:
        logger.info("Using existing FAISS index")

    # Warm all heavyweight resources once at startup.
    if hasattr(ranker, "_init_models"):
        ranker._init_models()
    if hasattr(ranker, "_load_doc_texts"):
        ranker._load_doc_texts()
    logger.info("Retriever warmup complete (cache size=%d)", QUERY_CACHE_SIZE)

    yield

    logger.info("Shutting down krkn-retriever FastAPI service")


app = FastAPI(
    title="krkn Retriever Service",
    version="1.0.0",
    description="FAISS + Cross-Encoder scenario retrieval for krkn",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "service": "krkn-retriever",
        "backend": BACKEND,
        "retrieve_k": RETRIEVE_K,
        "rerank_k": RERANK_K,
        "endpoints": {
            "health": "/health",
            "retrieve": "/retrieve",
            "chat_completions_legacy": "/v1/chat/completions",
            "legacy_query": "/query",
        },
    }


@app.get("/health")
async def health_check():
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")
    return {
        "status": "healthy",
        "backend": BACKEND,
        "index_loaded": ranker.faiss_index is not None,
        "documents_indexed": len(ranker.doc_ids),
    }


@app.post("/v1/chat/completions", response_model=QueryResponse)
async def chat_completions(request: QueryRequest):
    if request.stream:
        raise HTTPException(status_code=400, detail="Streaming not supported")
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    query = _extract_user_query(request.messages)
    if not query:
        raise HTTPException(status_code=400, detail="No user message found")

    k_retrieve = request.retrieve_k or RETRIEVE_K
    k_rerank = request.rerank_k or RERANK_K

    results, elapsed_ms, cache_hit = _rank_with_cache(query, k_retrieve, k_rerank)
    results = _with_display_scores(results)
    logger.info("query_time_ms=%d cache_hit=%s query=%s", elapsed_ms, cache_hit, query[:120])

    clear = _clear_answers(results)
    scenario_names = [row["id"] for row in clear]
    scenario_name = scenario_names[0] if scenario_names else None

    if scenario_names:
        if len(scenario_names) == 1:
            content = f"Scenario: {scenario_names[0]}"
        else:
            content = f"Scenarios: {', '.join(scenario_names)}"
    else:
        content = "No matching scenarios."

    now = int(time.time())
    return QueryResponse(
        id=f"chatcmpl-{now}",
        object="chat.completion",
        created=now,
        model=request.model or "krkn-retriever",
        choices=[
            QueryChoice(
                index=0,
                message=ChatMessage(role="assistant", content=content),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=len(query.split()),
            completion_tokens=len(content.split()),
            total_tokens=len(query.split()) + len(content.split()),
        ),
        scenario_name=scenario_name,
        scenario_names=scenario_names,
        clear_answers=clear,
        results=results,
    )


@app.post("/query", response_model=ScenarioQueryResponse)
async def legacy_query(request: ScenarioQueryRequest):
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    results, _, _ = _rank_with_cache(
        request.query,
        request.retrieve_k or RETRIEVE_K,
        request.rerank_k or RERANK_K,
    )
    results = _with_display_scores(results)
    clear = _clear_answers(results)
    scenario_names = [row["id"] for row in clear]
    return ScenarioQueryResponse(
        query=request.query,
        scenario_name=scenario_names[0] if scenario_names else None,
        scenario_names=scenario_names,
        clear_answers=clear,
        results=results,
    )


@app.post("/query/compact", response_model=CompactQueryResponse)
async def compact_query(request: ScenarioQueryRequest):
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    results, _, _ = _rank_with_cache(
        request.query,
        request.retrieve_k or RETRIEVE_K,
        request.rerank_k or RERANK_K,
    )
    results = _with_display_scores(results)
    clear = _clear_answers(results)
    scenario_names = [row["id"] for row in clear]

    if not scenario_names:
        answer = "No matching scenarios."
    elif len(scenario_names) == 1:
        answer = scenario_names[0]
    else:
        answer = ", ".join(scenario_names)

    return CompactQueryResponse(
        answer=answer,
        scenario_names=scenario_names,
        clear_answers=clear,
        results=results,
    )


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    k_retrieve = request.k or request.retrieve_k or RETRIEVE_K
    k_rerank = request.rerank_k or RERANK_K
    results, elapsed_ms, cache_hit = _rank_with_cache(
        query,
        k_retrieve,
        k_rerank,
    )
    clean_results = [
        RetrieveResult(
            id=row["id"],
            name=row.get("name", row["id"]),
            retrieval_score=round(float(row.get("retrieval_score", 0.0)), 4),
            rerank_score=round(float(row.get("score", 0.0)), 4),
            final_score=round(_display_score(row), 4),
            score_percent=round(_display_score(row) * 100.0, 1),
        )
        for row in results
    ]
    top_match = clean_results[0].id if clean_results else None
    if clean_results:
        message = f"Found {len(clean_results)} relevant scenarios"
    else:
        message = "No matching chaos scenarios found"
    logger.info(
        "retrieve_time_ms=%d cache_hit=%s query=%s",
        elapsed_ms,
        cache_hit,
        query[:120],
    )

    return RetrieveResponse(
        query=query,
        results=clean_results,
        top_match=top_match,
        message=message,
    )


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting krknctl Scenario Identification Service...")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
