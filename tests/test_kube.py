"""Test listening to and rejecting already seen messages."""
from kubernetes.client.models.v1_pod import V1Pod  # type: ignore
from tests.wait import wait_for_ip


def make_kube_pod(
    kube_api,
    name='abc',
    namespace='default',
    wait=True,
    image='k8s.gcr.io/pause'
) -> V1Pod:
    """Create a testing pod."""
    pod = kube_api.create_namespaced_pod(
        namespace,
        body={
            'metadata': {
                'namespace': namespace,
                'name': name,
            },
            'spec': {
                'containers': [
                    {
                        'name': 'abc',
                        'image': image,
                    }
                ],
            }
        }
    )
    if wait:
        pod = wait_for_ip(kube_api, pod)
    return pod


def test_run_event_pipe(kube_api, clean_kube, kube_event_pipe) -> None:
    """Test watching and skipping seen events."""
    with kube_event_pipe() as get_events:
        assert get_events() == [], 'Expecting clean state'
        make_kube_pod(kube_api)
        events = get_events()
        messages = [e['message'] for e in events]
        assert len(messages) > 2
        assert messages[-1] == 'Started container abc'

    with kube_event_pipe() as get_events:
        assert get_events() == [], 'The program, if restarted, should skip events already seen.'

    with kube_event_pipe(state_subdir='another') as get_events:
        same_events = get_events()
        assert same_events == events, ('If using a different persistence file, we expect to see '
                                       'events already processed by the previous invocation')
