"""Build monitor target list from environment variables and .env."""

import os
import re
from pathlib import Path

from scraper import DEFAULT_BASE_URL


def _read_dotenv(path: str = ".env") -> dict[str, str]:
    """Read .env as KEY=VALUE pairs.

    Minimal parser by design: ignores comments and blank lines.
    """
    env_map: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env_map

    for raw_line in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        env_map[key] = value
    return env_map


_DOTENV = _read_dotenv()


def _env(key: str, default: str = "") -> str:
    """Prefer process env, then local .env, then default."""
    if key in os.environ and os.environ[key]:
        return os.environ[key]
    return _DOTENV.get(key, default)


LEGACY_TARGET_IDS = {
    1: "default",
    2: "kobayashi",
    3: "fanza_kuji",
    4: "shining_musume",
}


def _normalize_url(url: str) -> str:
    """Apply lightweight normalization for URLs copied from editors/webpages."""
    return url.strip().replace("&amp;", "&")


def _target_id_for_index(index: int) -> str:
    """Keep historical IDs for 1..4 and derive stable IDs for extra targets."""
    return LEGACY_TARGET_IDS.get(index, f"target_{index}")


def _collect_target_indexes() -> list[int]:
    """Collect TARGET_<n>_URL indexes from process env and .env."""
    pattern = re.compile(r"^TARGET_(\d+)_URL$")
    seen: set[int] = set()
    for key in set(_DOTENV.keys()) | set(os.environ.keys()):
        m = pattern.match(key)
        if not m:
            continue
        try:
            seen.add(int(m.group(1)))
        except ValueError:
            continue

    if not seen:
        # Backward-compatible fallback when no index can be discovered.
        return [1, 2, 3, 4]
    return sorted(seen)


def _build_targets() -> list[dict[str, str]]:
    """Build monitoring targets from TARGET_<n>_NAME / TARGET_<n>_URL pairs."""
    targets: list[dict[str, str]] = []

    for index in _collect_target_indexes():
        tid = _target_id_for_index(index)
        nkey = f"TARGET_{index}_NAME"
        ukey = f"TARGET_{index}_URL"

        default_name = f"監視対象{index}"
        default_url = DEFAULT_BASE_URL if index == 1 else ""

        name = _env(nkey, default_name).strip()
        url = _normalize_url(_env(ukey, default_url))
        if not url:
            continue

        targets.append({"id": tid, "name": name, "url": url})

    if not targets:
        raise RuntimeError(
            "No monitoring targets configured. Set TARGET_1_URL (or others) in .env."
        )
    return targets


# Imported by app/dashboard to get active monitoring targets.
FIXED_TARGETS = _build_targets()
