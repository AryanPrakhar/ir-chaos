#!/usr/bin/env python3
"""
FastAPI service wrapper for krkn-retriever.
"""

import os
import time
import logging
import math
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from retriever import (
    DOCS_DIR,
    INDEX_PATH,
    META_PATH,
    DEFAULT_BACKEND,
    DEFAULT_LLAMA_MODEL,
    DEFAULT_LLAMA_GPU_LAYERS,
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
RETRIEVE_K = int(os.environ.get("RETRIEVE_K", "10"))
RERANK_K = int(os.environ.get("RERANK_K", "5"))
FORCE_REINDEX = os.environ.get("FORCE_REINDEX", "false").lower() == "true"

ranker = None


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


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _display_score(row: dict) -> float:
    ce = float(row.get("score", 0.0))
    faiss = max(0.0, min(1.0, float(row.get("retrieval_score", 0.0))))
    blended = (FINAL_CE_WEIGHT * _sigmoid(ce)) + (FINAL_FAISS_WEIGHT * faiss)
    return max(0.0, min(1.0, blended))


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ranker

    logger.info("Starting krkn-retriever FastAPI service")
    reset_ranker()
    ranker = get_ranker(
        device_preference=DEVICE,
        cpu_only=CPU_ONLY,
        backend=BACKEND,
        llama_model_path=LLAMA_MODEL,
        llama_gpu_layers=LLAMA_GPU_LAYERS,
    )

    if FORCE_REINDEX or not (os.path.exists(INDEX_PATH) and os.path.exists(META_PATH)):
        logger.info("Building FAISS index (startup)")
        ranker.build_index(DOCS_DIR)
        ranker._load_index()
    else:
        logger.info("Using existing FAISS index")

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
            "chat_completions": "/v1/chat/completions",
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

    started = time.time()
    results = ranker.find_match(query, retrieve_k=k_retrieve, rerank_k=k_rerank)
    results = _with_display_scores(results)
    elapsed = time.time() - started
    logger.info("query_time=%.3fs query=%s", elapsed, query[:120])

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

    results = ranker.find_match(
        request.query,
        retrieve_k=request.retrieve_k or RETRIEVE_K,
        rerank_k=request.rerank_k or RERANK_K,
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

    results = ranker.find_match(
        request.query,
        retrieve_k=request.retrieve_k or RETRIEVE_K,
        rerank_k=request.rerank_k or RERANK_K,
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
