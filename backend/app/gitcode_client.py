from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .config import Settings


class GitCodeApiError(RuntimeError):
    pass


class GitCodeClient:
    REQUEST_TIMEOUT_SECONDS = 45
    MAX_RETRIES = 3

    def __init__(self, settings: Settings):
        self.settings = settings

    def _open(self, request: str | Request):
        """Retry transient GitCode network/server failures before aborting a sync."""
        for attempt in range(self.MAX_RETRIES):
            try:
                return urlopen(request, timeout=self.REQUEST_TIMEOUT_SECONDS)  # nosec B310
            except HTTPError as error:
                if error.code not in {408, 429} and error.code < 500:
                    raise
                if attempt == self.MAX_RETRIES - 1:
                    raise
            except (TimeoutError, URLError):
                if attempt == self.MAX_RETRIES - 1:
                    raise
            time.sleep(2**attempt)

    def _get_json(self, endpoint: str) -> Any:
        """Retry when GitCode stalls while reading a response body."""
        for attempt in range(self.MAX_RETRIES):
            try:
                with self._open(endpoint) as response:
                    return json.loads(response.read().decode("utf-8"))
            except TimeoutError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(2**attempt)

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
                payload = self._get_json(endpoint)
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
            with self._open(request):
                return
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise GitCodeApiError(
                f"GitCode assignee update returned HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise GitCodeApiError(f"Could not update GitCode Issue: {error.reason}") from error

    def list_issue_pull_requests(self, issue_number: str) -> list[dict[str, Any]]:
        query = urlencode({"access_token": self.settings.gitcode_token})
        endpoint = (
            f"{self.settings.gitcode_base_url.rstrip('/')}/repos/"
            f"{self.settings.gitcode_owner}/{self.settings.gitcode_repo}/issues/"
            f"{issue_number}/pull_requests?{query}"
        )
        try:
            payload = self._get_json(endpoint)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise GitCodeApiError(
                f"GitCode related PR lookup returned HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise GitCodeApiError(f"Could not list GitCode related PRs: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise GitCodeApiError("GitCode returned invalid related PR JSON.") from error
        if not isinstance(payload, list):
            raise GitCodeApiError("GitCode returned an unexpected related PR response.")
        return [item for item in payload if isinstance(item, dict)]

    def list_repository_members(self) -> list[dict[str, Any]]:
        """Fetch every member of the configured GitCode repository."""
        members: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urlencode(
                {
                    "access_token": self.settings.gitcode_token,
                    "page": page,
                    "per_page": 100,
                }
            )
            endpoint = (
                f"{self.settings.gitcode_base_url.rstrip('/')}/repos/"
                f"{self.settings.gitcode_owner}/{self.settings.gitcode_repo}/collaborators?{query}"
            )
            try:
                payload = self._get_json(endpoint)
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                raise GitCodeApiError(
                    f"GitCode repository member lookup returned HTTP {error.code}: {detail}"
                ) from error
            except URLError as error:
                raise GitCodeApiError(
                    f"Could not list GitCode repository members: {error.reason}"
                ) from error
            except json.JSONDecodeError as error:
                raise GitCodeApiError("GitCode returned invalid repository member JSON.") from error
            if not isinstance(payload, list):
                raise GitCodeApiError("GitCode returned an unexpected repository member response.")
            members.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < 100:
                return members
            page += 1

    def enable_pr_close_related_issue(self, pr_number: str) -> None:
        query = urlencode({"access_token": self.settings.gitcode_token})
        endpoint = (
            f"{self.settings.gitcode_base_url.rstrip('/')}/repos/"
            f"{self.settings.gitcode_owner}/{self.settings.gitcode_repo}/pulls/"
            f"{pr_number}?{query}"
        )
        body = json.dumps({"close_related_issue": True}).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            method="PATCH",
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._open(request):
                return
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise GitCodeApiError(
                f"GitCode PR update returned HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise GitCodeApiError(f"Could not update GitCode PR: {error.reason}") from error

    def user_exists(self, username: str) -> bool:
        endpoint = (
            f"{self.settings.gitcode_base_url.rstrip('/')}/users/"
            f"{quote(username, safe='')}?{urlencode({'access_token': self.settings.gitcode_token})}"
        )
        try:
            with self._open(endpoint):
                return True
        except HTTPError as error:
            if error.code == 404:
                return False
            detail = error.read().decode("utf-8", errors="replace")
            raise GitCodeApiError(
                f"GitCode user validation returned HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise GitCodeApiError(f"Could not validate GitCode user: {error.reason}") from error
