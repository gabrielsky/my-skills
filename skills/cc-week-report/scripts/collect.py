#!/usr/bin/env python3
"""Collect work evidence for cc-week-report over a given date/time range.

Sources:
1. Local AI session histories:
   - Antigravity: ~/.gemini/antigravity/brain/*/.system_generated/logs/transcript.jsonl
   - Claude Code: ~/.claude/projects/*/*.jsonl (excluding subagents/)
   - Codex:       ~/.codex/sessions/*/*/*/*.jsonl (excluding subagent threads)
2. GitLab (via glab api, default host git.darcytech.com, group repos/jx/aikf):
   - MR Reviews: approved MRs + commented-only others' MRs
   - Commits: all-branch deduplicated non-merge commits authored by current user

Uses Python standard library only.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_HOSTNAME = "git.darcytech.com"
DEFAULT_GROUP = "repos/jx/aikf"

ISSUE_REF_RE = re.compile(
    r"(?:(?:proj|maint|repos)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)?#\d+"
)
USER_REQUEST_RE = re.compile(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.DOTALL)
WORKSPACE_PATH_RE = re.compile(
    r"/Users/[^/\s\"'\\]+/((?:workspace/[^/\s\"'\\]+/[^/\s\"'\\]+)|(?:\.ai-tools-hub/repos/[^/\s\"'\\]+))"
)

CODEX_SKIP_PREFIXES = (
    "# AGENTS.md instructions",
    "<INSTRUCTIONS>",
    "<environment_context>",
    "<permissions instructions>",
    "<turn_aborted>",
    "<collaboration_mode>",
    "<codex_internal_context",
)

CLAUDE_SKIP_PREFIXES = (
    "<command-name>",
    "<local-command-stdout>",
    "<local-command-caveat>",
    "<system-reminder>",
    "[Request interrupted by user]",
)

TRIVIAL_COMMANDS = {"/clear", "/compact", "/model", "/help", "/status", "/exit", "/quit"}


def local_tz() -> dt.tzinfo:
    return dt.datetime.now().astimezone().tzinfo or dt.timezone(dt.timedelta(hours=8))


def parse_iso(ts: str | None) -> dt.datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(s)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=local_tz())
        return parsed.astimezone(local_tz())
    except ValueError:
        return None


def parse_bound(value: str, is_end: bool) -> dt.datetime:
    tz = local_tz()
    s = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        d = dt.date.fromisoformat(s)
        t = dt.time(23, 59, 59, 999999) if is_end else dt.time(0, 0, 0)
        return dt.datetime.combine(d, t, tzinfo=tz)
    parsed = parse_iso(s)
    if parsed is None:
        raise ValueError(f"Invalid date/time format: {value!r} (expected YYYY-MM-DD or ISO-8601)")
    return parsed


def clean_text(text: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def normalize_project_name(path_str: str | None) -> str:
    if not path_str:
        return "unknown"
    p = path_str.rstrip("/")
    # Collapse worktree paths like .../metis/.claude/worktrees/xxx -> metis
    m = re.search(r"/([^/]+)/\.(?:claude|git)/worktrees/", p)
    if m:
        return m.group(1)
    m = re.search(r"/workspace/[^/]+/([^/]+)", p)
    if m:
        return m.group(1)
    if ".ai-tools-hub" in p:
        return "ai-tools-hub"
    base = os.path.basename(p)
    return base or p


def file_mtime_in_range(path: str, start_dt: dt.datetime, end_dt: dt.datetime) -> bool:
    """Fast pre-filter: skip files last modified strictly before start_dt."""
    try:
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(path), tz=local_tz())
        return mtime >= start_dt
    except OSError:
        return False


def pick_sample_prompts(prompts: list[str], limit: int = 4) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for p in prompts:
        c = clean_text(p, 220)
        if not c or c in seen:
            continue
        # Skip single-word confirmations when we already have prompts
        if result and c.lower() in {"ok", "yes", "y", "好的", "可以", "继续", "行", "确认", "go", "proceed"}:
            continue
        seen.add(c)
        result.append(c)
        if len(result) >= limit:
            break
    return result


# ---------------------------------------------------------------------------
# 1. Local AI session collectors
# ---------------------------------------------------------------------------


def collect_antigravity_sessions(
    start_dt: dt.datetime, end_dt: dt.datetime
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    base = Path.home() / ".gemini" / "antigravity" / "brain"
    if not base.exists():
        warnings.append(f"Antigravity directory not found: {base}")
        return [], warnings

    pattern = str(base / "*" / ".system_generated" / "logs" / "transcript.jsonl")
    sessions: list[dict[str, Any]] = []

    for path in glob.glob(pattern):
        if not file_mtime_in_range(path, start_dt, end_dt):
            continue
        conv_id = Path(path).parents[2].name
        user_prompts: list[str] = []
        last_assistant = ""
        in_range_ts: list[dt.datetime] = []
        ws_counter: Counter[str] = Counter()

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts = parse_iso(obj.get("created_at"))
                    if ts is None or not (start_dt <= ts <= end_dt):
                        continue

                    rec_type = obj.get("type")
                    source = obj.get("source")
                    content = obj.get("content") or ""

                    if rec_type == "USER_INPUT" and source == "USER_EXPLICIT":
                        m = USER_REQUEST_RE.search(content)
                        if not m:
                            continue
                        req = m.group(1).strip()
                        if not req or req.lower() in TRIVIAL_COMMANDS:
                            continue
                        user_prompts.append(req)
                        in_range_ts.append(ts)
                    elif rec_type == "PLANNER_RESPONSE":
                        if isinstance(content, str) and content.strip():
                            last_assistant = content.strip()
                            in_range_ts.append(ts)
                        for tc in obj.get("tool_calls") or []:
                            args_str = json.dumps(tc.get("args", ""), ensure_ascii=False)
                            for wm in WORKSPACE_PATH_RE.findall(args_str):
                                ws_counter[wm] += 1
        except OSError as exc:
            warnings.append(f"Failed to read Antigravity transcript {conv_id}: {exc}")
            continue

        if not user_prompts:
            continue

        project = "general"
        if ws_counter:
            top_ws = ws_counter.most_common(1)[0][0]
            project = normalize_project_name("/Users/u/" + top_ws)

        sessions.append(
            {
                "tool": "antigravity",
                "session_id": conv_id,
                "project": project,
                "started_at": min(in_range_ts).isoformat(timespec="seconds"),
                "ended_at": max(in_range_ts).isoformat(timespec="seconds"),
                "user_turns": len(user_prompts),
                "prompts": pick_sample_prompts(user_prompts),
                "last_reply_snippet": clean_text(last_assistant, 320),
            }
        )

    return sessions, warnings


def extract_claude_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text")
                if isinstance(t, str) and t.strip():
                    parts.append(t.strip())
        return "\n".join(parts).strip()
    return ""


def collect_claude_sessions(
    start_dt: dt.datetime, end_dt: dt.datetime
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        warnings.append(f"Claude Code directory not found: {base}")
        return [], warnings

    pattern = str(base / "*" / "*.jsonl")
    sessions: list[dict[str, Any]] = []

    for path in glob.glob(pattern):
        if "/subagents/" in path:
            continue
        if not file_mtime_in_range(path, start_dt, end_dt):
            continue

        session_id = Path(path).stem
        cwd: str | None = None
        custom_title: str | None = None
        user_prompts: list[str] = []
        last_assistant = ""
        in_range_ts: list[dt.datetime] = []

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if obj.get("type") == "custom-title" and obj.get("customTitle"):
                        custom_title = str(obj["customTitle"]).strip()
                        continue

                    if obj.get("isSidechain") or obj.get("isMeta"):
                        continue

                    if not cwd and obj.get("cwd"):
                        cwd = str(obj["cwd"])

                    ts = parse_iso(obj.get("timestamp"))
                    if ts is None or not (start_dt <= ts <= end_dt):
                        continue

                    rec_type = obj.get("type")
                    msg = obj.get("message") or {}
                    text = extract_claude_text(msg.get("content"))
                    if not text:
                        continue

                    if rec_type == "user":
                        if any(text.startswith(pfx) for pfx in CLAUDE_SKIP_PREFIXES):
                            continue
                        if text.lower() in TRIVIAL_COMMANDS:
                            continue
                        user_prompts.append(text)
                        in_range_ts.append(ts)
                    elif rec_type == "assistant":
                        last_assistant = text
                        in_range_ts.append(ts)
        except OSError as exc:
            warnings.append(f"Failed to read Claude session {session_id}: {exc}")
            continue

        if not user_prompts:
            continue

        project = normalize_project_name(cwd or Path(path).parent.name)
        entry: dict[str, Any] = {
            "tool": "claude-code",
            "session_id": session_id,
            "project": project,
            "started_at": min(in_range_ts).isoformat(timespec="seconds"),
            "ended_at": max(in_range_ts).isoformat(timespec="seconds"),
            "user_turns": len(user_prompts),
            "prompts": pick_sample_prompts(user_prompts),
            "last_reply_snippet": clean_text(last_assistant, 320),
        }
        if custom_title:
            entry["title"] = custom_title
        sessions.append(entry)

    return sessions, warnings


def extract_codex_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("text"):
            parts.append(str(item["text"]).strip())
    return "\n".join(parts).strip()


def collect_codex_sessions(
    start_dt: dt.datetime, end_dt: dt.datetime
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    base = Path.home() / ".codex" / "sessions"
    if not base.exists():
        warnings.append(f"Codex directory not found: {base}")
        return [], warnings

    pattern = str(base / "*" / "*" / "*" / "*.jsonl")
    sessions: list[dict[str, Any]] = []

    for path in glob.glob(pattern):
        if not file_mtime_in_range(path, start_dt, end_dt):
            continue

        session_id = Path(path).stem
        cwd: str | None = None
        is_subagent = False
        user_prompts: list[str] = []
        last_assistant = ""
        in_range_ts: list[dt.datetime] = []

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    rec_type = obj.get("type")
                    payload = obj.get("payload") or {}

                    if rec_type == "session_meta":
                        if isinstance(payload.get("source"), dict):
                            is_subagent = True
                            break
                        if payload.get("id"):
                            session_id = str(payload["id"])
                        if payload.get("cwd"):
                            cwd = str(payload["cwd"])
                        continue

                    ts = parse_iso(obj.get("timestamp"))
                    if ts is None or not (start_dt <= ts <= end_dt):
                        continue

                    if rec_type == "response_item" and payload.get("type") == "message":
                        role = payload.get("role")
                        text = extract_codex_text(payload.get("content"))
                        if not text:
                            continue
                        if role == "user":
                            if any(text.startswith(pfx) for pfx in CODEX_SKIP_PREFIXES):
                                continue
                            if text.lower() in TRIVIAL_COMMANDS:
                                continue
                            user_prompts.append(text)
                            in_range_ts.append(ts)
                        elif role == "assistant":
                            last_assistant = text
                            in_range_ts.append(ts)
        except OSError as exc:
            warnings.append(f"Failed to read Codex session {session_id}: {exc}")
            continue

        if is_subagent or not user_prompts:
            continue

        sessions.append(
            {
                "tool": "codex",
                "session_id": session_id,
                "project": normalize_project_name(cwd),
                "started_at": min(in_range_ts).isoformat(timespec="seconds"),
                "ended_at": max(in_range_ts).isoformat(timespec="seconds"),
                "user_turns": len(user_prompts),
                "prompts": pick_sample_prompts(user_prompts),
                "last_reply_snippet": clean_text(last_assistant, 320),
            }
        )

    return sessions, warnings


# ---------------------------------------------------------------------------
# 2. GitLab collectors via glab api
# ---------------------------------------------------------------------------


def glab_api_json(hostname: str, endpoint: str) -> Any:
    cmd = ["glab", "api", "--hostname", hostname, endpoint]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"glab api failed ({endpoint}): {err}")
    return json.loads(proc.stdout)


def glab_api_paginated(hostname: str, endpoint: str, max_pages: int = 20) -> list[Any]:
    sep = "&" if "?" in endpoint else "?"
    items: list[Any] = []
    for page in range(1, max_pages + 1):
        paged = f"{endpoint}{sep}per_page=100&page={page}"
        data = glab_api_json(hostname, paged)
        if not isinstance(data, list) or not data:
            break
        items.extend(data)
        if len(data) < 100:
            break
    return items


def git_global_config(key: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "config", "--global", key], capture_output=True, text=True, timeout=5
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except OSError:
        return ""


def collect_gitlab_data(
    hostname: str, group_path: str, start_dt: dt.datetime, end_dt: dt.datetime
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "ok",
        "hostname": hostname,
        "group": group_path,
        "user": {},
        "projects_total": 0,
        "projects_active": 0,
        "reviews": {
            "approved": [],
            "commented_only": [],
        },
        "commits": {
            "total_commits": 0,
            "by_repo": [],
        },
        "warnings": [],
    }

    if not shutil.which("glab"):
        result["status"] = "unavailable"
        result["warnings"].append("glab CLI not found in PATH")
        return result

    try:
        user = glab_api_json(hostname, "user")
    except Exception as exc:
        result["status"] = "unavailable"
        result["warnings"].append(f"GitLab auth/connectivity error: {exc}")
        return result

    username = (user.get("username") or "").strip()
    user_name = (user.get("name") or "").strip()
    emails = {
        e.lower()
        for e in [
            user.get("email") or "",
            user.get("commit_email") or "",
            git_global_config("user.email"),
        ]
        if e
    }
    names = {n.lower() for n in [user_name, username, git_global_config("user.name")] if n}
    result["user"] = {
        "username": username,
        "name": user_name,
        "emails": sorted(emails),
    }

    encoded_group = urllib.parse.quote(group_path, safe="")
    try:
        projects = glab_api_paginated(
            hostname, f"groups/{encoded_group}/projects?include_subgroups=true"
        )
    except Exception as exc:
        result["status"] = "partial"
        result["warnings"].append(f"Failed to list group projects for {group_path}: {exc}")
        return result

    project_map: dict[int, dict[str, Any]] = {}
    for p in projects:
        pid = p.get("id")
        if pid is None:
            continue
        full_path = p.get("path_with_namespace") or p.get("path") or str(pid)
        short_name = full_path.removeprefix(group_path + "/")
        project_map[int(pid)] = {
            "id": int(pid),
            "name": short_name,
            "path_with_namespace": full_path,
            "web_url": p.get("web_url") or "",
            "default_branch": p.get("default_branch") or "",
            "last_activity_at": parse_iso(p.get("last_activity_at")),
        }

    result["projects_total"] = len(project_map)

    # GitLab events API `after` / `before` are exclusive YYYY-MM-DD dates.
    after_date = (start_dt.date() - dt.timedelta(days=1)).isoformat()
    before_date = (end_dt.date() + dt.timedelta(days=1)).isoformat()

    # Fetch approved & commented events in parallel
    approved_events: list[dict[str, Any]] = []
    commented_events: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        f_approved = pool.submit(
            glab_api_paginated,
            hostname,
            f"events?action=approved&after={after_date}&before={before_date}",
        )
        f_commented = pool.submit(
            glab_api_paginated,
            hostname,
            f"events?action=commented&after={after_date}&before={before_date}",
        )

        # Active projects for commit scan
        active_projects = [
            p
            for p in project_map.values()
            if p["last_activity_at"] is None or p["last_activity_at"] >= start_dt
        ]
        result["projects_active"] = len(active_projects)

        since_iso = urllib.parse.quote(start_dt.isoformat(timespec="seconds"), safe="")
        until_iso = urllib.parse.quote(end_dt.isoformat(timespec="seconds"), safe="")

        commit_futures = {
            pool.submit(
                glab_api_paginated,
                hostname,
                f"projects/{p['id']}/repository/commits?since={since_iso}&until={until_iso}&all=true",
            ): p
            for p in active_projects
        }

        try:
            approved_events = f_approved.result()
        except Exception as exc:
            result["warnings"].append(f"Failed to fetch approved events: {exc}")

        try:
            commented_events = f_commented.result()
        except Exception as exc:
            result["warnings"].append(f"Failed to fetch commented events: {exc}")

        # Process commits per repo
        total_commits = 0
        by_repo: list[dict[str, Any]] = []
        for fut, proj in commit_futures.items():
            try:
                raw_commits = fut.result()
            except Exception as exc:
                result["warnings"].append(f"Failed to fetch commits for {proj['name']}: {exc}")
                continue

            seen_shas: set[str] = set()
            matched_commits: list[dict[str, Any]] = []
            for c in raw_commits:
                sha = c.get("id") or ""
                if not sha or sha in seen_shas:
                    continue
                seen_shas.add(sha)

                a_email = (c.get("author_email") or "").strip().lower()
                a_name = (c.get("author_name") or "").strip().lower()
                if a_email not in emails and a_name not in names:
                    continue

                authored_dt = parse_iso(c.get("authored_date") or c.get("created_at"))
                if authored_dt is None or not (start_dt <= authored_dt <= end_dt):
                    continue

                title = (c.get("title") or "").strip()
                parent_ids = c.get("parent_ids") or []
                if len(parent_ids) > 1 or title.startswith(
                    ("Merge branch ", "Merge remote-tracking branch ", "Merge pull request ", "Merge tag ")
                ):
                    continue

                issues = sorted(set(ISSUE_REF_RE.findall(c.get("message") or title)))
                matched_commits.append(
                    {
                        "short_id": c.get("short_id") or sha[:8],
                        "title": title,
                        "authored_at": authored_dt.isoformat(timespec="seconds"),
                        "web_url": c.get("web_url") or "",
                        "issues": issues,
                    }
                )

            if not matched_commits:
                continue

            matched_commits.sort(key=lambda x: x["authored_at"], reverse=True)
            total_commits += len(matched_commits)

            # Pre-group commits by primary issue ref (or ungrouped)
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for mc in matched_commits:
                key = mc["issues"][0] if mc["issues"] else "_no_issue"
                groups[key].append(mc)

            grouped_items: list[dict[str, Any]] = []
            for key, items in groups.items():
                grouped_items.append(
                    {
                        "issue": None if key == "_no_issue" else key,
                        "commit_count": len(items),
                        "latest_at": items[0]["authored_at"],
                        "latest_short_id": items[0]["short_id"],
                        "latest_web_url": items[0]["web_url"],
                        "commits": items,
                    }
                )
            grouped_items.sort(key=lambda x: x["latest_at"], reverse=True)

            by_repo.append(
                {
                    "repo": proj["name"],
                    "repo_web_url": proj["web_url"],
                    "commit_count": len(matched_commits),
                    "groups": grouped_items,
                }
            )

        by_repo.sort(key=lambda x: x["commit_count"], reverse=True)
        result["commits"] = {
            "total_commits": total_commits,
            "by_repo": by_repo,
        }

    # Aggregate approved and commented MR keys
    approved_map: dict[tuple[int, int], dt.datetime] = {}
    for ev in approved_events:
        if ev.get("target_type") != "MergeRequest":
            continue
        pid = ev.get("project_id")
        iid = ev.get("target_iid")
        ts = parse_iso(ev.get("created_at"))
        if pid is None or iid is None or ts is None:
            continue
        pid_i, iid_i = int(pid), int(iid)
        if pid_i not in project_map or not (start_dt <= ts <= end_dt):
            continue
        prev = approved_map.get((pid_i, iid_i))
        if prev is None or ts > prev:
            approved_map[(pid_i, iid_i)] = ts

    comments_map: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for ev in commented_events:
        note = ev.get("note") or {}
        if note.get("noteable_type") != "MergeRequest" or note.get("system"):
            continue
        pid = ev.get("project_id")
        iid = note.get("noteable_iid")
        ts = parse_iso(ev.get("created_at"))
        if pid is None or iid is None or ts is None:
            continue
        pid_i, iid_i = int(pid), int(iid)
        if pid_i not in project_map or not (start_dt <= ts <= end_dt):
            continue
        body = clean_text(note.get("body") or "", 200)
        if body:
            comments_map[(pid_i, iid_i)].append(
                {"at": ts.isoformat(timespec="seconds"), "body": body}
            )

    all_mr_keys = sorted(set(approved_map.keys()) | set(comments_map.keys()))
    mr_details: dict[tuple[int, int], dict[str, Any]] = {}

    if all_mr_keys:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futs = {
                pool.submit(
                    glab_api_json, hostname, f"projects/{pid}/merge_requests/{iid}"
                ): (pid, iid)
                for pid, iid in all_mr_keys
            }
            for fut, key in futs.items():
                try:
                    mr_details[key] = fut.result()
                except Exception as exc:
                    result["warnings"].append(
                        f"Failed to fetch MR {project_map[key[0]]['name']}!{key[1]}: {exc}"
                    )

    approved_list: list[dict[str, Any]] = []
    commented_only_list: list[dict[str, Any]] = []

    for key in all_mr_keys:
        pid, iid = key
        proj = project_map[pid]
        mr = mr_details.get(key) or {}
        author_obj = mr.get("author") or {}
        author_username = (author_obj.get("username") or "").strip()
        author_name = (author_obj.get("name") or author_username or "unknown").strip()
        title = (mr.get("title") or "").strip()
        issues = sorted(set(ISSUE_REF_RE.findall(title + " " + (mr.get("description") or ""))))
        comments = sorted(comments_map.get(key, []), key=lambda x: x["at"])

        entry: dict[str, Any] = {
            "repo": proj["name"],
            "iid": iid,
            "title": title,
            "web_url": mr.get("web_url") or f"{proj['web_url']}/-/merge_requests/{iid}",
            "author": author_name,
            "author_username": author_username,
            "state": mr.get("state") or "unknown",
            "merged_at": (
                parse_iso(mr.get("merged_at")).isoformat(timespec="seconds")
                if parse_iso(mr.get("merged_at"))
                else None
            ),
            "issues": issues,
            "review_comments": [c["body"] for c in comments[:8]],
            "comment_count": len(comments),
        }

        if key in approved_map:
            entry["approved_at"] = approved_map[key].isoformat(timespec="seconds")
            entry["self_authored"] = bool(username and author_username == username)
            approved_list.append(entry)
        else:
            # Exclude comments made on your own MRs (replying to reviewers != reviewing others' code)
            if username and author_username == username:
                continue
            entry["last_commented_at"] = comments[-1]["at"] if comments else None
            commented_only_list.append(entry)

    approved_list.sort(key=lambda x: x["approved_at"], reverse=True)
    commented_only_list.sort(key=lambda x: x.get("last_commented_at") or "", reverse=True)

    result["reviews"] = {
        "approved": approved_list,
        "commented_only": commented_only_list,
    }
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect session & GitLab data for cc-week-report")
    parser.add_argument("--start", required=True, help="Start date/time (YYYY-MM-DD or ISO-8601)")
    parser.add_argument("--end", required=True, help="End date/time (YYYY-MM-DD or ISO-8601)")
    parser.add_argument("--hostname", default=DEFAULT_HOSTNAME, help="GitLab hostname")
    parser.add_argument("--group", default=DEFAULT_GROUP, help="GitLab group path")
    parser.add_argument("--out", help="Optional path to write JSON output instead of stdout")
    args = parser.parse_args()

    start_dt = parse_bound(args.start, is_end=False)
    end_dt = parse_bound(args.end, is_end=True)
    if start_dt > end_dt:
        print(f"Error: start ({start_dt}) is after end ({end_dt})", file=sys.stderr)
        return 2

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        f_agy = pool.submit(collect_antigravity_sessions, start_dt, end_dt)
        f_cc = pool.submit(collect_claude_sessions, start_dt, end_dt)
        f_cx = pool.submit(collect_codex_sessions, start_dt, end_dt)
        f_gl = pool.submit(collect_gitlab_data, args.hostname, args.group, start_dt, end_dt)

        agy_sessions, agy_warn = f_agy.result()
        cc_sessions, cc_warn = f_cc.result()
        cx_sessions, cx_warn = f_cx.result()
        gitlab_data = f_gl.result()

    all_sessions = agy_sessions + cc_sessions + cx_sessions
    all_sessions.sort(key=lambda s: s["ended_at"], reverse=True)

    payload = {
        "range": {
            "start": start_dt.isoformat(timespec="seconds"),
            "end": end_dt.isoformat(timespec="seconds"),
            "timezone": str(local_tz()),
        },
        "sessions": {
            "counts": {
                "antigravity": len(agy_sessions),
                "claude-code": len(cc_sessions),
                "codex": len(cx_sessions),
                "total": len(all_sessions),
            },
            "warnings": agy_warn + cc_warn + cx_warn,
            "items": all_sessions,
        },
        "gitlab": gitlab_data,
    }

    output = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    else:
        print(output)

    print(
        f"[cc-week-report] range={args.start}..{args.end} | "
        f"sessions={len(all_sessions)} (agy={len(agy_sessions)}, cc={len(cc_sessions)}, codex={len(cx_sessions)}) | "
        f"commits={gitlab_data['commits']['total_commits']} | "
        f"reviews: approved={len(gitlab_data['reviews']['approved'])}, "
        f"commented_only={len(gitlab_data['reviews']['commented_only'])} | "
        f"gitlab_status={gitlab_data['status']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
