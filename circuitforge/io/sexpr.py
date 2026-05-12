"""Minimal S-expression reader/writer used by the KiCAD format support.

We treat values as either tokens (str/int/float) or nested lists. Strings
containing whitespace or special chars are quoted with double quotes.
"""

import re


class SExprError(ValueError):
    pass


_TOKEN_RE = re.compile(r'\s+|\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def parse(text):
    """Parse text into a nested list. Returns the first top-level form."""
    tokens = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise SExprError(f"unparseable at offset {pos}")
        tok = m.group()
        pos = m.end()
        if tok.isspace():
            continue
        tokens.append(tok)

    def _parse(it):
        try:
            tok = next(it)
        except StopIteration:
            raise SExprError("unexpected EOF")
        if tok == "(":
            out = []
            while True:
                try:
                    tok = next(it)
                except StopIteration:
                    raise SExprError("missing closing paren")
                if tok == ")":
                    return out
                if tok == "(":
                    # rewind effectively
                    out.append(_parse(_chain([tok], it)))
                else:
                    out.append(_decode(tok))
        elif tok == ")":
            raise SExprError("unexpected closing paren")
        else:
            return _decode(tok)

    return _parse(iter(tokens))


def _chain(prefix, it):
    for x in prefix:
        yield x
    for x in it:
        yield x


def _decode(tok):
    if tok.startswith('"') and tok.endswith('"'):
        return tok[1:-1].encode().decode("unicode_escape")
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def dump(node, indent=0):
    if isinstance(node, list):
        inner = " ".join(dump(x) for x in node)
        return f"({inner})"
    if isinstance(node, str):
        if not node or re.search(r'[\s()"]', node):
            return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return node
    if isinstance(node, bool):
        return "yes" if node else "no"
    if isinstance(node, float):
        return f"{node:g}"
    return str(node)


def dump_pretty(node, level=0):
    pad = "  " * level
    if not isinstance(node, list):
        return pad + dump(node)
    if not node:
        return pad + "()"
    head, *rest = node
    if all(not isinstance(x, list) for x in rest):
        return pad + dump(node)
    out = [pad + "(" + dump(head)]
    for r in rest:
        out.append(dump_pretty(r, level + 1))
    out.append(pad + ")")
    return "\n".join(out)
