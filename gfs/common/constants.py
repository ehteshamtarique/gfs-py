from enum import IntEnum

# Chunk & file commons

ChunkHandle = int
ChunkVersion = int
ChunkIndex = int
Offset = int


# Server commons

class ServerType(IntEnum):
    MASTER = 0
    CHUNKSERVER = 1