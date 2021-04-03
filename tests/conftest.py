"""Test setup."""
import os
import signal
import json
import logging
from fcntl import fcntl, F_GETFL, F_SETFL
from contextlib import contextmanager
from functools import partial
import pytest  # type: ignore
from subprocess import Popen, PIPE
from typing import List, Iterator, Dict, Callable, ContextManager, Optional, IO
from pathlib import Path
from time import sleep
from kubernetes import client, config  # type: ignore
from kubernetes.client.models.v1_event import V1Event  # type: ignore
from kube_event_pipe.main import ENV_LOG_LEVEL, ENV_DESTINATION, ENV_PERSISTENCE_PATH
from tests.wait import wait_until, DEFAULT_TIMEOUT


TESTS_DIR = Path(__file__).parent


def make_kube_event(
    kube_api,
    name: Optional[str] = None,
    generate_name: str = 'test-event.',
    namespace: str = 'default',
    message: str = 'Test event',
    count: Optional[int] = None,
) -> V1Event:
    """Create a testing pod."""
    event = kube_api.create_namespaced_event(
        namespace,
        {
            'metadata': {'name': name} if name is not None else {'generateName': generate_name},
            'message': message,
            'count': count,
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


class KubeEventPipeHandle():
    """Kube-event-pipe process handler."""

    process: Popen
    output_path: Path
    output_file: IO
    rotated_files: List[Path]

    def __init__(self, process: Popen, output_path: Path):
        """Set up."""
        self.process = process
        self.output_path = output_path
        self._open_output()
        self.rotated_paths: List[Path] = []

    def _open_output(self):
        """Open the output file, which, if it's a pipe, needs to be made non-blocking."""
        self.output_file = self.output_path.open('r')
        existing_flags = fcntl(self.output_file, F_GETFL)
        fcntl(self.output_file, F_SETFL, existing_flags | os.O_NONBLOCK)

    def get_events(self, min_count: int = 0, timeout: float = DEFAULT_TIMEOUT) -> List[dict]:
        """
        Read `min_count` events or time out.

        :raise: tests.wait.Timeout
        """
        events = []

        def accumulate_events() -> List[Dict]:
            if self.output_file.closed:
                try:
                    self._open_output()
                except FileNotFoundError:
                    # No records appeared yet after rotaton.
                    return []
            new_events = [json.loads(e) for e in self.output_file.readlines()]
            events.extend(new_events)
            return events

        wait_until(accumulate_events, check=lambda f: len(f) >= min_count)

        return events

    def rotate_output(self) -> None:
        """Rotate the output file and reopen."""
        output_path = Path(self.output_file.name)
        rotated_path = output_path.with_suffix(f'{output_path.suffix}.1')
        output_path.rename(rotated_path)
        self.rotated_paths.append(rotated_path)
        self.output_file.close()

        self.process.send_signal(signal.SIGHUP)

    def close(self) -> None:
        """Tear down."""
        self.output_file.close()
        self.process.terminate()
        self.process.wait()


@contextmanager
def run_kube_event_pipe(
    tmpdir_path: Path,
    output_file_name: Optional[str] = 'filtered.log',
    state_subdir: str = '',
    env: Optional[Dict[str, str]] = None,
) -> Iterator[KubeEventPipeHandle]:
    """
    Run the program in a subprocess.

    If `output_file_name` is None, the process will write to stdout.
    """
    state_location = tmpdir_path / state_subdir
    state_location.mkdir(exist_ok=True)

    subprocess_env = os.environ.copy()
    subprocess_env.setdefault(ENV_LOG_LEVEL, 'DEBUG')
    if env is not None:
        subprocess_env.update(env)
    subprocess_env[ENV_PERSISTENCE_PATH] = str(state_location)

    if output_file_name is not None:
        output_path = tmpdir_path / output_file_name
        subprocess_env[ENV_DESTINATION] = str(output_path)
        stdout = None
    else:
        stdout = PIPE

    process = Popen(
        ['kube-event-pipe', ''],
        env=subprocess_env,
        stdout=stdout,
    )

    # If writing to stdout, open it.
    if stdout == PIPE:
        output_path = Path('/proc') / str(process.pid) / 'fd' / '1'

    # Let it read all events so far. There should be none.
    sleep(2)

    try:
        event_pipe = KubeEventPipeHandle(process=process, output_path=output_path)
        yield event_pipe
    finally:
        event_pipe.close()


KubeEventPipe = Callable[..., ContextManager[KubeEventPipeHandle]]


@pytest.fixture
def kube_event_pipe(
    kube_api, clean_kube, tmpdir_path: Path,
) -> KubeEventPipe:
    """Produce instances of the run_kube_event_pipe context manager."""
    return partial(run_kube_event_pipe, tmpdir_path)
