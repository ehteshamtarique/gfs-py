from datetime import timedelta


CHUNK_SIZE = 64 * 1024 * 1024
NUMBER_OF_REPLICAS = 3

PERIODIC_WORK_INTERVAL = timedelta(seconds=60)
HEARTBEAT_INTERVAL = timedelta(milliseconds=200)
HEARTBEAT_TIMEOUT = timedelta(seconds=1)
LEASE_TIMEOUT = timedelta(seconds=5)