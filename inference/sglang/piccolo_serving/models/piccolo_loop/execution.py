"""Physical-layer scheduling and FP32 mixing for native SGLang execution."""


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
