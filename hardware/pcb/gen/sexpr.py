"""Minimal S-expression reader and writer for KiCad files."""


class Sym(str):
    """An unquoted atom. Plain str values are written quoted."""


def parse(text):
    pos = 0
    n = len(text)

    def read():
        nonlocal pos
        while pos < n and text[pos].isspace():
            pos += 1
        if text[pos] == "(":
            pos += 1
            items = []
            while True:
                while pos < n and text[pos].isspace():
                    pos += 1
                if text[pos] == ")":
                    pos += 1
                    return items
                items.append(read())
        if text[pos] == '"':
            pos += 1
            out = []
            while text[pos] != '"':
                if text[pos] == "\\":
                    pos += 1
                    out.append({"n": "\n", "t": "\t"}.get(text[pos], text[pos]))
                else:
                    out.append(text[pos])
                pos += 1
            pos += 1
            return "".join(out)
        start = pos
        while pos < n and not text[pos].isspace() and text[pos] not in "()":
            pos += 1
        return Sym(text[start:pos])

    return read()


def dump(node, indent=0):
    pad = "\t" * indent
    if isinstance(node, list):
        if all(not isinstance(x, list) for x in node):
            return pad + "(" + " ".join(atom(x) for x in node) + ")"
        # Leading atoms share the opening line; everything after the first
        # list keeps its order, one item per line.
        first_list = next(i for i, x in enumerate(node) if isinstance(x, list))
        lines = [pad + "(" + " ".join(atom(x) for x in node[:first_list])]
        for x in node[first_list:]:
            lines.append(dump(x, indent + 1))
        lines.append(pad + ")")
        return "\n".join(lines)
    return pad + atom(node)


def atom(x):
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(x, float):
        return ("%.4f" % x).rstrip("0").rstrip(".")
    return str(x)


def find(node, key):
    """First child list whose head is `key`, or None."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]
