__all__ = ["MockLoom"]

import asyncio

from .mock_streams import open_mock_connection

DIRECTION_NAMES = {True: "weave", False: "unweave"}

TERMINATOR = "\r"


class MockLoom:
    """Simulate a Seguin dobby loom.

    The user controls this loom by:

    * writing commands to self.cmd_writer, a mock asyncio.StreamWriter
    * reading from self.reply_reader, a mock asyncio.StreamWriter
    """

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.weave_forward = True
        self.reply_reader, self.cmd_writer = open_mock_connection(
            async_callback=self.handle_command
        )
        self.done_task: asyncio.Future = asyncio.Future()
        self.error_flag = False
        self.shaft_word = 0
        self.weave_cycle_completed = False
        # Indicate that the loom is ready
        self.report_state()
        self.report_direction()
        self.report_shafts()

    @classmethod
    async def amain(cls) -> None:
        loom = cls()
        await loom.done_task

    async def handle_command(self, cmd: str) -> None:
        if self.verbose:
            print(f"MockLoom: process client command {cmd!r}")
        if not cmd:
            return
        if cmd[0:1] != "=":
            print(f"MockLoom: invalid command {cmd!r}: must begin with '='")
            return
        if len(cmd) < 2:
            print(f"MockLoom: invalid command {cmd!r}: must be at least 2 characters")
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
                self.report_shafts()
            case "U":
                # Client commands unweave on/off
                # (as opposed to use pushing the button on the loom,
                #  in which case the loom changes it and reports it to client)
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
                self.report_direction()
            case "V":
                self.reply("=v001")
            case "Q":
                self.report_state()
            case "#":
                # Out of band command specific to the mock loom.
                # Cast to lowercase becase uppercase is default on iOS.
                match cmd_data.lower():
                    case "d":
                        self.weave_forward = not self.weave_forward
                        self.report_direction()
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
                        self.report_state()
                    case "n":
                        if self.verbose:
                            print("MockLoom: oob request next pick")
                        self.weave_cycle_completed = True
                        self.report_state()
                    case "q":
                        if self.verbose:
                            print("MockLoom: oob quit command")
                        if self.cmd_writer is not None:
                            self.cmd_writer.close()
                        self.done_task.set_result(None)
                    case _:
                        print(f"MockLoom: unrecognized oob command: {cmd_data!r}")

    def reply(self, reply: str) -> None:
        """Issue the specified reply, which should not be terminated"""
        if self.verbose:
            print(f"MockLoom: send reply {reply!r}")
        self.reply_reader.appendline(reply + TERMINATOR)

    def report_direction(self) -> None:
        self.reply(f"=u{int(not self.weave_forward)}")

    def report_shafts(self) -> None:
        self.reply(f"=c{self.shaft_word:08x}")

    def report_state(self) -> None:
        bitmask = 1
        if self.weave_cycle_completed:
            bitmask += 4
        if self.error_flag:
            bitmask += 8
        self.reply(f"=s{bitmask:01x}")
