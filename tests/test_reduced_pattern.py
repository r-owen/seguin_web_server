import pathlib

import dtx_to_wif

from seguin_loom_server.reduced_pattern import (
    ReducedPattern,
    reduced_pattern_from_pattern_data,
)

datadir = pathlib.Path(__file__).parent / "data"


def read_full_pattern(path: pathlib.Path) -> dtx_to_wif.PatternData:
    readfunc = {
        ".wif": dtx_to_wif.read_wif,
        ".dtx": dtx_to_wif.read_dtx,
    }[path.suffix]
    with open(path, "r") as f:
        full_pattern = readfunc(f)
    return full_pattern


def shaft_set_from_reduced(
    reduced_pattern: ReducedPattern, pick_number: int
) -> set[int]:
    """Get the shaft set for a specified 1-based pick_number."""
    reduced_pick = reduced_pattern.picks[pick_number - 1]
    return {
        shaft_index + 1
        for shaft_index, is_up in enumerate(reduced_pick.are_shafts_up)
        if is_up
    }


def test_basics() -> None:
    for filepath in list(datadir.glob("*.wif")) + list(datadir.glob("*.dtx")):
        full_pattern = read_full_pattern(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )

        assert reduced_pattern.type == "ReducedPattern"
        assert reduced_pattern.name == filepath.name
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.repeat_number == 1

        for pick_number, weft_color in full_pattern.weft_colors.items():
            assert weft_color - 1 == reduced_pattern.picks[pick_number - 1].color

        for end_number, warp_color in full_pattern.warp_colors.items():
            assert warp_color - 1 == reduced_pattern.warp_colors[end_number - 1]

        for end_number, shaft_set in full_pattern.threading.items():
            shaft_set -= {0}
            if len(shaft_set) > 1:
                shaft = max(shaft_set)
            else:
                shaft = shaft_set.pop()
            assert shaft - 1 == reduced_pattern.threading[end_number - 1]

        # Test ReducedPattern.picks
        if full_pattern.liftplan:
            assert len(full_pattern.liftplan) == len(reduced_pattern.picks)
            for pick_number, shaft_set_from_liftplan in full_pattern.liftplan.items():
                assert shaft_set_from_liftplan == shaft_set_from_reduced(
                    reduced_pattern=reduced_pattern, pick_number=pick_number
                )
        else:
            assert len(full_pattern.treadling) == len(reduced_pattern.picks)
            for pick_number, treadle_set in full_pattern.treadling.items():
                shaft_set_from_treadles: set[int] = set()
                for treadle in treadle_set - {0}:
                    shaft_set_from_treadles |= full_pattern.tieup[treadle]
                assert shaft_set_from_treadles == shaft_set_from_reduced(
                    reduced_pattern=reduced_pattern, pick_number=pick_number
                )


def test_color_table() -> None:
    for filepath in list(datadir.glob("*.wif")) + list(datadir.glob("*.dtx")):
        full_pattern = read_full_pattern(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )
        assert full_pattern.color_range is not None
        min_color_from_full, max_color_from_full = full_pattern.color_range
        # Note: all test files include white and black colors,
        # so check that these are present before and after conversion.
        assert (min_color_from_full,) * 3 in full_pattern.color_table.values()
        assert (max_color_from_full,) * 3 in full_pattern.color_table.values()
        assert "#000000" in reduced_pattern.color_table
        assert "#ffffff" in reduced_pattern.color_table

        # Check all colors in the color table.
        assert full_pattern.color_table is not None
        assert full_pattern.color_range is not None
        min_full_color = full_pattern.color_range[0]
        full_color_scale = 255 / (
            full_pattern.color_range[1] - full_pattern.color_range[0]
        )
        for i, color in enumerate(reduced_pattern.color_table):
            assert color.startswith("#")
            assert len(color) == 7
            reduced_rgbstrs = [color[1 + 2 * rgbi : 3 + 2 * rgbi] for rgbi in range(3)]
            reduced_rgbvalues = [
                int(color_str, base=16) for color_str in reduced_rgbstrs
            ]
            full_rgbvalues = full_pattern.color_table[i + 1]
            expected_reduced_rgbvalues = [
                int((full_rgbvalues[rgbi] - min_full_color) * full_color_scale)
                for rgbi in range(3)
            ]
            assert reduced_rgbvalues == expected_reduced_rgbvalues
