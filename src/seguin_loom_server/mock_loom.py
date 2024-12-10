from __future__ import annotations

__all__ = ["MockLoom"]

import asyncio
from types import TracebackType
from typing import Type

from .mock_streams import open_mock_connection

DIRECTION_NAMES = {True: "weave", False: "unweave"}

TERMINATOR = "\r"


class MockLoom:
    """Simulate a Seguin dobby loom.

    The user controls this loom by:

    * writing commands to self.command_stream, a mock asyncio.StreamWriter
    * reading from self.reply_stream, a mock asyncio.StreamWriter
    """

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.weave_forward = True
        self.reply_stream, self.command_stream = open_mock_connection()
        self.done_task: asyncio.Future = asyncio.Future()
        self.error_flag = False
        self.shaft_word = 0
        self.weave_cycle_completed = False
        asyncio.create_task(self.start())

    async def start(self) -> None:
        self.read_commands_task = asyncio.create_task(self.handle_commands_loop())
        await self.report_state()
        await self.report_direction()
        await self.report_shafts()

    async def close(self) -> None:
        self.read_commands_task.cancel()
        self.reply_stream.close()
        await self.reply_stream.wait_closed()

    @classmethod
    async def amain(cls) -> None:
        loom = cls()
        await loom.done_task

    async def handle_commands_loop(self) -> None:
        while True:
            cmdbytes = await self.command_stream.readline()
            print("MockLoom read command", cmdbytes)
            if not cmdbytes:
                break
            cmd = cmdbytes.decode().rstrip()
            if self.verbose:
                print(f"MockLoom: process client command {cmd!r}")
            if not cmd:
                return
            if cmd[0:1] != "=":
                print(f"MockLoom: invalid command {cmd!r}: must begin with '='")
                return
            if len(cmd) < 2:
                print(
                    f"MockLoom: invalid command {cmd!r}: must be at least 2 characters"
                )
                return
            cmd_char = cmd[1]
            cmd_data = cmd[2:]
            match cmd_char:
                case "C":
                    # Specify which shafts to raise as a hex value
                    try:
                        self.shaft_word = int(cmd_data, base=16)
                    except Exception:
                        print(
                            f"MockLoom: invalid command {cmd!r}: data after =C not a hex value"
                        )
                        return
                    if self.verbose:
                        print(f"MockLoom: raise shafts {self.shaft_word:08x}")
                    self.weave_cycle_completed = False
                    await self.report_shafts()
                case "U":
                    # Client commands unweave on/off
                    # (as opposed to the user pushing the button on the loom,
                    # in which case the loom changes it and reports it
                    # to the client).
                    if cmd_data == "0":
                        self.weave_forward = True
                        if self.verbose:
                            print("MockLoom: weave forward commanded by software")
                    elif cmd_data == "1":
                        self.weave_forward = False
                        if self.verbose:
                            print("MockLoom: weave backwards commanded by software")
                    else:
                        print(f"MockLoom: invalid command {cmd!r}: arg nmust be 0 or 1")
                        return
                    await self.report_direction()
                case "V":
                    await self.reply("=v001")
                case "Q":
                    await self.report_state()
                case "#":
                    # Out of band command specific to the mock loom.
                    # Cast to lowercase becase uppercase is default on iOS.
                    match cmd_data.lower():
                        case "d":
                            self.weave_forward = not self.weave_forward
                            await self.report_direction()
                            if self.verbose:
                                print(
                                    "MockLoom: oob toggle weave direction: "
                                    f"{DIRECTION_NAMES[self.weave_forward]}"
                                )
                        case "e":
                            self.error_flag = not self.error_flag
                            if self.verbose:
                                print(
                                    f"MockLoom: oob toggle loom error flag to {self.error_flag}"
                                )
                            await self.report_state()
                        case "n":
                            if self.verbose:
                                print("MockLoom: oob request next pick")
                            self.weave_cycle_completed = True
                            await self.report_state()
                        case "q":
                            if self.verbose:
                                print("MockLoom: oob quit command")
                            if self.command_stream is not None:
                                self.command_stream.close()
                            self.done_task.set_result(None)
                        case _:
                            print(f"MockLoom: unrecognized oob command: {cmd_data!r}")

    async def reply(self, reply: str) -> None:
        """Issue the specified reply, which should not be terminated"""
        if self.verbose:
            print(f"MockLoom: send reply {reply!r}")
        self.reply_stream.write((reply + TERMINATOR).encode())
        await self.reply_stream.drain()

    async def report_direction(self) -> None:
        await self.reply(f"=u{int(not self.weave_forward)}")

    async def report_shafts(self) -> None:
        await self.reply(f"=c{self.shaft_word:08x}")

    async def report_state(self) -> None:
        bitmask = 1
        if self.weave_cycle_completed:
            bitmask += 4
        if self.error_flag:
            bitmask += 8
        await self.reply(f"=s{bitmask:01x}")

    async def __aenter__(self) -> MockLoom:
        await self.start()
        return self

    async def __aexit__(
        self,
        type: Type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
