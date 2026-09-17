from praetorian_cli.ui.terminal import supports_fullscreen


class TtyStream:
    def isatty(self):
        return True


class ClosedStream:
    def isatty(self):
        raise ValueError('I/O operation on closed file')


def test_closed_terminal_stream_does_not_support_fullscreen():
    assert supports_fullscreen(ClosedStream(), TtyStream()) is False
    assert supports_fullscreen(TtyStream(), ClosedStream()) is False
