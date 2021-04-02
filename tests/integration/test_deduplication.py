"""Test listening to and rejecting already seen messages."""
import pytest
from tests.conftest import make_kube_event, KubeEventPipe
from tests.wait import Timeout


def test_run_event_pipe(kube_api, clean_kube, kube_event_pipe: KubeEventPipe) -> None:
    """Test watching and skipping seen events."""
    with kube_event_pipe(output_file_name='first.log') as get_events:
        assert get_events() == [], 'Expecting clean state'
        for _ in range(3):
            make_kube_event(kube_api)

        events = get_events(min_count=3)
        assert len(events) == 3

    with kube_event_pipe(output_file_name='second.log') as get_events:
        no_events = get_events()
        assert no_events == [], 'The program, if restarted, should skip events already seen.'

    with kube_event_pipe(output_file_name='third.log', state_subdir='another') as get_events:
        same_events = get_events()

        for events_list in [same_events, events]:
            events_list.sort(key=lambda d: d['metadata']['name'])
        assert same_events == events, ('If using a different persistence file, we expect to see '
                                       'events already processed by the previous invocation')


def test_event_identity(kube_api, clean_kube, kube_event_pipe: KubeEventPipe) -> None:
    """Ensure events are deduplicated by a tuple of key name and count."""
    with kube_event_pipe(output_file_name='first.log') as get_events:
        assert get_events() == [], 'Expecting clean state'

        event_name = 'single-event'
        event = make_kube_event(kube_api, name=event_name)
        namespaced_event = (event.metadata.name, event.metadata.namespace)
        for count in [2, 2, 2, 3]:
            kube_api.patch_namespaced_event(*namespaced_event, body={'count': count})

        kube_api.delete_namespaced_event(*namespaced_event)

        event_recreated = make_kube_event(kube_api, name=event_name)
        namespaced_event_recreated = (event_recreated.metadata.name,
                                      event_recreated.metadata.namespace)
        assert namespaced_event == namespaced_event_recreated
        for count in [2, 2, 2, 3]:
            kube_api.patch_namespaced_event(*namespaced_event_recreated, body={'count': count})

        events = get_events(min_count=3)
        assert len(events) == 3

        with pytest.raises(Timeout):
            get_events(min_count=1, timeout=1)
