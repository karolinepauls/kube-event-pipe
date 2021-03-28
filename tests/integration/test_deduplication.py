"""Test listening to and rejecting already seen messages."""
from typing import List, Dict
from tests.conftest import make_kube_event, KubeEventPipe
from tests.wait import wait_until


def test_run_event_pipe(kube_api, clean_kube, kube_event_pipe: KubeEventPipe) -> None:
    """Test watching and skipping seen events."""
    with kube_event_pipe(output_file_name='first.log') as get_events:
        assert get_events() == [], 'Expecting clean state'
        for _ in range(3):
            make_kube_event(kube_api)

        events = []

        def accumulate_events() -> List[Dict]:
            events.extend(get_events())
            return events

        events = wait_until(accumulate_events, check=lambda f: len(f) == 3)
        assert len(events) == 3

    with kube_event_pipe(output_file_name='second.log') as get_events:
        assert get_events() == [], 'The program, if restarted, should skip events already seen.'

    with kube_event_pipe(output_file_name='third.log', state_subdir='another') as get_events:
        same_events = get_events()

        for events_list in [same_events, events]:
            events_list.sort(key=lambda d: d['metadata']['name'])
        assert same_events == events, ('If using a different persistence file, we expect to see '
                                       'events already processed by the previous invocation')
