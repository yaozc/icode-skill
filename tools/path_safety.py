"""Classify link-like paths without following their targets."""
from pathlib import Path
import stat


# A reparse attribute alone also describes ordinary cloud/virtual files.
LINK_TAGS = {0xA000001D, 0xA000000C, 0xA0000003}  # LX, symlink, junction


def is_link(path):
    """Recognize POSIX links and Windows link tags, including WSL LX links."""
    try:
        info = Path(path).lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    return stat.S_ISLNK(info.st_mode) or getattr(info, "st_reparse_tag", 0) in LINK_TAGS


def has_link(path):
    """Check original components from the root before any resolve/read."""
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    # Check parents first: lstat on a child would already traverse its parents.
    return any(is_link(part) for part in reversed((path, *path.parents)))
