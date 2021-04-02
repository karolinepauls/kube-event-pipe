"""Entry point."""
import logging
import json
import sys
import signal
from os import environ
from typing import TypeVar, Callable, Union, IO
from datetime import timedelta
from pathlib import Path
from kube_event_pipe.batched_bloom_filter import BatchedBloomFilter  # type: ignore
from kubernetes import client, config, watch  # type: ignore

DEFAULT_DESTINATION = '-'
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_PERSISTENCE_PATH = '.'
DEFAULT_CAPACITY = '1_000_000'
DEFAULT_ERROR_RATE = '0.01'
DEFAULT_BATCH_COUNT = '3'
DEFAULT_BATCH_DURATION = str(int(timedelta(hours=1).total_seconds()))

ENV_DESTINATION = 'KUBE_EVENT_PIPE_DESTINATION'
ENV_LOG_LEVEL = 'KUBE_EVENT_PIPE_LOG_LEVEL'
ENV_PERSISTENCE_PATH = 'KUBE_EVENT_PIPE_PERSISTENCE_PATH'
ENV_FILTER_CAPACITY = 'KUBE_EVENT_PIPE_FILTER_CAPACITY'
ENV_FILTER_ERROR_RATE = 'KUBE_EVENT_PIPE_FILTER_ERROR_RATE'
ENV_BATCH_COUNT = 'KUBE_EVENT_PIPE_BATCH_COUNT'
ENV_BATCH_DURATION_SEC = 'KUBE_EVENT_PIPE_BATCH_DURATION_SEC'

log = logging.getLogger(__name__)


def signal_to_system_exit(signum, frame):
    """Raise SystemExit."""
    log.info('Caught signal %s. Exiting.', signum)
    sys.exit(0)


def pipe_events(
    destination_file: IO,
    persistence_path: Path,
    filter_capacity: int,
    filter_error_rate: float,
    batch_count: int,
    batch_duration_sec: int,
):
    """List and watch, deduplicate, and write events to stdout."""
    events_seen: BatchedBloomFilter[str] = BatchedBloomFilter(
        directory=persistence_path,
        filter_capacity=filter_capacity,
        filter_error_rate=filter_error_rate,
        batch_count=batch_count,
        batch_duration_sec=batch_duration_sec,
    )

    kube_api = client.CoreV1Api()
    watcher = watch.Watch()
    events = watcher.stream(kube_api.list_event_for_all_namespaces)
    try:
        skipped = 0
        log.info('Watching events...')
        for event in events:
            event_obj = event['object']
            # We pass a string as event identity because otherwise standard Python's `hash` function
            # is used, rather than a dedicated hash functions.
            event_identity = f'{event_obj.metadata.name}-{event_obj.count}'

            if event_identity in events_seen:
                skipped += 1
                log.debug('Skipped repeated event: %s: %r', event_identity, event_obj.message)
                continue
            else:
                if skipped > 0:
                    log.info('New event seen, after skipping %s previously seen events', skipped)
                skipped = 0
                log.debug('Logging event: %s: %r', event_identity, event_obj.message)

            event_data = event['raw_object']
            events_seen.add(event_identity)
            json.dump(event_data, destination_file)
            destination_file.write('\n')
            destination_file.flush()
    except (SystemExit, KeyboardInterrupt):
        log.info('Terminating')
        events_seen.close()
        return


Num = TypeVar('Num', bound=Union[int, float])


def env_get_positive_number(key: str, default: str, constructor: Callable[[str], Num]) -> Num:
    """Parse the named environment variable as the given number type."""
    val = None
    try:
        val = constructor(environ.get(key, default))
        if val <= 0:
            raise ValueError
    except ValueError:
        log.error('Environment variable %r must be a positive %s, is %r', key, constructor, val)
        exit(1)
    return val


def main():
    """Run kube-event-pipe."""
    log_level = environ.get('KUBE_EVENT_PIPE_LOG_LEVEL', DEFAULT_LOG_LEVEL).upper()
    logging.basicConfig(level=log_level)

    signal.signal(signal.SIGTERM, signal_to_system_exit)
    signal.signal(signal.SIGQUIT, signal_to_system_exit)

    destination = environ.get(ENV_DESTINATION, DEFAULT_DESTINATION)
    persistence_path = Path(environ.get(ENV_PERSISTENCE_PATH, DEFAULT_PERSISTENCE_PATH)).resolve()
    filter_capacity = env_get_positive_number(
        ENV_FILTER_CAPACITY, DEFAULT_CAPACITY, constructor=int)
    filter_error_rate = env_get_positive_number(
        ENV_FILTER_ERROR_RATE, DEFAULT_ERROR_RATE, constructor=float)
    batch_count = env_get_positive_number(
        ENV_BATCH_COUNT, DEFAULT_BATCH_COUNT, constructor=int)
    batch_duration_sec = env_get_positive_number(
        ENV_BATCH_DURATION_SEC, DEFAULT_BATCH_DURATION, constructor=int)

    log.info(
        'kube-event-pipe configuration: '
        '%s: %s, '
        '%s: %s, '
        '%s: %s, '
        '%s: %s, '
        '%s: %s, '
        '%s: %s, '
        '%s: %s',
        ENV_DESTINATION, destination,
        ENV_LOG_LEVEL, log_level,
        ENV_PERSISTENCE_PATH, persistence_path,
        ENV_FILTER_CAPACITY, filter_capacity,
        ENV_FILTER_ERROR_RATE, filter_error_rate,
        ENV_BATCH_COUNT, batch_count,
        ENV_BATCH_DURATION_SEC, batch_duration_sec,
    )

    try:
        config.load_kube_config()
        log.info("Loaded kubeconfig")
    except config.ConfigException:
        config.load_incluster_config()
        log.info("Loaded in-cluster config")

    if destination == '-':
        destination_file = sys.stdout
    else:
        destination_file = open(destination, 'a')

    pipe_events(
        destination_file=destination_file,
        persistence_path=persistence_path,
        filter_capacity=filter_capacity,
        filter_error_rate=filter_error_rate,
        batch_count=batch_count,
        batch_duration_sec=batch_duration_sec,
    )
