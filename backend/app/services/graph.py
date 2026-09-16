"""``build_graph(user_id)`` — assemble the knowledge graph from the live rows.

See ``.kiro/specs/phase-2-visual-and-graph/design.md`` § 4 (+ phase-2.5 journal
nodes). Pure read: six node queries, seven link rules, dedup, drop dangling
links, cap at :data:`NODE_CAP`. No LLM call.
"""

from __future__ import annotations

from typing import Any

from app.db import client
from app.services import tool_log

NODE_CAP = 250
_ALWAYS_KEEP = ("objective", "project")
_SYMMETRIC_KINDS = {"related"}


def _norm(source: str, target: str, kind: str) -> tuple[str, str, str]:
    if kind in _SYMMETRIC_KINDS and target < source:
        source, target = target, source
    return (source, target, kind)


async def build_graph(user_id: str) -> dict[str, Any]:
    nodes: dict[str, dict] = {}
    sortkey: dict[str, str] = {}  # node id -> recency string, for the cap tiebreak

    for r in await client.db_execute(
        "SELECT id, title, priority, horizon FROM objectives "
        "WHERE user_id = ? AND status = 'active'",
        [user_id],
    ):
        nid = f"objective:{r['id']}"
        nodes[nid] = {
            "id": nid,
            "type": "objective",
            "label": r["title"],
            "meta": {"priority": r["priority"], "horizon": r["horizon"]},
        }

    for r in await client.db_execute(
        "SELECT id, name, status FROM projects "
        "WHERE user_id = ? AND status IN ('active', 'paused')",
        [user_id],
    ):
        nid = f"project:{r['id']}"
        nodes[nid] = {
            "id": nid,
            "type": "project",
            "label": r["name"],
            "meta": {"status": r["status"]},
        }

    for r in await client.db_execute(
        "SELECT id, category, key, updated_at FROM context_entries "
        "WHERE user_id = ? AND status != 'archived'",
        [user_id],
    ):
        nid = f"context:{r['id']}"
        nodes[nid] = {
            "id": nid,
            "type": "context",
            "label": r["key"],
            "meta": {"category": r["category"], "key": r["key"]},
        }
        sortkey[nid] = r["updated_at"] or ""

    for r in await client.db_execute(
        "SELECT id, objective_id, title, status, updated_at FROM actions "
        "WHERE user_id = ? AND status IN ('todo', 'doing')",
        [user_id],
    ):
        nid = f"action:{r['id']}"
        nodes[nid] = {
            "id": nid,
            "type": "action",
            "label": r["title"],
            "meta": {"objective_id": r["objective_id"], "status": r["status"]},
        }
        sortkey[nid] = r["updated_at"] or ""

    for r in await client.db_execute(
        "SELECT id, title, last_message_at, created_at FROM conversations "
        "WHERE user_id = ? AND archived = 0 "
        "AND EXISTS (SELECT 1 FROM messages WHERE messages.conversation_id = conversations.id)",
        [user_id],
    ):
        nid = f"conversation:{r['id']}"
        nodes[nid] = {
            "id": nid,
            "type": "conversation",
            "label": r["title"] or "Untitled",
            "meta": {"last_message_at": r["last_message_at"]},
        }
        sortkey[nid] = r["last_message_at"] or r["created_at"] or ""

    for r in await client.db_execute(
        "SELECT id, title, body, mood, created_at FROM journal_entries "
        "WHERE user_id = ? AND TRIM(body) != ''",
        [user_id],
    ):
        nid = f"journal:{r['id']}"
        nodes[nid] = {
            "id": nid,
            "type": "journal",
            "label": r["title"] or r["body"][:40],
            "meta": {"mood": r["mood"], "created_at": r["created_at"]},
        }
        sortkey[nid] = r["created_at"] or ""

    truncated = False
    if len(nodes) > NODE_CAP:
        keep = {nid for nid, n in nodes.items() if n["type"] in _ALWAYS_KEEP}
        rest = sorted(
            (nid for nid in nodes if nid not in keep),
            key=lambda nid: sortkey.get(nid, ""),
            reverse=True,
        )
        for nid in rest:
            if len(keep) >= NODE_CAP:
                break
            keep.add(nid)
        nodes = {nid: n for nid, n in nodes.items() if nid in keep}
        truncated = True

    node_ids = set(nodes)
    link_set: set[tuple[str, str, str]] = set()

    def add(source: str, target: str, kind: str) -> None:
        link_set.add(_norm(source, target, kind))

    # has_action: objective -> action
    for nid, n in nodes.items():
        if n["type"] == "action":
            add(f"objective:{n['meta']['objective_id']}", nid, "has_action")

    # for_project: objective -> project
    for r in await client.db_execute(
        "SELECT id, project_id FROM objectives "
        "WHERE user_id = ? AND status = 'active' AND project_id IS NOT NULL AND project_id != ''",
        [user_id],
    ):
        add(f"objective:{r['id']}", f"project:{r['project_id']}", "for_project")

    # context_of: goal_context -> top-5 active objectives by priority;
    #             project_context -> every active project
    top5_objectives = [
        nid
        for nid, _ in sorted(
            ((nid, n) for nid, n in nodes.items() if n["type"] == "objective"),
            key=lambda x: x[1]["meta"]["priority"],
        )
    ][:5]
    active_projects = [
        nid
        for nid, n in nodes.items()
        if n["type"] == "project" and n["meta"]["status"] == "active"
    ]
    for nid, n in nodes.items():
        if n["type"] != "context":
            continue
        if n["meta"]["category"] == "goal_context":
            for oid in top5_objectives:
                add(nid, oid, "context_of")
        elif n["meta"]["category"] == "project_context":
            for pid in active_projects:
                add(nid, pid, "context_of")

    # touched: conversation -> entity, from tool_invocations
    by_conv: dict[str, list[dict]] = {}
    for r in await client.db_execute(
        "SELECT conversation_id, tool_name, result_json, is_error FROM tool_invocations "
        "WHERE user_id = ?",
        [user_id],
    ):
        by_conv.setdefault(r["conversation_id"], []).append(
            {
                "tool_name": r["tool_name"],
                "result": r["result_json"],
                "is_error": bool(r["is_error"]),
            }
        )
    for conv_id, calls in by_conv.items():
        source = f"conversation:{conv_id}"
        for entity_type, entity_id in tool_log.touches_from(calls):
            add(source, f"{entity_type}:{entity_id}", "touched")

    # mentions: journal -> linked objective / project
    for r in await client.db_execute(
        "SELECT id, linked_objective_id, linked_project_id FROM journal_entries "
        "WHERE user_id = ? AND TRIM(body) != '' "
        "AND (linked_objective_id IS NOT NULL OR linked_project_id IS NOT NULL)",
        [user_id],
    ):
        src = f"journal:{r['id']}"
        if r["linked_objective_id"]:
            add(src, f"objective:{r['linked_objective_id']}", "mentions")
        if r["linked_project_id"]:
            add(src, f"project:{r['linked_project_id']}", "mentions")

    # explicit: entity_links rows
    for r in await client.db_execute(
        "SELECT from_type, from_id, to_type, to_id, kind FROM entity_links WHERE user_id = ?",
        [user_id],
    ):
        add(f"{r['from_type']}:{r['from_id']}", f"{r['to_type']}:{r['to_id']}", r["kind"])

    links = [
        {"source": s, "target": t, "kind": k}
        for (s, t, k) in sorted(link_set)
        if s in node_ids and t in node_ids
    ]
    return {"nodes": list(nodes.values()), "links": links, "truncated": truncated}
