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

### RESPONSE GUIDELINES
1. Keep output concise and executable.
2. Use {{UPPERCASE_SNAKE_CASE}} placeholders only when context does not provide a value.
3. Preserve the section order and table format from the provided template.
4. Use only information present in the retrieved context.

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


def _split_markdown_row(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped:
        return False
    parts = _split_markdown_row(stripped)
    if not parts:
        return False
    return all(re.fullmatch(r":?-{3,}:?", p.replace(" ", "")) for p in parts if p)


def extract_param_rows_from_markdown(text: str, max_rows: int = 60) -> list[dict[str, str]]:
    lines = text.splitlines()
    rows: list[dict[str, str]] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if "|" not in line:
            i += 1
            continue

        header_cells = _split_markdown_row(line)
        lowered = [c.lower() for c in header_cells]
        has_param_col = any("parameter" in c or "variable" in c for c in lowered)
        has_desc_col = any("description" in c for c in lowered)

        if not (has_param_col and has_desc_col):
            i += 1
            continue

        if i + 1 >= len(lines) or not _is_table_separator(lines[i + 1]):
            i += 1
            continue

        param_idx = next((idx for idx, c in enumerate(lowered) if "parameter" in c or "variable" in c), 0)
        desc_idx = next((idx for idx, c in enumerate(lowered) if "description" in c), 1)
        default_idx = next((idx for idx, c in enumerate(lowered) if "default" in c), None)

        j = i + 2
        while j < len(lines):
            row_line = lines[j].strip()
            if "|" not in row_line:
                break
            if _is_table_separator(row_line):
                j += 1
                continue

            cells = _split_markdown_row(row_line)
            if len(cells) <= max(param_idx, desc_idx, default_idx or 0):
                j += 1
                continue

            variable = cells[param_idx].strip().strip("`")
            description = cells[desc_idx].strip().strip("`")
            default = cells[default_idx].strip().strip("`") if default_idx is not None else "N/A"

            if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", variable):
                j += 1
                continue

            rows.append(
                {
                    "variable": variable,
                    "description": re.sub(r"\s+", " ", description),
                    "default": re.sub(r"\s+", " ", default) if default else "N/A",
                }
            )
            if len(rows) >= max_rows:
                return rows
            j += 1

        i = j

    return rows


def infer_param_status(description: str, default: str) -> str:
    desc_lower = description.lower()
    default_clean = default.strip().lower()
    if "required" in desc_lower:
        return "Required"
    if default_clean in {"", '""', "''", "none", "n/a", "no default", "no default value"}:
        return "Required"
    return "Optional"


def infer_query_param_bindings(query: str, param_rows: list[dict[str, str]], max_bindings: int = 12) -> list[dict[str, str]]:
    q = query.strip()
    q_lower = q.lower()
    bindings: list[dict[str, str]] = []

    percent_match = re.search(r"\b(\d{1,3})\s*%", q)
    selector_match = re.search(r"\b([a-zA-Z0-9_.-]+=[a-zA-Z0-9_.:-]+)\b", q)
    duration_match = re.search(r"\b(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b", q_lower)
    namespace_match = re.search(r"\bin\s+the\s+([a-z0-9-]+)\s+namespace\b", q_lower)

    ingress_words = ("ingress", "incoming", "inbound")
    egress_words = ("egress", "outgoing", "outbound", "external")
    has_ingress_intent = any(w in q_lower for w in ingress_words)
    has_egress_intent = any(w in q_lower for w in egress_words)
    generic_block_intent = any(
        phrase in q_lower
        for phrase in (
            "traffic blockage",
            "block traffic",
            "network isolation",
            "refuses connections",
            "stop connections",
        )
    )

    for row in param_rows:
        var = row["variable"]
        var_lower = var.lower()
        value = ""
        source = ""

        explicit = re.search(rf"\b{re.escape(var)}\s*=\s*([^,\s]+)", q, flags=re.IGNORECASE)
        if explicit:
            value = explicit.group(1)
            source = f"explicit {var}=... in query"
        elif var_lower == "namespace" and namespace_match:
            value = namespace_match.group(1)
            source = "namespace phrase in query"
        elif "label_selector" in var_lower and selector_match:
            value = selector_match.group(1)
            source = "label selector inferred from query"
        elif var_lower == "traffic_type":
            if has_ingress_intent and has_egress_intent:
                value = "[ingress, egress]"
                source = "ingress+egress intent in query"
            elif has_ingress_intent:
                value = "[ingress]"
                source = "ingress intent in query"
            elif has_egress_intent:
                value = "[egress]"
                source = "egress intent in query"
            elif generic_block_intent:
                value = "[ingress, egress]"
                source = "generic traffic-block intent in query"
        elif var_lower == "ingress_ports" and (has_ingress_intent or generic_block_intent):
            value = "[]"
            source = "port block intent; empty list means all ports"
        elif var_lower == "egress_ports" and (has_egress_intent or generic_block_intent):
            value = "[]"
            source = "port block intent; empty list means all ports"
        elif "selector" in var_lower and selector_match:
            value = selector_match.group(1)
            source = "selector-like key=value in query"
        elif "percentage" in var_lower and percent_match:
            value = f"{percent_match.group(1)}%"
            source = "percentage mentioned in query"
        elif "duration" in var_lower and duration_match:
            duration_value, unit = duration_match.groups()
            if unit.startswith("min"):
                value = str(int(duration_value) * 60)
                source = "duration in minutes converted to seconds"
            elif unit.startswith("hour") or unit.startswith("hr"):
                value = str(int(duration_value) * 3600)
                source = "duration in hours converted to seconds"
            else:
                value = duration_value
                source = "duration in seconds from query"

        if value:
            bindings.append({"variable": var, "value": value, "source": source})
        if len(bindings) >= max_bindings:
            break

    return bindings


def _render_param_schema(param_rows: list[dict[str, str]], max_rows: int = 25) -> str:
    if not param_rows:
        return "(No structured parameter rows parsed from markdown tables)"

    lines = []
    for row in param_rows[:max_rows]:
        status = infer_param_status(row["description"], row["default"])
        lines.append(
            f"- {row['variable']}: status={status}; default={row['default']}; description={row['description']}"
        )
    return "\n".join(lines)


def _render_query_bindings(bindings: list[dict[str, str]]) -> str:
    if not bindings:
        return "(No direct bindings inferred from query; use placeholders only for truly missing values)"
    lines = []
    for b in bindings:
        lines.append(f"- {b['variable']}={b['value']} ({b['source']})")
    return "\n".join(lines)


def _extract_image_from_text(text: str) -> str:
    match = re.search(r"(quay\.io/krkn-chaos/krkn-hub:[a-z0-9-]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def _infer_image_from_context(ctx: dict) -> str:
    text = (ctx.get("text") or "").strip()
    image = _extract_image_from_text(text)
    if image:
        return image

    ctx_id = (ctx.get("id") or "").strip()
    if ctx_id:
        return f"quay.io/krkn-chaos/krkn-hub:{ctx_id}"
    return "quay.io/krkn-chaos/krkn-hub:{{SCENARIO_TAG}}"


def _quote_shell_value(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=%-]+", value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _build_quick_start_command(image: str, bindings: list[dict[str, str]], runtime: str = "docker") -> str:
    env_parts = [
        f"-e {b['variable']}={_quote_shell_value(b['value'])}"
        for b in bindings
    ]
    env_str = " \\\n+  ".join(env_parts)
    base = (
        f"{runtime} run --name={{CONTAINER_NAME}} --net=host"
        " -v {{KUBECONFIG_PATH}}:/home/krkn/.kube/config:Z"
    )
    if env_str:
        return (
            f"{base} \\\n+  {env_str} \\\n+  -d {image}"
        )
    return f"{base} -d {image}"


def _extract_critical_notes(text: str, max_notes: int = 4) -> list[str]:
    notes = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ")
        lowered = stripped.lower()
        if not stripped:
            continue
        if (
            "**tip**" in lowered
            or "**note**" in lowered
            or "warning" in lowered
            or "cerberus" in lowered
            or "kube config" in lowered
            or "kubeconfig" in lowered
        ):
            clean = re.sub(r"\*\*", "", stripped)
            notes.append(clean)
        if len(notes) >= max_notes:
            break
    return notes


def _assess_output_quality(text: str, bindings: list[dict[str, str]]) -> dict[str, float | bool]:
    lowered = text.lower()
    required_sections = ("#### Quick Start", "#### Parameters")
    optional_sections = ("#### Critical Notes", "#### Validation")
    required_hits = sum(1 for section in required_sections if section in text)
    optional_hits = sum(1 for section in optional_sections if section in text)
    has_command = "docker run" in lowered or "podman run" in lowered
    if not bindings:
        binding_coverage = 1.0
    else:
        matched = sum(1 for b in bindings if f"{b['variable']}={b['value']}" in text)
        binding_coverage = matched / len(bindings)
    not_prompt_echo = "[retrieved context]" not in lowered and "[user query]" not in lowered
    no_markdown_wrapper_noise = "```markdown" not in lowered and "``` ```" not in lowered
    quality_score = 0.0
    quality_score += 0.3 * (required_hits / len(required_sections))
    quality_score += 0.15 * (optional_hits / len(optional_sections))
    quality_score += 0.25 if has_command else 0.0
    quality_score += 0.2 * binding_coverage
    quality_score += 0.1 if (not_prompt_echo and no_markdown_wrapper_noise) else 0.0

    return {
        "score": round(quality_score, 4),
        "has_required_sections": required_hits == len(required_sections),
        "has_command": has_command,
        "binding_coverage": round(binding_coverage, 4),
        "clean": float(not_prompt_echo and no_markdown_wrapper_noise),
    }


def _extract_section(text: str, section_header: str) -> str:
    escaped = re.escape(section_header)
    pattern = rf"({escaped}\n(?:.|\n)*?)(?=\n####\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _repair_output_with_fallback(text: str, fallback: str) -> str:
    repaired = text.strip()
    for section in ("#### Quick Start", "#### Parameters", "#### Critical Notes", "#### Validation"):
        existing = _extract_section(repaired, section)
        if existing:
            continue
        fallback_section = _extract_section(fallback, section)
        if fallback_section:
            if repaired and not repaired.endswith("\n\n"):
                repaired += "\n\n"
            repaired += fallback_section
    return repaired


def _collect_bindings_for_contexts(query: str, contexts: list[dict]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for ctx in contexts:
        text = (ctx.get("text") or "").strip()
        param_rows = extract_param_rows_from_markdown(text)
        for b in infer_query_param_bindings(query, param_rows):
            merged[b["variable"]] = b
    return list(merged.values())


def _render_parameters_table(param_rows: list[dict[str, str]]) -> str:
    lines = [
        "| Variable | Status | Default | Description |",
        "| :--- | :--- | :--- | :--- |",
    ]
    if not param_rows:
        lines.append("| {{VAR_NAME}} | Required/Optional | N/A | Missing from context |")
        return "\n".join(lines)

    for row in param_rows:
        status = infer_param_status(row["description"], row["default"])
        lines.append(
            f"| {row['variable']} | {status} | {row['default'] or 'N/A'} | {row['description']} |"
        )
    return "\n".join(lines)


def _synthesize_grounded_output(query: str, contexts: list[dict]) -> str:
    if not contexts:
        return (
            "#### Quick Start\n"
            "```bash\n"
            "docker run --name={{CONTAINER_NAME}} --net=host -v {{KUBECONFIG_PATH}}:/home/krkn/.kube/config:Z -d quay.io/krkn-chaos/krkn-hub:{{SCENARIO_TAG}}\n"
            "```\n\n"
            "#### Parameters\n"
            "| Variable | Status | Default | Description |\n"
            "| :--- | :--- | :--- | :--- |\n"
            "| {{VAR_NAME}} | Required/Optional | N/A | Missing from context |\n\n"
            "#### Critical Notes\n"
            "- Retrieved context missing; fill placeholders before running.\n\n"
            "#### Validation\n"
            "```bash\n"
            "docker logs -f {{CONTAINER_NAME}}\n"
            "docker inspect {{CONTAINER_NAME}} --format \"{{.State.ExitCode}}\"\n"
            "```"
        )

    primary_ctx = contexts[0]
    full_text = (primary_ctx.get("text") or "").strip()
    image = _infer_image_from_context(primary_ctx)
    param_rows = extract_param_rows_from_markdown(full_text)
    bindings = infer_query_param_bindings(query, param_rows)
    notes = _extract_critical_notes(full_text)

    quick_start_cmd = _build_quick_start_command(image=image, bindings=bindings, runtime="docker")
    params_table = _render_parameters_table(param_rows)

    mapped_binding_notes = [f"{b['variable']} mapped to {b['value']} from query." for b in bindings]
    critical_notes = mapped_binding_notes + notes
    if not critical_notes:
        critical_notes = ["Ensure kube config is mounted and readable by the container user."]

    critical_notes_md = "\n".join(f"- {n}" for n in critical_notes[:6])

    return (
        "#### Quick Start\n"
        "```bash\n"
        f"{quick_start_cmd}\n"
        "```\n\n"
        "#### Parameters\n"
        f"{params_table}\n\n"
        "#### Critical Notes\n"
        f"{critical_notes_md}\n\n"
        "#### Validation\n"
        "```bash\n"
        "docker logs -f {{CONTAINER_NAME}}\n"
        "docker inspect {{CONTAINER_NAME}} --format \"{{.State.ExitCode}}\"\n"
        "```"
    )


def _context_supports_grounded_generation(contexts: list[dict]) -> bool:
    for ctx in contexts:
        text = (ctx.get("text") or "").strip()
        if not text:
            continue
        has_command = bool(extract_command_lines(text, max_lines=1))
        has_params = len(extract_param_rows_from_markdown(text, max_rows=10)) >= 3
        if has_command and has_params:
            return True
    return False


def _dedupe_param_rows(param_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for row in param_rows:
        variable = row.get("variable", "").strip()
        if not variable:
            continue
        existing = merged.get(variable)
        if not existing:
            merged[variable] = row
            continue
        # Prefer row with a meaningful default/description when duplicates exist.
        existing_default = (existing.get("default") or "").strip().lower()
        new_default = (row.get("default") or "").strip().lower()
        if existing_default in {"", "n/a", "none", '""', "''"} and new_default not in {"", "n/a", "none", '""', "''"}:
            merged[variable] = row
            continue
        if len((row.get("description") or "").strip()) > len((existing.get("description") or "").strip()):
            merged[variable] = row
    return list(merged.values())


def _build_prefilled_template(query: str, contexts: list[dict]) -> str:
    all_commands: list[str] = []
    logs_cmd = ""
    exit_cmd = ""
    collected_rows: list[dict[str, str]] = []
    collected_notes: list[str] = []

    for ctx in contexts:
        text = (ctx.get("text") or "").strip()
        if not text:
            continue

        commands = extract_command_lines(text, max_lines=20)
        all_commands.extend(commands)
        for cmd in commands:
            lower = cmd.lower()
            if not logs_cmd and (" podman logs" in f" {lower}" or " docker logs" in f" {lower}" or lower.startswith("podman logs") or lower.startswith("docker logs")):
                logs_cmd = cmd
            if not exit_cmd and (" podman inspect" in f" {lower}" or " docker inspect" in f" {lower}" or lower.startswith("podman inspect") or lower.startswith("docker inspect")):
                exit_cmd = cmd

        rows = extract_param_rows_from_markdown(text, max_rows=80)
        if rows:
            collected_rows.extend(rows)

        notes = _extract_critical_notes(text, max_notes=8)
        if notes:
            collected_notes.extend(notes)

    param_rows = _dedupe_param_rows(collected_rows)
    if not param_rows:
        # Fallback to variable-like tokens if table parsing fails.
        fallback_envs: list[str] = []
        for ctx in contexts:
            text = (ctx.get("text") or "").strip()
            fallback_envs.extend(extract_env_vars(text, max_vars=12))
        seen = set()
        for env in fallback_envs:
            if env in seen:
                continue
            seen.add(env)
            param_rows.append(
                {
                    "variable": env,
                    "description": "Fill from retrieved context.",
                    "default": "N/A",
                }
            )
            if len(param_rows) >= 12:
                break

    query_bindings = _collect_bindings_for_contexts(query, contexts)
    binding_by_var = {b["variable"]: b["value"] for b in query_bindings}

    table_lines = [
        "| Variable | Status | Default | Description |",
        "| :--- | :--- | :--- | :--- |",
    ]
    if param_rows:
        for row in param_rows[:20]:
            variable = row["variable"]
            status = infer_param_status(row.get("description", ""), row.get("default", ""))
            default = row.get("default") or "N/A"
            if variable in binding_by_var:
                default = binding_by_var[variable]
            desc = row.get("description") or "Fill from retrieved context."
            table_lines.append(f"| {variable} | {status} | {default} | {desc} |")
    else:
        table_lines.append("| {{VAR_NAME}} | Required/Optional | N/A | Fill from retrieved context. |")

    quick_start = all_commands[0] if all_commands else "{{QUICK_START_COMMAND_FROM_CONTEXT}}"
    if not logs_cmd:
        logs_cmd = "docker logs -f {{CONTAINER_NAME}}"
    if not exit_cmd:
        exit_cmd = 'docker inspect {{CONTAINER_NAME}} --format "{{.State.ExitCode}}"'

    notes_lines = []
    if query_bindings:
        for b in query_bindings[:6]:
            notes_lines.append(f"- {b['variable']} mapped to {b['value']} from query")
    for note in collected_notes:
        notes_lines.append(f"- {note}")
        if len(notes_lines) >= 8:
            break
    if not notes_lines:
        notes_lines = ["- {{FILL_FROM_TIPS_WARNINGS_OR_PREREQUISITES}}"]

    return (
        "#### Quick Start\n"
        "```bash\n"
        f"{quick_start}\n"
        "```\n\n"
        "#### Parameters\n"
        f"{'\\n'.join(table_lines)}\n\n"
        "#### Critical Notes\n"
        f"{'\\n'.join(notes_lines)}\n\n"
        "#### Validation\n"
        "```bash\n"
        f"{logs_cmd}\n"
        f"{exit_cmd}\n"
        "```"
    )


def build_prompt(query: str, contexts: list[dict], max_chars_per_context: int, system_prompt: str) -> str:
    blocks = []
    for idx, ctx in enumerate(contexts, 1):
        title = ctx.get("name") or ctx.get("id") or f"context-{idx}"
        full_text = (ctx.get("text") or "").strip()
        text = full_text
        effective_max_chars = max_chars_per_context if max_chars_per_context > 0 else 3500
        text = text[:effective_max_chars]

        commands = extract_command_lines(text, max_lines=4)
        notes = _extract_critical_notes(text, max_notes=3)

        block = [
            f"Scenario: {title}",
            f"DocID: {ctx.get('id', title)}",
            "KeyExcerpt:",
            text,
        ]
        if commands:
            block.append("KeyCommands: " + " | ".join(commands))
        if notes:
            block.append("KeyNotes: " + " | ".join(notes))
        blocks.append("\n".join(block))

    joined_context = "\n\n".join(blocks) if blocks else "(No context provided)"
    prefilled_template = _build_prefilled_template(query, contexts)

    return (
        f"[SYSTEM PROMPT]\n{system_prompt}\n\n"
        f"[USER QUERY]: \"{query}\"\n\n"
        f"[RETRIEVED CONTEXT]:\n{joined_context}\n\n"
        "[INSTRUCTION]\n"
        "Complete the prefilled template below using ONLY the retrieved context.\n"
        "Keep edits minimal and preserve headers/table format exactly.\n"
        "Keep unknown values in {{UPPERCASE_SNAKE_CASE}} form.\n"
        "Return ONLY markdown.\n\n"
        "[PREFILLED TEMPLATE]\n"
        f"{prefilled_template}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local LLM inference using retrieval export JSON")
    parser.add_argument("--input", required=True, help="Path to retrieval JSON export")
    parser.add_argument("--output", required=True, help="Path to write inference JSON output")
    parser.add_argument("--model", required=True, help="Path to GGUF model file")
    parser.add_argument("--max-tokens", type=int, default=896)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--n-ctx", type=int, default=6144, help="Inference context window")
    parser.add_argument("--n-batch", type=int, default=256, help="Prompt processing batch size")
    parser.add_argument("--threads", type=int, default=0, help="CPU threads (0 = auto)")
    parser.add_argument(
        "--generation-mode",
        choices=["auto", "llm", "grounded"],
        default="auto",
        help="auto: skip LLM on CPU when context is strongly structured; llm: always run model; grounded: deterministic synthesis only",
    )
    parser.add_argument("--n-gpu-layers", type=int, default=None, help="Override GPU offload layers")
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=0,
        help="Max characters per retrieved context (0 disables truncation and keeps full text)",
    )
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

    cpu_total = os.cpu_count() or 4
    n_threads = args.threads if args.threads > 0 else min(8, max(1, cpu_total - 1))
    print(f"[inference] n_ctx={args.n_ctx} n_batch={args.n_batch} threads={n_threads}")

    expected_bindings = _collect_bindings_for_contexts(query, results)
    should_use_grounded = False
    if args.generation_mode == "grounded":
        should_use_grounded = True
    elif args.generation_mode == "auto" and gpu_mode == "cpu" and _context_supports_grounded_generation(results):
        should_use_grounded = True

    if should_use_grounded:
        print("[inference] Using grounded generation path (skipping LLM)")
        text = _synthesize_grounded_output(query, results)
    else:
        llm = Llama(
            model_path=args.model,
            n_gpu_layers=n_gpu_layers,
            n_ctx=args.n_ctx,
            n_batch=args.n_batch,
            n_threads=n_threads,
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
        quality = _assess_output_quality(text, expected_bindings)
        print(
            "[inference] quality "
            f"score={quality['score']} required={quality['has_required_sections']} "
            f"command={quality['has_command']} bindings={quality['binding_coverage']}"
        )
        if not quality["has_required_sections"] or not quality["has_command"]:
            print("[inference] Output missing required structure; repairing from grounded fallback")
            fallback = _synthesize_grounded_output(query, results)
            text = _repair_output_with_fallback(text, fallback)
            repaired = _assess_output_quality(text, expected_bindings)
            if not repaired["has_required_sections"] or not repaired["has_command"]:
                print("[inference] Repair insufficient; replacing with grounded fallback")
                text = fallback
        elif float(quality["score"]) < 0.75:
            print("[inference] Output partially complete; repairing missing sections from fallback")
            fallback = _synthesize_grounded_output(query, results)
            text = _repair_output_with_fallback(text, fallback)

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
