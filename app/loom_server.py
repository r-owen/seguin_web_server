from __future__ import annotations

__all__ = ["LoomServer"]

import asyncio
import dataclasses
import enum
import io
import json
import traceback
from types import SimpleNamespace, TracebackType
from typing import Any, Type

from dtx_to_wif import read_dtx, read_wif
from fastapi import WebSocket, WebSocketDisconnect

from . import client_replies
from .mock_loom import MockLoom, Terminator
from .mock_streams import MockStreamReader, MockStreamWriter
from .reduced_pattern import Pick, ReducedPattern, reduced_pattern_from_pattern_data

# The maximum number of patterns that can be in the history
MaxPatterns = 20


class CloseCode(enum.IntEnum):
    """WebSocket close codes

    A subset from
    https://www.rfc-editor.org/rfc/rfc6455.html#section-7.4
    """

    Normal = 1000
    GoingAway = 1001
    Error = 1011


class CommandError(Exception):
    pass


async def close_websocket(
    ws: WebSocket, code: CloseCode = CloseCode.Normal, reason: str = ""
) -> None:
    """Close a websocket using best effort and a short timeout."""
    try:
        async with asyncio.timeout(0.1):
            await ws.close(code, reason)
    except Exception as e:
        print(f"Failed to close websocket: {e!r}")


class LoomServer:
    """Communicate with the client software and the loom.

    The preferred way to create and run a LoomServer is to call
    LoomServer.amain(...).

    Parameters
    ----------
    emulate_loom : bool
        If True, connect to a mock loom, instead of a real loom.
    verbose : bool
        If True, print diagnostic information to stdout.
    """

    def __init__(self, emulate_loom: bool, verbose: bool) -> None:
        self.websocket: WebSocket | None = None
        self.emulate_loom = emulate_loom
        self.verbose = verbose
        self.connecting = False
        self.disconnecting = False
        self.client_connected = False
        self.mock_loom: MockLoom | None = None
        self.loom_reader: asyncio.StreamReader | MockStreamReader | None = None
        self.loom_writer: asyncio.StreamWriter | MockStreamWriter | None = None
        self.read_client_task: asyncio.Future = asyncio.Future()
        self.read_loom_task: asyncio.Future = asyncio.Future()
        self.done_task: asyncio.Future = asyncio.Future()
        self.current_pattern: ReducedPattern | None = None
        self.pattern_dict: dict[str, ReducedPattern] = dict()
        self.weave_forward = True
        self.loom_error_flag = False
        self.command_dispatch_table = dict(
            clear_pattern_names=self.cmd_clear_pattern_names,
            file=self.cmd_file,
            jump_to_pick=self.cmd_jump_to_pick,
            select_pattern=self.cmd_select_pattern,
            weave_direction=self.cmd_weave_direction,
            oobcommand=self.cmd_oobcommand,
        )

    async def add_pattern(self, pattern: ReducedPattern) -> None:
        """Add a pattern to self.pattern_dict.

        Also purge the MaxPatterns oldest entries (excluding
        the current pattern, if any) and report the new list
        of pattern names to the client.
        """
        current_name = (
            None if self.current_pattern is None else self.current_pattern.name
        )
        self.pattern_dict[pattern.name] = pattern
        for name in list(self.pattern_dict.keys())[:-MaxPatterns]:
            if name != current_name:
                del self.pattern_dict[name]
        await self.report_pattern_names()

    async def clear_pattern_dict(self) -> None:
        """Clear self.pattern_dict, except for the current pattern (if any).

        Report the new list of pattern names to the client.
        """
        self.pattern_dict = dict()
        if self.current_pattern is not None:
            await self.add_pattern(self.current_pattern)
        else:
            await self.report_pattern_names()

    @property
    def connected(self) -> bool:
        """Return True if connected to the loom."""
        return not (
            self.loom_writer is None
            or self.loom_reader is None
            or self.loom_writer.is_closing()
            or self.loom_reader.at_eof()
        )

    async def connect(self) -> None:
        """Connect to the loom.

        If already connected, disconnect first.
        """
        if self.connected:
            await self.disconnect()
        try:
            self.connecting = True
            await self.report_connection_state()
            if self.emulate_loom:
                self.mock_loom = MockLoom(verbose=True)
                self.loom_reader = self.mock_loom.reply_sender
                self.loom_writer = self.mock_loom.cmd_receiver
            else:
                raise RuntimeError("Real loom connection not yet supported")
        finally:
            self.connecting = False
            await self.report_connection_state()

        self.read_loom_task = asyncio.create_task(self.read_loom_loop())

    async def run_client(self, websocket: WebSocket) -> None:
        """Run a client connection, closing any existing connection.

        Also open a connection to the loom, if that was closed.

        Parameters
        ----------
        websocket : WebSocket
            Connection to the client.
        """
        if self.client_connected:
            print("A client was already connected; closing that connection")
            await self.disconnect_client()
        await websocket.accept()
        self.websocket = websocket
        self.read_client_task = asyncio.create_task(self.read_client_loop())
        if not self.connected:
            try:
                await self.connect()
            except Exception as e:
                print(f"Could not connect to the loom: {e!r}")
        await self.done_task

    async def disconnect_client(self, cancel_read_client_loop: bool = True) -> None:
        self.read_client_task.cancel()
        websocket = self.websocket
        self.websocket = None
        if websocket is not None:
            await close_websocket(
                websocket, code=CloseCode.GoingAway, reason="another client barged in"
            )

    async def disconnect(self) -> None:
        """Disconnect from the loom. A no-op if already disconnected."""

        if not self.connected:
            return
        self.disconnecting = True
        await self.report_connection_state()
        try:
            if self.loom_writer is not None:
                self.loom_writer.close()
                self.loom_reader = None
                self.loom_writer = None
            self.mock_loom = None
        finally:
            self.disconnecting = False
            await self.report_connection_state()

    async def command_pick(self, pick: Pick) -> None:
        """Send an =C<shaft_word> pick command to the loom"""
        shaft_word = sum(1 << i for i, isup in enumerate(pick.are_shafts_up) if isup)
        await self.command_loom(f"=C{shaft_word:08x}")

    async def command_loom(self, cmd: str) -> None:
        """Send a command to the loom.

        Parameters
        ----------
        cmd : str
            The command to send, without a terminator.
            (This method will append the terminator).
        """
        if self.loom_writer is None or self.loom_writer.is_closing():
            raise RuntimeError("Cannot write to the loom: no connection.")
        cmd_bytes = (cmd + Terminator).encode()
        if self.verbose:
            print(f"Sending command to loom: {cmd_bytes!r}")
        self.loom_writer.write(cmd_bytes)
        await self.loom_writer.drain()

    def increment_pick_number(self) -> int:
        """Increment pick_number in the specified direction.

        Increment repeat_number as well, if appropriate.

        Return the new pick number. This will be 0 if repeat_number changed,
        or if unweaving and repeat_number would be decremented to 0.
        """
        if self.current_pattern is None:
            return 0
        return self.current_pattern.increment_pick_number(
            weave_forward=self.weave_forward
        )

    async def cmd_clear_pattern_names(self, command: SimpleNamespace) -> None:
        await self.clear_pattern_dict()

    async def cmd_file(self, command: SimpleNamespace) -> None:
        filename = command.name
        try:
            if self.verbose:
                print(
                    f"Read weaving pattern {filename!r}: data={command.data[0:40]!r}...",
                )
            if filename.lower().endswith(".dtx"):
                with io.StringIO(command.data) as dtx_file:
                    pattern_data = read_dtx(dtx_file)
            elif filename.lower().endswith(".wif"):
                with io.StringIO(command.data) as wif_file:
                    pattern_data = read_wif(wif_file)
            else:
                raise CommandError(
                    f"Cannot load pattern {filename!r}: unsupported file type"
                )
            pattern = reduced_pattern_from_pattern_data(
                name=command.name, data=pattern_data
            )
            await self.add_pattern(pattern)

        except Exception as e:
            print(f"Failed to read pattern {filename!r}: {e!r}")

    async def cmd_jump_to_pick(self, command: SimpleNamespace) -> None:
        jump_to_pick_number = command.pick_number
        if self.current_pattern is None:
            raise CommandError("Cannot jump to a pick: no pattern")
        try:
            self.current_pattern.set_current_pick_number(jump_to_pick_number)
        except IndexError:
            raise CommandError(
                f"Invalid jump pick number {jump_to_pick_number} < 0 or "
                f"> {len(self.current_pattern.picks)}"
            )
        if self.current_pattern.pick_number > 0:
            pick = self.current_pattern.get_current_pick()
            await self.command_pick(pick)
        await self.report_pick_number()

    async def cmd_select_pattern(self, command: SimpleNamespace) -> None:
        name = command.name
        if self.current_pattern is not None and self.current_pattern.name == name:
            return
        pattern = self.pattern_dict.get(name)
        if pattern is None:
            raise CommandError(f"select_pattern failed: no such pattern: {name}")
        self.current_pattern = pattern
        await self.report_current_pattern()
        await self.report_pick_number()

    async def cmd_weave_direction(self, command: SimpleNamespace) -> None:
        # Warning: this code assumes that the loom server sends "=u"
        # after it receives "=U". It is not clear from the manual
        # if that is actually the case.
        loom_command = f"=U{int(not command.forward)}"
        await self.command_loom(loom_command)

    async def cmd_oobcommand(self, command: SimpleNamespace) -> None:
        await self.command_loom(f"=#{command.command}")

    async def reply_to_client(self, reply: Any) -> None:
        """Send a reply to the client.

        Parameters
        ----------
        reply : dataclasses.dataclass
            The reply as a dataclass. It should have a "type" field
            whose value is a string.
        """
        if self.client_connected:
            assert self.websocket is not None
            reply_dict = dataclasses.asdict(reply)
            if self.verbose:
                reply_str = str(reply_dict)
                if len(reply_str) > 120:
                    reply_str = reply_str[0:120] + "..."
                print(f"LoomServer reply to client: {reply_str}")
            await self.websocket.send_json(reply_dict)
        else:
            if self.verbose:
                print(f"Could not send reply {reply} to client: not connected")

    async def report_connection_state(self) -> None:
        """Report ConnectionState to the client."""
        state = client_replies.ConnectionStateEnum.Disconnected
        if self.connecting:
            state = client_replies.ConnectionStateEnum.Connecting
        elif self.connecting:
            state = client_replies.ConnectionStateEnum.Disconnecting
        elif self.connected:
            state = client_replies.ConnectionStateEnum.Connected
        reply = client_replies.ConnectionState(state=state)
        await self.reply_to_client(reply)

    async def report_current_pattern(self) -> None:
        """Report pattern to the client"""
        if self.current_pattern is not None:
            await self.reply_to_client(self.current_pattern)

    async def report_pattern_names(self) -> None:
        """Report PatternNames to the client."""
        names = list(self.pattern_dict.keys())
        if self.current_pattern is not None:
            current_name = self.current_pattern.name
            if current_name not in names:
                names.append(current_name)
        reply = client_replies.PatternNames(names=names)
        await self.reply_to_client(reply)

    async def report_loom_state(self, state_word: int) -> None:
        """Report LoomState to the client."""
        reply = client_replies.LoomState.from_state_word(state_word)
        await self.reply_to_client(reply)

    async def report_pick_number(self) -> None:
        """Report CurrentPickNumber to the client."""
        if self.current_pattern is None:
            return
        reply = client_replies.CurrentPickNumber(
            pick_number=self.current_pattern.pick_number,
            repeat_number=self.current_pattern.repeat_number,
        )
        await self.reply_to_client(reply)

    async def report_weave_direction(self) -> None:
        """Report WeaveDirection"""
        client_reply = client_replies.WeaveDirection(forward=self.weave_forward)
        await self.reply_to_client(client_reply)

    async def close(
        self, stop_read_loom: bool = True, stop_read_client: bool = True
    ) -> None:
        """Disconnect from client and loom and stop all tasks."""
        if self.loom_writer is not None:
            if stop_read_loom:
                self.read_loom_task.cancel()
            if stop_read_client:
                self.read_client_task.cancel()
            self.loom_writer.close()
        if not self.done_task.done():
            self.done_task.set_result(None)

    async def read_client_loop(self) -> None:
        """Read and process commands from the client."""
        # report loom connection state
        # and (if connected) request loom status
        try:
            self.client_connected = True
            await self.report_connection_state()
            await self.report_pattern_names()
            await self.report_weave_direction()
            await self.report_current_pattern()
            await self.report_pick_number()
            if self.connected:
                # request loom status
                await self.command_loom("=Q")
            else:
                await self.connect()
            while self.client_connected:
                assert self.websocket is not None
                try:
                    data = await self.websocket.receive_json()
                except json.JSONDecodeError:
                    print("Ignoring client message: not json-encoded")
                    continue

                # Parse the command
                try:
                    cmd_type = data.get("type")
                    if cmd_type is None:
                        print(f"Ignoring client command {data!r}: no 'type' field")
                        continue
                    command = SimpleNamespace(**data)
                    if self.verbose:
                        msg_summary = str(command)
                        if len(msg_summary) > 80:
                            msg_summary = msg_summary[0:80] + "..."
                        print(f"Read client command {msg_summary}")
                    cmd_handler = self.command_dispatch_table.get(cmd_type)
                except Exception as e:
                    print(f"Client command {data} failed: {e!r}")
                    traceback.print_exc()

                # Execute the command
                try:
                    if cmd_handler is None:
                        print(f"Client command {command} failed: unknown type")
                        continue
                    await cmd_handler(command)
                except CommandError as e:
                    print(f"Client command {command} failed: {e!r}")
                except Exception as e:
                    print(f"Client command {command} failed: {e!r}")
                    traceback.print_exc()

        except WebSocketDisconnect:
            print("Client disconnected")
            return
        except Exception as e:
            print(f"read_client_loop failed: {e!r}")
            traceback.print_exc()
            self.client_connected = False
            if self.websocket is not None:
                await close_websocket(
                    self.websocket, code=CloseCode.Error, reason=repr(e)
                )

    async def read_loom_loop(self) -> None:
        """Read and process replies from the loom."""
        try:
            if self.loom_reader is None:
                raise RuntimeError("No loom reader")
            while True:
                reply_bytes = await self.loom_reader.readline()
                if self.verbose:
                    print(f"Read loom reply: {reply_bytes!r}")
                if not reply_bytes:
                    return
                reply = reply_bytes.decode().strip()
                if len(reply) < 2:
                    print(f"Invalid loom reply {reply!r}: less than 2 chars")
                if reply[0] != "=":
                    print(f"Invalid loom reply {reply!r}: must start with =")
                reply_char = reply[1]
                reply_data = reply[2:]
                match reply_char:
                    case "c":
                        # Actual shafts that are up
                        pass
                    case "u":
                        # Weave direction
                        # The loom expects a new pick, as a result
                        if reply_data == "0":
                            self.weave_forward = True
                        elif reply_data == "1":
                            self.weave_forward = False
                        else:
                            print(
                                f"Invalid loom reply {reply!r}: direction must be 0 or 1"
                            )
                            continue

                        await self.report_weave_direction()

                        # Command a new pick, if there is one.
                        if self.current_pattern is None:
                            continue
                        new_pick_number = self.increment_pick_number()
                        if new_pick_number > 0:
                            pick = self.current_pattern.get_current_pick()
                            await self.command_pick(pick)
                        await self.report_pick_number()
                    case "s":
                        # Loom status (may include a request for the next pick)
                        state_word = int(reply_data, base=16)
                        await self.report_loom_state(state_word)

                        # Check for error flag
                        error_flag = bool(state_word & 0x8)
                        if error_flag != self.loom_error_flag:
                            self.loom_error_flag = error_flag
                            if self.verbose:
                                print(f"Loom error flag changed to {error_flag}")

                        pick_wanted = bool(state_word & 0x4)
                        if pick_wanted and self.current_pattern is not None:
                            # Command a new pick, if there is one.
                            new_pick_number = self.increment_pick_number()
                            if new_pick_number > 0:
                                pick = self.current_pattern.get_current_pick()
                                await self.command_pick(pick)
                            await self.report_pick_number()

        except Exception as e:
            print(f"read_loom_loop failed: {e!r}")
            traceback.print_exc()
            await self.disconnect()

    async def __aenter__(self) -> LoomServer:
        await self.connect()
        return self

    async def __aexit__(
        self,
        type: Type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
