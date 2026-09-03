from datetime import date
import unittest

from app.cloud_sync import _has_assignee
from app.config import Settings
from app.dashboard_service import build_dashboard


SETTINGS = Settings(
    gitcode_base_url="https://api.gitcode.com/api/v5",
    gitcode_token="token",
    gitcode_owner="Ascend",
    gitcode_repo="torchair",
    duty_name="张三",
    duty_account="zhangsan",
    database_path=None,
)


class DashboardServiceTests(unittest.TestCase):
    def test_assignee_detection_accepts_gitcode_username_shapes(self):
        self.assertTrue(_has_assignee({"assignee": {"username": "someone"}}))
        self.assertTrue(_has_assignee({"assignees": [{"user_name": "someone"}]}))
        self.assertFalse(_has_assignee({"assignee": {}}))

    def test_uses_state_assignee_and_first_label_for_statistics(self):
        today = date.today().isoformat()
        issues = [
            {
                "state": "open",
                "assignee": {"name": "李明", "login": "liming"},
                "labels": [{"name": "bug"}, {"name": "backend"}],
                "created_at": f"{today}T09:00:00+08:00",
            },
            {
                "state": "closed",
                "assignee": {"login": "wangxue"},
                "labels": [{"name": "feature"}],
                "created_at": f"{today}T10:00:00+08:00",
                "finished_at": f"{today}T11:00:00+08:00",
            },
            {
                "state": "closed",
                "labels": [],
                "created_at": f"{today}T12:00:00+08:00",
                "finished_at": f"{today}T13:00:00+08:00",
            },
        ]

        result = build_dashboard(
            issues, SETTINGS, duty={"date": today, "name": "张三", "account": None}
        )

        self.assertEqual([item.value for item in result.summary], ["3", "1", "66.70%"])
        self.assertEqual([item.name for item in result.ownerRanking], ["wangxue", "李明"])
        self.assertEqual(result.labelStats[0].label, "bug")
        self.assertNotIn("backend", [item.label for item in result.labelStats])
        self.assertEqual(result.labelStats[-1].label, "未标记")
        self.assertEqual(result.dailyIssueStats[0].opened, 1)
        self.assertEqual(result.dailyIssueStats[0].closed, 2)

    def test_ranks_sustained_closed_work_before_a_single_closed_issue(self):
        issues = [
            {"state": "closed", "assignee": {"login": "single"}, "labels": []},
            *[
                {"state": "closed", "assignee": {"login": "steady"}, "labels": []}
                for _ in range(8)
            ],
            {"state": "open", "assignee": {"login": "steady"}, "labels": []},
        ]

        result = build_dashboard(
            issues,
            SETTINGS,
            duty={"date": date.today().isoformat(), "name": "张三", "account": None},
        )

        self.assertEqual([item.name for item in result.ownerRanking], ["steady", "single"])


if __name__ == "__main__":
    unittest.main()
