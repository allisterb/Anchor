"""A recursive-descent parser for the modelled subset of Dogwood.

Split out from the differential harness once the grammar stopped being regex-shaped: `&&`, `!`,
parentheses and the infix `since within` nest, and a regex that appears to handle them is the
"silently mishandles a construct" failure this project keeps guarding against.

THE SUBSET, and everything outside it raises `Unsupported`:

    body   := ("when" | "unless") "temporal" "{" expr "}"
    expr   := conj
    conj   := unary ("&&" unary)*
    unary  := "!" unary | "(" expr ")" | term
    term   := "formerly" "within" DUR pred
            | "previous" "within" DUR pred
            | [ "!" ] pred "since" "within" DUR pred
    pred   := NS "::Action::" STR "::" IDENT "{" binds "}"
    bind   := ("input"|"output") "." IDENT ":" rhs
            | ("callerPrincipal"|"callerResource") ":" ("principal"|"resource")
    rhs    := "context.input." IDENT | "true" | "false" | STR | "_"

Aggregations are covered in the one shape the corpus actually uses:

    exists (n: T). ((count for (t: Timepoint). where (phi)) == n && n >= 3)

which says nothing more than `count(...) >= 3`. That exact shape is recognised; any other use of
`exists` is REFUSED rather than approximated, because general existential quantification over a
value domain is a different thing and pretending otherwise is guessing.

Still refused: macros (`call`), parameter sigils (`?p`, `$t`), and comparisons that are not the
aggregation idiom.
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
        """`count for (...). where (C)` or `sum v for (...). where (C)`."""
        kind = self.take()
        over = "" if kind == "count" else self.take()
        bs = self.binders()
        self.expect("where")
        self.expect("(")
        cond = self.expr()
        self.expect(")")
        return {"kind": kind, "over": over, "binders": bs, "cond": cond}

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
            if self.peek() == "(":
                return {"op": "not", "args": [self.group()]}
            self.i = save
            return self.term()
        if self.peek() == "(":
            return self.group()
        return self.term()

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

        # Otherwise the only remaining form is an infix `since`.
        neg = self.accept("!")
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

        return {"op": "pred", "pred": self.pred()}

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
