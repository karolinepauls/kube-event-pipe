"""A wrapper for multiple bloom filters that are rotated periodically."""
import time
import logging
from typing import TypeVar, List, Generic
from pathlib import Path
from pybloomfilter import BloomFilter  # type: ignore


log = logging.getLogger(__name__)


Element = TypeVar('Element')


class BatchedBloomFilter(Generic[Element]):
    """A wrapper for multiple persistent bloom filters that are rotated periodically."""

    batches: List[BloomFilter]
    directory: Path
    filter_capacity: int
    filter_error_rate: float
    batch_count: int
    batch_duration_sec: int
    last_batch_ts: int

    def __init__(
        self,
        directory: Path,
        filter_capacity: int,
        filter_error_rate: float,
        batch_count: int,
        batch_duration_sec: int,
    ):
        """Create a BatchedBloomFilter from a set of files, named `<unix_timestamp>.bloom`."""
        self.directory = directory
        self.filter_capacity = filter_capacity
        self.filter_error_rate = filter_error_rate
        self.batch_count = batch_count
        self.batch_duration_sec = batch_duration_sec

        files = list(self.directory.glob('*.bloom'))

        timestamps = []
        timestamp_to_path = {}
        for path in files:
            try:
                timestamp = int(path.stem)
            except ValueError:
                log.info('Ignoring invalid file name (expecting <unix_timestamp>.bloom): %s', path)
            else:
                timestamps.append(timestamp)
                timestamp_to_path[timestamp] = path

        recent_timestamps = sorted(timestamps)[-self.batch_count:]
        try:
            self.last_batch_ts = recent_timestamps[-1]
        except IndexError:
            self.last_batch_ts = 0

        self.batches = [BloomFilter.open(str(timestamp_to_path[ts])) for ts in recent_timestamps]
        log.info('Found existing bloom filters: %s', dict(zip(recent_timestamps, self.batches)))
        self.rotate_if_needed()

    def rotate_if_needed(self):
        """Remove stale filters, create a new filter if needed, named `<unix_timestamp>.bloom`."""
        ts = int(time.time())
        if ts - self.last_batch_ts > self.batch_duration_sec:
            retained = self.batch_count - 1
            stale = self.batches[:-retained]
            self.batches = self.batches[-retained:]

            for stale_bf in stale:
                file_name = Path(stale_bf.filename)
                stale_bf.close()
                file_name.unlink()
                log.info('Closed stale bloom filter: %s', file_name)

            bloom_filter_file = self.directory / f'{ts}.bloom'
            self.batches.append(BloomFilter(
                self.filter_capacity, self.filter_error_rate, str(bloom_filter_file)))
            self.last_batch_ts = ts
            log.info('Created a new bloom filter: %s', bloom_filter_file)

            log.info('Operating with filters: %r', [(bf.filename, bf) for bf in self.batches])

    @property
    def recent_filter(self):
        """Return the most recent bloom filter, the one written to."""
        return self.batches[-1]

    def __contains__(self, element: Element):
        """Check if the element has been seen by any of the filters."""
        self.rotate_if_needed()

        for bf in self.batches:
            if element in bf:
                return True
        return False

    def add(self, element: Element):
        """Add the element to the most recent filter."""
        self.recent_filter.add(element)

    def close(self):
        """Close all bloom filter files."""
        for bf in self.batches:
            bf.close()
