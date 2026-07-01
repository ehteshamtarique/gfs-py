from pydantic import BaseModel, ConfigDict

from gfs.common.constants import ChunkHandle, ChunkVersion
from gfs.common.utils import ServerInfo


class ChunkInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    version: ChunkVersion
    handle: ChunkHandle
    length: int


class HeartBeatArgs(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    server_info: ServerInfo
    chunks: list[ChunkInfo]


class HeartBeatReply(BaseModel):
    expired_chunks: list[ChunkHandle] = []
