"""Quick script to check the articles table schema."""

import asyncio
from app.db.session import engine
from sqlalchemy import text


async def main():
    async with engine.connect() as conn:
        # 1. Get columns
        r = await conn.execute(
            text(
                "SELECT column_name, data_type, character_maximum_length "
                "FROM information_schema.columns "
                "WHERE table_name = 'articles' ORDER BY ordinal_position"
            )
        )
        print("=== ARTICLES TABLE COLUMNS ===")
        for row in r.fetchall():
            print(f"  {row[0]:30s} {row[1]:20s} max_len={row[2]}")

        # 2. Get sample rows
        r2 = await conn.execute(
            text("SELECT id, artikelnummer, artikelbenamning FROM articles LIMIT 10")
        )
        print("\n=== SAMPLE DATA ===")
        for row in r2.fetchall():
            print(f"  id={row[0]}  artikelnummer={row[1]}  artikelbenamning={row[2]}")

        # 3. Count
        r3 = await conn.execute(text("SELECT COUNT(*) FROM articles"))
        print(f"\nTotal articles: {r3.scalar()}")


asyncio.run(main())
