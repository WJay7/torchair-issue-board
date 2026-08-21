"""Run one cloud synchronization cycle for GitHub Actions.

The job deliberately keeps the GitCode token and Supabase service key on the
runner. The browser only reads the public dashboard snapshot.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import Settings
from .dashboard_service import build_dashboard
from .gitcode_client import GitCodeClient, GitCodeApiError
from .schemas import DutyInfo


GRACE_SECONDS = 60


class SupabaseError(RuntimeError):
    pass


class SupabaseRestClient:
    def __init__(self, url: str, service_key: str):
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.service_key = service_key

    def request(
        self,
        method: str,
        table: str,
        payload: Any = None,
        query: str = "",
        prefer: str | None = None,
    ) -> Any:
        endpoint = f"{self.base_url}/{table}{query}"
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        request = Request(endpoint, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read().decode("utf-8")
        except Exception as error:  # urllib exposes several platform-specific errors
            raise SupabaseError(f"Supabase request failed: {error}") from error
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise SupabaseError("Supabase returned invalid JSON.") from error

    def list_rows(self, table: str, query: str = "") -> list[dict[str, Any]]:
        result = self.request("GET", table, query=query)
        if not isinstance(result, list):
            raise SupabaseError(f"Supabase returned an invalid {table} response.")
        return [row for row in result if isinstance(row, dict)]

    def upsert(self, table: str, rows: list[dict[str, Any]]) -> None:
        if rows:
            self.request(
                "POST",
                table,
                rows,
                prefer="resolution=merge-duplicates,return=minimal",
            )


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _issue_key(issue: dict[str, Any]) -> str | None:
    value = issue.get("id") or issue.get("number")
    return str(value) if value is not None else None


def _has_assignee(issue: dict[str, Any]) -> bool:
    assignee = issue.get("assignee") or issue.get("assignees")
    if isinstance(assignee, dict):
        return bool(assignee.get("login") or assignee.get("name"))
    if isinstance(assignee, list):
        return bool(assignee)
    return isinstance(assignee, str) and bool(assignee.strip())


def _created_day(issue: dict[str, Any]) -> str | None:
    value = issue.get("created_at")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _duty_history(
    schedules: list[dict[str, Any]], members: list[dict[str, Any]]
) -> dict[str, DutyInfo]:
    member_accounts = {
        row.get("person_name"): row.get("gitcode_account")
        for row in members
        if row.get("person_name")
    }
    return {
        row["duty_date"]: DutyInfo(
            date=row["duty_date"],
            name=row["person_name"],
            account=member_accounts.get(row["person_name"]),
        )
        for row in schedules
        if row.get("duty_date") and row.get("person_name")
    }


def run() -> None:
    settings = Settings(
        gitcode_base_url=os.getenv("GITCODE_BASE_URL", "https://api.gitcode.com/api/v5"),
        gitcode_token=_env("GITCODE_TOKEN"),
        gitcode_owner=os.getenv("GITCODE_OWNER", "Ascend"),
        gitcode_repo=os.getenv("GITCODE_REPO", "torchair"),
        duty_name="未排班",
        duty_account="",
        database_path=None,
    )
    # Supabase now calls the elevated key a "secret key". Keep the legacy
    # service-role name as a fallback for projects that have not migrated.
    supabase_key = os.getenv("SUPABASE_SECRET_KEY", "").strip() or _env(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase = SupabaseRestClient(_env("SUPABASE_URL"), supabase_key)
    gitcode = GitCodeClient(settings)
    issues = gitcode.list_all_issues()
    now = datetime.now(timezone.utc)

    schedules = supabase.list_rows("duty_schedules", "?select=duty_date,person_name")
    members = supabase.list_rows("duty_members", "?select=person_name,gitcode_account")
    history = _duty_history(schedules, members)
    issue_by_key = {key: issue for issue in issues if (key := _issue_key(issue))}

    existing_sync = supabase.list_rows("issue_sync", "?select=issue_key,first_seen_at,assignment_status,assigned_at")
    sync_by_key = {row["issue_key"]: row for row in existing_sync if row.get("issue_key")}
    new_sync_rows = []
    for key in issue_by_key:
        if key not in sync_by_key:
            new_sync_rows.append(
                {
                    "issue_key": key,
                    "first_seen_at": now.isoformat(timespec="seconds"),
                    "assignment_status": "pending",
                }
            )
    supabase.upsert("issue_sync", new_sync_rows)
    sync_by_key.update({row["issue_key"]: row for row in new_sync_rows})

    cutoff = now - timedelta(seconds=GRACE_SECONDS)
    assigned_any = False
    for key, row in sync_by_key.items():
        issue = issue_by_key.get(key)
        if not issue or row.get("assignment_status") != "pending":
            continue
        first_seen = datetime.fromisoformat(row["first_seen_at"].replace("Z", "+00:00"))
        if first_seen > cutoff or str(issue.get("state", "")).lower() not in {"open", "opened"}:
            continue
        if _has_assignee(issue):
            supabase.request(
                "PATCH",
                "issue_sync",
                {"assignment_status": "complete", "assigned_at": now.isoformat(timespec="seconds")},
                f"?issue_key=eq.{quote(key, safe='')}"
            )
            continue
        duty_day = _created_day(issue)
        duty = history.get(duty_day or "")
        if not duty or not duty.account:
            continue
        number = str(issue.get("number") or issue.get("id"))
        gitcode.update_issue_assignee(number, duty.account)
        supabase.request(
            "PATCH",
            "issue_sync",
            {
                "assignment_status": "complete",
                "assigned_at": now.isoformat(timespec="seconds"),
                "assigned_to": duty.account,
            },
            f"?issue_key=eq.{quote(key, safe='')}"
        )
        assigned_any = True

    if assigned_any:
        issues = gitcode.list_all_issues()

    issue_rows = []
    for issue in issues:
        key = _issue_key(issue)
        if not key:
            continue
        labels = issue.get("labels") or []
        first_label = "未标记"
        if labels:
            label = labels[0]
            first_label = str(label.get("name") if isinstance(label, dict) else label)
        issue_rows.append(
            {
                "issue_key": key,
                "issue_number": str(issue.get("number") or issue.get("id")),
                "title": str(issue.get("title") or ""),
                "state": str(issue.get("state") or ""),
                "owner": None,
                "first_label": first_label,
                "created_at": issue.get("created_at"),
                "issue_url": issue.get("html_url") or issue.get("web_url"),
                "raw_payload": issue,
                "synced_at": now.isoformat(timespec="seconds"),
            }
        )
    supabase.upsert("issues", issue_rows)

    today = date.today().isoformat()
    duty = history.get(today, DutyInfo(date=today, name="未排班", account=None))
    snapshot = build_dashboard(issues, settings, duty, history).model_dump(mode="json")
    supabase.upsert(
        "dashboard_snapshots",
        [{"id": 1, "payload": snapshot, "generated_at": now.isoformat(timespec="seconds")}],
    )
    print(f"Synced {len(issues)} issues; assigned={assigned_any}")


if __name__ == "__main__":
    try:
        run()
    except (GitCodeApiError, SupabaseError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
