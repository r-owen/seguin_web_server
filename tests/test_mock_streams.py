import asyncio

from seguin_loom_server import mock_streams

TEST_BYTES = (
    b"one line\r",
    b"another line\r",
    b" \t \ta line with leading whitespace and an embedded null \0\r",
)


async def test_open_mock_connection() -> None:
    reader, writer = mock_streams.open_mock_connection()

    # Check initial state
    # Note: reader and writer are both instances of MockStream,
    # which acts as both a reader and a writer. So test some attributes
    # of each that a real reader or real writer would not have
    assert not reader.is_closing()
    assert not reader.at_eof()
    assert not writer.is_closing()
    assert not writer.at_eof()

    # Start a task that awaits wait_closed,
    # so we can see if it finishes when we close the writer.
    reader_closed_watcher = StreamClosedWatcher(reader)
    writer_closed_watcher = StreamClosedWatcher(writer)
    # Give watchers tasks a chance to start before chacking their state
    await asyncio.sleep(0)
    assert not reader_closed_watcher.wait_done
    assert not writer_closed_watcher.wait_done

    # Close the writer, which also closes the reader
    writer.close()
    assert reader.is_closing()
    assert reader.at_eof()
    assert writer.is_closing()
    assert writer.at_eof()
    # Give watchers tasks a chance to finish before chacking their state
    await asyncio.sleep(0)
    assert reader_closed_watcher.wait_done
    assert writer_closed_watcher.wait_done

    # wait_closed should have no further effect
    await writer.wait_closed()
    assert reader.is_closing()
    assert reader.at_eof()
    assert writer.is_closing()
    assert writer.at_eof()


async def test_stream() -> None:
    stream = mock_streams.MockStream()
    assert not stream.is_closing()
    assert not stream.at_eof()
    assert len(stream.queue) == 0

    # Read after each write
    for data in TEST_BYTES:
        stream.write(data)
        await stream.drain()
        assert len(stream.queue) == 1
        read_data = await stream.readline()
        assert read_data == data
        assert not stream.is_closing()
        assert not stream.at_eof()
        assert len(stream.queue) == 0

    # Queue up a batch of writes,
    # then drain them all at once,
    # then read all of them with readline
    for i, data in enumerate(TEST_BYTES):
        stream.write(data)
        assert len(stream.queue) == i + 1
    for i, data in enumerate(TEST_BYTES):
        assert stream.queue[i] == data
    await stream.drain()
    for data in TEST_BYTES:
        read_data = await stream.readline()
        assert read_data == data
        assert not stream.is_closing()
        assert not stream.at_eof()
    assert len(stream.queue) == 0

    # Queue up a batch of writes, draining after each write,
    # then read all data.
    for i, data in enumerate(TEST_BYTES):
        stream.write(data)
        await stream.drain()
        assert len(stream.queue) == i + 1
    for i, data in enumerate(TEST_BYTES):
        assert stream.queue[i] == data
    for data in TEST_BYTES:
        read_data = await stream.readline()
        assert read_data == data
        assert not stream.is_closing()
        assert not stream.at_eof()
    assert len(stream.queue) == 0


class StreamClosedWatcher:
    """Await writer.wait_closed() and wait_done=True when seen"""

    def __init__(self, writer: mock_streams.MockStream) -> None:
        self.writer = writer
        self.wait_done = False
        self.wait_task = asyncio.create_task(self.do_wait_closed())

    async def do_wait_closed(self) -> None:
        await self.writer.wait_closed()
        self.wait_done = True
