"""Questions about a policy that its own text does not answer.

The translator turns policy text into something TLC can evaluate. This asks TLC things:

    VACUOUS     can this permit ever grant anything at all?
    REDUNDANT   it grants -- but would deleting it change any verdict?
    DEAD        this forbid never denies anything the rest of the set would have allowed.
    diff        is there a session these two versions of a policy decide differently?

All four are the same question -- *does deleting or changing this rule change some verdict* --
and every answer is either a witness session or a bounded no. A bounded no is not a proof; the
bound is stated with it.

The one answer this must never give is a WRONG vacuous: telling someone a working rule is inert
gets it deleted. Where the checker cannot decide, it refuses and says what is missing. Two findings
in `tests/policies/` exist only to hold that line -- `string_output.dw` and `like_impossible.dw`.

Kept apart from `translator` on purpose. Translating is deciding what a policy *says*; this decides
what follows from it. The MCP server will want both, and will want them separately.
"""
