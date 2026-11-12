# Copyright 2026 Antigravity
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Antigravity PE Frontier: Stage 2 Autonomous Multi-Role Physical Engineering Harness.

Engineered for the 56 hidden private test tasks and 29 public dev tasks:
1. ARCHITECT_PLANNER: Ingests all project drawings, specifications, transmittals,
   and code excerpts. Resolves document conflicts (superseded vs governing) and
   issues an exact Engineering Work Plan with deliverable schemas and verification criteria.
2. ENGINEERING_WORKER: Executes the plan using Python-driven numerical computation
   (strictly avoiding hand calculations). Writes deliverable artifacts (.xlsx, .dxf, .ifc, .zip, .md)
   with rigorous unit tracking, surgical edit_file capability, and code compliance
   (ASCE 7, AISC 360, ACI 318, NEC NFPA 70, ASHRAE 90.1, NFPA 13).
3. PE_VERIFIER: Independent licensed Professional Engineer persona that audits deliverable files,
   checks boundary limits, recomputes safety margins (Demand/Capacity <= 1.0), and enforces fix rounds.
4. TASK-PROVIDED MCP INTEGRATION: Auto-discovers and connects to task-provided MCP servers
   (spreadsheets, CAD viewers, calculation engines, transmittals) via mcp_find and mcp_call.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Any

import openai
import taskbridge

MODEL = os.environ.get("MODEL_NAME", "claude-opus-5-5")
MAX_EFFORT_MODELS = ("glm", "gpt-6", "deepseek-v4")
env_effort = (os.environ.get("REASONING_EFFORT") or "").strip().lower()
if env_effort in ("low", "medium", "high"):
    EFFORT = env_effort
else:
    EFFORT = "high" if any(m in MODEL.lower() for m in MAX_EFFORT_MODELS) else "medium"

USE_CLAUDE_EXTRAS = "claude" in MODEL.lower()
PASS_ONLY = re.compile(r"^[\s*_`#>]*PASS[\s*_`.!]*$", re.I)

WRAP_UP_SEC = 240
WRAP_UP = {
    "role": "user",
    "content": "Time is up for this step. Stop and reply with your final verified answer.",
}
RESULT_CHARS = 25_000
RETRY_WAITS = (5, 15, 30, 60, 120)

CONTEXT_FULL = re.compile(
    r"context.?(length|window)|prompt is too long|maximum prompt length"
    r"|exceed[^.]{0,40}(token|context)",
    re.I,
)
CUT_KEEP = 1200
MAX_NUDGES = 3
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "32000"))
CACHE_MARK = "claude" in MODEL.lower()

PLAN_SHARE = 0.12
CHECK_SHARE = 0.25
MIN_STEP_SEC = 120
MAX_FIX_ROUNDS = 2

# Evaluator sets OPENAI_BASE_URL and OPENAI_API_KEY
client = openai.AsyncOpenAI(max_retries=0, timeout=1800)

PLANNER_PROMPT = """You are a Principal Engineering Architect planning a long-horizon physical engineering project in a containerized Linux workspace ({workdir}) with no internet access.
Your role is to inspect the project package, resolve all document ambiguities, and author an exact, unambiguous Engineering Work Plan.

### Rules of Engagement:
1. Inspect the workspace using bash and read_file (do NOT create, write, or modify any files).
2. Discover all relevant files (drawings, specifications, schedules, boring logs, CAD/IFC models, transmittals).
3. Document Hierarchy: Check transmittal sheets, revision dates, and notes to distinguish GOVERNING documents from SUPERSEDED versions.
4. Extract Requirements: Identify every single deliverable, its exact target path, required format, and boundary criteria.
5. Formulate Methodology: Outline the governing physical equations, regulatory codes (AISC 360, ACI 318, ASCE 7, NEC NFPA 70, ASHRAE 90.1, NFPA 13), required unit conversions, and verification tests.
6. Reply with your structured Engineering Work Plan covering:
   - Governing Documents Register (Governing vs Superseded)
   - Deliverables Matrix (Path, Format, Grader Requirements)
   - Numerical Criteria & Code Limits (Demand/Capacity, deflections, clearance, ampacity)
   - Step-by-Step Implementation & Calculation Protocol
   - Verification Checklist for the Worker and Reviewer
"""

WORKER_PROMPT = """You are a Lead Physical Engineer executing an engineering task in a Linux workspace ({workdir}) with no internet access.
You receive the task instructions and the Architect's Work Plan. Your goal is to produce stamped, production-grade engineering deliverables.

### Professional Standards:
1. Code-First Computation: NEVER calculate complex engineering formulas or unit conversions by hand or mental math. Write Python scripts (numpy, scipy, pandas, openpyxl, ezdxf, ifcopenshell) to compute exact numerical values, equilibrium equations, and load combinations.
2. Unit Discipline: Explicitly track and verify units across all transitions (kN <-> lbf, ft <-> m, psi <-> kPa, gpm <-> L/s).
3. Surgical Edits: Use edit_file for targeted script adjustments, formula corrections, and configuration updates to preserve context and avoid full-file rewrites. Use write_file when creating new files.
4. Exact Deliverables: Place every deliverable file at the exact relative or absolute path specified in the task instruction. Ensure all required sheets, tables, layers, and metadata are populated.
5. Self-Inspection: After writing each deliverable (.xlsx, .dxf, .ifc, .zip, .md), inspect it to ensure it is valid, non-empty, and free from formula errors (#DIV/0!, #REF!).
6. Final Summary: When finished, reply without calling any tool: provide an executive-level deliverable summary detailing file paths, design basis, safety margins, and key engineering parameters.
"""

VERIFIER_PROMPT = """You are a licensed Professional Engineer (PE) and hostile Technical Auditor conducting a final quality audit on an engineering package in {workdir}.
You receive the task instruction, the work plan, and the Lead Engineer's deliverable summary.

### Audit Protocol:
1. Inspect every deliverable file using bash and read_file (do NOT create or modify any files).
2. Completeness Check: Verify every deliverable exists at its exact target path, has non-zero size, and is readable.
3. Code & Safety Margin Verification: Recompute critical safety factors and demand/capacity ratios (D/C <= 1.0, deflection limits, clearance clashes = 0).
4. Formatting & Schema Check: Verify spreadsheet sheets, column headers, units, and CAD/IFC geometric consistency.
5. Verdict:
   - If ALL deliverables pass all checks without flaws, reply with the single word PASS and nothing else.
   - If ANY deliverable has gaps, omissions, mathematical flaws, or missing criteria, reply with a numbered, specific list of actionable gaps for the engineer to fix.
"""


def tool(name: str, description: str, **params: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": v} for k, v in params.items()},
                "required": list(params),
            },
        },
    }


BASE_TOOLS = [
    tool("bash", "Run a bash command (120 s limit) and return its exit code and output.", command="string"),
    tool("read_file", "Read a text file from the task container.", path="string"),
    tool("write_file", "Create or overwrite a file in the task container; parent folders are created.", path="string", content="string"),
    tool("edit_file", "Replace target text in a file with replacement text (exact string match).", path="string", target="string", replacement="string"),
]
BASE_READ_ONLY = [
    BASE_TOOLS[0],  # bash
    BASE_TOOLS[1],  # read_file
]


class MCPServer(taskbridge.MCPClient):
    """Client wrapper for a task-provided MCP server and its discovered tools."""

    def __init__(self, session: taskbridge.Session, spec: dict[str, Any]):
        super().__init__(session, spec["url"], client="antigravity-pe-frontier")
        self.name = spec["name"]
        self.tools: list[dict[str, Any]] = []

    async def start(self) -> None:
        await self.initialize()
        self.tools = await self.list_tools()

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self.call_tool(name, arguments)
        parts = []
        content = result.get("content") if isinstance(result.get("content"), list) else []
        for item in content:
            kind = item.get("type") if isinstance(item, dict) else None
            if kind == "text":
                parts.append(str(item.get("text", "")))
            elif kind in ("resource", "resource_link"):
                parts.append(json.dumps(item)[:RESULT_CHARS])
        if result.get("isError"):
            return f"error: {result.get('error') or '\n'.join(parts) or 'MCP tool call failed'}"
        return clip("\n".join(parts) or "ok (tool executed with no text output)")


class MCPRegistry:
    """Manages active task MCP servers and exposes search and execution."""

    def __init__(self, session: taskbridge.Session):
        self.session = session
        self.servers: dict[str, MCPServer] = {}
        self.tools: dict[str, tuple[MCPServer, dict[str, Any]]] = {}

    async def connect_all(self) -> None:
        for spec in getattr(self.session, "mcp_servers", []):
            try:
                server = MCPServer(self.session, spec)
                await server.start()
                self.servers[server.name] = server
                for t in server.tools:
                    qualified_name = f"{server.name}__{t['name']}"
                    self.tools[qualified_name] = (server, t)
                await self.session.log(f"Connected MCP server '{server.name}' with {len(server.tools)} tools")
            except Exception as exc:
                await self.session.log(f"Warning: could not connect to MCP server {spec.get('name')}: {exc}")

    def find_tools(self, query: str) -> str:
        if not self.tools:
            return "No task MCP tools are available for this task."
        words = [w for w in re.split(r"[^a-z0-9]+", query.lower()) if w]

        def score(item):
            name, (_, t) = item
            text = f"{name} {t.get('description') or ''}".lower()
            return (query.lower() == name.lower()) * 100 + sum(w in name.lower() for w in words) * 3 + sum(w in text for w in words)

        best = [item for item in sorted(self.tools.items(), key=score, reverse=True)[:8] if score(item) > 0]
        if not best:
            return f"No MCP tools match {query!r}. Available tools: {', '.join(self.tools.keys())}"
        found = [
            f"Server: {server.name} | Tool: {t['name']} (Qualified: {name})\n"
            f"Description: {(t.get('description') or 'No description')[:300]}\n"
            f"Parameters: {json.dumps(t.get('inputSchema') or {})}"
            for name, (server, t) in best
        ]
        return "\n\n".join(found)

    async def execute_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        server = self.servers.get(server_name)
        if not server:
            return f"error: MCP server '{server_name}' not found. Available servers: {list(self.servers.keys())}"
        return await server.call(tool_name, arguments)


def clip(text: str) -> str:
    if len(text) <= RESULT_CHARS:
        return text
    half = RESULT_CHARS // 2
    return f"{text[:half]}\n[... {len(text) - RESULT_CHARS} characters clipped for context hygiene ...]\n{text[-half:]}"


def marked(messages: list[dict]) -> list[dict]:
    if not CACHE_MARK:
        return messages
    out = list(messages)
    for i in {0, len(out) - 1}:
        m = out[i]
        content = m.get("content")
        if isinstance(content, str) and content:
            out[i] = {
                **m,
                "content": [{
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                }],
            }
        else:
            out[i] = {**m, "cache_control": {"type": "ephemeral"}}
    return out


async def run_tool(session: taskbridge.Session, fn: dict, mcp_reg: MCPRegistry) -> str:
    name = fn["name"]
    try:
        args = json.loads(fn.get("arguments") or "{}")
        if not isinstance(args, dict):
            raise TypeError("not a JSON object")
        fn["arguments"] = json.dumps(args, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fn["arguments"] = "{}"
        return f"error: the arguments are not a JSON object ({exc}); resend"

    try:
        if name == "bash":
            res = await session.exec(args["command"])
            return clip(f"exit code {res['exit_code']}\n{res['output']}")
        if name == "read_file":
            raw = await session.read_file(args["path"])
            return clip(raw.decode("utf-8", "replace"))
        if name == "write_file":
            count = await session.write_file(args["path"], args["content"])
            return f"wrote {count} bytes to {args['path']}"
        if name == "edit_file":
            path = args["path"]
            target = args["target"]
            replacement = args["replacement"]
            raw = await session.read_file(path)
            content = raw.decode("utf-8", "replace")
            if target not in content:
                return f"error: target string not found in {path}. Ensure exact character match including indentation."
            count = content.count(target)
            new_content = content.replace(target, replacement, 1)
            byte_count = await session.write_file(path, new_content)
            return f"successfully replaced target in {path} ({byte_count} bytes total, {count} occurrence(s) found)"
        if name == "mcp_find":
            query = args.get("query", "")
            return mcp_reg.find_tools(query)
        if name == "mcp_call":
            s_name = args.get("server", "")
            t_name = args.get("tool", "")
            t_args = args.get("arguments", {})
            if isinstance(t_args, str):
                try:
                    t_args = json.loads(t_args)
                except Exception:
                    pass
            return await mcp_reg.execute_tool(s_name, t_name, t_args if isinstance(t_args, dict) else {})
        return f"error: unknown tool {name}"
    except Exception as exc:
        return f"error: {type(exc).__name__}: {exc}"


async def recover(session: taskbridge.Session, messages: list[dict], exc: Exception, waits, until: float) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 400 and CONTEXT_FULL.search(str(exc)):
        return await shorten(session, messages)
    wait = next(waits, None)
    if wait is None or not (status is None or status in (408, 409, 429) or status >= 500):
        return False
    left = session.time_left()
    if left is not None:
        slack = left - until
        if slack <= 10:
            return False
        wait = min(wait, slack - 10)
    await session.log(f"Model call retry ({str(exc)[:150]}); backoff {wait:.0f}s")
    await asyncio.sleep(wait)
    return True


async def shorten(session: taskbridge.Session, messages: list[dict]) -> bool:
    long = [
        n for n, m in enumerate(messages)
        if m.get("role") == "tool" and len(m.get("content", "")) > 2 * CUT_KEEP
    ]
    if not long:
        return False
    cut = long[: max(1, len(long) // 2)]
    for n in cut:
        messages[n]["content"] = (
            messages[n]["content"][:CUT_KEEP]
            + "\n[... clipped to preserve context window ...]"
        )
    await session.log(f"Compacted {len(cut)} old tool outputs to preserve context window")
    return True


def conversation(system: str, session: taskbridge.Session, prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": system.format(workdir=session.workdir)},
        {"role": "user", "content": prompt},
    ]


async def agent(session: taskbridge.Session, messages: list[dict], tools: list[dict], until: float, mcp_reg: MCPRegistry, final: bool = False) -> str:
    global USE_CLAUDE_EXTRAS
    nudges, head, waits = 0, "", iter(RETRY_WAITS)
    while True:
        left = session.time_left()
        wrap_up = left is not None and left <= until + WRAP_UP_SEC
        call_tools = [] if wrap_up else tools
        kwargs = {
            "model": MODEL,
            "messages": marked(messages + ([WRAP_UP] if wrap_up else [])),
            "max_tokens": MAX_OUTPUT_TOKENS,
        }
        if wrap_up:
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "none"
        elif tools:
            kwargs["tools"] = tools

        if "claude" in MODEL.lower():
            if USE_CLAUDE_EXTRAS:
                kwargs["extra_body"] = {
                    "thinking": {"type": "adaptive"},
                    "output_config": {"effort": "high"},
                }
        elif "gemini" in MODEL.lower() or "gemma" in MODEL.lower():
            kwargs["reasoning_effort"] = "high"
        elif EFFORT in ("low", "medium", "high"):
            kwargs["reasoning_effort"] = EFFORT

        try:
            left = session.time_left()
            per_call = 1800.0 if left is None else max(60.0, min(1800.0, left - 30.0))
            res = await client.chat.completions.create(**kwargs, timeout=per_call)
            waits = iter(RETRY_WAITS)
        except openai.BadRequestError as exc:
            if USE_CLAUDE_EXTRAS and re.search(r"thinking|output_config|effort|signature|extra_body", str(exc), re.I):
                USE_CLAUDE_EXTRAS = False
                await session.log(f"Gateway rejected thinking parameters ({exc}); retrying call without extra_body")
                continue
            if await recover(session, messages, exc, waits, until):
                continue
            raise
        except openai.APIError as exc:
            if await recover(session, messages, exc, waits, until):
                continue
            raise

        message = res.choices[0].message
        text = head + (message.content or "")
        cut = res.choices[0].finish_reason == "length"

        if final and text:
            session.final_message = text

        if res.usage:
            u = res.usage
            cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
            session.send_usage(
                model=MODEL,
                input_tokens=u.prompt_tokens,
                output_tokens=u.completion_tokens,
                cache_read_tokens=cached,
            )

        turn = message.model_dump(exclude_none=True)
        if wrap_up or not message.tool_calls:
            turn.pop("tool_calls", None)
            if message.content:
                messages.append(turn)
            if wrap_up or (message.content and not cut) or nudges == MAX_NUDGES:
                return text
            nudges, head = nudges + 1, text
            messages.append({
                "role": "user",
                "content": "Your reply was cut off; continue where it stopped." if cut else "Continue and finish with your verified answer.",
            })
            continue

        nudges, head = 0, ""
        messages.append(turn)
        for call in turn["tool_calls"]:
            fname = call["function"]["name"]
            fargs = call["function"]["arguments"]
            await session.log(f"{fname} {fargs[:160]}")
            content = await run_tool(session, call["function"], mcp_reg)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": content,
            })

        if left is not None:
            mins_left = int((session.time_left() - until) // 60)
            messages[-1]["content"] += f"\n[{mins_left} minutes remaining for this step]"


async def inspect_deliverables(session: taskbridge.Session) -> str:
    """Pre-flight scan: list candidate deliverables and flag zero-byte files."""
    command = (
        "find . -maxdepth 6 -type f \\( -name '*.xlsx' -o -name '*.xlsm' "
        "-o -name '*.dxf' -o -name '*.dwg' -o -name '*.ifc' -o -name '*.docx' "
        "-o -name '*.pdf' -o -name '*.zip' -o -name '*.csv' -o -name '*.md' \\) "
        "-printf '%s\\t%p\\n' 2>/dev/null | sort -nr | head -n 40"
    )
    try:
        res = await session.exec(command)
    except Exception as exc:
        return f"Inspection error: {exc}"
    output = (res.get("output") or "").strip()
    if not output:
        return "No candidate deliverable files found under the task workdir."
    rows: list[tuple[int, str]] = []
    for line in output.splitlines():
        size_text, separator, path = line.partition("\t")
        if not separator:
            continue
        try:
            rows.append((int(size_text), path))
        except ValueError:
            continue
    if not rows:
        return "No candidate deliverable files found under the task workdir."
    total = sum(size for size, _ in rows)
    zero = [path for size, path in rows if size == 0]
    summary = f"{len(rows)} candidate deliverable(s), {total / (1024 * 1024):.2f} MiB total."
    if zero:
        summary += " Zero-byte: " + ", ".join(zero[:8])
    return summary + "\n" + output


async def solve(session: taskbridge.Session) -> str:
    total = session.time_left()

    # Step 0: Auto-discover and connect task MCP servers
    mcp_reg = MCPRegistry(session)
    await mcp_reg.connect_all()

    active_tools = list(BASE_TOOLS)
    active_read_only = list(BASE_READ_ONLY)
    if mcp_reg.tools:
        mcp_find_tool = tool("mcp_find", "Find available task-provided MCP tools matching keywords or name.", query="string")
        mcp_call_tool = tool("mcp_call", "Call an MCP tool on a task server.", server="string", tool="string", arguments="string")
        active_tools.extend([mcp_find_tool, mcp_call_tool])
        # Planner and verifier may discover MCP tools but must not mutate task state.
        active_read_only.append(mcp_find_tool)

    task = session.instruction
    await session.log(f"Starting Stage 2 Task Execution: {task[:200]}...")

    # Phase 1: Architect Planner (capped planning share; unused time stays with the worker)
    plan_until = 0.0 if total is None else min(total * (1.0 - PLAN_SHARE), max(total - WRAP_UP_SEC - 300, total * 0.5))
    try:
        plan = await agent(
            session,
            conversation(PLANNER_PROMPT, session, task),
            active_read_only,
            plan_until,
            mcp_reg,
        )
        await session.log(f"Architecture Plan established ({len(plan)} chars). Unused planning time remains available to the worker.")
    except Exception as exc:
        await session.log(f"Planner failed ({exc}); worker proceeds directly from task text")
        plan = "(No plan available. Derive all deliverables directly from the task instructions.)"

    # Phase 2: Engineering Worker (runs until the fixed verifier reserve remains)
    worker_until = 0.0 if total is None else max(0.0, total * CHECK_SHARE)
    work = conversation(WORKER_PROMPT, session, f"{task}\n\n## Engineering Work Plan\n{plan}")
    try:
        summary = await agent(session, work, active_tools, worker_until, mcp_reg, final=True)
    except Exception as work_err:
        await session.log(f"Worker phase exception ({work_err}); falling back to final message")
        summary = getattr(session, "final_message", "") or ""
    await session.log(f"Worker initial deliverable summary: {len(summary)} chars")

    # Phase 3: Hostile PE Reviewer & Fix Rounds
    try:
        for r in range(MAX_FIX_ROUNDS):
            left = session.time_left()
            if left is not None and left < WRAP_UP_SEC + MIN_STEP_SEC * 2:
                await session.log(f"Remaining time ({left:.0f}s) insufficient for another audit round; proceeding to finalization.")
                break

            audit_budget = max(MIN_STEP_SEC, (left or 600) * 0.25)
            audit_until = 0.0 if left is None else max(0.0, left - audit_budget - WRAP_UP_SEC)
            review_context = f"## Task Specification\n{task}\n\n## Work Plan\n{plan}\n\n## Engineer's Deliverable Summary\n{summary}"
            verdict = await agent(
                session,
                conversation(VERIFIER_PROMPT, session, review_context),
                active_read_only,
                audit_until,
                mcp_reg,
            )
            await session.log(f"PE Reviewer Round {r+1} Verdict: {verdict[:300]}")

            if PASS_ONLY.fullmatch(verdict.strip()):
                await session.log("PE Quality Audit PASSED: Zero critical defects found.")
                break
            elif not verdict.strip():
                await session.log("PE Quality Audit inconclusive; retaining verified deliverables.")
                break

            work.append({
                "role": "user",
                "content": f"The Professional Engineer Auditor identified these specific gaps:\n{verdict}\n\nFix every listed defect, verify the output files on disk, and reply with your updated summary.",
            })
            left_after_audit = session.time_left()
            fix_until = 0.0 if left_after_audit is None else max(0.0, left_after_audit * 0.5 - WRAP_UP_SEC)
            summary = await agent(session, work, active_tools, fix_until, mcp_reg, final=True) or summary
    except Exception as audit_err:
        await session.log(f"PE Quality Audit warning: {audit_err}; preserving worker deliverables.")

    # Phase 4: Pre-Flight Deliverable Verification
    files_summary = await inspect_deliverables(session)
    await session.log(f"Pre-Flight Deliverables Found:\n{files_summary}")

    return summary or getattr(session, "final_message", "") or ""


if __name__ == "__main__":
    taskbridge.run(solve)
