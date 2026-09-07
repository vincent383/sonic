import random

import pytest


def test_modem_round_trip_and_normalized_samples():
    from sonic_transfer.modem import Modem, ModemConfig

    modem = Modem(ModemConfig(sample_rate=8000, mode="robust"))
    data = bytes(random.Random(7).randrange(256) for _ in range(23))
    samples = modem.encode(data)
    assert max(abs(x) for x in samples) <= 1.0
    assert modem.decode(samples) == data


def test_virtual_channel_can_report_corruption():
    from sonic_transfer.modem import DecodeError, Modem, ModemConfig
    from sonic_transfer.virtual_channel import VirtualChannel

    modem = Modem(ModemConfig(sample_rate=8000))
    samples = VirtualChannel(noise=0.8, seed=1).transmit(modem.encode(b"payload"))
    with pytest.raises(DecodeError):
        modem.decode(samples)
