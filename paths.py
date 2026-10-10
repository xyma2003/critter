"""Checkout resources and persistent user data have independent locations."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"


def resolve_state_file(data_dir: str | None = None, *, home: Path | None = None) -> Path:
    """Keep the existing state file unless a separate data directory is chosen.

    This only resolves paths: it never creates, copies, or migrates user data.
    ``home`` allows compatibility checks without touching the real home directory.
    """
    if not data_dir or not data_dir.strip():
        return (home if home is not None else Path.home()) / ".desktop-pet-state.json"
    if home is not None and (data_dir == "~" or data_dir.startswith("~/")):
        directory = home / data_dir[2:]
    else:
        directory = Path(data_dir).expanduser()
    if not directory.is_absolute():
        raise ValueError("CRITTER_DATA_DIR 必须使用绝对路径（可以用 ~ 表示用户目录）")
    return directory.resolve() / "state.json"
