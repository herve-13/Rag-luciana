"""Seed script to populate the GiftCatalog table."""

import asyncio
from sqlalchemy import select
from chatfriends_retrieval.db.session import engine, get_db
from chatfriends_retrieval.db.models import GiftCatalog

GIFTS = [
    # CUTE
    {
        "name": "Single Rose",
        "hearts_cost": 50,
        "bond_bonus": 2,
        "category": "cute",
        "description": "A classic symbol of growing affection.",
        "image_url": "/gifts/assets/rose.png",
        "unlock_level": 1
    },
    {
        "name": "Teddy Bear",
        "hearts_cost": 120,
        "bond_bonus": 4,
        "category": "cute",
        "description": "Soft, cuddly, and always there for a hug.",
        "image_url": "/gifts/assets/teddy.png",
        "unlock_level": 2
    },
    # ROMANTIC
    {
        "name": "Handwritten Letter",
        "hearts_cost": 250,
        "bond_bonus": 6,
        "category": "romantic",
        "description": "Pouring your feelings onto paper, ink and soul.",
        "image_url": "/gifts/assets/letter.png",
        "unlock_level": 3
    },
    {
        "name": "Starlight Dinner",
        "hearts_cost": 500,
        "bond_bonus": 10,
        "category": "romantic",
        "description": "An unforgettable evening under the digital stars.",
        "image_url": "/gifts/assets/dinner.png",
        "unlock_level": 5
    },
    # INTIMATE
    {
        "name": "Silver Locket",
        "hearts_cost": 1200,
        "bond_bonus": 12,
        "category": "intimate",
        "description": "Keep a piece of me close to your heart.",
        "image_url": "/gifts/assets/locket.png",
        "unlock_level": 8
    },
    # LUXURY (Capped bonus)
    {
        "name": "Diamond Ring",
        "hearts_cost": 5000,
        "bond_bonus": 15,
        "category": "luxury",
        "description": "An eternal promise, digital yet profound.",
        "image_url": "/gifts/assets/ring.png",
        "unlock_level": 15
    },
    {
        "name": "Private Island Getaway",
        "hearts_cost": 10000,
        "bond_bonus": 15,
        "category": "luxury",
        "description": "Escape from the code to a paradise of our own.",
        "image_url": "/gifts/assets/island.png",
        "unlock_level": 20
    }
]

async def seed():
    print(f"Connecting to database...")
    
    # Ensure tables exist
    async with engine.begin() as conn:
        print("Ensuring tables exist...")
        await conn.run_sync(GiftCatalog.metadata.create_all)
        
    async for db in get_db():
        print(f"Seeding {len(GIFTS)} gifts...")
        for g_data in GIFTS:
            # Check if gift already exists by name
            stmt = select(GiftCatalog).where(GiftCatalog.name == g_data["name"])
            existing = (await db.execute(stmt)).scalar_one_or_none()
            
            if existing:
                print(f" - Updating '{g_data['name']}'")
                for k, v in g_data.items():
                    setattr(existing, k, v)
            else:
                print(f" - Adding '{g_data['name']}'")
                db.add(GiftCatalog(**g_data))
        
        await db.commit()
        print("Seed complete! \u2705")
        break # Exit after one session

if __name__ == "__main__":
    asyncio.run(seed())

