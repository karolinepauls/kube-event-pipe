"""In-process tests for BatchedBloomFilter."""
from pathlib import Path
from kube_event_pipe.batched_bloom_filter import BatchedBloomFilter  # type: ignore


params: dict = {
    'filter_capacity': 10000,
    'filter_error_rate': 0.01,
    'batch_count': 3,
    'batch_duration_sec': 3600,
}


def test_batched_bloom_filter_state_load(tmpdir_path: Path):
    """Test loading prior filters."""
    first_filter: BatchedBloomFilter[str] = BatchedBloomFilter(
        directory=tmpdir_path, **params
    )
    first_filter.close()
    filter_files = list(tmpdir_path.glob('*.bloom'))
    assert len(filter_files) == 1

    second_filter: BatchedBloomFilter[str] = BatchedBloomFilter(
        directory=tmpdir_path, **params
    )
    second_filter_files = list(tmpdir_path.glob('*.bloom'))
    assert filter_files == second_filter_files

    # Simulate time passing to trigger filter rotation.
    second_filter.last_batch_ts -= 100000  # Force rotation.
    # We're rather fast here so the code would create another filter with the same timestamp,
    # which won't happen in real use, since cheating by taking from `last_batch_ts` won't take
    # place.
    filter_renamed = second_filter_files[0].parent / '1212.bloom'
    second_filter_files[0].rename(filter_renamed)

    second_filter.rotate_if_needed()
    second_filter.close()
    filter_files_rotated = sorted(tmpdir_path.glob('*.bloom'))

    assert len(filter_files_rotated) == 2
    assert filter_files_rotated[0] == filter_renamed
