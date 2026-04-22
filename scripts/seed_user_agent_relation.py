#!/usr/bin/env python3
"""Seed MariaDB with user + character + initial user-agent relation.

Reads:
- BACKEND_LUCIANA/data/users/{user_id}/profile.json
- BACKEND_LUCIANA/data/ai_profiles/{agent_id}/profile.json

Writes directly to chatfriends_retrieval_service DB tables via repository functions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chatfriends_retrieval.db import repo
from chatfriends_retrieval.db.session import async_session_factory, engine


def _default_paths(user_id: str, agent_id: str) -> tuple[Path, Path]:
    workspace_root = Path(__file__).resolve().parents[2]
    user_profile = (
        workspace_root / "BACKEND_LUCIANA" / "data" / "users" / user_id / "profile.json"
    )
    agent_profile = (
        workspace_root
        / "BACKEND_LUCIANA"
        / "data"
        / "ai_profiles"
        / agent_id
        / "profile.json"
    )
    return user_profile, agent_profile


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON object in {path}")
    return data


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_user_payload(data: dict[str, Any], fallback_user_id: str) -> tuple[str, str, dict[str, Any]]:
    user_id = str(data.get("user_id") or fallback_user_id)
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    display_name = str(identity.get("display_name") or data.get("name") or user_id)
    return user_id, display_name, data


def _extract_character_payload(
    data: dict[str, Any], fallback_agent_id: str
) -> tuple[str, str, str | None, dict[str, Any]]:
    character_id = str(data.get("avatar_id") or data.get("character_id") or fallback_agent_id)
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    name = str(identity.get("name") or data.get("name") or character_id)
    description = identity.get("bio")
    if description is not None:
        description = str(description)
    return character_id, name, description, data


def _relation_defaults(data: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    defaults = data.get("relation_defaults") if isinstance(data.get("relation_defaults"), dict) else {}
    version = str(defaults.get("version") or "1.0")
    relation_state = defaults.get("relation_state") if isinstance(defaults.get("relation_state"), dict) else {}
    interaction_stats = (
        defaults.get("interaction_stats") if isinstance(defaults.get("interaction_stats"), dict) else {}
    )
    flags = defaults.get("flags") if isinstance(defaults.get("flags"), dict) else {}

    relation_state = {
        "familiarity": float(relation_state.get("familiarity", 0.10)),
        "trust": float(relation_state.get("trust", 0.10)),
        "attachment": float(relation_state.get("attachment", 0.05)),
        "tension": float(relation_state.get("tension", 0.00)),
    }
    interaction_stats = {
        "total_messages": int(interaction_stats.get("total_messages", 0)),
        "last_interaction": interaction_stats.get("last_interaction"),
    }
    flags = {
        "favorite": bool(flags.get("favorite", False)),
        "blocked": bool(flags.get("blocked", False)),
    }
    now_iso = _iso_now()
    meta = {
        "created_at": now_iso,
        "last_updated": now_iso,
    }
    return version, relation_state, interaction_stats, flags, meta


async def seed(
    *,
    user_profile_path: Path,
    agent_profile_path: Path,
    fallback_user_id: str,
    fallback_agent_id: str,
) -> dict[str, Any]:
    if not user_profile_path.exists():
        raise FileNotFoundError(f"User profile not found: {user_profile_path}")
    if not agent_profile_path.exists():
        raise FileNotFoundError(f"Agent profile not found: {agent_profile_path}")

    user_json = _read_json(user_profile_path)
    agent_json = _read_json(agent_profile_path)

    user_id, display_name, user_meta = _extract_user_payload(user_json, fallback_user_id)
    character_id, character_name, description, character_meta = _extract_character_payload(
        agent_json, fallback_agent_id
    )
    version, relation_state, interaction_stats, flags, relation_meta = _relation_defaults(agent_json)

    async with async_session_factory() as db:
        # User
        existing_user = await repo.get_user(db, user_id)
        if existing_user is None:
            await repo.create_user(
                db,
                user_id=user_id,
                display_name=display_name,
                meta_json=user_meta,
            )
        else:
            await repo.update_user(
                db,
                user_id,
                display_name=display_name,
                meta_json=user_meta,
            )

        # Character
        existing_character = await repo.get_character(db, character_id)
        if existing_character is None:
            await repo.create_character(
                db,
                character_id=character_id,
                name=character_name,
                description=description,
                meta_json=character_meta,
            )
        else:
            await repo.update_character(
                db,
                character_id,
                name=character_name,
                description=description,
                meta_json=character_meta,
            )

        # Relation
        relation = await repo.upsert_user_agent_relation(
            db,
            user_id=user_id,
            character_id=character_id,
            version=version,
            relation_state_json=relation_state,
            interaction_stats_json=interaction_stats,
            flags_json=flags,
            meta_json=relation_meta,
        )

        await db.commit()

        return {
            "user_id": user_id,
            "agent_id": character_id,
            "user_created": existing_user is None,
            "agent_created": existing_character is None,
            "relation_version": relation.version,
            "relation_state": relation.relation_state_json,
            "interaction_stats": relation.interaction_stats_json,
            "flags": relation.flags_json,
            "meta": relation.meta_json,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed user + agent + relation into MariaDB")
    parser.add_argument("--user-id", default="herve")
    parser.add_argument("--agent-id", default="aria")
    parser.add_argument("--user-profile", help="Path to user profile.json")
    parser.add_argument("--agent-profile", help="Path to ai profile.json")
    args = parser.parse_args()

    default_user_profile, default_agent_profile = _default_paths(args.user_id, args.agent_id)
    user_profile_path = Path(args.user_profile) if args.user_profile else default_user_profile
    agent_profile_path = Path(args.agent_profile) if args.agent_profile else default_agent_profile

    async def _run() -> None:
        try:
            result = await seed(
                user_profile_path=user_profile_path,
                agent_profile_path=agent_profile_path,
                fallback_user_id=args.user_id,
                fallback_agent_id=args.agent_id,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        finally:
            await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()


