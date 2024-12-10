import asyncio
import contextlib

from seguin_loom_server.mock_loom import MockLoom


@contextlib.asynccontextmanager
async def create_loom():
    """Create a MockLoom and read (and check) the initial replies."""
    async with MockLoom() as loom:
        loom = MockLoom()
        for expected_reply in (
            b"=s1\r",
            b"=u0\r",
            b"=c00000000\r",
        ):
            async with asyncio.timeout(1):
                reply = await read_reply(loom)
                assert expected_reply == reply
        assert not loom.command_stream.is_closing()
        assert not loom.reply_stream.at_eof()
        yield loom


async def read_reply(loom: MockLoom, timeout: float = 1) -> bytes:
    async with asyncio.timeout(timeout):
        return await loom.reply_stream.readline()


async def write_command(loom: MockLoom, command: bytes, timeout: float = 1) -> None:
    loom.command_stream.write(command)
    async with asyncio.timeout(timeout):
        await loom.command_stream.drain()


async def test_get_status() -> None:
    async with create_loom() as loom:
        await write_command(loom, b"=Q\r")
        reply = await read_reply(loom)
        assert reply == b"=s1\r"
        assert not loom.done_task.done()


async def test_set_direction() -> None:
    async with create_loom() as loom:
        for direction in (0, 1, 0, 1):
            await write_command(loom, f"=U{direction:d}\r".encode())
            reply = await read_reply(loom)
            assert reply == f"=u{direction:d}\r".encode()
        assert not loom.done_task.done()


async def test_raise_shafts() -> None:
    async with create_loom() as loom:
        for shaftword in (0x0, 0x1, 0x5, 0xFE, 0xFF19, 0xFFFFFFFE, 0xFFFFFFFF):
            await write_command(loom, f"=C{shaftword:08x}\r".encode())
            reply = await read_reply(loom)
            assert reply == f"=c{shaftword:08x}\r".encode()
        assert not loom.done_task.done()


async def test_oob_change_direction() -> None:
    async with create_loom() as loom:
        for expected_direction in (1, 0, 1, 0, 1):
            cmdchar = "d"
            if expected_direction == 0:
                cmdchar = cmdchar.upper()
            await write_command(loom, f"=#{cmdchar}\r".encode())
            reply = await read_reply(loom)
            assert reply == f"=u{expected_direction:d}\r".encode()
        assert not loom.done_task.done()


async def test_oob_next_pick() -> None:
    async with create_loom() as loom:
        for i in range(4):
            cmdchar = "n"
            if i == 0:
                cmdchar = cmdchar.upper()
            await write_command(loom, f"=#{cmdchar}\r".encode())
            reply = await read_reply(loom)
            assert reply == b"=s5\r"
        assert not loom.done_task.done()


async def test_oob_toggle_error() -> None:
    async with create_loom() as loom:
        for i in range(1, 5):
            expected_error = bool(i % 2)
            expected_status_word = 0x01 | (0x08 if expected_error else 0)
            cmdchar = "e"
            if i == 0:
                cmdchar = cmdchar.upper()
            await write_command(loom, f"=#{cmdchar}\r".encode())
            await asyncio.sleep(0)
            assert loom.error_flag == expected_error
            reply = await read_reply(loom)
            assert reply == f"=s{expected_status_word:x}\r".encode()
        assert not loom.done_task.done()


async def test_oob_quit() -> None:
    async with create_loom() as loom:
        await write_command(loom, b"=#q\r")
        async with asyncio.timeout(1):
            await loom.done_task
        assert loom.command_stream.is_closing()
        assert loom.reply_stream.at_eof()
