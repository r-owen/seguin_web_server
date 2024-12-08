__all__ = ["MockStreamReader", "MockStreamWriter", "open_mock_connection"]

import asyncio
import collections
from collections.abc import Awaitable, Callable
from typing import Deque

# TO DO: when we require Python 3.12 and later, change this to
# ``type WriterCallbackType = ...``
# It is not needed in this case, but does add some clarity.
WriterCallbackType = Callable[[str], Awaitable[None]]


class MockStreamReader:
    """Minimal mock stream reader that only supports readline.

    Intended to be constructed by `open_mock_connection`.
    """

    def __init__(self) -> None:
        self.queue: Deque[bytes] = collections.deque()
        self.data_available_event = asyncio.Event()
        self.shaft_word = 0
        self.isopen = True

    def appendline(self, str_data: str) -> None:
        """Append a line of str data to be read by readline.

        This method is not part of the standard API for StreamReader.
        It is intended for use by the writer to the stream,
        which is the end not expecting a true StreamReader.

        Parameters
        ----------
        str_data : str
            Data as a str (not bytes). This should be properly terminated
            as this class only deals with terminated strings. It should also
            be encodable to bytes using the default encoder.
        """
        self.queue.append(str_data.encode())
        self.data_available_event.set()

    def at_eof(self) -> bool:
        return not self.isopen

    async def readline(self) -> bytes:
        while not self.queue:
            self.data_available_event.clear()
            await self.data_available_event.wait()
        self.data_available_event.clear()
        if not self.isopen:
            return b""
        data = self.queue.popleft()
        return data


class MockStreamWriter:
    """Minimal mock stream writer that assumes each write is a line.

    Intended to be constructed by `open_mock_connection`.

    Parameters
    ----------
    async_callback : callable
        An async function that will be called when `drain` is called,
        once for every message written since the last call to `drain`.
        It receives one positional argument: a line of data as an
        unterminated str (decoded bytes).
    reader : MockStreamReader
        If specified (and `open_mock_connection` does specify it),
        this writer sets ``reader.isopen`` false when the writer is closed.
        This makes closing a writer/reader pair more realistic.
    """

    def __init__(
        self, async_callback: WriterCallbackType, reader: MockStreamReader | None = None
    ) -> None:
        self.queue: Deque[bytes] = collections.deque()
        self.async_callback = async_callback
        self.reader = reader
        self.isopen = True

    def _assert_open(self) -> None:
        if not self.isopen:
            raise RuntimeError("MockStreamWriter is closed")

    def close(self) -> None:
        print("MockStreamWriter.close()")
        self.isopen = False
        if self.reader is not None:
            self.reader.isopen = False

    def is_closing(self) -> bool:
        return not self.isopen

    async def drain(self) -> None:
        self._assert_open()
        while self.queue:
            str_data = self.queue.popleft().decode().rstrip()
            await self.async_callback(str_data)

    async def wait_closed(self) -> None:
        return

    def write(self, data: bytes) -> None:
        print(f"MockStreamWriter.write({data!r}); {self.isopen=}")
        self._assert_open()
        self.queue.append(data)


def open_mock_connection(
    async_callback: WriterCallbackType,
) -> tuple[MockStreamReader, MockStreamWriter]:
    """Create a mock stream reader and writer pair.

    Parameters
    ----------
    async_callback : callable
        An async function that will be called when `drain` is called,
        once for every message written since the last call to `drain`.
        It receives one positional argument: a line of data as an
        unterminated str (decoded bytes).
    """
    reader = MockStreamReader()
    writer = MockStreamWriter(async_callback=async_callback, reader=reader)
    return (reader, writer)
