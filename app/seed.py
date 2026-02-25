"""Seed database with initial data: cities, locations, consoles."""

import asyncio
import logging
import sys

from sqlalchemy import select

from app.database import engine, async_session
from app.models import Base
from app.models.city import City
from app.models.location import Location
from app.models.console import Console

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

SEED_DATA = [
    {
        "city": {"name": "Москва", "slug": "msk"},
        "locations": [
            {
                "address": "ул. Ленина, 10",
                "entrance": "1",
                "description": "1 этаж, налево",
                "consoles": [
                    {"name": "PS5 #1", "code": "ps_001", "shelly_ip": "192.168.1.101"},
                    {"name": "PS5 #2", "code": "ps_002", "shelly_ip": "192.168.1.102"},
                ],
            },
            {
                "address": "ул. Пушкина, 25",
                "entrance": "2",
                "description": "2 этаж, направо",
                "consoles": [
                    {"name": "PS5 #3", "code": "ps_003", "shelly_ip": "192.168.1.103"},
                ],
            },
        ],
    },
    {
        "city": {"name": "Санкт-Петербург", "slug": "spb"},
        "locations": [
            {
                "address": "Невский пр., 50",
                "entrance": "1",
                "description": "Цокольный этаж",
                "consoles": [
                    {"name": "PS5 #4", "code": "ps_004", "shelly_ip": "192.168.2.101"},
                    {"name": "PS5 #5", "code": "ps_005", "shelly_ip": "192.168.2.102"},
                ],
            },
        ],
    },
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        for entry in SEED_DATA:
            city_data = entry["city"]

            existing = await db.execute(
                select(City).where(City.slug == city_data["slug"])
            )
            if existing.scalars().first():
                logger.info("City '%s' already exists, skipping", city_data["name"])
                continue

            city = City(**city_data)
            db.add(city)
            await db.flush()
            logger.info("Created city: %s", city.name)

            for loc_data in entry["locations"]:
                consoles_data = loc_data.pop("consoles")
                location = Location(city_id=city.id, **loc_data)
                db.add(location)
                await db.flush()
                logger.info("  Created location: %s", location.address)

                for con_data in consoles_data:
                    console = Console(location_id=location.id, **con_data)
                    db.add(console)
                    logger.info("    Created console: %s (%s)", con_data["name"], con_data["code"])

        await db.commit()

    logger.info("Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
