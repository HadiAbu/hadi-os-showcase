"""J0 task 0.2 — journal_store CRUD + ownership checks."""

from __future__ import annotations

import pytest

from app.services import journal_store, objectives_store, projects_store, style, users

LONG = "x " * 150  # 300 chars, over the 200-char style-sample threshold


@pytest.fixture
async def other_id() -> str:
    user = await users.create_user("other@example.com", "x")
    return user["id"]


async def _labelled(user_id: str, label: str) -> dict | None:
    return next(
        (s for s in await style.list_samples(user_id) if s["label"] == label), None
    )


async def test_create_and_get_round_trip(owner_id):
    entry = await journal_store.create_entry(
        owner_id,
        {"title": "Day one", "body": "Shipped J0.", "mood": "good", "tags": ["work", "hadi-os"]},
    )
    assert entry["title"] == "Day one"
    assert entry["tags"] == ["work", "hadi-os"]
    assert entry["mood"] == "good"
    assert entry["learn_from_style"] is True

    got = await journal_store.get_entry(owner_id, entry["id"])
    assert got == entry


async def test_list_is_newest_first_and_filterable(owner_id):
    proj = await projects_store.create_project(owner_id, {"name": "P"})
    obj = await objectives_store.create_objective(owner_id, {"title": "O", "horizon": "year"})

    a = await journal_store.create_entry(owner_id, {"body": "first"})
    b = await journal_store.create_entry(
        owner_id, {"body": "second", "linked_project_id": proj["id"]}
    )
    c = await journal_store.create_entry(
        owner_id, {"body": "third", "linked_objective_id": obj["id"]}
    )

    ids = [e["id"] for e in await journal_store.list_entries(owner_id)]
    assert ids == [c["id"], b["id"], a["id"]]

    by_proj = await journal_store.list_entries(owner_id, project_id=proj["id"])
    assert [e["id"] for e in by_proj] == [b["id"]]
    by_obj = await journal_store.list_entries(owner_id, objective_id=obj["id"])
    assert [e["id"] for e in by_obj] == [c["id"]]


async def test_patch_updates_fields_and_can_clear_a_link(owner_id):
    proj = await projects_store.create_project(owner_id, {"name": "P"})
    entry = await journal_store.create_entry(
        owner_id, {"body": "draft", "linked_project_id": proj["id"]}
    )

    patched = await journal_store.patch_entry(
        owner_id, entry["id"], {"body": "final", "mood": "flat", "tags": ["done"]}
    )
    assert patched["body"] == "final"
    assert patched["mood"] == "flat"
    assert patched["tags"] == ["done"]
    assert patched["linked_project_id"] == proj["id"]
    assert patched["updated_at"] >= entry["updated_at"]

    cleared = await journal_store.patch_entry(owner_id, entry["id"], {"linked_project_id": ""})
    assert cleared["linked_project_id"] is None


async def test_delete(owner_id):
    entry = await journal_store.create_entry(owner_id, {"body": "temp"})
    assert await journal_store.delete_entry(owner_id, entry["id"]) is True
    assert await journal_store.get_entry(owner_id, entry["id"]) is None
    assert await journal_store.delete_entry(owner_id, entry["id"]) is False


async def test_foreign_objective_link_is_rejected(owner_id, other_id):
    foreign = await objectives_store.create_objective(
        other_id, {"title": "theirs", "horizon": "year"}
    )
    with pytest.raises(journal_store.LinkNotOwned):
        await journal_store.create_entry(
            owner_id, {"body": "x", "linked_objective_id": foreign["id"]}
        )


async def test_foreign_project_link_is_rejected_on_patch(owner_id, other_id):
    foreign = await projects_store.create_project(other_id, {"name": "theirs"})
    entry = await journal_store.create_entry(owner_id, {"body": "x"})
    with pytest.raises(journal_store.LinkNotOwned):
        await journal_store.patch_entry(
            owner_id, entry["id"], {"linked_project_id": foreign["id"]}
        )


async def test_long_entry_is_mirrored_into_style_samples(owner_id):
    entry = await journal_store.create_entry(owner_id, {"body": LONG})
    label = f"journal:{entry['id']}"
    sample = await _labelled(owner_id, label)
    assert sample is not None and sample["text"] == LONG

    # editing the body updates the same sample, not a second one
    await journal_store.patch_entry(owner_id, entry["id"], {"body": LONG + " more"})
    samples = [s for s in await style.list_samples(owner_id) if s["label"] == label]
    assert len(samples) == 1 and samples[0]["text"] == LONG + " more"


async def test_short_entry_has_no_sample(owner_id):
    entry = await journal_store.create_entry(owner_id, {"body": "quick note"})
    assert await _labelled(owner_id, f"journal:{entry['id']}") is None


async def test_sample_removed_when_shortened_or_opted_out_or_deleted(owner_id):
    entry = await journal_store.create_entry(owner_id, {"body": LONG})
    label = f"journal:{entry['id']}"
    assert await _labelled(owner_id, label) is not None

    await journal_store.patch_entry(owner_id, entry["id"], {"body": "tiny"})
    assert await _labelled(owner_id, label) is None

    await journal_store.patch_entry(owner_id, entry["id"], {"body": LONG})
    assert await _labelled(owner_id, label) is not None
    await journal_store.patch_entry(owner_id, entry["id"], {"learn_from_style": False})
    assert await _labelled(owner_id, label) is None

    await journal_store.patch_entry(owner_id, entry["id"], {"learn_from_style": True})
    assert await _labelled(owner_id, label) is not None
    await journal_store.delete_entry(owner_id, entry["id"])
    assert await _labelled(owner_id, label) is None


async def test_entries_are_user_scoped(owner_id, other_id):
    mine = await journal_store.create_entry(owner_id, {"body": "mine"})
    assert await journal_store.get_entry(other_id, mine["id"]) is None
    assert await journal_store.list_entries(other_id) == []
    assert await journal_store.patch_entry(other_id, mine["id"], {"body": "hijack"}) is None
    assert await journal_store.delete_entry(other_id, mine["id"]) is False
