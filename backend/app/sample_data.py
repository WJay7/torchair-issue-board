from .schemas import DashboardResponse


def _rank(name: str, total: int, closed: int):
    rate = round((closed / total) * 100, 1) if total else 0.0
    return {
        "name": name,
        "total": total,
        "opened": total - closed,
        "closed": closed,
        "rate": rate,
    }


OWNER_STATS = [
    _rank("李明", 42, 24),
    _rank("王雪", 31, 19),
    _rank("张三", 28, 11),
    _rank("陈晨", 19, 8),
]

OWNER_RANKING = sorted(
    OWNER_STATS,
    key=lambda item: (-item["rate"], -item["closed"], -item["total"], item["name"]),
)

for index, item in enumerate(OWNER_RANKING, start=1):
    item["rank"] = index


DATA = DashboardResponse(
    source="mock",
    generatedAt="2026-08-18T14:55:00+08:00",
        summary=[
        {"label": "总数", "value": "204", "tone": "total"},
        {"label": "开启数", "value": "128", "tone": "open"},
        {"label": "关闭率", "value": "37.30%", "tone": "rate"},
    ],
    duty={"date": "2026-08-18", "name": "张三", "account": "zhangsan"},
    ownerRanking=OWNER_RANKING,
    labelStats=[
        {"label": "bug", "open": 31, "closed": 27},
        {"label": "feature", "open": 28, "closed": 18},
        {"label": "infra", "open": 12, "closed": 23},
        {"label": "docs", "open": 14, "closed": 7},
    ],
    dailyIssueStats=[
        {"date": "08-12", "opened": 12, "closed": 8},
        {"date": "08-13", "opened": 15, "closed": 10},
        {"date": "08-14", "opened": 11, "closed": 14},
        {"date": "08-15", "opened": 18, "closed": 9},
        {"date": "08-16", "opened": 9, "closed": 13},
        {"date": "08-17", "opened": 16, "closed": 12},
        {"date": "08-18", "opened": 13, "closed": 7},
    ],
    dailyIssueDetails=[],
)
