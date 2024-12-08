from __future__ import annotations

__all__ = ["Pick", "ReducedPattern", "reduced_pattern_from_pattern_data"]

import dataclasses
import typing

if typing.TYPE_CHECKING:
    from dtx_to_wif import PatternData


@dataclasses.dataclass
class Pick:
    """One pick of a pattern

    Parameters
    ----------
    color: weft color, as an index into the color table
    are_shafts_up: a list of bools, one per shaft;
        True means the shaft is up, False means down
    """

    color: int
    are_shafts_up: list[bool]


@dataclasses.dataclass
class ReducedPattern:
    """A weaving pattern reduced to the bare essentials.

    Contains just enough information to allow loom control,
    with a simple display.

    Picks are accessed by pick number, which is 1-based.
    0 indicates that nothing has been woven.
    """

    type: str = dataclasses.field(init=False, default="ReducedPattern")
    name: str
    color_table: list[str]
    warp_colors: list[int]
    threading: list[int]
    picks: list[Pick]
    pick_number: int = 0
    repeat_number: int = 1

    def increment_pick_number(self, weave_forward: bool) -> int:
        """Increment pick_number in the specified direction.

        Increment repeat_number as well, if appropriate.

        Return the new pick number.
        """
        if self.pick_number < 0 or self.pick_number > len(self.picks):
            raise RuntimeError(
                f"Bug: {self.pick_number=} out of range [0, {len(self.picks)}"
            )
        next_pick_number = self.pick_number + (1 if weave_forward else -1)
        if next_pick_number < 0:
            self.repeat_number -= 1
            next_pick_number = len(self.picks)
        elif next_pick_number > len(self.picks):
            self.repeat_number += 1
            next_pick_number = 0
        self.pick_number = next_pick_number
        return next_pick_number

    def get_current_pick(self, pick_number: int | None = None) -> Pick:
        """Get the current pick.

        Parameters
        ----------
        pick_number : int | None
            The pick number, or None for the current pick.

        Raises
        ------
        IndexError
            If current pick number < 1 or > len(self.picks)
        """
        if pick_number is None:
            pick_number = self.pick_number
        if pick_number < 1 or pick_number > len(self.picks):
            raise IndexError(f"{pick_number=} < 1 or > {len(self.picks)}")
        return self.picks[pick_number - 1]

    def set_current_pick_number(self, pick_number: int) -> None:
        """Set pick_number.

        Parameters
        ----------
        pick_number : int
            The pick pick_number.

        Raise IndexError if pick_number < 0 or > num picks.
        """
        if pick_number < 0 or pick_number > len(self.picks):
            raise IndexError(f"{pick_number=} < 0 or > {len(self.picks)}")
        self.pick_number = pick_number


def _smallest_shaft(shafts: set[int]) -> int:
    """Return the smallest non-zero shaft from a set of shafts.

    Return 0 if no non-zero shafts"""
    pruned_shafts = shafts - {0}
    if pruned_shafts:
        return list(sorted(shafts))[0]
    return 0


def reduced_pattern_from_pattern_data(name: str, data: PatternData) -> ReducedPattern:
    """Convert a dtx_to_wif.PatternData to a ReducedPattern.

    The result is simpler and smaller, and can be sent to easily
    encoded and sent to javascript.

    Note that all input (PatternData) indices are 1-based
    and all output (ReducedPattern) indices are 0-based.
    """
    if data.color_table:
        # Note: PatternData promises to have color_range
        # if color_table is present.
        if data.color_range is None:
            raise RuntimeError("color_table specified, but color_range is None")

        # Compute a scaled version of the color table, where each
        # scaled r,g,b value is in range 0-255 (0-0xff) inclusive
        min_color = data.color_range[0]
        color_scale = (data.color_range[1] - min_color) / 255
        # Note: PatternData promises that color_table
        # keys are 1, 2, ...N, with no missing keys,
        # so we can ignore the keys and just use the values.
        scaled_color_rgbs = (
            [int((value - min_color) * color_scale) for value in color_rgb]
            for color_rgb in data.color_table.values()
        )
        color_strs = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in scaled_color_rgbs]
        if len(color_strs) < 1:
            # Make sure we have at least 2 entries
            color_strs += ["#ffffff", "#000000"]
    else:
        color_strs = ["#ffffff", "#000000"]
    num_warps = max(data.threading.keys())
    warps_from1 = list(range(1, num_warps + 1))
    num_wefts = (
        max(data.liftplan.keys()) if data.liftplan else max(data.treadling.keys())
    )
    wefts_from1 = list(range(1, num_wefts + 1))
    default_warp_color = data.warp.color if data.warp.color is not None else 1
    warp_colors = [
        data.warp_colors.get(warp, default_warp_color) - 1 for warp in warps_from1
    ]
    default_weft_color = data.weft.color if data.weft.color is not None else 2
    weft_colors = [
        data.weft_colors.get(weft, default_weft_color) - 1 for weft in wefts_from1
    ]

    if data.liftplan:
        shaft_sets = list(data.liftplan.get(weft, {}) - {0} for weft in wefts_from1)  # type: ignore
    else:
        shaft_sets = []
        for weft in wefts_from1:
            treadle_set = data.treadling.get(weft, {}) - {0}  # type: ignore
            shaft_sets.append(
                set.union(*(data.tieup[treadle] for treadle in treadle_set)) - {0}
            )
    if len(shaft_sets) != len(weft_colors):
        raise RuntimeError(
            f"{len(shaft_sets)=} != {len(weft_colors)=}\n{shaft_sets=}\n{weft_colors=}"
        )
    try:
        num_shafts = max(max(shaft_set) for shaft_set in shaft_sets if shaft_set)
    except (ValueError, TypeError):
        raise RuntimeError("No shafts are raised")
    threading = [
        _smallest_shaft(data.threading.get(warp, {0})) - 1 for warp in warps_from1
    ]
    shafts_from1 = list(range(1, num_shafts + 1))
    if data.is_rising_shed:
        are_shafts_up_list = [
            [shaft in shaft_set for shaft in shafts_from1] for shaft_set in shaft_sets
        ]
    else:
        are_shafts_up_list = [
            [shaft not in shaft_set for shaft in shafts_from1]
            for shaft_set in shaft_sets
        ]
    picks = [
        Pick(are_shafts_up=are_shafts_up, color=weft_color)
        for are_shafts_up, weft_color in zip(are_shafts_up_list, weft_colors)
    ]

    result = ReducedPattern(
        color_table=color_strs,
        name=name,
        warp_colors=warp_colors,
        threading=threading,
        picks=picks,
    )
    return result
