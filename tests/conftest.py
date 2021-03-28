"""Test setup."""
import os
import json
import logging
from contextlib import contextmanager
from functools import partial
import pytest  # type: ignore
from subprocess import Popen
from typing import List, Iterator, Dict, Callable, ContextManager
from pathlib import Path
from time import sleep
from kubernetes import client, config  # type: ignore
from kubernetes.client.models.v1_event import V1Event  # type: ignore
from kube_event_pipe.main import ENV_LOG_LEVEL, ENV_DESTINATION, ENV_PERSISTENCE_PATH


TESTS_DIR = Path(__file__).parent


def make_kube_event(
    kube_api,
    generate_name='test-event.',
    namespace='default',
    message='Test event',
) -> V1Event:
    """Create a testing pod."""
    event = kube_api.create_namespaced_event(
        namespace,
        {
            'metadata': {'generateName': generate_name},
            'message': message,
        },
    )
    return event


@pytest.fixture(autouse=True)
def logging_setup() -> None:
    """Set up logging in tests automatically."""
    logging.getLogger('kubernetes').setLevel('INFO')


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
    """Clean up events on startup, and other created Kubernetes resources on teardown."""
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
    output_file_name: str = 'filtered.log',
    state_subdir: str = '',
    env: Dict[str, str] = {},
) -> Iterator[Callable[[], List[dict]]]:
    """Run the program in a subprocess."""
    state_location = tmpdir_path / state_subdir
    state_location.mkdir(exist_ok=True)

    subprocess_env = os.environ.copy()
    subprocess_env.setdefault(ENV_LOG_LEVEL, 'DEBUG')
    subprocess_env.update(env)
    subprocess_env[ENV_PERSISTENCE_PATH] = str(state_location)

    output_file = tmpdir_path / output_file_name
    subprocess_env[ENV_DESTINATION] = str(output_file)
    process = Popen(
        ['kube-event-pipe', ''],
        env=subprocess_env
    )

    # Let it read all events so far. There should be none.
    sleep(2)

    try:
        with open(output_file, 'r') as output_readable:
            def read_events() -> List[dict]:
                return [json.loads(e) for e in output_readable.readlines()]

            yield read_events
    finally:
        process.terminate()
        process.wait()


KubeEventPipe = Callable[..., ContextManager[Callable[[], List[dict]]]]


@pytest.fixture
def kube_event_pipe(
    kube_api, clean_kube, tmpdir_path: Path,
) -> KubeEventPipe:
    """Produce instances of the run_kube_event_pipe context manager."""
    return partial(run_kube_event_pipe, tmpdir_path)
