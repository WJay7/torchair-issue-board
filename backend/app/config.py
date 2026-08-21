from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> dict[str, str]:
    """Read the project's optional .env file without adding a runtime dependency."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_FILE_ENV = _load_dotenv()


def _value(name: str, default: str = "") -> str:
    return os.getenv(name, _FILE_ENV.get(name, default)).strip()


@dataclass(frozen=True)
class Settings:
    gitcode_base_url: str
    gitcode_token: str
    gitcode_owner: str
    gitcode_repo: str
    duty_name: str
    duty_account: str
    database_path: Path

    @property
    def gitcode_configured(self) -> bool:
        return bool(self.gitcode_token and self.gitcode_owner and self.gitcode_repo)


def get_settings() -> Settings:
    return Settings(
        gitcode_base_url=_value("GITCODE_BASE_URL", "https://api.gitcode.com/api/v5"),
        gitcode_token=_value("GITCODE_TOKEN"),
        gitcode_owner=_value("GITCODE_OWNER", "Ascend"),
        gitcode_repo=_value("GITCODE_REPO", "torchair"),
        duty_name=_value("TORCHAIR_DUTY_NAME", "张三"),
        duty_account=_value("TORCHAIR_DUTY_ACCOUNT", "zhangsan"),
        database_path=Path(
            _value(
                "TORCHAIR_DATABASE_PATH",
                str(Path(__file__).resolve().parents[1] / "data" / "torchair.db"),
            )
        ),
    )
