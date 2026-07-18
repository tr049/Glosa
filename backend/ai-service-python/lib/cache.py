"""
lib/cache.py — two-tier cache: memory + SQLite
=====================================================================
Why two tiers?
  - MEMORY (dict): instant, but lost on restart.
  - SQLite (disk): survives restarts, and is where the service's learned
    translations can be inspected. Check memory first, then disk, then LLM.

The cache key is deterministic for the same (text, target): hashing the
input with sha256 gives a compact, collision-safe key.
"""
import hashlib

import aiosqlite


def _key(text: str, target: str) -> str:
    return hashlib.sha256(f"{target}::{text}".encode("utf-8")).hexdigest()


class TwoTierCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._mem: dict[str, str] = {}
        self._stats = {"requests": 0, "memory_hits": 0, "db_hits": 0, "misses": 0}

    async def init(self) -> None:
        """Create the translations table if it doesn't exist."""
        # `key TEXT PRIMARY KEY` already builds a unique index on key, so no
        # separate CREATE INDEX is needed. created_at is filled by SQLite
        # (CURRENT_TIMESTAMP) so Python never touches datetime.
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS translations (
                    key          TEXT PRIMARY KEY,
                    source       TEXT,
                    target       TEXT,
                    translated   TEXT,
                    model        TEXT,
                    access_count INTEGER   DEFAULT 1,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            await db.commit()

    async def get(self, text: str, target: str) -> str | None:
        """Return a cached translation or None. Check memory, then SQLite."""
        self._stats["requests"] += 1
        k = _key(text, target)

        # 1) memory tier
        if k in self._mem:
            self._stats["memory_hits"] += 1
            return self._mem[k]

        # 2) SQLite tier
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout = 5000")
            async with db.execute(
                "SELECT translated FROM translations WHERE key = ?", (k,)
            ) as cur:
                row = await cur.fetchone()
            if row is not None:
                await db.execute(
                    "UPDATE translations SET access_count = access_count + 1 WHERE key = ?",
                    (k,),
                )
                await db.commit()
                self._mem[k] = row[0]  # warm memory so future reads skip disk
                self._stats["db_hits"] += 1
                return row[0]

        self._stats["misses"] += 1
        return None

    async def set(self, text: str, target: str, translated: str, model: str) -> None:
        """Store a translation in both tiers."""
        k = _key(text, target)
        self._mem[k] = translated
        # Upsert: on conflict refresh only translated/model — created_at and
        # access_count are preserved (their defaults apply on first insert).
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA busy_timeout = 5000")
            await db.execute(
                """INSERT INTO translations (key, source, target, translated, model)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       translated = excluded.translated,
                       model      = excluded.model""",
                (k, text, target, translated, model),
            )
            await db.commit()

    async def size(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM translations") as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

    async def stats(self) -> dict:
        total = self._stats["memory_hits"] + self._stats["db_hits"] + self._stats["misses"]
        hits = self._stats["memory_hits"] + self._stats["db_hits"]
        hit_rate = round(100 * hits / total, 1) if total else 0.0
        return {**self._stats, "hit_rate_pct": hit_rate, "memory_entries": len(self._mem)}
