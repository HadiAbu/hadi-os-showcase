"""M4 task 4.2 — ``graph.build_graph`` node/edge assembly."""

from __future__ import annotations

import json

from app.services import (
    chat_store,
    context_store,
    graph,
    graph_links,
    journal_store,
    llm_client,
    objectives_store,
    projects_store,
    tool_log,
)


async def _conversation_with_message(user_id: str) -> str:
    conv = await chat_store.create_conversation(user_id)
    await chat_store.append_message(
        conv["id"], user_id, "user", "hi", {"role": "user", "content": "hi"}
    )
    return conv["id"]


def _ids(result: dict) -> set[str]:
    return {n["id"] for n in result["nodes"]}


def _edges(result: dict) -> set[tuple[str, str, str]]:
    return {(link_["source"], link_["target"], link_["kind"]) for link_ in result["links"]}


async def test_node_type_membership_and_filters(owner_id):
    active_obj = await objectives_store.create_objective(
        owner_id, {"title": "Active", "horizon": "quarter"}
    )
    dropped_obj = await objectives_store.create_objective(
        owner_id, {"title": "Dropped", "horizon": "quarter"}
    )
    await objectives_store.patch_objective(owner_id, dropped_obj["id"], {"status": "dropped"})

    paused_proj = await projects_store.create_project(
        owner_id, {"name": "Paused", "status": "paused"}
    )
    shipped_proj = await projects_store.create_project(
        owner_id, {"name": "Shipped", "status": "shipped"}
    )

    live_ctx = await context_store.create_entry(owner_id, "identity", "role", "eng", status="active")
    dead_ctx = await context_store.create_entry(owner_id, "misc", "old", "x", status="active")
    await context_store.set_status(owner_id, dead_ctx["id"], "archived")

    todo_action = await objectives_store.create_action(owner_id, active_obj["id"], "do it")
    done_action = await objectives_store.create_action(owner_id, active_obj["id"], "done it")
    await objectives_store.patch_action(owner_id, done_action["id"], {"status": "done"})

    conv_id = await _conversation_with_message(owner_id)
    empty_conv = await chat_store.create_conversation(owner_id)

    ids = _ids(await graph.build_graph(owner_id))
    assert f"objective:{active_obj['id']}" in ids
    assert f"objective:{dropped_obj['id']}" not in ids
    assert f"project:{paused_proj['id']}" in ids
    assert f"project:{shipped_proj['id']}" not in ids
    assert f"context:{live_ctx['id']}" in ids
    assert f"context:{dead_ctx['id']}" not in ids
    assert f"action:{todo_action['id']}" in ids
    assert f"action:{done_action['id']}" not in ids
    assert f"conversation:{conv_id}" in ids
    assert f"conversation:{empty_conv['id']}" not in ids


async def test_has_action_and_for_project_edges(owner_id):
    proj = await projects_store.create_project(owner_id, {"name": "P"})
    obj = await objectives_store.create_objective(
        owner_id, {"title": "O", "horizon": "quarter", "project_id": proj["id"]}
    )
    action = await objectives_store.create_action(owner_id, obj["id"], "step")

    edges = _edges(await graph.build_graph(owner_id))
    assert (f"objective:{obj['id']}", f"action:{action['id']}", "has_action") in edges
    assert (f"objective:{obj['id']}", f"project:{proj['id']}", "for_project") in edges


async def test_context_of_top5_objectives_and_all_active_projects(owner_id):
    objs = []
    for i in range(6):
        objs.append(
            await objectives_store.create_objective(
                owner_id, {"title": f"O{i}", "horizon": "quarter", "priority": 1 + (i % 3)}
            )
        )
    goal_ctx = await context_store.create_entry(
        owner_id, "goal_context", "north_star", "grow", status="active"
    )
    proj_ctx = await context_store.create_entry(
        owner_id, "project_context", "stack", "fastapi", status="active"
    )
    p1 = await projects_store.create_project(owner_id, {"name": "P1", "status": "active"})
    p2 = await projects_store.create_project(owner_id, {"name": "P2", "status": "active"})

    edges = _edges(await graph.build_graph(owner_id))
    goal_edges = [e for e in edges if e[0] == f"context:{goal_ctx['id']}"]
    assert len(goal_edges) == 5
    assert all(k == "context_of" and t.startswith("objective:") for _, t, k in goal_edges)

    proj_edges = {e for e in edges if e[0] == f"context:{proj_ctx['id']}"}
    assert proj_edges == {
        (f"context:{proj_ctx['id']}", f"project:{p1['id']}", "context_of"),
        (f"context:{proj_ctx['id']}", f"project:{p2['id']}", "context_of"),
    }


async def test_touched_edge_from_tool_invocations(owner_id):
    obj = await objectives_store.create_objective(
        owner_id, {"title": "Made in chat", "horizon": "quarter"}
    )
    conv_id = await _conversation_with_message(owner_id)
    await tool_log.record_invocations(
        conv_id,
        owner_id,
        "msg-1",
        [
            {
                "tool_name": "create_objective",
                "args": {"title": "Made in chat", "horizon": "quarter"},
                "result": json.dumps({"id": obj["id"], "status": "active"}),
                "is_error": False,
            }
        ],
    )
    edges = _edges(await graph.build_graph(owner_id))
    assert (f"conversation:{conv_id}", f"objective:{obj['id']}", "touched") in edges


async def test_explicit_entity_link_edge(owner_id):
    obj = await objectives_store.create_objective(owner_id, {"title": "O", "horizon": "year"})
    proj = await projects_store.create_project(owner_id, {"name": "P"})
    await graph_links.create_link(
        owner_id,
        {
            "from_type": "objective",
            "from_id": obj["id"],
            "to_type": "project",
            "to_id": proj["id"],
            "kind": "related",
        },
    )
    edges = _edges(await graph.build_graph(owner_id))
    # "related" is symmetric -> endpoints order-normalised (sorted)
    src, tgt = sorted([f"objective:{obj['id']}", f"project:{proj['id']}"])
    assert (src, tgt, "related") in edges


async def test_dangling_links_are_dropped(owner_id):
    # a tool_invocation that touched an objective which is now dropped (not a node)
    obj = await objectives_store.create_objective(owner_id, {"title": "gone", "horizon": "year"})
    await objectives_store.patch_objective(owner_id, obj["id"], {"status": "dropped"})
    conv_id = await _conversation_with_message(owner_id)
    await tool_log.record_invocations(
        conv_id,
        owner_id,
        "m",
        [
            {
                "tool_name": "update_objective",
                "args": {},
                "result": json.dumps({"id": obj["id"], "status": "dropped"}),
                "is_error": False,
            }
        ],
    )
    result = await graph.build_graph(owner_id)
    node_ids = _ids(result)
    for link_ in result["links"]:
        assert link_["source"] in node_ids and link_["target"] in node_ids


async def test_cap_truncates_and_leaves_no_dangling_links(owner_id):
    await objectives_store.create_objective(owner_id, {"title": "keeper", "horizon": "year"})
    entries = []
    for i in range(graph.NODE_CAP + 20):
        entries.append(
            await context_store.create_entry(
                owner_id, "misc", f"k{i}", "v", status="active"
            )
        )
    # an explicit link between two context entries — at least one will be capped out
    await graph_links.create_link(
        owner_id,
        {
            "from_type": "context",
            "from_id": entries[0]["id"],
            "to_type": "context",
            "to_id": entries[-1]["id"],
            "kind": "related",
        },
    )
    result = await graph.build_graph(owner_id)
    assert result["truncated"] is True
    assert len(result["nodes"]) == graph.NODE_CAP
    node_ids = _ids(result)
    for link_ in result["links"]:
        assert link_["source"] in node_ids and link_["target"] in node_ids


async def test_journal_nodes_and_mentions_edges(owner_id):
    obj = await objectives_store.create_objective(
        owner_id, {"title": "Ship 2.5", "horizon": "quarter"}
    )
    proj = await projects_store.create_project(owner_id, {"name": "hadi-os"})
    written = await journal_store.create_entry(
        owner_id,
        {"body": "Notes on shipping the journal.", "linked_objective_id": obj["id"],
         "linked_project_id": proj["id"]},
    )
    blank = await journal_store.create_entry(owner_id, {"title": "empty", "body": "   "})

    result = await graph.build_graph(owner_id)
    ids, edges = _ids(result), _edges(result)
    assert f"journal:{written['id']}" in ids
    assert f"journal:{blank['id']}" not in ids  # no body -> no node
    assert (f"journal:{written['id']}", f"objective:{obj['id']}", "mentions") in edges
    assert (f"journal:{written['id']}", f"project:{proj['id']}", "mentions") in edges


async def test_journal_mention_to_dropped_objective_is_not_dangling(owner_id):
    obj = await objectives_store.create_objective(
        owner_id, {"title": "gone", "horizon": "year"}
    )
    await objectives_store.patch_objective(owner_id, obj["id"], {"status": "dropped"})
    entry = await journal_store.create_entry(
        owner_id, {"body": "about a dropped objective", "linked_objective_id": obj["id"]}
    )

    result = await graph.build_graph(owner_id)
    node_ids = _ids(result)
    assert f"journal:{entry['id']}" in node_ids
    for link_ in result["links"]:
        assert link_["source"] in node_ids and link_["target"] in node_ids


async def test_build_graph_makes_no_llm_call(owner_id, monkeypatch):
    async def _boom(*_a, **_k):
        raise AssertionError("build_graph must not call the LLM")

    monkeypatch.setattr(llm_client, "create_chat", _boom, raising=False)
    await objectives_store.create_objective(owner_id, {"title": "O", "horizon": "year"})
    assert (await graph.build_graph(owner_id))["nodes"]
