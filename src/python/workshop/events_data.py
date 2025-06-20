import json
import logging
from typing import Optional

import aiosqlite
import pandas as pd

from terminal_colors import TerminalColors as tc
from utilities import Utilities

DATA_BASE = "database/tutorials.db"

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class EventsData:
    conn: Optional[aiosqlite.Connection]

    def __init__(self: "EventsData", utilities: Utilities) -> None:
        self.conn = None
        self.utilities = utilities

    async def connect(self: "EventsData") -> None:
        db_uri = f"file:{self.utilities.shared_files_path}/{DATA_BASE}?mode=ro"

        try:
            self.conn = await aiosqlite.connect(db_uri, uri=True)
            logger.debug("Database connection opened.")
        except aiosqlite.Error as e:
            logger.exception("An error occurred", exc_info=e)
            self.conn = None

    async def close(self: "EventsData") -> None:
        if self.conn:
            await self.conn.close()
            logger.debug("Database connection closed.")

    async def _get_table_names(self: "EventsData") -> list:
        """Return a list of table names."""
        async with self.conn.execute("SELECT name FROM sqlite_master WHERE type='table';") as tables:
            return [table[0] async for table in tables if table[0] != "sqlite_sequence"]

    async def _get_column_info(self: "EventsData", table_name: str) -> list:
        """Return a list of column names and types."""
        async with self.conn.execute(f"PRAGMA table_info('{table_name}');") as columns:
            return [f"{col[1]}: {col[2]}" async for col in columns]

    async def get_database_info(self: "EventsData") -> str:
        """Build and return the database schema description for grounding."""
        table_dicts = []
        for table_name in await self._get_table_names():
            columns = await self._get_column_info(table_name)
            table_dicts.append({
                "table_name": table_name,
                "column_names": columns
            })

        schema_string = "\n".join([
            f"Table {table['table_name']} Columns: {', '.join(table['column_names'])}"
            for table in table_dicts
        ])
        return schema_string

    async def async_fetch_tutorial_data_using_sqlite_query(self: "EventsData", sqlite_query: str) -> str:
        """Execute a user-provided SQLite query and return results as JSON."""
        print(f"\n{tc.BLUE}Function Call: async_fetch_tutorial_data_using_sqlite_query{tc.RESET}\n")
        print(f"{tc.BLUE}Executing query: {sqlite_query}{tc.RESET}\n")

        try:
            async with self.conn.execute(sqlite_query) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]

            if not rows:
                return json.dumps("The query returned no results.")
            
            df = pd.DataFrame(rows, columns=columns)
            return df.to_json(orient="split", index=False)

        except Exception as e:
            return json.dumps({
                "error": str(e),
                "query": sqlite_query
            })
