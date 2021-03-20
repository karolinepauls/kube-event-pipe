"""Entry point."""
import logging
import json
import sys
import signal
from os import environ
from pathlib import Path
from pybloomfilter import BloomFilter  # type: ignore
from kubernetes import client, config, watch  # type: ignore

DEFAULT_CAPACITY = 1_000_000
DEFAULT_ERROR_RATE = 0.01

log = logging.getLogger(__name__)


def signal_to_system_exit(signum, frame):
    """Raise SystemExit."""
    log.info('Caught signal %s. Exiting.', signum)
    sys.exit(0)


def pipe_events(
    persistence_path: Path,
    filter_capacity: int,
    filter_error_rate: float,
):
    """List and watch, deduplicate, and write events to stdout."""
    bloom_filter_file = str(persistence_path / 'filter.bloom')
    try:
        events_seen = BloomFilter.open(bloom_filter_file)
        log.info('Opened an existing bloom filter: %s', bloom_filter_file)
    except FileNotFoundError:
        events_seen = BloomFilter(filter_capacity, filter_error_rate, bloom_filter_file)
        log.info('Created a new bloom filter: %s', bloom_filter_file)

    kube_api = client.CoreV1Api()
    watcher = watch.Watch()
    events = watcher.stream(kube_api.list_event_for_all_namespaces)
    try:
        skipped = 0
        log.info('Watching events...')
        for event in events:
            event_obj = event['object']
            event_name = event_obj.metadata.name

            if event_name in events_seen:
                skipped += 1
                continue
            else:
                if skipped > 0:
                    log.info('New event seen, after skipping %s previously seen events', skipped)
                skipped = 0

            event_data = event['raw_object']
            events_seen.add(event_name)
            assert event_name in events_seen
            json.dump(event_data, sys.stdout)
            sys.stdout.write('\n')
            sys.stdout.flush()
    except (SystemExit, KeyboardInterrupt):
        log.info('Terminating')
        events_seen.sync()
        return


def main():
    """Run kube-event-pipe."""
    log_level = environ.get('KUBE_EVENT_PIPE_LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=log_level)

    signal.signal(signal.SIGTERM, signal_to_system_exit)
    signal.signal(signal.SIGQUIT, signal_to_system_exit)

    persistence_path = Path(environ.get('KUBE_EVENT_PIPE_PERSISTENCE_PATH', '.')).resolve()
    try:
        filter_capacity = int(environ.get('KUBE_EVENT_PIPE_FILTER_CAPACITY', DEFAULT_CAPACITY))
        if filter_capacity <= 0:
            raise ValueError
    except ValueError:
        log.error('KUBE_EVENT_PIPE_FILTER_CAPACITY must be a positive integer')
        exit(1)

    try:
        filter_error_rate = float(environ.get('KUBE_EVENT_PIPE_FILTER_ERROR_RATE',
                                              DEFAULT_ERROR_RATE))
        if filter_error_rate <= 0:
            raise ValueError
    except ValueError:
        log.exception('KUBE_EVENT_PIPE_FILTER_ERROR_RATE must be a positive float')
        exit(1)

    log.info(
        'kube-event-pipe configuration: '
        'log level: %s, '
        'persistence path: %s, '
        'bloom filter capacity: %s '
        'bloom filter error rate: %s ',
        log_level, persistence_path, filter_capacity, filter_error_rate,
    )

    try:
        config.load_kube_config()
        log.info("Loaded kubeconfig")
    except config.ConfigException:
        config.load_incluster_config()
        log.info("Loaded in-cluster config")

    pipe_events(
        persistence_path=persistence_path,
        filter_capacity=filter_capacity,
        filter_error_rate=filter_error_rate,
    )
