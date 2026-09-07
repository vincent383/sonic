def test_receiver_buffers_out_of_order_and_releases_contiguous_data():
    from sonic_transfer.arq import ReceiverWindow

    receiver = ReceiverWindow(4)
    assert receiver.receive(1, b"b") == []
    assert receiver.receive(0, b"a") == [b"a", b"b"]
    assert receiver.receive(1, b"duplicate") == []
    assert receiver.ack_state() == (1, ())


def test_sender_reports_timeout_and_acknowledges():
    from sonic_transfer.arq import SenderWindow

    sender = SenderWindow(2, timeout=1.0)
    sender.queue(0, b"a", now=0.0)
    assert sender.due(0.5) == []
    assert sender.due(1.1) == [(0, b"a")]
    sender.acknowledge(0)
    assert sender.complete
