"""Test setup."""
import signal
import os
import json
from contextlib import contextmanager
from functools import partial
import pytest  # type: ignore
from subprocess import Popen
from typing import List, Iterator, Dict, Callable, ContextManager
from pathlib import Path
from time import sleep
from kubernetes import client, config  # type: ignore


TESTS_DIR = Path(__file__).parent


@pytest.fixture
def tmpdir_path(tmpdir) -> Path:
    """Wrap pytest's `tmpdir` fixture to return a Path object."""
    return Path(str(tmpdir))


@pytest.fixture
def kube_api():
    """Connect to Kubernetes."""
    config.load_kube_config()
    api = client.CoreV1Api()
    return api


@pytest.fixture
def clean_kube(kube_api) -> Iterator[None]:
    """Clean up Kubernetes resources on teardown."""
    def get_resource(api_call):
        return {(i.metadata.name, i.metadata.namespace) for i in api_call().items}

    def get_resources():
        pods = get_resource(kube_api.list_pod_for_all_namespaces)
        services = get_resource(kube_api.list_service_for_all_namespaces)
        namespaces = {i.metadata.name for i in kube_api.list_namespace().items}
        return pods, services, namespaces

    resources_before = get_resources()

    # Clean events.
    for e in kube_api.list_event_for_all_namespaces().items:
        kube_api.delete_namespaced_event(e.metadata.name, e.metadata.namespace)

    yield

    resources_after_test = get_resources()
    created_pods, created_services, created_namespaces = [
        after - before for before, after in zip(resources_before, resources_after_test)
    ]
    for pod_name, pod_namespace in created_pods:
        kube_api.delete_namespaced_pod(pod_name, pod_namespace, grace_period_seconds=0)
    for service_name, service_namespace in created_services:
        kube_api.delete_namespaced_service(service_name, service_namespace, grace_period_seconds=0)
    for namespace in created_namespaces:
        kube_api.delete_namespace(namespace, grace_period_seconds=0)

    while True:
        resources_after_deletion = get_resources()
        if resources_after_deletion != resources_before:
            sleep(0.1)
        else:
            break


@contextmanager
def run_kube_event_pipe(
    tmpdir_path: Path,
    state_subdir: str = '',
    env: Dict[str, str] = {},
) -> Iterator[Callable[[], List[dict]]]:
    """Run the program in a subprocess."""
    state_location = tmpdir_path / state_subdir
    state_location.mkdir(exist_ok=True)

    subprocess_env = os.environ.copy()
    subprocess_env.update(env)
    subprocess_env['KUBE_EVENT_PIPE_PERSISTENCE_PATH'] = str(state_location)

    output_file = tmpdir_path / 'filtered.log'
    with output_file.open('w') as out:
        process = Popen(
            ['kube-event-pipe', ''],
            stdout=out,
            env=subprocess_env
        )

        sleep(0.5)  # Let it read all events so far.

        try:
            with output_file.open('r') as output_readable:

                def read_events() -> List[dict]:
                    return [json.loads(e) for e in output_readable.readlines()]

                yield read_events
        finally:
            process.send_signal(signal.SIGINT)
            process.wait()


@pytest.fixture
def kube_event_pipe(
    kube_api, clean_kube, tmpdir_path: Path,
) -> Callable[[], ContextManager[Callable[[], List[dict]]]]:
    """Produce instances of the run_kube_event_pipe context manager."""
    return partial(run_kube_event_pipe, tmpdir_path)
