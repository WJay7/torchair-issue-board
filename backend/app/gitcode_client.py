from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Settings


class GitCodeApiError(RuntimeError):
    pass


class GitCodeClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def list_all_issues(self) -> list[dict[str, Any]]:
        """Fetch every Issue from the configured repository, 100 at a time."""
        issues: list[dict[str, Any]] = []
        page = 1

        while True:
            query = urlencode(
                {
                    "access_token": self.settings.gitcode_token,
                    "state": "all",
                    "page": page,
                    "per_page": 100,
                }
            )
            endpoint = (
                f"{self.settings.gitcode_base_url.rstrip('/')}/repos/"
                f"{self.settings.gitcode_owner}/{self.settings.gitcode_repo}/issues?{query}"
            )

            try:
                with urlopen(endpoint, timeout=15) as response:  # nosec B310: URL comes from local config
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                raise GitCodeApiError(f"GitCode returned HTTP {error.code}: {detail}") from error
            except URLError as error:
                raise GitCodeApiError(f"Could not reach GitCode: {error.reason}") from error
            except json.JSONDecodeError as error:
                raise GitCodeApiError("GitCode returned invalid JSON.") from error

            if not isinstance(payload, list):
                raise GitCodeApiError("GitCode returned an unexpected Issue list response.")

            issues.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < 100:
                return issues
            page += 1

    def update_issue_assignee(self, issue_number: str, account: str) -> None:
        query = urlencode({"access_token": self.settings.gitcode_token})
        endpoint = (
            f"{self.settings.gitcode_base_url.rstrip('/')}/repos/"
            f"{self.settings.gitcode_owner}/{self.settings.gitcode_repo}/issues/"
            f"{issue_number}?{query}"
        )
        body = urlencode({"assignee": account}).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            method="PATCH",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urlopen(request, timeout=15):  # nosec B310: URL comes from local config
                return
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise GitCodeApiError(
                f"GitCode assignee update returned HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise GitCodeApiError(f"Could not update GitCode Issue: {error.reason}") from error
