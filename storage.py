from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("bootlegger.db")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scrapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL
            );
            """
        )


def save_events(events: list[dict[str, Any]]) -> None:
    with connect() as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO events (id, timestamp, payload) VALUES (?, ?, ?)",
            [(event["id"], event["timestamp"], json.dumps(event)) for event in events],
        )
        connection.execute(
            "DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY timestamp DESC LIMIT 5000)"
        )


def load_events(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute("SELECT payload FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def save_checkpoint(snapshot: dict[str, Any]) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO checkpoints (id, created_at, reason, payload) VALUES (?, ?, ?, ?)",
            (snapshot["id"], snapshot["created_at"], snapshot["reason"], json.dumps(snapshot)),
        )


def save_scrape(result: dict[str, Any]) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO scrapes (fetched_at, url, status, payload) VALUES (?, ?, ?, ?)",
            (result["fetched_at"], result["url"], result["status"], json.dumps(result)),
        )


def audit(actor: str, action: str, details: str = "") -> None:
    from datetime import datetime, timezone

    with connect() as connection:
        connection.execute(
            "INSERT INTO audit_log (created_at, actor, action, details) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), actor, action, details),
        )
