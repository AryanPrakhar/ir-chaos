#!/usr/bin/env python3
"""
Smoke tests for krkn-retriever indexing and query flow.
"""

from __future__ import annotations

import os
import sys
import time
import logging
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from krkn_retriever.ranking import create_ranker
from krkn_retriever.settings import DOCS_DIR, DOCS_CACHE_PATH, INDEX_PATH, INDEX_TTL_DAYS, META_PATH


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _index_last_modified() -> float:
    timestamps = []
    for path in (INDEX_PATH, META_PATH, DOCS_CACHE_PATH):
        if os.path.exists(path):
            try:
                timestamps.append(os.path.getmtime(path))
            except OSError:
                continue
    return max(timestamps) if timestamps else 0.0


def _index_is_stale() -> bool:
    ttl_seconds = max(0.0, float(INDEX_TTL_DAYS)) * 86400.0
    if ttl_seconds <= 0:
        return False
    if not (os.path.exists(INDEX_PATH) and os.path.exists(META_PATH)):
        return True
    if not os.path.exists(DOCS_CACHE_PATH):
        return True
    last_modified = _index_last_modified()
    if last_modified <= 0:
        return True
    return (time.time() - last_modified) >= ttl_seconds


def test_pipeline_loading():
    print("\n=== Testing Pipeline Loading ===")
    ranker = create_ranker(
        device_preference=os.environ.get("RETRIEVER_DEVICE", "auto"),
        cpu_only=os.environ.get("RETRIEVER_CPU_ONLY", "0") == "1",
        backend=os.environ.get("RETRIEVER_BACKEND", "auto"),
        llama_model_path=os.environ.get("LLAMA_EMBED_MODEL", ""),
        llama_gpu_layers=int(os.environ.get("LLAMA_GPU_LAYERS", "-1")),
    )

    force_reindex = os.environ.get("FORCE_REINDEX", "false").lower() == "true"
    if force_reindex or _index_is_stale() or not (
        os.path.exists(INDEX_PATH) and os.path.exists(META_PATH)
    ):
        print("Building FAISS index...")
        ranker.build_index(DOCS_DIR)

    ranker._init_models()
    ranker._load_doc_texts()
    print("✅ Retriever initialized")
    return ranker


def test_query_execution(ranker):
    print("\n=== Testing Query Execution ===")
    test_queries = [
        "What is krknctl?",
        "How do I run a pod kill scenario?",
        "What scenarios are available for chaos engineering?",
        "Tell me about node scenarios",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            results = ranker.find_match(query, retrieve_k=10, rerank_k=5)
            top = results[0]["id"] if results else None
            print(f"✅ Retrieved {len(results)} candidates")
            print(f"Top scenario: {top or 'None'}")
        except Exception as exc:
            print(f"❌ Query failed: {exc}")


def test_openai_compatibility():
    print("\n=== Testing OpenAI Compatibility ===")
    try:
        chat_message = {"role": "user", "content": "What is krknctl used for?"}
        query_request = {
            "model": "krkn-retriever",
            "messages": [chat_message],
            "temperature": 0.1,
            "max_tokens": 512,
            "stream": False,
        }
        print("✅ OpenAI-compatible request structure created")
        print(f"Request format: {list(query_request.keys())}")

        query_response = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "krkn-retriever",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Scenario: pod-kill"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            "scenario_name": "pod-kill",
            "scenarios": [{"name": "pod-kill", "score": 0.9}],
            "timing_ms": 123,
        }
        print("✅ OpenAI-compatible response structure created")
        print(f"Response format: {list(query_response.keys())}")
    except Exception as exc:
        print(f"❌ OpenAI compatibility test failed: {exc}")


def test_scenario_detection():
    print("\n=== Testing Scenario Detection ===")
    test_responses = [
        "Scenario: pod-kill",
        "Scenarios: node-cpu-hog, node-memory-hog",
        "No confident scenario match found",
    ]

    for response in test_responses:
        scenario_name: Optional[str] = None
        if response.startswith("Scenario:"):
            scenario_name = response.split("Scenario:", 1)[1].strip()
        elif response.startswith("Scenarios:"):
            scenario_name = response.split("Scenarios:", 1)[1].split(",", 1)[0].strip()

        print(f"Response: {response}")
        print(f"Detected scenario: {scenario_name or 'None'}")
        print("---")


def main():
    print("🚀 Starting krkn-retriever integration tests")

    ranker = test_pipeline_loading()
    test_query_execution(ranker)
    test_openai_compatibility()
    test_scenario_detection()

    print("\n🎉 All tests completed!")
    print("\nNext steps:")
    print("1. Run the FastAPI server: python api_server.py")
    print("2. Test the API endpoints:")
    print("   - GET /health")
    print("   - POST /v1/chat/completions")
    print("   - POST /query")
    print("   - POST /retrieve (debug)")


if __name__ == "__main__":
    main()
