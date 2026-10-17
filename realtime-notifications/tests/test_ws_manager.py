import pytest

from app.ws import ConnectionManager


class FakeWS:
    def __init__(self, fail=False):
        self.fail, self.sent, self.accepted = fail, [], False

    async def accept(self):
        self.accepted = True

    async def send_text(self, text):
        if self.fail:
            raise RuntimeError("socket fechado")
        self.sent.append(text)


async def test_only_target_user_receives():
    m = ConnectionManager()
    a, b = FakeWS(), FakeWS()
    await m.connect("1", a)
    await m.connect("2", b)
    await m.send_to_user("1", "oi")
    assert a.sent == ["oi"] and b.sent == [] and a.accepted


async def test_dead_socket_is_dropped():
    m = ConnectionManager()
    dead, ok = FakeWS(fail=True), FakeWS()
    await m.connect("1", dead)
    await m.connect("1", ok)
    await m.send_to_user("1", "x")
    await m.send_to_user("1", "y")
    assert ok.sent == ["x", "y"]
