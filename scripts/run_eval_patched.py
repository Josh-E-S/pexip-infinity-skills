#!/usr/bin/env python3
"""Eval harness for pexip-infinity-skills.

Mirrors anthropics/skills skill-creator/scripts/run_eval.py CLI surface
and stream-event detection, but reimplements the orchestrator so we can
also count a trigger when the model reads the REAL SKILL.md (whose path
contains the bare skill_name) — not only when it loads the throwaway
slash-command shim (whose name has a uuid suffix).

Why: in our repo, `claude -p` sees both the shim and the real skill files.
The model correctly prefers the real ones. Upstream only detects the shim,
so correct behavior reads as a miss. This wrapper fixes the measurement.

Same CLI as upstream: --skill-path, --eval-set, --runs-per-query,
--num-workers, --timeout, --trigger-threshold, --model, --verbose,
--description. Emits the same JSON shape on stdout."""

import argparse
import json
import os
import re
import select
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def parse_skill_md(skill_path: Path) -> tuple[str, str]:
    text = (skill_path / "SKILL.md").read_text()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        raise ValueError(f"no frontmatter in {skill_path}/SKILL.md")
    fm = m.group(1)
    name_m = re.search(r"^name:\s*(.+?)\s*$", fm, re.M)
    # Description may be a single line OR a YAML block scalar (`>` / `|`).
    desc_m = re.search(
        r"^description:\s*(.+?)(?=^\S|\Z)", fm + "\n", re.M | re.S
    )
    if not name_m or not desc_m:
        raise ValueError(f"frontmatter missing name/description in {skill_path}")
    name = name_m.group(1).strip()
    description = re.sub(r"\s+", " ", desc_m.group(1).strip())
    return name, description


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: str | None,
    debug: bool,
) -> bool:
    """Run one `claude -p` invocation and return True iff the skill triggered.

    A trigger is any of:
      - Skill tool called with skill arg matching the shim's clean_name
        OR the bare skill_name (with path-component boundary)
      - Read tool called with file_path containing the bare skill_name
        as a path component
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    commands_dir = Path(project_root) / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    command_file = commands_dir / f"{clean_name}.md"

    indented_desc = "\n  ".join(skill_description.split("\n"))
    command_file.write_text(
        "---\n"
        "description: |\n"
        f"  {indented_desc}\n"
        "---\n\n"
        f"# {skill_name}\n\n"
        f"This skill handles: {skill_description}\n"
    )

    # Path-component match: bounded by /, ", whitespace, dot, or string edge.
    name_re = re.compile(
        rf"(^|[/\"\s]){re.escape(skill_name)}([/\"\s.]|$)"
    )
    clean_re = re.compile(re.escape(clean_name))
    # Match any shim of the form `<skill_name>-skill-<hex>` — when runs
    # execute in parallel, multiple shims coexist in .claude/commands/
    # and the model may load a sibling process's shim. That's still a
    # correct trigger for this skill, so count it.
    any_shim_re = re.compile(
        rf"(^|[/\"\s]){re.escape(skill_name)}-skill-[0-9a-f]+([/\"\s.]|$)"
    )

    try:
        cmd = [
            "claude",
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=project_root,
            env=env,
        )

        triggered = False
        start_time = time.time()
        buffer = ""
        try:
            while time.time() - start_time < timeout:
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break
                ready, _, _ = select.select([process.stdout], [], [], 1.0)
                if not ready:
                    continue
                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if event.get("type") == "assistant":
                        for content_item in event.get("message", {}).get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if debug:
                                print(
                                    f"[debug:{clean_name}] {tool_name} -> "
                                    f"{json.dumps(tool_input)[:200]}",
                                    file=sys.stderr,
                                )
                            if tool_name == "Skill":
                                skill_arg = tool_input.get("skill", "")
                                if (
                                    clean_re.search(skill_arg)
                                    or any_shim_re.search(skill_arg)
                                    or name_re.search(skill_arg)
                                    or skill_arg == skill_name
                                ):
                                    return True
                            elif tool_name == "Read":
                                path = tool_input.get("file_path", "")
                                if (
                                    clean_re.search(path)
                                    or any_shim_re.search(path)
                                    or name_re.search(path)
                                ):
                                    return True
                    elif event.get("type") == "result":
                        return triggered
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        return triggered
    finally:
        try:
            command_file.unlink()
        except FileNotFoundError:
            pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--eval-set", required=True)
    p.add_argument("--skill-path", required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--num-workers", type=int, default=10)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--runs-per-query", type=int, default=3)
    p.add_argument("--trigger-threshold", type=float, default=0.5)
    p.add_argument("--model", default=None)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = str(find_project_root())
    debug = bool(os.environ.get("EVAL_DEBUG"))

    eval_set = json.loads(Path(args.eval_set).read_text())
    if args.verbose:
        print(f"Evaluating: {description[:200]}...", file=sys.stderr)
        print(f"Project root: {project_root}", file=sys.stderr)

    query_triggers: dict[str, list[bool]] = {}
    query_items: dict[str, dict] = {}

    with ProcessPoolExecutor(max_workers=args.num_workers) as executor:
        future_to_query = {}
        for item in eval_set:
            for _ in range(args.runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    name,
                    description,
                    args.timeout,
                    project_root,
                    args.model,
                    debug,
                )
                future_to_query[future] = item

        for future in as_completed(future_to_query):
            item = future_to_query[future]
            query = item["query"]
            query_items[query] = item
            query_triggers.setdefault(query, [])
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    results = []
    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should = item["should_trigger"]
        did_pass = (
            trigger_rate >= args.trigger_threshold
            if should
            else trigger_rate < args.trigger_threshold
        )
        results.append({
            "query": query,
            "should_trigger": should,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    out = {
        "skill_name": name,
        "description": description,
        "results": results,
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
    }

    if args.verbose:
        print(f"Results: {passed}/{len(results)} passed", file=sys.stderr)
        for r in results:
            status = "PASS" if r["pass"] else "FAIL"
            print(
                f"  [{status}] rate={r['triggers']}/{r['runs']} "
                f"expected={r['should_trigger']}: {r['query'][:70]}",
                file=sys.stderr,
            )

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
