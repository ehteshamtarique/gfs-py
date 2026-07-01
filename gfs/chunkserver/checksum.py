import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Checksum:
    value: int = 0

    def update_with_bytes(self, data: bytes) -> None:
        self.value = zlib.crc32(data) & 0xFFFFFFFF

    def update_with_file(self, path: Path) -> None:
        self.update_with_bytes(path.read_bytes())

    def check(self, data: bytes) -> bool:
        return self.value == (zlib.crc32(data) & 0xFFFFFFFF)
