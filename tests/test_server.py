import dataclasses
import io
import pathlib
import sys
from typing import Any

from dtx_to_wif import read_dtx, read_wif

appdir = pathlib.Path(__file__).parents[1]
sys.path.append(str(appdir))

from app.reduced_pattern import reduced_pattern_from_pattern_data  # noqa
from app.testutils import create_test_client, receive_dict  # noqa

datadir = pathlib.Path(__file__).parent / "data"

all_pattern_paths = list(datadir.glob("*.wif")) + list(datadir.glob("*.dtx"))


def test_jump_to_pick() -> None:
    pattern_name = all_pattern_paths[3].name

    with create_test_client(upload_patterns=all_pattern_paths[2:5]) as (
        client,
        websocket,
    ):
        websocket.send_json(dict(type="select_pattern", name=pattern_name))
        reply = receive_dict(websocket)
        assert reply["type"] == "ReducedPattern"
        num_picks_in_pattern = len(reply["picks"])
        reply = receive_dict(websocket)
        assert reply == dict(type="CurrentPickNumber", pick_number=0, repeat_number=1)

        for pick_number in (0, 1, num_picks_in_pattern // 3, num_picks_in_pattern):
            websocket.send_json(dict(type="jump_to_pick", pick_number=pick_number))
            reply = receive_dict(websocket)
            assert reply == dict(
                type="CurrentPickNumber", pick_number=pick_number, repeat_number=1
            )


def test_oobcommand() -> None:
    pattern_name = all_pattern_paths[2].name

    with create_test_client(upload_patterns=all_pattern_paths[0:3]) as (
        client,
        websocket,
    ):
        websocket.send_json(dict(type="select_pattern", name=pattern_name))
        reply = receive_dict(websocket)
        assert reply["type"] == "ReducedPattern"
        num_picks_in_pattern = len(reply["picks"])
        reply = receive_dict(websocket)
        assert reply == dict(type="CurrentPickNumber", pick_number=0, repeat_number=1)

        # Make enough forward picks to get into the 3rd repeat
        expected_pick_number = 0
        expected_repeat_number = 1
        while not (expected_repeat_number == 3 and expected_pick_number > 2):
            expected_pick_number += 1
            if expected_pick_number > num_picks_in_pattern:
                expected_pick_number -= num_picks_in_pattern + 1
                expected_repeat_number += 1
            websocket.send_json(dict(type="oobcommand", command="n"))
            for _ in range(2):
                reply = receive_dict(websocket)
                if reply["type"] == "CurrentPickNumber":
                    assert reply == dict(
                        type="CurrentPickNumber",
                        pick_number=expected_pick_number,
                        repeat_number=expected_repeat_number,
                    )
                elif reply["type"] == "LoomState":
                    assert reply == dict(
                        type="LoomState",
                        shed_closed=True,
                        cycle_complete=True,
                        error=False,
                    )
                else:
                    raise AssertionError(f"Unexpected reply type in {reply=}")

        websocket.send_json(dict(type="oobcommand", command="d"))
        expected_pick_number -= 1
        reply = receive_dict(websocket)
        assert reply == dict(type="WeaveDirection", forward=False)
        reply = receive_dict(websocket)
        assert reply == dict(
            type="CurrentPickNumber",
            pick_number=expected_pick_number,
            repeat_number=expected_repeat_number,
        )

        # Now go backwards to the beginning
        while not (expected_pick_number == 0 and expected_repeat_number == 1):
            expected_pick_number -= 1
            if expected_pick_number < 0:
                expected_pick_number += num_picks_in_pattern + 1
                expected_repeat_number -= 1
            websocket.send_json(dict(type="oobcommand", command="n"))
            for _ in range(2):
                reply = receive_dict(websocket)
                if reply["type"] == "CurrentPickNumber":
                    assert reply == dict(
                        type="CurrentPickNumber",
                        pick_number=expected_pick_number,
                        repeat_number=expected_repeat_number,
                    )
                elif reply["type"] == "LoomState":
                    assert reply == dict(
                        type="LoomState",
                        shed_closed=True,
                        cycle_complete=True,
                        error=False,
                    )
                else:
                    raise AssertionError(f"Unexpected reply type in {reply=}")
        assert expected_pick_number == 0
        assert expected_repeat_number == 1

        # Change direction to forward
        websocket.send_json(dict(type="oobcommand", command="d"))
        expected_pick_number += 1
        reply = receive_dict(websocket)
        assert reply == dict(type="WeaveDirection", forward=True)
        reply = receive_dict(websocket)
        assert reply == dict(
            type="CurrentPickNumber",
            pick_number=expected_pick_number,
            repeat_number=expected_repeat_number,
        )

        # Toggle error flag on and off
        websocket.send_json(dict(type="oobcommand", command="e"))
        reply = receive_dict(websocket)
        assert reply == dict(
            type="LoomState",
            shed_closed=True,
            cycle_complete=False,
            error=True,
        )

        websocket.send_json(dict(type="oobcommand", command="e"))
        reply = receive_dict(websocket)
        assert reply == dict(
            type="LoomState",
            shed_closed=True,
            cycle_complete=False,
            error=False,
        )


def test_select_pattern() -> None:
    # Read a pattern file in and convert the data to a ReducedPattern
    pattern_path = all_pattern_paths[1]
    pattern_name = all_pattern_paths[1].name
    with open(pattern_path, "r") as f:
        pattern_data = f.read()
    if pattern_name.endswith(".dtx"):
        with io.StringIO(pattern_data) as dtx_file:
            pattern_data = read_dtx(dtx_file)
    elif pattern_name.endswith(".wif"):
        with io.StringIO(pattern_data) as wif_file:
            pattern_data = read_wif(wif_file)
    else:
        raise AssertionError("Unexpected unsupported file type: {pattern_path!s}")
    reduced_pattern = reduced_pattern_from_pattern_data(
        name=pattern_name, data=pattern_data
    )

    with create_test_client(upload_patterns=all_pattern_paths[0:3]) as (
        client,
        websocket,
    ):
        websocket.send_json(dict(type="select_pattern", name=pattern_name))
        reply = receive_dict(websocket)
        assert reply["type"] == "ReducedPattern"
        assert reply == dataclasses.asdict(reduced_pattern)
        reply = receive_dict(websocket)
        assert reply == dict(type="CurrentPickNumber", pick_number=0, repeat_number=1)


def test_upload() -> None:
    with create_test_client(upload_patterns=all_pattern_paths) as (
        client,
        websocket,
    ):
        pass


def test_weave_direction() -> None:
    pattern_name = all_pattern_paths[1].name

    with create_test_client(upload_patterns=all_pattern_paths[0:4]) as (
        client,
        websocket,
    ):
        websocket.send_json(dict(type="select_pattern", name=pattern_name))
        reply = receive_dict(websocket)
        assert reply["type"] == "ReducedPattern"
        assert reply["name"] == pattern_name
        reply = receive_dict(websocket)
        assert reply == dict(type="CurrentPickNumber", pick_number=0, repeat_number=1)

        for forward, desired_pick_number in ((True, 1), (False, 0), (False, 0)):
            websocket.send_json(dict(type="weave_direction", forward=forward))
            reply = receive_dict(websocket)
            assert reply == dict(type="WeaveDirection", forward=forward)
            reply = receive_dict(websocket)
            assert reply == dict(
                type="CurrentPickNumber",
                pick_number=desired_pick_number,
                repeat_number=1,
            )
