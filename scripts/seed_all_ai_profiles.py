#!/usr/bin/env python3
"""Seed all AI profiles from BACKEND_LUCIANA/data/ai_profiles into MariaDB characters table."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from rag_luciana.db import repo
from rag_luciana.db.session import async_session_factory, engine


def _default_profiles_root() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return workspace_root / "BACKEND_LUCIANA" / "data" / "ai_profiles"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid JSON object in {path}")
    return data


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


async def seed_all(*, profiles_root: Path) -> dict[str, Any]:
    if not profiles_root.exists():
        raise FileNotFoundError(f"AI profiles root not found: {profiles_root}")

    profile_paths = sorted(profiles_root.glob("*/profile.json"))
    if not profile_paths:
        raise FileNotFoundError(f"No profile.json found under: {profiles_root}")

    created = 0
    updated = 0
    errors: list[dict[str, str]] = []
    processed: list[dict[str, str]] = []

    async with async_session_factory() as db:
        for profile_path in profile_paths:
            fallback_agent_id = profile_path.parent.name
            try:
                raw = _read_json(profile_path)
                character_id, name, description, meta_json = _extract_character_payload(
                    raw, fallback_agent_id
                )
                existing = await repo.get_character(db, character_id)
                if existing is None:
                    await repo.create_character(
                        db,
                        character_id=character_id,
                        name=name,
                        description=description,
                        meta_json=meta_json,
                    )
                    created += 1
                    action = "created"
                else:
                    await repo.update_character(
                        db,
                        character_id,
                        name=name,
                        description=description,
                        meta_json=meta_json,
                    )
                    updated += 1
                    action = "updated"

                processed.append(
                    {
                        "agent_id": character_id,
                        "name": name,
                        "action": action,
                    }
                )
            except Exception as exc:
                errors.append(
                    {
                        "profile": str(profile_path),
                        "error": str(exc),
                    }
                )

        await db.commit()

    return {
        "profiles_root": str(profiles_root),
        "total_profiles_found": len(profile_paths),
        "created": created,
        "updated": updated,
        "errors_count": len(errors),
        "processed": processed,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed all AI profiles into rag-luciana MariaDB characters table"
    )
    parser.add_argument("--profiles-root", help="Path to BACKEND_LUCIANA/data/ai_profiles")
    args = parser.parse_args()

    profiles_root = Path(args.profiles_root) if args.profiles_root else _default_profiles_root()

    async def _run() -> None:
        try:
            result = await seed_all(profiles_root=profiles_root)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        finally:
            await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()

