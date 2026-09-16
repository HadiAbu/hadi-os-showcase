"""Common English words dropped before theme extraction (insights._grams).

Not exhaustive — just enough that the top n-grams are content words, not
function words. Tokens shorter than 3 chars are also dropped by the caller.
"""

from __future__ import annotations

STOPWORDS: frozenset[str] = frozenset(
    """
    the and for are but not you your yours with was were will would that this these those
    have has had having doing does did done from they them their there then than
    into out over under about above below off can could should shall may might must
    ago now today yesterday tomorrow day days week weeks month months year years time
    just also very much more most some any all each few lot lots really quite
    been being get got getting make made making take took taken keep kept
    like want wanted need needed feel felt feeling think thought thinking know knew
    say said says going went gone come came still yet even though although because
    when where what which who whom whose why how while during after before between
    here their its our ours mine his hers theirs
    one two three four five six seven eight nine ten
    thing things stuff way ways bit lots kind sort part parts
    good bad okay fine great nice better best worse worst
    work working worked today's tonight morning evening afternoon night
    """.split()
)
