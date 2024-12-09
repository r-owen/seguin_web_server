__all__ = ["create_test_client"]

import collections.abc
import contextlib
import pathlib
import sys
from types import SimpleNamespace
from typing import Any, TypeAlias

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from starlette.testclient import WebSocketTestSession

from . import main
from .client_replies import ConnectionStateEnum

WebSocketType: TypeAlias = WebSocket | WebSocketTestSession


def receive_dict(websocket: WebSocketType) -> dict[str, Any]:
    """Wrapper around websocket.receive_json to make mypy happy"""
    data: Any = websocket.receive_json()
    assert isinstance(data, dict)
    return data


@contextlib.contextmanager
def create_test_client(
    read_initial_state: bool = True,
    upload_patterns: collections.abc.Iterable[pathlib.Path] | None = None,
) -> collections.abc.Generator[tuple[TestClient, WebSocketType], None]:
    """Create a test server, client, websocket. Return (client, websocket).

    Parameters
    ----------
    read_initial_state : bool
        If true, read and check the initial server replies from the websocket
    upload_patterns : collections.abc.Iterable[pathlib.Path] | None
        Initial patterns to upload, if any.
    """
    sys.argv = ["testutils", "mock", "--verbose"]
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
                            assert reply.names == []
                        case "WeaveDirection":
                            assert reply.forward
                        case _:
                            raise AssertionError(
                                f"Unexpected message type {reply.type}"
                            )
                    seen_types.add(reply.type)
                    if seen_types == expected_types:
                        break

            if upload_patterns is not None:
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
