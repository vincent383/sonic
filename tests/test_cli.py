def test_devices_command_is_available(capsys):
    from sonic_transfer.cli import main

    assert main(["devices"]) == 0
    assert "audio" in capsys.readouterr().out.lower()


def test_send_missing_file_returns_nonzero(capsys):
    from sonic_transfer.cli import main

    assert main(["send", "/does/not/exist"]) != 0
    assert "error" in capsys.readouterr().err.lower()
