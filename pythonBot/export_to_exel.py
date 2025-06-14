import asyncio
import asyncpg
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()
PG_URL = os.getenv("PG_URL")

EXCEL_FILE = "exported_data.xlsx"

# Получить список всех таблиц в PostgreSQL
async def get_table_names(conn):
    rows = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    """)
    return [row['table_name'] for row in rows]

# Экспорт всех таблиц в Excel
async def export_all_tables():
    try:
        conn = await asyncpg.connect(PG_URL)
        table_names = await get_table_names(conn)

        if not table_names:
            print("❌ No tables found in the PostgreSQL database.")
            await conn.close()
            return

        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            for table in table_names:
                rows = await conn.fetch(f'SELECT * FROM "{table}"')
                if not rows:
                    continue

                # Получение названий колонок
                col_names = rows[0].keys()
                data = [tuple(row.values()) for row in rows]

                df = pd.DataFrame(data, columns=col_names)

                # Удаляем колонку telegram_id если она есть
                if "telegram_id" in df.columns:
                    df.drop(columns=["telegram_id"], inplace=True)

                df.to_excel(writer, sheet_name=table, index=False)

        await conn.close()
        print(f"✅ Exported {len(table_names)} tables to {EXCEL_FILE}")

    except Exception as e:
        print(f"❌ Error exporting tables: {e}")

if __name__ == "__main__":
    asyncio.run(export_all_tables())
