#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path

from llama_cpp import Llama


CHAOS_ARCHITECT_SYSTEM_PROMPT = """### ROLE
You are a Senior SRE and Chaos Engineering Expert specialized in the Krkn (Kraken) framework.
Your goal is to provide developers with immediate, executable solutions based on the provided documentation chunks.

### TASK
Analyze the user's query and the retrieved context to generate a Quick-Start Execution Plan.

### RESPONSE GUIDELINES (STRICT)
1. CODE-FIRST: If a command exists, lead with it. Do not add conversational preambles.
2. PLACEHOLDERS: Use {{UPPERCASE_SNAKE_CASE}} for values users must fill.
3. PARAMETER EXTRACTION: Explicitly list Required vs Optional environment variables found in context.
4. SAFETY GUARDRAILS: If context includes TIP/WARNING/prerequisites, include them in Critical Notes.
5. VERIFICATION: Always include commands to stream logs and check exit code.
6. USER VALUE BINDING: If the user provides specific values (e.g., node names, percentages, durations), you MUST incorporate them into the code blocks using -e VARIABLE_NAME=value or export VARIABLE_NAME=value.

### OUTPUT STRUCTURE
#### Quick Start
[Single copy-pasteable podman/docker command]

#### Parameters
| Variable | Status | Default | Description |
| :--- | :--- | :--- | :--- |

#### Critical Notes
[Permissions, prerequisites, or Cerberus requirements]

#### Validation
[Logs and inspect commands]
"""


def pick_gpu_layers(mode: str, user_value: int | None) -> int:
    if user_value is not None:
        return user_value
    if mode in ("vulkan", "nvidia"):
        return 99
    return 0


def extract_command_lines(text: str, max_lines: int = 6) -> list[str]:
    commands = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            stripped.startswith("$")
            or "podman run" in stripped
            or "docker run" in stripped
            or "podman logs" in stripped
            or "docker logs" in stripped
            or "podman inspect" in stripped
            or "docker inspect" in stripped
        ):
            commands.append(stripped.lstrip("$ "))
        if len(commands) >= max_lines:
            break
    return commands


def extract_env_vars(text: str, max_vars: int = 20) -> list[str]:
    # Heuristic extraction of variable-like tokens from docs.
    matches = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", text))
    ignore = {
        "API",
        "HTTP",
        "HTTPS",
        "TCP",
        "UDP",
        "TIP",
        "WARNING",
        "OR",
        "AND",
    }
    envs = sorted(x for x in matches if x not in ignore)
    return envs[:max_vars]


def build_prompt(query: str, contexts: list[dict], max_chars_per_context: int, system_prompt: str) -> str:
    blocks = []
    for idx, ctx in enumerate(contexts, 1):
        title = ctx.get("name") or ctx.get("id") or f"context-{idx}"
        text = (ctx.get("text") or "").strip()
        if max_chars_per_context > 0:
            text = text[:max_chars_per_context]

        commands = extract_command_lines(text)
        env_vars = extract_env_vars(text)

        block = [
            f"Scenario: {title}",
            f"DocID: {ctx.get('id', title)}",
            "Excerpt:",
            text,
        ]
        if commands:
            block.append("CommandHints: " + " | ".join(commands))
        if env_vars:
            block.append("ParamsHints: " + ", ".join(env_vars))
        blocks.append("\n".join(block))

    joined_context = "\n\n".join(blocks) if blocks else "(No context provided)"

    return (
        f"[SYSTEM PROMPT]\n{system_prompt}\n\n"
        f"[USER QUERY]: \"{query}\"\n\n"
        f"[RETRIEVED CONTEXT]:\n{joined_context}\n\n"
        "[INSTRUCTION]\n"
        "Produce output in the exact section order from the system prompt.\n"
        "Return ONLY markdown using this exact skeleton:\n\n"
        "#### Quick Start\n"
        "```bash\n"
        "<single best command here>\n"
        "```\n\n"
        "#### Parameters\n"
        "| Variable | Status | Default | Description |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| {{VAR_NAME}} | Required/Optional | <default-or-N/A> | <short description> |\n\n"
        "#### Critical Notes\n"
        "- <TIP/WARNING/prerequisite>\n\n"
        "#### Validation\n"
        "```bash\n"
        "<logs command>\n"
        "<exit code command>\n"
        "```\n\n"
        "If information is missing, keep placeholders in {{UPPERCASE_SNAKE_CASE}} form."
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
    parser.add_argument("--top-k-contexts", type=int, default=1)
    parser.add_argument(
        "--system-prompt-file",
        default=None,
        help="Optional file path to override the default Chaos Architect system prompt",
    )
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

    system_prompt = CHAOS_ARCHITECT_SYSTEM_PROMPT
    if args.system_prompt_file:
        system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8")

    print(f"[inference] GPU_MODE={gpu_mode} n_gpu_layers={n_gpu_layers}")
    print(f"[inference] Loading model: {args.model}")

    llm = Llama(
        model_path=args.model,
        n_gpu_layers=n_gpu_layers,
        n_ctx=4096,
        verbose=False,
    )

    prompt = build_prompt(query, results, args.max_context_chars, system_prompt)
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
