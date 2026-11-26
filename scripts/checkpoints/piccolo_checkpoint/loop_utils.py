"""Shared loop configuration, execution segments and FP32 interpolation."""

from copy import deepcopy
from math import isfinite


def normalize_loop_config(value, text_depth, vision_depth):
    if not isinstance(value, dict):
        raise ValueError("PiccoloLoop requires loop_config")
    result = deepcopy(value)
    unknown = result.keys() - {"text", "vision"}
    if unknown:
        raise ValueError(f"Unknown loop_config fields: {sorted(unknown)}")
    for tower, depth in (("text", text_depth), ("vision", vision_depth)):
        section = result.setdefault(tower, {"blocks": []})
        if not isinstance(section, dict) or section.keys() != {"blocks"}:
            raise ValueError(f"loop_config.{tower} must contain only blocks")
        if not isinstance(section["blocks"], list):
            raise ValueError(f"loop_config.{tower}.blocks must be a list")
        previous = 0
        for block in section["blocks"]:
            if not isinstance(block, dict) or block.keys() - {"layers", "alphas"}:
                raise ValueError(f"Invalid {tower} loop block fields")
            bounds = block.get("layers")
            if (
                not isinstance(bounds, list)
                or len(bounds) != 2
                or any(type(x) is not int for x in bounds)
                or not previous <= bounds[0] < bounds[1] <= depth
            ):
                raise ValueError(f"{tower} loop ranges must be ordered, disjoint and within depth")
            previous = bounds[1]
            alphas = block.get("alphas")
            if (
                not isinstance(alphas, list)
                or not alphas
                or any(
                    type(x) not in (int, float) or not isfinite(x) or not 0 <= x <= 1
                    for x in alphas
                )
            ):
                raise ValueError(f"{tower} alphas must be finite numbers in [0, 1]")
            block["alphas"] = [float(x) for x in alphas]
    return result


def execution_segments(depth, section):
    """Yield (physical_start, physical_end, alphas), including ordinary layers."""
    cursor = 0
    for block in section["blocks"]:
        start, end = block["layers"]
        if cursor < start:
            yield cursor, start, (1.0,)
        yield start, end, tuple(block["alphas"])
        cursor = end
    if cursor < depth:
        yield cursor, depth, (1.0,)


def mix_hidden(before, after, alpha):
    # Keep the explicit FP32 subtract/multiply/add sequence even for alpha=1.
    return (before.float() + alpha * (after.float() - before.float())).to(before.dtype)
