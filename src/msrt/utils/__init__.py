"""Cross-cutting utilities (currently logging helpers only).

Whatever lands here must have *no* dependencies on other ``msrt``
subpackages — that's the whole point of having a shared ``utils``
namespace. If you find yourself reaching back into the pipeline or
config from here, the helper probably belongs next to its caller.
"""
