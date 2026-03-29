import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from retriever import get_ranker


@dataclass
class BenchmarkResult:
    query_id: str   # <-- added
    input_query: str
    expected_label: str
    retrieved_labels: list
    retrieved_scores: list
    ranks: dict
    query_type: str = "default"
    latency_ms: float = 0.0

    @property
    def top1_correct(self):
        return self.retrieved_labels and self.retrieved_labels[0] == self.expected_label

    @property
    def top_k_correct(self):
        return self.expected_label in self.retrieved_labels

    @property
    def reciprocal_rank(self):
        rank = self.ranks.get(self.expected_label)
        return 0.0 if rank is None else 1.0 / rank

def run_query(ranker, query, retrieve_k, rerank_k):
    start   = time.perf_counter()
    result  = ranker.find_match(query, retrieve_k=retrieve_k, rerank_k=rerank_k)
    latency = (time.perf_counter() - start) * 1000

    labels = [r["id"]    for r in result]
    scores = [r["score"] for r in result]

    return labels, scores, latency


def benchmark(ranker, dataset_path, retrieve_k=10, rerank_k=3, limit=None):
    results = []

    print("Initializing models + index...", file=sys.stderr)
    start_init = time.perf_counter()
    ranker._init_models()
    ranker._load_doc_texts()
    print(f"✓ Init done in {(time.perf_counter()-start_init):.2f}s", file=sys.stderr)

    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader):
            if limit and idx >= limit:
                break

            query = row.get("input", "").strip()
            label = row.get("label", "").strip()
            qtype = row.get("type", "default")
            qid   = row.get("id", "").strip()   # <-- added

            if not query or not label:
                continue

            labels, scores, latency = run_query(ranker, query, retrieve_k, rerank_k)
            ranks = {l: i + 1 for i, l in enumerate(labels)}

            results.append(BenchmarkResult(
                query_id=qid,   # <-- added
                input_query=query,
                expected_label=label,
                retrieved_labels=labels,
                retrieved_scores=scores,
                ranks=ranks,
                query_type=qtype,
                latency_ms=latency,
            ))

            if (idx + 1) % 10 == 0:
                acc = sum(r.top1_correct for r in results) / len(results)
                lat = sum(r.latency_ms   for r in results) / len(results)
                print(f"[{idx+1}] Top-1 Acc: {acc:.1%} | Avg Latency: {lat:.1f}ms",
                      file=sys.stderr)

    return results


def compute_metrics(results, rerank_k):
    n          = len(results)
    top1_count = sum(r.top1_correct for r in results)
    topk_count = sum(r.top_k_correct for r in results)
    mrr        = sum(r.reciprocal_rank for r in results) / n if n else 0.0
    lat        = sum(r.latency_ms      for r in results) / n if n else 0.0

    return {
        "overall": {
            "total_queries":  n,
            "top1_accuracy":  top1_count / n if n else 0.0,
            "top1_count":     top1_count,
            "topk_accuracy":  topk_count / n if n else 0.0,
            "topk_count":     topk_count,
            "mrr":            mrr,
            "avg_latency_ms": lat,
            "top_k":          rerank_k,
        }
    }


def save_failures(results, output_path="outputs/failed_queries.csv"):
    failures = [r for r in results if not r.top1_correct]

    if not failures:
        print("No failures — perfect top-1 accuracy!")
        return

    rows = []
    for r in failures:
        top1_score     = r.retrieved_scores[0] if r.retrieved_scores else ""
        top1_predicted = r.retrieved_labels[0] if r.retrieved_labels else ""
        expected_rank  = r.ranks.get(r.expected_label, "not_retrieved")

        correct_score = ""
        if expected_rank != "not_retrieved":
            idx = expected_rank - 1
            if idx < len(r.retrieved_scores):
                correct_score = round(r.retrieved_scores[idx], 4)

        rows.append({
            "id":             r.query_id,
            "input":          r.input_query,
            "label":          r.expected_label,
            "top1_predicted": top1_predicted,
            "top1_score":     round(top1_score, 4) if top1_score != "" else "",
            "correct_score":  correct_score,
            "expected_rank":  expected_rank,
            "type":           r.query_type,
        })

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id",
            "input", "label",
            "top1_predicted", "top1_score", "correct_score",
            "expected_rank", "type",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} failed queries → {output_file}")


def log_benchmark(results, metrics, ranker, output_path="outputs/benchmark_log.jsonl"):
    if not metrics:
        return

    overall   = metrics["overall"]
    log_entry = {
        "timestamp":           datetime.now().isoformat(),
        "retriever_model":     ranker.retriever_model_name,
        "cross_encoder_model": ranker.cross_encoder_model_name,
        "total_queries":       overall["total_queries"],
        "top1_accuracy":       overall["top1_accuracy"],
        "top1_count":          overall["top1_count"],
        "topk_accuracy":       overall["topk_accuracy"],
        "topk_count":          overall["topk_count"],
        "mrr":                 overall["mrr"],
        "avg_latency_ms":      overall["avg_latency_ms"],
        "top_k":               overall["top_k"],
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    print(f"Benchmark logged to {output_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset",      default="data.csv")
    parser.add_argument("--retrieve-k",   type=int, default=10, help="FAISS candidate pool size (default: 50)")
    parser.add_argument("--rerank-k",     type=int, default=5, help="Top results after reranking (default: 5)")
    parser.add_argument("--limit",        type=int, default=None)
    parser.add_argument("--failures-out", default="outputs/failed_queries.csv")
    args = parser.parse_args()

    ranker  = get_ranker()
    results = benchmark(
        ranker,
        args.dataset,
        retrieve_k=args.retrieve_k,
        rerank_k=args.rerank_k,
        limit=args.limit,
    )

    metrics = compute_metrics(results, args.rerank_k)
    overall = metrics["overall"]

    print("\n" + "=" * 70)
    print("CROSS-ENCODER TWO-STAGE BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Retrieval Model:     {ranker.retriever_model_name}")
    print(f"Cross-Encoder Model: {ranker.cross_encoder_model_name}")
    print(f"Retrieve K: {args.retrieve_k} | Rerank K: {args.rerank_k}")
    print(f"\nTotal Queries:    {overall['total_queries']}")
    print(f"Top-1 Accuracy:   {overall['top1_accuracy']:.1%} ({overall['top1_count']}/{overall['total_queries']})")
    print(f"Top-{args.rerank_k} Accuracy: {overall['topk_accuracy']:.1%} ({overall['topk_count']}/{overall['total_queries']})")
    print(f"MRR:              {overall['mrr']:.4f}")
    print(f"Avg Latency:      {overall['avg_latency_ms']:.2f}ms")
    print("=" * 70)

    save_failures(results, args.failures_out)
    log_benchmark(results, metrics, ranker)


if __name__ == "__main__":
    main()