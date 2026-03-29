#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from llama_cpp import Llama


def pick_gpu_layers(mode: str, user_value: int | None) -> int:
    if user_value is not None:
        return user_value
    if mode in ("vulkan", "nvidia"):
        return 99
    return 0


def build_prompt(query: str, contexts: list[dict], max_chars_per_context: int) -> str:
    blocks = []
    for idx, ctx in enumerate(contexts, 1):
        title = ctx.get("name") or ctx.get("id") or f"context-{idx}"
        text = (ctx.get("text") or "").strip()
        if max_chars_per_context > 0:
            text = text[:max_chars_per_context]
        blocks.append(f"[{idx}] {title}\n{text}")

    joined_context = "\n\n".join(blocks) if blocks else "(No context provided)"

    return (
        "You are an expert chaos engineering assistant. Use the retrieved contexts to answer the user query.\n"
        "If the contexts are insufficient, state what is missing.\n\n"
        f"User query:\n{query}\n\n"
        f"Retrieved contexts:\n{joined_context}\n\n"
        "Answer with practical, testable steps."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local LLM inference using retrieval export JSON")
    parser.add_argument("--input", required=True, help="Path to retrieval JSON export")
    parser.add_argument("--output", required=True, help="Path to write inference JSON output")
    parser.add_argument("--model", required=True, help="Path to GGUF model file")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--n-gpu-layers", type=int, default=None, help="Override GPU offload layers")
    parser.add_argument("--max-context-chars", type=int, default=3500)
    parser.add_argument("--top-k-contexts", type=int, default=3)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    query = payload.get("query", "")
    results = payload.get("results", [])[: args.top_k_contexts]

    gpu_mode = os.environ.get("GPU_MODE", "cpu")
    n_gpu_layers = pick_gpu_layers(gpu_mode, args.n_gpu_layers)

    print(f"[inference] GPU_MODE={gpu_mode} n_gpu_layers={n_gpu_layers}")
    print(f"[inference] Loading model: {args.model}")

    llm = Llama(
        model_path=args.model,
        n_gpu_layers=n_gpu_layers,
        n_ctx=4096,
        verbose=False,
    )

    prompt = build_prompt(query, results, args.max_context_chars)
    response = llm(
        prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        echo=False,
    )

    text = response["choices"][0]["text"].strip()

    result_payload = {
        "query": query,
        "gpu_mode": gpu_mode,
        "n_gpu_layers": n_gpu_layers,
        "model": args.model,
        "input_file": str(input_path),
        "output": text,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

    print(f"[inference] Wrote output: {output_path}")


if __name__ == "__main__":
    main()
