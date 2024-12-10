from __future__ import annotations

__all__ = ["MockStream", "open_mock_connection"]

import asyncio
import collections
import weakref
from typing import Deque


class MockStream:
    """Minimal mock stream reader/writer that only supports line-oriented data.

    Intended to be constructed by `open_mock_connection`,
    so that each stream can close its sibling.

    Example of use:

    * A mock server may use a pair of mock streams created by
      `open_mock_connection`. I suggest names "command_stream"
      (which the server reads from) and "reply_stream" (which the
      server writes to).
    * The client using the mock server will communicate via
      those same streams, writing commands to "command_stream"
      and reading replies from "reply_stream".
      Hence the recommended names, to avoid confusion.
      (If the server used names "command_reader" and "reply_writer",
      the client ends up writing to the so-called reader
      and reading from the so-called writer.)
    * Either end can close the connection by calling "close"
      and "wait_closed" on the stream it writes to.
    * Note that with some extra code to create the streams differently,
      on demand, you have the option to communicate with the mock server
      with real streams. In this scenerio you would normally use mock streams,
      e.g. for most unit tests, but can also run or test with real streams,
      to make sure you are using the mock streams correctly.
    """

    def __init__(self) -> None:
        self.closed_event = asyncio.Event()
        self.data_available_event = asyncio.Event()
        self.queue: Deque[bytes] = collections.deque()
        self.shaft_word = 0
        self.sibling: weakref.ProxyType[MockStream] | None = None

    def _set_sibling(self, stream: MockStream) -> None:
        self.sibling = weakref.proxy(stream)

    def at_eof(self) -> bool:
        return self.is_closing()

    async def readline(self) -> bytes:
        while not self.queue:
            self.data_available_event.clear()
            if self.is_closing():
                return b""
            await self.data_available_event.wait()
        if self.is_closing():
            return b""
        data = self.queue.popleft()
        if not self.queue:
            self.data_available_event.clear()
        return data

    def close(self) -> None:
        self.closed_event.set()
        if self.sibling is not None and not self.sibling.closed_event.set():
            # Avoid infinite recursion
            sibling, self.sibling = self.sibling, None
            sibling.close()

    def is_closing(self) -> bool:
        return self.closed_event.is_set()

    async def drain(self) -> None:
        if self.is_closing():
            return
        self.data_available_event.set()

    async def wait_closed(self) -> None:
        await self.closed_event.wait()

    def write(self, data: bytes) -> None:
        if self.is_closing():
            return
        self.queue.append(data)


def open_mock_connection() -> tuple[MockStream, MockStream]:
    """Create a mock stream reader, writer pair.

    The pair is connected, so that closing one will close the other.
    """
    reader = MockStream()
    writer = MockStream()
    reader._set_sibling(writer)
    writer._set_sibling(reader)
    return (reader, writer)
