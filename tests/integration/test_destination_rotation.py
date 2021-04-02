"""Testing rotation of the log file."""
from pathlib import Path
from tests.conftest import make_kube_event, KubeEventPipe


def test_logfile_rotation(kube_api, clean_kube, kube_event_pipe: KubeEventPipe) -> None:
    """Test reopening the log file on SIGHUP."""
    with kube_event_pipe(output_file_name='destination.log') as event_pipe:
        make_kube_event(kube_api)
        event_pipe.get_events(min_count=1)

        event_pipe.rotate_output()

        make_kube_event(kube_api)
        event_pipe.get_events(min_count=1)

        assert len(event_pipe.rotated_paths) == 1
        old_log = event_pipe.rotated_paths[0]
        new_log = event_pipe.output_path

        def read_log(log_file: Path):
            with log_file.open() as f:
                return f.readlines()

        old_contents = read_log(old_log)
        new_contents = read_log(new_log)
        assert old_contents != new_contents
        assert len(old_contents) == len(new_contents) == 1
