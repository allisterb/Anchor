"""A recursive-descent parser for the modelled subset of Dogwood.

Split out from the differential harness once the grammar stopped being regex-shaped: `&&`, `!`,
parentheses and the infix `since within` nest, and a regex that appears to handle them is the
"silently mishandles a construct" failure this project keeps guarding against.

THE SUBSET, and everything outside it raises `Unsupported`:

    body   := ("when" | "unless") "temporal" "{" expr "}"
    expr   := conj
    conj   := unary ("&&" unary)*
    unary  := "!" unary | "(" expr ")" | term
    term   := "formerly" "within" DUR atom
            | "previous" "within" DUR atom
            | [ "!" ] ( pred | "(" pred ")" ) "since" "within" DUR atom
    atom   := pred | "tp" "(" IDENT ")" | cmp | "(" atom ("&&" atom)* ")"
    pred   := NS "::Action::" STR "::" IDENT "{" binds "}"
    cmp    := "context.input." IDENT OP LITERAL
    bind   := ("input"|"output") "." IDENT ":" rhs
            | ("callerPrincipal"|"callerResource") ":" ("principal"|"resource")
    rhs    := "context.input." IDENT | "true" | "false" | STR | "_"

Aggregations are covered in the one shape the corpus actually uses:

    exists (n: T). ((count for (t: Timepoint). where (phi)) == n && n >= 3)

`phi` is either a temporal term or -- with NO temporal operator anywhere in it -- a bare
conjunction of atoms, which means "at the decision's own timepoint". An unwrapped aggregate counts
what is happening now rather than what has happened. The two are told apart by looking for a
temporal keyword in the body, not by parsing and backtracking: a failure inside the temporal
reading can mean "this is the bare form" or "this uses something unsupported", and catching it
would conflate them.

which says nothing more than `count(...) >= 3`. That exact shape is recognised; any other use of
`exists` is REFUSED rather than approximated, because general existential quantification over a
value domain is a different thing and pretending otherwise is guessing.

`cmp` reads the DECISION event, not the candidate one, so it evaluates the same at every
candidate index -- it filters the request rather than the history, and appears inside a group only
because that is where an author writes it. Only a literal right-hand side is accepted; the corpus
also contains `context.input.amount > context.input.limit`, an enum entity
(`Drupe::Grant_Input_role::"o'admin"`) and a comparison to a bound variable, and those are three
further features rather than three spellings of this one.

Still refused: macros (`call`), parameter sigils (`?p`, `$t`), `since` nested inside an aggregate
body, event schemas that `pin` a field into every predicate, and comparisons that are neither the
aggregation idiom nor the `cmp` above.
"""

from __future__ import annotations

import re

UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# `count` and `sum` bring binders, `exists` and `tp(...)`; a bare identifier bind value is a
# pattern variable that only has meaning inside one. All refused together.
AGGREGATIONS = ("count ", "sum ", "exists ", "tp(")

TOKEN = re.compile(r"""
      (?P<str>"[^"]*")
    | (?P<dur>\d+[smhd]\b)
    | (?P<int>\d+)
    | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<sym>::|&&|\|\||<=|>=|!=|==|[!(){}:.,<>=+?$-])
    | (?P<ws>\s+)
""", re.X)


class Unsupported(Exception):
    """The policy uses a construct outside the modelled subset."""


def tokenize(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        m = TOKEN.match(text, i)
        if not m:
            raise Unsupported(f"unlexable at {text[i:i + 24]!r}")
        if not m.group("ws"):
            out.append(m.group(0))
        i = m.end()
    return out


class Parser:
    def __init__(self, tokens: list[str]):
        self.t = tokens
        self.i = 0

    # -- token helpers ---------------------------------------------------------
    def peek(self, n: int = 0) -> str | None:
        return self.t[self.i + n] if self.i + n < len(self.t) else None

    def take(self) -> str:
        if self.i >= len(self.t):
            raise Unsupported("unexpected end of policy")
        self.i += 1
        return self.t[self.i - 1]

    def expect(self, tok: str) -> str:
        got = self.take()
        if got != tok:
            raise Unsupported(f"expected {tok!r}, got {got!r}")
        return got

    def accept(self, tok: str) -> bool:
        if self.peek() == tok:
            self.i += 1
            return True
        return False

    # -- grammar ---------------------------------------------------------------
    def expr(self) -> dict:
        parts = [self.unary()]
        while self.accept("&&"):
            parts.append(self.unary())
        if self.peek() == "||":
            raise Unsupported("disjunction between temporal terms")
        return parts[0] if len(parts) == 1 else {"op": "and", "args": parts}

    def binders(self) -> list[dict]:
        """`for (t: Timepoint), (x: String).`"""
        self.expect("for")
        out = []
        while True:
            self.expect("(")
            name = self.take()
            self.expect(":")
            ty = self.take()
            while self.accept("::"):
                ty = self.take()
            self.expect(")")
            out.append({"name": name, "type": ty})
            if not self.accept(","):
                break
        self.expect(".")
        return out

    def aggregate(self) -> dict:
        """`count for (...). where (C)` or `sum v for (...). where (C)`.

        Inside the body -- and ONLY there -- a bare predicate with no temporal operator is
        allowed, and means "at the decision's own timepoint". The flag is scoped to this call
        because that is where the corpus evidence is: a bare predicate at the top level of a
        `when temporal` block is a different question, with nothing to check an answer against.
        """
        kind = self.take()
        over = "" if kind == "count" else self.take()
        bs = self.binders()
        self.expect("where")
        self.expect("(")

        if self.body_has_temporal():
            cond = self.expr()
        else:
            # No temporal operator anywhere in the body: it sees only the decision's own
            # timepoint, so the conjuncts are ATOMS and the whole thing becomes one `at` term.
            # Window 0 is a placeholder; the `at` arm of TermHolds never reads it.
            at = self.atom_conj()
            cond = {"op": "term",
                    "term": {"op": "at", "window": 0, "atom": at, "left": at, "leftNeg": False}}

        self.expect(")")
        return {"kind": kind, "over": over, "binders": bs, "cond": cond}

    def atom_conj(self) -> dict:
        """`atom ("&&" atom)*`, unparenthesised -- the shape an unwrapped body has."""
        parts = [self.atom()]
        while self.accept("&&"):
            parts.append(self.atom())
        return parts[0] if len(parts) == 1 else {"op": "and", "args": parts}

    def body_has_temporal(self) -> bool:
        """Does a temporal operator appear before the `)` that closes the body?

        Includes nested ones. A `since` inside a group is still outside the modelled subset, and
        routing such a body to `expr()` keeps it REFUSED rather than silently reading it as the
        bare form -- which would be a wrong answer rather than an absent one.
        """
        depth, j = 0, self.i
        while j < len(self.t):
            tok = self.t[j]
            if tok == "(":
                depth += 1
            elif tok == ")":
                if depth == 0:
                    return False
                depth -= 1
            elif tok in ("formerly", "previous", "since"):
                return True
            j += 1
        raise Unsupported("unbalanced parentheses in an aggregate body")

    def exists_idiom(self) -> dict:
        """`exists (n: T). ((AGG) == n && n CMP k)` -- the corpus's only use of `exists`.

        Recognised as exactly `AGG CMP k`. Anything else about `exists` is refused: general
        quantification over a value domain is a different thing from this shape.
        """
        self.expect("exists")
        self.expect("(")
        var = self.take()
        self.expect(":")
        self.take()
        self.expect(")")
        self.expect(".")
        self.expect("(")
        self.expect("(")
        agg = self.aggregate()
        self.expect(")")
        if self.take() != "==":
            raise Unsupported("exists body is not `AGG == v && v CMP k`")
        if self.take() != var:
            raise Unsupported("exists binds a variable the aggregate is not compared to")
        self.expect("&&")
        if self.take() != var:
            raise Unsupported("exists comparison does not start from the bound variable")
        cmp_op = self.take()
        if cmp_op not in ("==", "!=", ">=", "<=", ">", "<"):
            raise Unsupported(f"comparison {cmp_op!r}")
        value = self.take()
        if not re.fullmatch(r"-?\d+", value):
            raise Unsupported(f"comparison bound {value!r} is not an integer")
        self.expect(")")
        return {"op": "agg", "agg": agg, "cmp": cmp_op, "value": int(value)}

    def unary(self) -> dict:
        if self.peek() == "exists":
            return self.exists_idiom()
        if self.peek() == "!":
            # `!A since within W B` negates the LEFT OPERAND of the since, not the whole
            # term, so a bare predicate after `!` has to be looked past before deciding.
            save = self.i
            self.take()
            # `!(A) since ...` is the same thing with the operand parenthesised, and it reads
            # identically up to the closing paren. Look past it before committing: if a `since`
            # follows, this is a negated since-left, not a negation of a group.
            if self.peek() == "(" and self.after_group() != "since":
                return {"op": "not", "args": [self.group()]}
            self.i = save
            return self.term()
        if self.peek() == "(":
            return self.group()
        return self.term()

    def after_group(self) -> str | None:
        """The token following the `(`...`)` starting at the cursor, without consuming anything."""
        depth, j = 0, self.i
        while j < len(self.t):
            if self.t[j] == "(":
                depth += 1
            elif self.t[j] == ")":
                depth -= 1
                if depth == 0:
                    return self.t[j + 1] if j + 1 < len(self.t) else None
            j += 1
        raise Unsupported("unbalanced parentheses")

    def group(self) -> dict:
        self.expect("(")
        inner = self.expr()
        self.expect(")")
        return inner

    def term(self) -> dict:
        head = self.peek()

        if head in ("formerly", "previous"):
            self.take()
            self.expect("within")
            window = self.duration(self.take())
            at = self.atom()
            return {"op": "term",
                    "term": {"op": head, "window": window, "atom": at,
                             "left": at, "leftNeg": False}}

        # Otherwise the only remaining form is an infix `since`. Its left operand may be
        # parenthesised -- `!(A) since ...` -- which changes nothing about its meaning.
        neg = self.accept("!")
        if self.peek() == "(":
            self.take()
            left = self.pred()
            self.expect(")")
        else:
            left = self.pred()
        if self.peek() != "since":
            raise Unsupported(f"bare predicate with no temporal operator (next: {self.peek()!r})")
        self.take()
        self.expect("within")
        window = self.duration(self.take())
        right = self.atom()
        return {"op": "term",
                "term": {"op": "since", "window": window, "atom": right,
                         "left": {"op": "pred", "pred": left}, "leftNeg": neg}}

    def atom(self) -> dict:
        """What a temporal operator scopes over: a predicate, a `tp(v)`, or a group of both.

        An atom is evaluated AT A CANDIDATE EVENT rather than at the decision point, which is
        how `tp(t)` gets to bind `t` to the index of whatever the enclosing `formerly` found.
        """
        if self.peek() == "(":
            self.expect("(")
            parts = [self.atom()]
            while self.accept("&&"):
                parts.append(self.atom())
            self.expect(")")
            return parts[0] if len(parts) == 1 else {"op": "and", "args": parts}

        if self.peek() == "tp":
            self.take()
            self.expect("(")
            var = self.take()
            self.expect(")")
            return {"op": "tp", "var": var}

        if self.peek() == "context":
            return self.comparison()

        return {"op": "pred", "pred": self.pred()}

    def comparison(self) -> dict:
        """`context.input.FIELD OP <literal>` -- a filter on the request, not on the history.

        It reads the decision event, so its value is the same at every candidate index. Only a
        literal right-hand side is accepted; see the module header for what is refused and why.
        """
        self.expect("context")
        self.expect(".")
        self.expect("input")
        self.expect(".")
        field = self.take()

        op = self.take()
        if op not in ("==", "!=", ">=", "<=", ">", "<"):
            raise Unsupported(f"comparison operator {op!r}")

        neg = self.accept("-")
        tok = self.take()
        if tok.startswith('"'):
            value = tok[1:-1]
        elif tok in ("true", "false"):
            value = tok == "true"
        elif re.fullmatch(r"\d+", tok):
            value = -int(tok) if neg else int(tok)
        else:
            # `context.input.limit`, an enum entity, or a binder variable. Each is its own
            # feature and none is guessed at.
            raise Unsupported(f"comparison right-hand side {tok!r} is not a literal")

        if not isinstance(value, int) or isinstance(value, bool):
            if op not in ("==", "!="):
                raise Unsupported(f"operator {op!r} on a non-numeric value")

        return {"op": "cmp", "field": field, "cmp": op, "value": value}

    def duration(self, tok: str) -> int:
        m = re.fullmatch(r"(\d+)([smhd])", tok)
        if not m:
            raise Unsupported(f"duration {tok!r}")
        return int(m.group(1)) * UNITS[m.group(2)]

    def pred(self) -> dict:
        self.take()                      # namespace
        self.expect("::")
        self.expect("Action")
        self.expect("::")
        action = self.take()
        if not action.startswith('"'):
            raise Unsupported(f"action name {action!r}")
        self.expect("::")
        kind = self.take()
        self.expect("{")
        binds = []
        if self.peek() != "}":
            binds.append(self.bind())
            while self.accept(","):
                binds.append(self.bind())
        self.expect("}")
        return {"action": action[1:-1], "kind": kind, "binds": binds}

    def bind(self) -> dict:
        lhs = self.take()

        if lhs in ("callerPrincipal", "callerResource"):
            self.expect(":")
            rhs = self.take()
            if rhs not in ("principal", "resource"):
                raise Unsupported(f"scope bind value {rhs!r}")
            return {"side": "scope", "field": lhs, "kind": "scope", "name": rhs, "value": ""}

        if lhs not in ("input", "output"):
            raise Unsupported(f"bind target {lhs!r}")
        self.expect(".")
        field = self.take()
        self.expect(":")

        nxt = self.peek()
        if nxt == "_":
            self.take()
            return {"side": lhs, "field": field, "kind": "any", "name": "", "value": ""}
        if nxt == "context":
            self.take()
            self.expect(".")
            self.expect("input")
            self.expect(".")
            return {"side": lhs, "field": field, "kind": "ctx", "name": self.take(), "value": ""}
        if nxt in ("true", "false"):
            return {"side": lhs, "field": field, "kind": "lit", "name": "",
                    "value": self.take() == "true"}
        if nxt and nxt.startswith('"'):
            return {"side": lhs, "field": field, "kind": "lit", "name": "",
                    "value": self.take()[1:-1]}
        # A bare identifier is a variable bound by an enclosing `count`/`sum`.
        if nxt and re.fullmatch(r"[A-Za-z_]\w*", nxt):
            return {"side": lhs, "field": field, "kind": "var", "name": self.take(), "value": ""}
        raise Unsupported(f"bind value {nxt!r}")


def parse_policies(text: str) -> list[dict]:
    """Every `permit`/`forbid` in the file, as [effect, action, cond]."""
    text = re.sub(r"//[^\n]*", "", text)
    policies = []

    for m in re.finditer(r"(permit|forbid)\s*\((.*?)\)\s*(.*?);", text, re.S):
        effect, scope, body = m.group(1), " ".join(m.group(2).split()), " ".join(m.group(3).split())

        sm = re.fullmatch(r'principal,\s*action == \w+::Action::"([^"]+)",\s*resource', scope)
        if not sm:
            # A bare `action`, or a constrained `resource`, changes what the policy applies to.
            raise Unsupported(f"scope {scope!r}")
        action = sm.group(1)

        if not body:
            policies.append({"effect": effect, "action": action,
                             "cond": {"op": "true", "args": []}})
            continue

        bm = re.fullmatch(r"(when|unless) temporal \{(.*)\}", body)
        if not bm:
            raise Unsupported(f"body {body[:48]!r}")
        keyword, inner = bm.group(1), bm.group(2).strip()

        p = Parser(tokenize(inner))
        cond = p.expr()
        if p.peek() is not None:
            raise Unsupported(f"trailing tokens from {p.peek()!r}")

        # `unless temporal { C }` applies the policy when C does NOT hold.
        if keyword == "unless":
            cond = {"op": "not", "args": [cond]}

        policies.append({"effect": effect, "action": action, "cond": cond})

    if not policies:
        raise Unsupported("no policies parsed")
    return policies
