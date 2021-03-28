"""Test bloom filter rotation."""
from pathlib import Path
from typing import List
from time import sleep
from kube_event_pipe.main import ENV_BATCH_DURATION_SEC, ENV_BATCH_COUNT
from tests.conftest import make_kube_event
from tests.wait import wait_until


def test_bloom_filters_rotation(kube_api, clean_kube, kube_event_pipe, tmpdir_path) -> None:
    """
    Test rotating the filters.

    Here we rely on the sleep call in `run_kube_event_pipe` to give it time to read all events.
    Since our rotation time is less than that, even the first event will trigger rotation.
    """
    duration = 1

    def get_filters() -> List[Path]:
        return sorted(tmpdir_path.glob('*.bloom'))

    with kube_event_pipe(env={ENV_BATCH_DURATION_SEC: str(duration), ENV_BATCH_COUNT: '3'}):
        initial_filters = wait_until(get_filters, check=lambda f: len(f) == 1,
                                     message='Expecting clean state (single filter)')
        assert len(initial_filters) == 1

        sleep(duration * 2)
        make_kube_event(kube_api)
        rotated_filters = wait_until(get_filters, check=lambda f: len(f) == 2,
                                     message='Bloom filters should have been rotated')

        sleep(duration * 2)
        make_kube_event(kube_api)
        rotated_filters_again = wait_until(get_filters, check=lambda f: len(f) == 3,
                                           message='Bloom filters should have been rotated again')

        sleep(duration * 2)
        make_kube_event(kube_api)
        rotated_filters_over_batch_count = wait_until(
            get_filters,
            check=lambda f: (len(f) == 3 and f != rotated_filters_again),
        )
        assert len(rotated_filters_over_batch_count) == 3, (
            "Bloom filters shouldn't exceed the batch count")

        # Ensure filters are
        assert initial_filters == rotated_filters[:1]
        assert rotated_filters == rotated_filters_again[:2]
        assert rotated_filters_again[1:] == rotated_filters_over_batch_count[:-1]
