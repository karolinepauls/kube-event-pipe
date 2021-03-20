"""Entry point."""
import logging
from os import environ
from pathlib import Path
from kubernetes import client, config


log = logging.getLogger(__name__)


def pipe_events(
    persistence_path: Path,
):
    """List and watch, dedupicate, and write events to stdout."""
    kube_api = client.CoreV1Api()
    kube_ev1b1_api = client.ExtensionsV1beta1Api(client.ApiClient())

    try:
        import pdb
        pdb.set_trace()
    except SystemExit:
        return


def main():
    """Run kube-event-pipe."""
    log_level = environ.get('KUBE_EVENT_PIPE_LOG_LEVEL', 'info')
    logging.basicConfig(level=log_level)

    persistence_path = Path(environ['KUBE_EVENT_PIPE_PERSISTENCE_PATH'])

    log.info(
        'kube-event-pipe configuration: \n'
        'log level: %s, \n'
        'persistence path: %s, \n',
        log_level, persistence_path
    )

    try:
        config.load_kube_config()
        log.info("Loaded kubeconfig")
    except config.ConfigException:
        config.load_incluster_config()
        log.info("Loaded in-cluster config")

    pipe_events(persistence_path)
