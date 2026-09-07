import threading


def test_sender_and_receiver_transfer_over_memory(tmp_path):
    from sonic_transfer.session import MemoryDuplex, ReceiverSession, SenderSession

    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(256)) * 20)
    left, right = MemoryDuplex.pair()
    result = {}

    def receive():
        result["stats"] = ReceiverSession(right).run(tmp_path / "out", resume=False)

    thread = threading.Thread(target=receive)
    thread.start()
    sent = SenderSession(left).run(source)
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert (tmp_path / "out" / source.name).read_bytes() == source.read_bytes()
    assert sent.bytes_sent == source.stat().st_size
