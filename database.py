from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Iterable, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DB_PATH = DATA_DIR / "bot.db"

class DatabaseManager:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._create_tables()

    def _create_tables(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS command_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    command_name TEXT NOT NULL,
                    guild_id INTEGER,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS guild_members (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    first_joined_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    join_count INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (guild_id, user_id)
                );
                """
            )
            self._conn.commit()

    def log_command(self, user_id: int, command_name: str, guild_id: Optional[int]) -> None:
        timestamp = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO command_log (user_id, command_name, guild_id, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, command_name, guild_id, timestamp),
            )
            self._conn.commit()

    def record_member_join(self, guild_id: int, user_id: int, joined_at: Optional[datetime]) -> bool:
        timestamp = (joined_at or datetime.utcnow()).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "SELECT join_count FROM guild_members WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = cur.fetchone()
            is_new = row is None

            if is_new:
                self._conn.execute(
                    """
                    INSERT INTO guild_members (guild_id, user_id, first_joined_at, last_seen_at, join_count, is_active)
                    VALUES (?, ?, ?, ?, 1, 1)
                    """,
                    (guild_id, user_id, timestamp, timestamp),
                )
            else:
                self._conn.execute(
                    """
                    UPDATE guild_members
                    SET last_seen_at = ?, join_count = join_count + 1, is_active = 1
                    WHERE guild_id = ? AND user_id = ?
                    """,
                    (timestamp, guild_id, user_id),
                )

            self._conn.commit()
            return is_new

    def record_member_leave(self, guild_id: int, user_id: int) -> None:
        timestamp = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                """
                UPDATE guild_members
                SET last_seen_at = ?, is_active = 0
                WHERE guild_id = ? AND user_id = ?
                """,
                (timestamp, guild_id, user_id),
            )
            self._conn.commit()

    def get_total_members_all_time(self, guild_id: int) -> int:
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) AS total FROM guild_members WHERE guild_id = ?",
                (guild_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_total_commands(self, guild_id: Optional[int] = None) -> int:
        query = "SELECT COUNT(*) AS total FROM command_log"
        params: tuple[()] | tuple[int] = ()
        if guild_id is not None:
            query += " WHERE guild_id = ?"
            params = (guild_id,)
        with self._lock:
            cur = self._conn.execute(query, params)
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_unique_command_users(self, guild_id: Optional[int] = None) -> int:
        query = "SELECT COUNT(DISTINCT user_id) FROM command_log"
        params: tuple[()] | tuple[int] = ()
        if guild_id is not None:
            query += " WHERE guild_id = ?"
            params = (guild_id,)
        with self._lock:
            cur = self._conn.execute(query, params)
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_last_commands_for_user(
        self,
        user_id: int,
        limit: int = 5,
        guild_id: Optional[int] = None,
    ) -> list[tuple[str, str]]:
        query = "SELECT command_name, timestamp FROM command_log WHERE user_id = ?"
        params: list[object] = [user_id]
        if guild_id is not None:
            query += " AND guild_id = ?"
            params.append(guild_id)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            cur = self._conn.execute(query, params)
            return [(row["command_name"], row["timestamp"]) for row in cur.fetchall()]

    def get_active_member_count(self, guild_id: int) -> int:
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM guild_members WHERE guild_id = ? AND is_active = 1",
                (guild_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get_new_member_count(self, guild_id: int, days: int = 30) -> int:
        threshold = datetime.utcnow() - timedelta(days=days)
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM guild_members WHERE guild_id = ? AND first_joined_at >= ?",
                (guild_id, threshold.isoformat()),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def sync_guild_members(self, guild_id: int, member_payload: Iterable[tuple[int, Optional[datetime]]]) -> None:
        payload = list(member_payload)
        with self._lock:
            self._conn.execute(
                "UPDATE guild_members SET is_active = 0 WHERE guild_id = ?",
                (guild_id,),
            )

            for user_id, joined_at in payload:
                ts = (joined_at or datetime.utcnow()).isoformat()
                cur = self._conn.execute(
                    "SELECT 1 FROM guild_members WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id),
                )
                if cur.fetchone() is None:
                    self._conn.execute(
                        """
                        INSERT INTO guild_members (guild_id, user_id, first_joined_at, last_seen_at, join_count, is_active)
                        VALUES (?, ?, ?, ?, 0, 1)
                        """,
                        (guild_id, user_id, ts, ts),
                    )
                else:
                    self._conn.execute(
                        """
                        UPDATE guild_members
                        SET last_seen_at = ?, is_active = 1
                        WHERE guild_id = ? AND user_id = ?
                        """,
                        (ts, guild_id, user_id),
                    )

            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()