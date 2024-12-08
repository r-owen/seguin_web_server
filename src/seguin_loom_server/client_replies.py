from __future__ import annotations

import dataclasses
import enum


class ConnectionStateEnum(enum.IntEnum):
    """Client websocket connection state."""

    DISCONNECTED = 0
    CONNECTED = 1
    CONNECTING = 2
    DISCONNECTING = 3


@dataclasses.dataclass
class CurrentPickNumber:
    """The current pick and repeat numbers"""

    type: str = dataclasses.field(init=False, default="CurrentPickNumber")
    pick_number: int
    repeat_number: int


@dataclasses.dataclass
class ConnectionState:
    """The state of the server's connection to the loom"""

    type: str = dataclasses.field(init=False, default="ConnectionState")
    state: ConnectionStateEnum


@dataclasses.dataclass
class PatternNames:
    """The list of loaded patterns (including the current pattern)"""

    type: str = dataclasses.field(init=False, default="PatternNames")
    names: list[str]


@dataclasses.dataclass
class LoomState:
    """The state output by the loom.

    In detail the states are (from the manual):

    * shed_closed: True when the shed is fully closed.
    * cycle_complete: True when a weaving cycle has been completed,
            and the loom is requesting a fresh pattern.
    * error: True when the loom is not ready (trouble with the loom).
    """

    type: str = dataclasses.field(init=False, default="LoomState")
    shed_closed: bool
    cycle_complete: bool
    error: bool

    @classmethod
    def from_state_word(cls, state_word: int) -> LoomState:
        """Construct a LoomState from the state value of the =s reply."""
        return cls(
            shed_closed=bool(state_word & 0x01),
            cycle_complete=bool(state_word & 0x04),
            error=bool(state_word & 0x08),
        )


@dataclasses.dataclass
class WeaveDirection:
    """The weaving direction"""

    type: str = dataclasses.field(init=False, default="WeaveDirection")
    forward: bool
