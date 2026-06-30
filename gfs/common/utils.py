from dataclasses import dataclass

from common.exceptions import GFSError


@dataclass
class PathInfo:
    pathname: str
    is_dir: bool

    def parent(self) -> "PathInfo":
        index = self.pathname.rfind("/")

        if index == -1:
            raise GFSError(-1, "No parent")

        return PathInfo(
            pathname=self.pathname[:index],
            is_dir=True,
        )


@dataclass
class ServerInfo:
    server_type: int
    server_addr: str


def make_path_info(pathname: str, is_dir: bool) -> PathInfo | None:
    if pathname == "/":
        return PathInfo(pathname="/", is_dir=True)

    if "//" in pathname:
        return None

    if "/." in pathname:
        return None

    if not pathname.startswith("/"):
        return None

    return PathInfo(
        pathname=pathname.rstrip("/"),
        is_dir=is_dir,
    )