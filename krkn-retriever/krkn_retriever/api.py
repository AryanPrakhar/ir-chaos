import logging
import math
import os
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .ranking import create_ranker, reset_ranker
from .settings import (
    DEFAULT_BACKEND,
    DEFAULT_CPU_ONLY,
    DEFAULT_DEVICE,
    DEFAULT_LLAMA_GPU_LAYERS,
    DEFAULT_LLAMA_MODEL,
    DOCS_DIR,
    FINAL_CE_WEIGHT,
    FINAL_FAISS_WEIGHT,
    INDEX_PATH,
    META_PATH,
    MIN_MATCH_SCORE,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEVICE = os.environ.get("RETRIEVER_DEVICE", DEFAULT_DEVICE)
CPU_ONLY = os.environ.get("RETRIEVER_CPU_ONLY", "1" if DEFAULT_CPU_ONLY else "0") == "1"
BACKEND = os.environ.get("RETRIEVER_BACKEND", DEFAULT_BACKEND)
LLAMA_MODEL = os.environ.get("LLAMA_EMBED_MODEL", DEFAULT_LLAMA_MODEL)
LLAMA_GPU_LAYERS = int(os.environ.get("LLAMA_GPU_LAYERS", str(DEFAULT_LLAMA_GPU_LAYERS)))
RETRIEVE_K = int(os.environ.get("RETRIEVE_K", "10"))
RERANK_K = int(os.environ.get("RERANK_K", "5"))
FORCE_REINDEX = os.environ.get("FORCE_REINDEX", "false").lower() == "true"
QUERY_CACHE_SIZE = int(os.environ.get("RETRIEVER_QUERY_CACHE_SIZE", "256"))
RELEVANCE_THRESHOLD = float(os.environ.get("RELEVANCE_THRESHOLD", str(MIN_MATCH_SCORE)))
SERVICE_NAME = os.environ.get("RETRIEVER_SERVICE_NAME", "krknctl-assist")
SERVICE_MODEL = os.environ.get("RETRIEVER_SERVICE_MODEL", "krkn-retriever")

ranker = None
query_cache: OrderedDict[tuple[str, int, int], list[dict]] = OrderedDict()


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
    timing_ms: Optional[dict[str, int]] = None


class RetrieveResponse(BaseModel):
    query: str
    results: list[RetrieveResult]
    top_match: Optional[str] = None
    message: str


class ChatMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    stream: Optional[bool] = False


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
    choices: list[QueryChoice]
    usage: Usage
    scenario_name: Optional[str] = None


class ScenarioQueryRequest(BaseModel):
    query: str


class ScenarioQueryResponse(BaseModel):
    query: str
    scenario_name: Optional[str] = None
    relevance_score: Optional[float] = None


def display_score(row: dict) -> float:
    if "final_score" in row:
        return max(0.0, min(1.0, float(row["final_score"])))
    ce_score = float(row.get("score", 0.0))
    retrieval_score = max(0.0, min(1.0, float(row.get("retrieval_score", 0.0))))
    ce_sigmoid = 1.0 / (1.0 + math.exp(-ce_score))
    return (FINAL_CE_WEIGHT * ce_sigmoid) + (FINAL_FAISS_WEIGHT * retrieval_score)


def cache_get(cache_key: tuple[str, int, int]) -> list[dict] | None:
    cached = query_cache.get(cache_key)
    if cached is None:
        return None
    query_cache.move_to_end(cache_key)
    return [dict(row) for row in cached]


def cache_put(cache_key: tuple[str, int, int], results: list[dict]) -> None:
    query_cache[cache_key] = [dict(row) for row in results]
    query_cache.move_to_end(cache_key)
    while len(query_cache) > QUERY_CACHE_SIZE:
        query_cache.popitem(last=False)


def rank_with_cache(query: str, retrieve_k: int, rerank_k: int) -> tuple[list[dict], int, bool]:
    cache_key = (query, retrieve_k, rerank_k)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached, 0, True
    started = time.perf_counter()
    results = ranker.find_match(query, retrieve_k=retrieve_k, rerank_k=rerank_k)
    elapsed_ms = int(round((time.perf_counter() - started) * 1000))
    cache_put(cache_key, results)
    return results, elapsed_ms, False


@asynccontextmanager
async def lifespan(_: FastAPI):
    global ranker

    reset_ranker()
    query_cache.clear()
    ranker = create_ranker(
        device_preference=DEVICE,
        cpu_only=CPU_ONLY,
        backend=BACKEND,
        llama_model_path=LLAMA_MODEL,
        llama_gpu_layers=LLAMA_GPU_LAYERS,
    )

    if FORCE_REINDEX or not (os.path.exists(INDEX_PATH) and os.path.exists(META_PATH)):
        logger.info("Building FAISS index")
        ranker.build_index(DOCS_DIR)

    ranker._init_models()
    ranker._load_doc_texts()
    logger.info("Retriever ready")
    yield


app = FastAPI(
    title="krkn Retriever Service",
    version="1.0.0",
    description="Scenario retrieval service",
    lifespan=lifespan,
)


def get_user_query_from_messages(messages: list[ChatMessage]) -> str:
    for message in reversed(messages or []):
        if message.role == "user":
            return (message.content or "").strip()
    return ""


@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "model": SERVICE_MODEL,
        "backend": BACKEND,
        "retrieve_k": RETRIEVE_K,
        "rerank_k": RERANK_K,
        "relevance_threshold": RELEVANCE_THRESHOLD,
        "endpoints": {
            "health": "/health",
            "retrieve": "/retrieve",
            "query": "/v1/chat/completions",
        },
    }


@app.get("/health")
async def health_check():
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    documents_indexed = len(ranker.doc_ids) if getattr(ranker, "doc_ids", None) else 0
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "model": SERVICE_MODEL,
        "backend": BACKEND,
        "index_loaded": ranker.faiss_index is not None,
        "documents_indexed": documents_indexed,
    }


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    retrieve_k = request.retrieve_k or RETRIEVE_K
    rerank_k = request.rerank_k or RERANK_K
    final_k = request.k or rerank_k
    if final_k < 1:
        raise HTTPException(status_code=400, detail="k must be >= 1")
    if retrieve_k < final_k:
        retrieve_k = final_k

    results, elapsed_ms, cache_hit = rank_with_cache(query, retrieve_k, rerank_k)
    results = results[:final_k]
    logger.info("retrieve_time_ms=%d cache_hit=%s query=%s", elapsed_ms, cache_hit, query[:120])

    payload = [
        RetrieveResult(
            id=row["id"],
            name=row.get("name", row["id"]),
            retrieval_score=round(float(row.get("retrieval_score", 0.0)), 4),
            rerank_score=round(float(row.get("score", 0.0)), 4),
            final_score=round(display_score(row), 4),
            score_percent=round(display_score(row) * 100.0, 1),
            timing_ms=row.get("timing_ms"),
        )
        for row in results
    ]
    return RetrieveResponse(
        query=query,
        results=payload,
        top_match=payload[0].id if payload else None,
        message=f"Found {len(payload)} relevant scenarios" if payload else "No matching chaos scenarios found",
    )


@app.post("/v1/chat/completions", response_model=QueryResponse)
async def chat_completions(request: QueryRequest):
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    if request.stream:
        raise HTTPException(status_code=400, detail="Streaming not supported")

    user_query = get_user_query_from_messages(request.messages)
    if not user_query:
        raise HTTPException(status_code=400, detail="No user message found in request")

    results, elapsed_ms, cache_hit = rank_with_cache(user_query, RETRIEVE_K, RERANK_K)
    top_match = results[0] if results else None
    relevance_score = display_score(top_match) if top_match else 0.0

    scenario_name: str | None = None
    if top_match and relevance_score >= RELEVANCE_THRESHOLD:
        scenario_name = str(top_match.get("id") or "").strip() or None

    logger.info(
        "chat_completion_time_ms=%d cache_hit=%s relevance_score=%.4f scenario=%s query=%s",
        elapsed_ms,
        cache_hit,
        relevance_score,
        scenario_name or "",
        user_query[:120],
    )

    current_time = int(time.time())
    response_id = f"chatcmpl-{current_time}"

    response_content = f"Scenario: {scenario_name}" if scenario_name else f"Query: {user_query}"

    prompt_tokens = len(user_query.split())
    completion_tokens = len(response_content.split())

    return QueryResponse(
        id=response_id,
        object="chat.completion",
        created=current_time,
        model=request.model or SERVICE_MODEL,
        choices=[
            QueryChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response_content),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        scenario_name=scenario_name,
    )


@app.post("/query", response_model=ScenarioQueryResponse)
async def legacy_query(request: ScenarioQueryRequest):
    if ranker is None:
        raise HTTPException(status_code=503, detail="Retriever not initialized")

    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    results, elapsed_ms, cache_hit = rank_with_cache(query, RETRIEVE_K, RERANK_K)
    top_match = results[0] if results else None
    relevance_score = display_score(top_match) if top_match else 0.0

    scenario_name: str | None = None
    if top_match and relevance_score >= RELEVANCE_THRESHOLD:
        scenario_name = str(top_match.get("id") or "").strip() or None

    logger.info(
        "legacy_query_time_ms=%d cache_hit=%s relevance_score=%.4f scenario=%s query=%s",
        elapsed_ms,
        cache_hit,
        relevance_score,
        scenario_name or "",
        query[:120],
    )

    return ScenarioQueryResponse(
        query=query,
        scenario_name=scenario_name,
        relevance_score=round(float(relevance_score), 4),
    )


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
