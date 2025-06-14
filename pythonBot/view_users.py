import asyncio
import aiosqlite

DB_PATH = "users.db"

async def show_users():
    async with aiosqlite.connect(DB_PATH) as db:
        query = """
        SELECT id, telegram_id, full_name, language, name, phone, region, rating
        FROM users
        ORDER BY id DESC;
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()

            if not rows:
                print("❌ No users found.")
                return

            for row in rows:
                print("🧾 ID:", row[0])
                print("👤 Telegram ID:", row[1])
                print("👥 Full Name:", row[2])
                print("🌐 Language:", row[3])
                print("📛 Name:", row[4])
                print("📞 Phone:", row[5])
                print("📍 Region:", row[6])
                print("⭐️ Rating:", row[7] or "—")
                print("-" * 50)

asyncio.run(show_users())
