from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class DutyScheduleRepository:
    """Stores the minimal duty schedule: one person for one calendar date."""

    def __init__(self, database_path: Path):
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS duty_schedules (
                    duty_date TEXT PRIMARY KEY,
                    person_name TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS duty_members (
                    person_name TEXT PRIMARY KEY,
                    gitcode_account TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS issue_sync (
                    issue_key TEXT PRIMARY KEY,
                    first_seen_at TEXT NOT NULL,
                    assignment_status TEXT NOT NULL DEFAULT 'complete',
                    assigned_at TEXT,
                    assigned_to TEXT
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(issue_sync)").fetchall()
            }
            if "assignment_status" not in columns:
                connection.execute(
                    "ALTER TABLE issue_sync ADD COLUMN assignment_status TEXT NOT NULL DEFAULT 'complete'"
                )
            if "assigned_at" not in columns:
                connection.execute("ALTER TABLE issue_sync ADD COLUMN assigned_at TEXT")
            if "assigned_to" not in columns:
                connection.execute("ALTER TABLE issue_sync ADD COLUMN assigned_to TEXT")

    def get(self, duty_date: str) -> dict[str, str] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT duty_date, person_name FROM duty_schedules WHERE duty_date = ?",
                (duty_date,),
            ).fetchone()
        return dict(row) if row else None

    def list(self, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, str]]:
        query = "SELECT duty_date, person_name FROM duty_schedules"
        parameters: list[str] = []
        filters: list[str] = []
        if start_date:
            filters.append("duty_date >= ?")
            parameters.append(start_date)
        if end_date:
            filters.append("duty_date <= ?")
            parameters.append(end_date)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY duty_date ASC"

        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def save(self, duty_date: str, person_name: str) -> dict[str, str]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO duty_schedules (duty_date, person_name)
                VALUES (?, ?)
                ON CONFLICT(duty_date) DO UPDATE SET person_name = excluded.person_name
                """,
                (duty_date, person_name),
            )
        return {"duty_date": duty_date, "person_name": person_name}

    def delete(self, duty_date: str) -> bool:
        with self._connection() as connection:
            result = connection.execute(
                "DELETE FROM duty_schedules WHERE duty_date = ?", (duty_date,)
            )
        return result.rowcount > 0

    def get_member(self, person_name: str) -> dict[str, str] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT person_name, gitcode_account FROM duty_members WHERE person_name = ?",
                (person_name,),
            ).fetchone()
        return dict(row) if row else None

    def list_members(self) -> list[dict[str, str]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT person_name, gitcode_account FROM duty_members ORDER BY person_name ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def save_member(self, person_name: str, gitcode_account: str) -> dict[str, str]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO duty_members (person_name, gitcode_account)
                VALUES (?, ?)
                ON CONFLICT(person_name) DO UPDATE SET gitcode_account = excluded.gitcode_account
                """,
                (person_name, gitcode_account),
            )
        return {"person_name": person_name, "gitcode_account": gitcode_account}

    def delete_member(self, person_name: str) -> bool:
        with self._connection() as connection:
            result = connection.execute(
                "DELETE FROM duty_members WHERE person_name = ?", (person_name,)
            )
        return result.rowcount > 0

    def register_issue_keys(self, issue_keys: list[str], seen_at: str) -> list[str]:
        """Create the initial baseline, then return only Issue keys first seen later."""
        if not issue_keys:
            return []

        with self._connection() as connection:
            existing_count = connection.execute(
                "SELECT COUNT(*) FROM issue_sync"
            ).fetchone()[0]
            if existing_count == 0:
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO issue_sync
                    (issue_key, first_seen_at, assignment_status)
                    VALUES (?, ?, 'complete')
                    """,
                    [(issue_key, seen_at) for issue_key in issue_keys],
                )
                return []

            new_keys: list[str] = []
            for issue_key in issue_keys:
                inserted = connection.execute(
                    """
                    INSERT OR IGNORE INTO issue_sync
                    (issue_key, first_seen_at, assignment_status)
                    VALUES (?, ?, 'pending')
                    """,
                    (issue_key, seen_at),
                )
                if inserted.rowcount > 0:
                    new_keys.append(issue_key)
        return new_keys

    def pending_issue_keys(self, issue_keys: list[str]) -> list[str]:
        if not issue_keys:
            return []

        placeholders = ", ".join("?" for _ in issue_keys)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT issue_key FROM issue_sync
                WHERE assignment_status = 'pending'
                  AND issue_key IN ({placeholders})
                """,
                issue_keys,
            ).fetchall()
        return [row[0] for row in rows]

    def eligible_issue_keys(
        self, issue_keys: list[str], _seen_before: str | None = None
    ) -> list[str]:
        """Return every tracked Issue that is pending or still unassigned."""
        if not issue_keys:
            return []

        placeholders = ", ".join("?" for _ in issue_keys)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT issue_key FROM issue_sync
                WHERE issue_key IN ({placeholders})
                  AND (assignment_status = 'pending' OR assigned_at IS NULL)
                """,
                issue_keys,
            ).fetchall()
        return [row[0] for row in rows]

    def complete_issue_assignment(
        self, issue_key: str, assigned_at: str, assigned_to: str | None = None
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE issue_sync
                SET assignment_status = 'complete', assigned_at = ?, assigned_to = ?
                WHERE issue_key = ?
                """,
                (assigned_at, assigned_to, issue_key),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
