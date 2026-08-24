from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from .config import Settings
from .schemas import DashboardResponse, DutyInfo


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_closed(issue: dict[str, Any]) -> bool:
    return str(issue.get("state", "")).lower() in {"closed", "close"}


def _assignee_name(issue: dict[str, Any]) -> str | None:
    assignee = issue.get("assignee")
    if isinstance(assignee, dict):
        return assignee.get("name") or assignee.get("login")
    if isinstance(assignee, str) and assignee.strip():
        return assignee.strip()
    assignees = issue.get("assignees")
    if isinstance(assignees, list) and assignees and isinstance(assignees[0], dict):
        return assignees[0].get("name") or assignees[0].get("login")
    return None


def _first_label(issue: dict[str, Any]) -> str:
    labels = issue.get("labels")
    if isinstance(labels, list) and labels:
        first = labels[0]
        if isinstance(first, dict) and first.get("name"):
            return str(first["name"])
        if isinstance(first, str) and first.strip():
            return first.strip()
    return "未标记"


def _day_key(value: Any) -> str | None:
    timestamp = _parse_timestamp(value)
    return timestamp.date().isoformat() if timestamp else None


def build_dashboard(
    issues: list[dict[str, Any]],
    settings: Settings,
    duty: DutyInfo,
    duty_history: dict[str, DutyInfo] | None = None,
) -> DashboardResponse:
    total = len(issues)
    closed = sum(1 for issue in issues if _is_closed(issue))
    opened = total - closed
    close_rate = round(closed / total * 100, 1) if total else 0.0

    owners: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "closed": 0})
    labels: dict[str, dict[str, int]] = defaultdict(lambda: {"open": 0, "closed": 0})
    for issue in issues:
        is_closed = _is_closed(issue)
        owner = _assignee_name(issue)
        if owner:
            owners[owner]["total"] += 1
            if is_closed:
                owners[owner]["closed"] += 1

        label = _first_label(issue)
        labels[label]["closed" if is_closed else "open"] += 1

    owner_ranking = [
        {
            "name": name,
            "total": values["total"],
            "opened": values["total"] - values["closed"],
            "closed": values["closed"],
            "rate": round(values["closed"] / values["total"] * 100, 1),
        }
        for name, values in owners.items()
    ]
    # Closed volume comes first, so a single closed Issue does not outrank sustained work.
    owner_ranking.sort(key=lambda row: (-row["closed"], -row["rate"], -row["total"], row["name"]))
    for index, row in enumerate(owner_ranking, start=1):
        row["rank"] = index

    label_stats = [
        {"label": name, "open": values["open"], "closed": values["closed"]}
        for name, values in labels.items()
    ]
    label_stats.sort(key=lambda row: (-(row["open"] + row["closed"]), row["label"]))

    today = date.today()
    daily = {
        (today - timedelta(days=offset)).isoformat(): {"opened": 0, "closed": 0}
        for offset in range(0, 25)
    }
    for issue in issues:
        created_day = _day_key(issue.get("created_at"))
        if created_day in daily:
            daily[created_day]["closed" if _is_closed(issue) else "opened"] += 1

    daily_stats = [
        {
            "date": f"{datetime.fromisoformat(day).month}.{datetime.fromisoformat(day).day}",
            **values,
        }
        for day, values in daily.items()
    ]

    duty_date = duty.date if isinstance(duty, DutyInfo) else duty["date"]
    history = duty_history or {duty_date: duty}
    daily_issue_details = []
    for issue in issues:
        created_day = _day_key(issue.get("created_at"))
        if not created_day:
            continue
        issue_number = str(issue.get("number") or issue.get("id") or "")
        issue_title = str(issue.get("title") or f"Issue #{issue_number}")
        issue_duty = history.get(created_day)
        if issue_duty is None:
            issue_duty = DutyInfo(date=created_day, name="未排班", account=None)
        if isinstance(issue_duty, dict):
            duty_name = issue_duty.get("name", "未排班")
            duty_account = issue_duty.get("account")
        else:
            duty_name = issue_duty.name
            duty_account = issue_duty.account
        daily_issue_details.append(
            {
                "date": created_day,
                "dutyName": duty_name,
                "dutyAccount": duty_account,
                "issueNumber": issue_number,
                "issueTitle": issue_title,
                "issueState": "关闭" if _is_closed(issue) else "开启",
                "issueUrl": issue.get("html_url") or issue.get("web_url"),
                "owner": _assignee_name(issue) or "未分配",
            }
        )
    daily_issue_details.sort(
        key=lambda row: (row["date"], row["issueNumber"]), reverse=True
    )

    return DashboardResponse(
        source="gitcode",
        generatedAt=datetime.now().astimezone().isoformat(timespec="seconds"),
        summary=[
            {"label": "总数", "value": str(total), "tone": "total"},
            {"label": "开启数", "value": str(opened), "tone": "open"},
            {"label": "关闭率", "value": f"{close_rate:.2f}%", "tone": "rate"},
        ],
        duty=duty,
        ownerRanking=owner_ranking,
        labelStats=label_stats,
        dailyIssueStats=daily_stats,
        dailyIssueDetails=daily_issue_details,
    )
