#!/usr/bin/env python3
"""Fetch user + character + relation from MariaDB and print JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from rag_luciana.db import repo
from rag_luciana.db.session import async_session_factory, engine


async def fetch(*, user_id: str, agent_id: str) -> dict[str, Any]:
    async with async_session_factory() as db:
        user = await repo.get_user(db, user_id)
        character = await repo.get_character(db, agent_id)
        relation = await repo.get_user_agent_relation(
            db,
            user_id=user_id,
            character_id=agent_id,
        )

        return {
            "user": (
                {
                    "user_id": user.user_id,
                    "display_name": user.display_name,
                    "status": user.status,
                    "meta_json": user.meta_json,
                }
                if user
                else None
            ),
            "agent": (
                {
                    "agent_id": character.character_id,
                    "name": character.name,
                    "description": character.description,
                    "status": character.status,
                    "meta_json": character.meta_json,
                }
                if character
                else None
            ),
            "relation": (
                {
                    "user_id": relation.user_id,
                    "agent_id": relation.character_id,
                    "version": relation.version,
                    "relation_state": relation.relation_state_json,
                    "interaction_stats": relation.interaction_stats_json,
                    "flags": relation.flags_json,
                    "meta": relation.meta_json,
                    "created_at": relation.created_at.isoformat() if relation.created_at else None,
                    "updated_at": relation.updated_at.isoformat() if relation.updated_at else None,
                }
                if relation
                else None
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch user-agent relation from MariaDB")
    parser.add_argument("--user-id", default="herve")
    parser.add_argument("--agent-id", default="aria")
    args = parser.parse_args()

    async def _run() -> None:
        try:
            result = await fetch(user_id=args.user_id, agent_id=args.agent_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        finally:
            await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()

