__all__ = ["create_test_client"]

import collections.abc
import contextlib
import pathlib
import sys
import tempfile
from types import SimpleNamespace
from typing import Any, TypeAlias

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from starlette.testclient import WebSocketTestSession

from . import main
from .client_replies import ConnectionStateEnum
from .reduced_pattern import ReducedPattern

WebSocketType: TypeAlias = WebSocket | WebSocketTestSession


def receive_dict(websocket: WebSocketType) -> dict[str, Any]:
    """Wrapper around websocket.receive_json to make mypy happy"""
    data: Any = websocket.receive_json()
    assert isinstance(data, dict)
    return data


@contextlib.contextmanager
def create_test_client(
    read_initial_state: bool = True,
    upload_patterns: collections.abc.Iterable[pathlib.Path] = (),
    reset_db: bool = False,
    db_path: pathlib.Path | str | None = None,
    expected_pattern_names: collections.abc.Iterable[str] = (),
    expected_current_pattern: ReducedPattern | None = None,
) -> collections.abc.Generator[tuple[TestClient, WebSocketType], None]:
    """Create a test server, client, websocket. Return (client, websocket).

    Parameters
    ----------
    read_initial_state : bool
        If true, read and check the initial server replies from the websocket
    upload_patterns : collections.abc.Iterable[pathlib.Path]
        Initial patterns to upload, if any.
    reset_db : bool
        Specify argument --reset-db?
        If False then you should also specify expected_pattern_names
    db_path : pathLib.Path | str | None
        --db-path argument value. If None, use a temp file.
        If non-None and you expect the database to contain any patterns,
        then also specify expected_pattern_names and expected_current_pattern.
    expected_pattern_names : collections.abc.Iterable[str]
        Expected pattern names. Specify if and only if db_path is not None
        and you expect the database to contain any patterns.
    expected_current_pattern : ReducedPattern | None
        Expected_current_pattern. Specify if and only if db_path is not None
        and you expect the database to contain any patterns.
    """
    expected_pattern_names = list(expected_pattern_names)
    with tempfile.NamedTemporaryFile() as f:
        argv = ["testutils", "mock", "--verbose"]
        if reset_db:
            argv.append("--reset-db")
        if db_path is None:
            argv += ["--db-path", f.name]
        else:
            argv += ["--db-path", str(db_path)]
        sys.argv = argv

        with TestClient(main.app) as client:
            with client.websocket_connect("/ws") as websocket:

                if read_initial_state:
                    seen_types: set[str] = set()
                    expected_types = {
                        "LoomConnectionState",
                        "LoomState",
                        "PatternNames",
                        "WeaveDirection",
                    }
                    if expected_current_pattern:
                        expected_types |= {"ReducedPattern", "CurrentPickNumber"}
                    good_connection_states = {
                        ConnectionStateEnum.CONNECTING,
                        ConnectionStateEnum.CONNECTED,
                    }
                    while True:
                        reply_dict = receive_dict(websocket)
                        reply = SimpleNamespace(**reply_dict)
                        match reply.type:
                            case "LoomConnectionState":
                                if reply.state not in good_connection_states:
                                    raise AssertionError(
                                        f"Unexpected state in {reply=}; "
                                        f"should be in {good_connection_states}"
                                    )
                                elif reply.state != ConnectionStateEnum.CONNECTED:
                                    continue
                            case "LoomState":
                                assert reply.shed_closed
                                assert not reply.cycle_complete
                                assert not reply.error
                            case "PatternNames":
                                assert reply.names == expected_pattern_names
                            case "ReducedPattern":
                                if not expected_pattern_names:
                                    raise AssertionError(
                                        f"Unexpected message type {reply.type} "
                                        "because expected_current_pattern is None"
                                    )

                                assert reply.name == expected_pattern_names[-1]
                            case "CurrentPickNumber":
                                assert expected_current_pattern is not None
                                assert (
                                    reply.pick_number
                                    == expected_current_pattern.pick_number
                                )
                                assert (
                                    reply.repeat_number
                                    == expected_current_pattern.repeat_number
                                )
                            case "WeaveDirection":
                                assert reply.forward
                            case _:
                                raise AssertionError(
                                    f"Unexpected message type {reply.type}"
                                )
                        seen_types.add(reply.type)
                        if seen_types == expected_types:
                            break

                expected_names: list[str] = []
                for path in upload_patterns:
                    expected_names.append(path.name)
                    upload_pattern(websocket, path)
                    reply_dict = receive_dict(websocket)
                    assert reply_dict == dict(type="PatternNames", names=expected_names)

                yield (client, websocket)


def upload_pattern(websocket: WebSocketType, filepath: pathlib.Path) -> None:
    with open(filepath, "r") as f:
        data = f.read()
    cmd = dict(type="file", name=filepath.name, data=data)
    websocket.send_json(cmd)
