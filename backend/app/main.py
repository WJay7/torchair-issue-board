from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import DutyScheduleRepository
from .dashboard_service import build_dashboard
from .gitcode_client import GitCodeApiError, GitCodeClient
from .sample_data import DATA
from .schemas import (
    DutyInfo,
    DutyMember,
    DutyMemberInput,
    DutySchedule,
    DutyScheduleInput,
)

app = FastAPI(title="TorchAir Issue API", version="0.1.0")

ASSIGNMENT_GRACE_SECONDS = 60

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def duty_repository() -> DutyScheduleRepository:
    return DutyScheduleRepository(get_settings().database_path)


def today_duty() -> DutyInfo:
    settings = get_settings()
    today = date.today().isoformat()
    schedule = duty_repository().get(today)
    if schedule:
        member = duty_repository().get_member(schedule["person_name"])
        return DutyInfo(
            date=today,
            name=schedule["person_name"],
            account=member["gitcode_account"] if member else None,
        )
    return DutyInfo(
        date=today,
        name=settings.duty_name,
        account=settings.duty_account,
    )


def duty_for_date(duty_date: str) -> DutyInfo:
    settings = get_settings()
    repository = duty_repository()
    schedule = repository.get(duty_date)
    if schedule:
        member = repository.get_member(schedule["person_name"])
        return DutyInfo(
            date=duty_date,
            name=schedule["person_name"],
            account=member["gitcode_account"] if member else None,
        )
    if duty_date == date.today().isoformat():
        return DutyInfo(
            date=duty_date,
            name=settings.duty_name,
            account=settings.duty_account,
        )
    return DutyInfo(date=duty_date, name="未排班", account=None)


def issue_created_date(issue: dict) -> str | None:
    value = issue.get("created_at")
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def duty_history() -> dict[str, DutyInfo]:
    repository = duty_repository()
    today = date.today()
    start = today - timedelta(days=24)
    history: dict[str, DutyInfo] = {}
    for schedule in repository.list(start.isoformat(), today.isoformat()):
        member = repository.get_member(schedule["person_name"])
        duty_date = schedule["duty_date"]
        history[duty_date] = DutyInfo(
            date=duty_date,
            name=schedule["person_name"],
            account=member["gitcode_account"] if member else None,
        )
    return history


@app.on_event("startup")
def initialize_database() -> None:
    duty_repository().initialize()


@app.get("/")
def root():
    return {"name": "TorchAir issue API", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard():
    settings = get_settings()
    duty = today_duty()
    if not settings.gitcode_configured:
        return DATA.model_copy(update={"duty": duty})

    client = GitCodeClient(settings)
    try:
        issues = client.list_all_issues()
        issue_by_key = {
            str(issue.get("id") or issue.get("number")): issue
            for issue in issues
            if issue.get("id") or issue.get("number")
        }
        now = datetime.now().astimezone()
        seen_at = now.isoformat(timespec="seconds")
        duty_repository().register_issue_keys(list(issue_by_key), seen_at)
        assignment_cutoff = (
            now - timedelta(seconds=ASSIGNMENT_GRACE_SECONDS)
        ).isoformat(timespec="seconds")
        candidate_keys = duty_repository().eligible_issue_keys(
            list(issue_by_key), assignment_cutoff
        )
        assigned_count = 0
        for issue_key in candidate_keys:
            issue = issue_by_key[issue_key]
            if str(issue.get("state", "")).lower() not in {"open", "opened"}:
                duty_repository().complete_issue_assignment(issue_key, seen_at)
                continue
            assignee = issue.get("assignee") or issue.get("assignees")
            has_assignee = bool(
                assignee
                and (
                    (isinstance(assignee, dict) and (assignee.get("login") or assignee.get("name")))
                    or (isinstance(assignee, list) and any(assignee))
                    or (isinstance(assignee, str) and assignee.strip())
                )
            )
            if has_assignee:
                duty_repository().complete_issue_assignment(
                    issue_key,
                    seen_at,
                )
                continue
            created_day = issue_created_date(issue)
            if not created_day:
                continue
            issue_duty = duty_for_date(created_day)
            if not issue_duty.account:
                continue
            issue_number = str(issue.get("number") or issue.get("id"))
            client.update_issue_assignee(issue_number, issue_duty.account)
            duty_repository().complete_issue_assignment(
                issue_key,
                seen_at,
                issue_duty.account,
            )
            assigned_count += 1
        if assigned_count:
            issues = client.list_all_issues()
    except GitCodeApiError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return build_dashboard(issues, settings, duty, duty_history())


@app.get("/api/duty-schedules", response_model=list[DutySchedule])
def list_duty_schedules(start_date: date | None = None, end_date: date | None = None):
    schedules = duty_repository().list(
        start_date.isoformat() if start_date else None,
        end_date.isoformat() if end_date else None,
    )
    return [
        DutySchedule(date=item["duty_date"], name=item["person_name"])
        for item in schedules
    ]


@app.put("/api/duty-schedules/{duty_date}", response_model=DutySchedule)
def save_duty_schedule(duty_date: date, schedule: DutyScheduleInput):
    saved = duty_repository().save(duty_date.isoformat(), schedule.name.strip())
    return DutySchedule(date=saved["duty_date"], name=saved["person_name"])


@app.delete("/api/duty-schedules/{duty_date}", status_code=204)
def delete_duty_schedule(duty_date: date):
    if not duty_repository().delete(duty_date.isoformat()):
        raise HTTPException(status_code=404, detail="Duty schedule was not found.")
    return Response(status_code=204)


@app.get("/api/duty-members", response_model=list[DutyMember])
def list_duty_members():
    return [
        DutyMember(name=item["person_name"], account=item["gitcode_account"])
        for item in duty_repository().list_members()
    ]


@app.put("/api/duty-members/{name}", response_model=DutyMember)
def save_duty_member(name: str, member: DutyMemberInput):
    person_name = name.strip()
    account = member.account.strip()
    if not person_name or not account:
        raise HTTPException(status_code=422, detail="姓名和 GitCode 账号不能为空。")
    saved = duty_repository().save_member(person_name, account)
    return DutyMember(name=saved["person_name"], account=saved["gitcode_account"])


@app.delete("/api/duty-members/{name}", status_code=204)
def delete_duty_member(name: str):
    if not duty_repository().delete_member(name):
        raise HTTPException(status_code=404, detail="Duty member was not found.")
    return Response(status_code=204)


@app.get("/api/integration/status")
def integration_status():
    settings = get_settings()
    return {
        "gitcodeConfigured": settings.gitcode_configured,
        "repository": f"{settings.gitcode_owner}/{settings.gitcode_repo}",
        "source": "gitcode" if settings.gitcode_configured else "mock",
    }
