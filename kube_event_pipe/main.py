"""Entry point."""
import logging
from os import environ
from pathlib import Path
from pybloomfilter import BloomFilter  # type: ignore
from kubernetes import client, config, watch  # type: ignore


log = logging.getLogger(__name__)


def pipe_events(
    persistence_path: Path,
):
    """List and watch, deduplicate, and write events to stdout."""
    bloom_filter_file = str(persistence_path / 'filter.bloom')
    try:
        events_seen = BloomFilter.open(bloom_filter_file)
        log.info('Opened an existing bloom filter: %s', bloom_filter_file)
    except FileNotFoundError:
        events_seen = BloomFilter(10000000, 0.01, bloom_filter_file)
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
            print(event_data)
    except SystemExit:
        events_seen.sync()
        return


def main():
    """Run kube-event-pipe."""
    log_level = environ.get('KUBE_EVENT_PIPE_LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=log_level)

    persistence_path = Path(environ.get('KUBE_EVENT_PIPE_PERSISTENCE_PATH', '.')).resolve()

    log.info(
        'kube-event-pipe configuration: \n'
        'log level: %s, \n'
        'persistence path: %s, \n',
        log_level, persistence_path,
    )

    try:
        config.load_kube_config()
        log.info("Loaded kubeconfig")
    except config.ConfigException:
        config.load_incluster_config()
        log.info("Loaded in-cluster config")

    pipe_events(persistence_path)
