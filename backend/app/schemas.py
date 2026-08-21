from typing import List

from pydantic import BaseModel, Field


class SummaryItem(BaseModel):
    label: str
    value: str
    tone: str


class DutyInfo(BaseModel):
    date: str
    name: str
    account: str | None = None


class DutyScheduleInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class DutySchedule(BaseModel):
    date: str
    name: str


class DutyMemberInput(BaseModel):
    account: str = Field(min_length=1, max_length=120)


class DutyMember(BaseModel):
    name: str
    account: str


class OwnerRankItem(BaseModel):
    rank: int
    name: str
    total: int
    opened: int
    closed: int
    rate: float


class LabelStatItem(BaseModel):
    label: str
    open: int
    closed: int


class DailyIssueItem(BaseModel):
    date: str
    opened: int
    closed: int


class DailyIssueDetailItem(BaseModel):
    date: str
    dutyName: str
    dutyAccount: str | None = None
    issueNumber: str
    issueTitle: str
    issueState: str
    issueUrl: str | None = None
    owner: str


class DashboardResponse(BaseModel):
    source: str
    generatedAt: str
    summary: List[SummaryItem]
    duty: DutyInfo
    ownerRanking: List[OwnerRankItem]
    labelStats: List[LabelStatItem]
    dailyIssueStats: List[DailyIssueItem]
    dailyIssueDetails: List[DailyIssueDetailItem]
