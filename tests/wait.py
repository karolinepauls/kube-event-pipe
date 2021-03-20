"""Waiting for events."""
import time
from typing import Callable, TypeVar, Optional, Dict
from kubernetes.client.models.v1_pod import V1Pod  # type: ignore


def dict_to_selector(d: Dict[str, str]) -> str:
    """Build a Kubernetes API 'key=value,key2=value2' selector from a dict."""
    return ','.join(f'{k}={v}' for k, v in d.items())


Ret = TypeVar('Ret')


def wait_until(
    cond: Callable[[], Optional[Ret]],
    timeout: float = 15,
    interval: float = 0.1,
) -> Ret:
    """Poll until the condition is not falsy and return the value returned by `cond`."""
    start = time.monotonic()
    end = start + timeout
    while time.monotonic() <= end:
        val = cond()
        if val:
            return val
        time.sleep(interval)

    raise AssertionError("Condition not true in {} seconds".format(timeout))


def wait_for_ip(kube_api, pod: V1Pod) -> V1Pod:
    """Wait until pod's IP address is assigned and return updated pod object."""
    labels = pod.metadata.labels
    if labels is None:
        labels = {}

    def refresh_pod() -> Optional[str]:
        resp = kube_api.list_pod_for_all_namespaces(
            field_selector=(
                f'metadata.name={pod.metadata.name},'
                f'metadata.namespace={pod.metadata.namespace}'
            ),
            label_selector=dict_to_selector(labels))
        [fresh_pod] = resp.items
        if fresh_pod.status.pod_ip is None:
            return None
        else:
            return fresh_pod

    pod_with_ip = wait_until(refresh_pod)
    return pod_with_ip
