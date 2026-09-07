def test_devices_command_is_available(capsys):
    from sonic_transfer.cli import main

    assert main(["devices"]) == 0
    assert "audio" in capsys.readouterr().out.lower()
