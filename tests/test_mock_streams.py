import asyncio

import pytest

from seguin_loom_server import mock_streams

TEST_BYTES = (
    b"one line\r",
    b"another line\r",
    b" \t \ta line with leading whitespace and an embedded null \0\r",
)


async def test_open_mock_connection() -> None:
    written_lines: list[str] = []

    async def writer_callback(data: str) -> None:
        written_lines.append(data)

    reader, writer = mock_streams.open_mock_connection(async_callback=writer_callback)

    # Check initial state
    assert reader.isopen
    assert not reader.at_eof()
    assert not writer.closed_event.is_set()
    assert not writer.is_closing()

    # Start a task that awaits wait_closed,
    # so we can see if it finishes when we close the writer.
    close_watcher = CloseWatcher(writer)
    # Give the watcher's task a chance to start before chacking its state
    await asyncio.sleep(0)
    assert not close_watcher.wait_done

    # Close the writer, which also closes the reader
    writer.close()
    assert not reader.isopen
    assert reader.at_eof()
    assert writer.closed_event.is_set()
    assert writer.is_closing()
    # Give the watcher's task a chance to start before chacking its state
    await asyncio.sleep(0)
    assert close_watcher.wait_done

    # wait_closed should have no further effect
    await writer.wait_closed()
    assert not reader.isopen
    assert reader.at_eof()
    assert writer.closed_event.is_set()
    assert writer.is_closing()


async def test_reader() -> None:
    reader = mock_streams.MockStreamReader()
    assert reader.isopen
    assert not reader.at_eof()
    assert len(reader.queue) == 0

    # Alternate between appendline and readline
    for data in TEST_BYTES:
        datastr = data.decode()
        reader.appendline(datastr)
        assert len(reader.queue) == 1
        read_data = await reader.readline()
        assert read_data == data
        assert reader.isopen
        assert not reader.at_eof()
        assert len(reader.queue) == 0

    # Queue up a batch of readline,
    # then read all of them with readline
    for data in TEST_BYTES:
        datastr = data.decode()
        reader.appendline(datastr)
    assert len(reader.queue) == len(TEST_BYTES)
    for i, data in enumerate(TEST_BYTES):
        assert reader.queue[i] == data

    for i, data in enumerate(TEST_BYTES):
        read_data = await reader.readline()
        assert read_data == data
        assert reader.isopen
        assert not reader.at_eof()
    assert len(reader.queue) == 0


async def test_mock_writer() -> None:
    written_lines: list[str] = []

    async def writer_callback(data: str) -> None:
        written_lines.append(data)

    writer = mock_streams.MockStreamWriter(async_callback=writer_callback)
    assert not writer.closed_event.is_set()

    # Test write+drain
    for data in TEST_BYTES:
        writer.write(data)
        await writer.drain()
        assert written_lines[-1] == data.decode().rstrip()

    # Test that data is not written until drain is called
    written_lines = []
    for data in TEST_BYTES:
        writer.write(data)
    assert len(written_lines) == 0
    await writer.drain()
    assert written_lines == [item.decode().rstrip() for item in TEST_BYTES]

    writer.close()
    with pytest.raises(RuntimeError):
        writer.write(data)
    assert writer.closed_event.is_set()


class CloseWatcher:
    """Await writer.wait_closed() and wait_done=True when seen"""

    def __init__(self, writer: mock_streams.MockStreamWriter) -> None:
        self.writer = writer
        self.wait_done = False
        self.wait_task = asyncio.create_task(self.do_wait_closed())

    async def do_wait_closed(self) -> None:
        await self.writer.wait_closed()
        self.wait_done = True
