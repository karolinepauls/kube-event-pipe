"""Making sure we don't break pipe output."""
import os
import signal
from pathlib import Path
from tests.conftest import make_kube_event, KubeEventPipe


def test_output_stdout(kube_api, clean_kube, kube_event_pipe: KubeEventPipe) -> None:
    """Test writing events to stdout."""
    with kube_event_pipe(output_file_name=None) as event_pipe:
        make_kube_event(kube_api)
        event_pipe.get_events(min_count=1)
        # SIGHUP will still make it reopen the file and even though it's a pipe, it should still
        # work.
        event_pipe.process.send_signal(signal.SIGHUP)
        make_kube_event(kube_api)
        event_pipe.get_events(min_count=1)


def test_output_pipe(
    kube_api, clean_kube, tmpdir_path: Path, kube_event_pipe: KubeEventPipe,
) -> None:
    """
    Test writing events to a pipe and rotating.

    I don't know why someone would rotate a pipe but by implementing FIFO output and reopening the
    output file, I made it possible. Let's make sure it doesn't regress.
    """
    destination = tmpdir_path / '1.pipe'
    os.mkfifo(destination)

    with kube_event_pipe(output_file_name=destination.name) as event_pipe:
        event_name_1 = 'first-event'
        make_kube_event(kube_api, name=event_name_1)
        [event] = event_pipe.get_events(min_count=1)
        assert event['metadata']['name'] == event_name_1
        # SIGHUP will still make it reopen the file and even though it's a pipe, it should still
        # work.
        destination.rename(destination.with_suffix('.renamed'))

        # Again, I don't know why someone would do this, but in order to still write to a pipe after
        # rotation, one has to create it.
        os.mkfifo(destination)
        event_pipe.rotate_output()

        event_name_2 = 'another-event'
        make_kube_event(kube_api, name=event_name_2)
        [event] = event_pipe.get_events(min_count=1)
        assert event['metadata']['name'] == event_name_2
