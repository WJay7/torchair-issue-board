import tempfile
import unittest
from pathlib import Path

from app.database import DutyScheduleRepository


class DutyScheduleRepositoryTests(unittest.TestCase):
    def test_saves_reads_lists_and_deletes_a_schedule(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = DutyScheduleRepository(Path(directory) / "torchair.db")
            repository.initialize()

            repository.save("2026-08-19", "李明")
            repository.save("2026-08-20", "王雪")
            repository.save("2026-08-19", "张三")
            repository.save_member("张三", "zhangsan")

            self.assertEqual(
                repository.get("2026-08-19"),
                {"duty_date": "2026-08-19", "person_name": "张三"},
            )
            self.assertEqual(
                repository.list("2026-08-20", "2026-08-20"),
                [{"duty_date": "2026-08-20", "person_name": "王雪"}],
            )
            self.assertTrue(repository.delete("2026-08-19"))
            self.assertIsNone(repository.get("2026-08-19"))
            self.assertEqual(
                repository.get_member("张三"),
                {"person_name": "张三", "gitcode_account": "zhangsan"},
            )
            self.assertTrue(repository.delete_member("张三"))

            self.assertEqual(
                repository.register_issue_keys(["1", "2"], "2026-08-19T10:00:00+08:00"),
                [],
            )
            self.assertEqual(
                repository.register_issue_keys(["2", "3"], "2026-08-19T11:00:00+08:00"),
                ["3"],
            )
            self.assertEqual(repository.pending_issue_keys(["1", "2", "3"]), ["3"])
            self.assertEqual(
                repository.eligible_issue_keys(
                    ["1", "2", "3"], "2026-08-19T11:00:00+08:00"
                ),
                ["1", "2", "3"],
            )
            repository.complete_issue_assignment(
                "3", "2026-08-19T11:01:00+08:00", "zhangsan"
            )
            self.assertEqual(repository.pending_issue_keys(["1", "2", "3"]), [])
            self.assertEqual(
                repository.eligible_issue_keys(
                    ["1", "2", "3"], "2026-08-19T12:00:00+08:00"
                ),
                ["1", "2"],
            )
