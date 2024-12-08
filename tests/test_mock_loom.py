import asyncio

from seguin_loom_server.mock_loom import MockLoom


async def create_mock_loom() -> MockLoom:
    """Create a MockLoom and read (and check) the initial replies."""
    loom = MockLoom()
    for expected_reply in (
        b"=s1\r",
        b"=u0\r",
        b"=c00000000\r",
    ):
        async with asyncio.timeout(1):
            reply = await read_reply(loom)
            assert expected_reply == reply
    assert not loom.cmd_receiver.is_closing()
    assert not loom.reply_sender.at_eof()
    return loom


async def read_reply(loom: MockLoom, timeout: float = 1) -> bytes:
    async with asyncio.timeout(timeout):
        return await loom.reply_sender.readline()


async def write_command(loom: MockLoom, command: bytes, timeout: float = 1) -> None:
    loom.cmd_receiver.write(command)
    async with asyncio.timeout(timeout):
        await loom.cmd_receiver.drain()


async def test_get_status() -> None:
    loom = await create_mock_loom()
    await write_command(loom, b"=Q\r")
    reply = await read_reply(loom)
    assert reply == b"=s1\r"
    assert not loom.done_task.done()


async def test_set_direction() -> None:
    loom = await create_mock_loom()
    for direction in (0, 1, 0, 1):
        await write_command(loom, f"=U{direction:d}\r".encode())
        reply = await read_reply(loom)
        assert reply == f"=u{direction:d}\r".encode()
    assert not loom.done_task.done()


async def test_raise_shafts() -> None:
    loom = await create_mock_loom()
    for shaftword in (0x0, 0x1, 0x5, 0xFE, 0xFF19, 0xFFFFFFFE, 0xFFFFFFFF):
        await write_command(loom, f"=C{shaftword:08x}\r".encode())
        reply = await read_reply(loom)
        assert reply == f"=c{shaftword:08x}\r".encode()
    assert not loom.done_task.done()


async def test_oob_change_direction() -> None:
    loom = await create_mock_loom()
    for expected_direction in (1, 0, 1, 0, 1):
        await write_command(loom, b"=#d\r")
        reply = await read_reply(loom)
        assert reply == f"=u{expected_direction:d}\r".encode()
    assert not loom.done_task.done()


async def test_oob_next_pick() -> None:
    loom = await create_mock_loom()
    for _ in range(4):
        await write_command(loom, b"=#n\r")
        reply = await read_reply(loom)
        assert reply == b"=s5\r"
    assert not loom.done_task.done()


async def test_oob_toggle_error() -> None:
    loom = await create_mock_loom()
    for i in range(1, 5):
        expected_error = bool(i % 2)
        expected_status_word = 0x01 | (0x08 if expected_error else 0)
        await write_command(loom, b"=#e\r")
        assert loom.error_flag == expected_error
        reply = await read_reply(loom)
        assert reply == f"=s{expected_status_word:x}\r".encode()
    assert not loom.done_task.done()


async def test_oob_quit() -> None:
    loom = await create_mock_loom()
    await write_command(loom, b"=#q\r")
    async with asyncio.timeout(1):
        await loom.done_task
    assert loom.cmd_receiver.is_closing()
    assert loom.reply_sender.at_eof()
