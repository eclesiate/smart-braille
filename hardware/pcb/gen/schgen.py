"""Tiny KiCad schematic writer.

Places library symbols and connects each pin with a short wire and a net
label, so the circuit is described as "part, pin -> net" and the drawing
follows from that. Used by gen_schematic.py.
"""

import math
import uuid

import sexpr
from sexpr import Sym

SYMBOL_DIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"
NAMESPACE = uuid.UUID("6f0a3c1e-2b7d-4e55-9a41-5b1f6c0d7e21")
STUB = 2.54
NC = object()  # marks a pin as deliberately unconnected

GRID = 1.27
_libs = {}
CUSTOM = {}  # lib_id -> flattened symbol node, for project-local symbols


def snap(v):
    """Round to KiCad's 1.27 mm connection grid."""
    return round(round(v / GRID) * GRID, 4)


def uid(*parts):
    return str(uuid.uuid5(NAMESPACE, "/".join(str(p) for p in parts)))


def _lib(name):
    if name not in _libs:
        with open(SYMBOL_DIR + name + ".kicad_sym") as f:
            _libs[name] = sexpr.parse(f.read())
    return _libs[name]


def _raw_symbol(lib, name):
    for s in sexpr.find_all(_lib(lib), "symbol"):
        if s[1] == name:
            return s
    raise KeyError(f"{lib}:{name}")


def load_symbol(lib_id):
    """Return a flattened copy of a library symbol, named 'Lib:Name'."""
    if lib_id in CUSTOM:
        return CUSTOM[lib_id]
    lib, name = lib_id.split(":")
    node = _raw_symbol(lib, name)
    ext = sexpr.find(node, "extends")
    if ext is not None:
        parent = _raw_symbol(lib, ext[1])
        if sexpr.find(parent, "extends") is not None:
            raise NotImplementedError("two-level extends")
        merged = [Sym("symbol"), lib_id]
        child_props = {p[1]: p for p in sexpr.find_all(node, "property")}
        for item in parent[2:]:
            if isinstance(item, list) and item[0] == "property":
                merged.append(child_props.pop(item[1], item))
            elif isinstance(item, list) and item[0] == "symbol":
                unit = list(item)
                unit[1] = name + item[1][len(ext[1]):]
                merged.append(unit)
            else:
                merged.append(item)
        merged[2:2] = []
        for prop in child_props.values():
            merged.append(prop)
        return merged
    flat = list(node)
    flat[1] = lib_id
    return flat


def symbol_pins(symbol):
    """Return [(number, name, x, y, angle, unit)] for a flattened symbol."""
    pins = []
    for unit in sexpr.find_all(symbol, "symbol"):
        unit_no = int(unit[1].rsplit("_", 2)[1])
        for p in sexpr.find_all(unit, "pin"):
            at = sexpr.find(p, "at")
            pins.append(
                (
                    sexpr.find(p, "number")[1],
                    sexpr.find(p, "name")[1],
                    float(at[1]),
                    float(at[2]),
                    int(float(at[3])) if len(at) > 3 else 0,
                    unit_no,
                )
            )
    return pins


def _effects(size=1.27, justify=None, hide=False):
    node = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify:
        node.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        node.append([Sym("hide"), Sym("yes")])
    return node


def _r(v):
    return round(v, 4)


class Sheet:
    def __init__(self, project, name, paper, title, global_nets=(), hier_nets=()):
        self.project = project
        self.name = name
        self.uuid = uid(project, "sheet-file", name)
        self.paper = paper
        self.title = title
        self.global_nets = set(global_nets)
        self.hier_nets = dict(hier_nets)  # net -> shape
        self.lib_symbols = {}
        self.items = []
        self.parts = []  # (ref_key, symbol_node)
        self._at = {}  # (x, y) -> net or NC, to catch clashes
        self._count = 0
        self.netlist = {}  # (ref_key, pin) -> net, as intended
        self.pwr_flags = 0

    # --- drawing primitives ---
    def _next(self, kind):
        self._count += 1
        return uid(self.project, self.name, kind, self._count)

    def text(self, string, x, y, size=2.0):
        self.items.append(
            [Sym("text"), string, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), x, y, 0],
             _effects(size, "left bottom"), [Sym("uuid"), self._next("text")]]
        )

    def _wire(self, x1, y1, x2, y2):
        self.items.append(
            [Sym("wire"), [Sym("pts"), [Sym("xy"), _r(x1), _r(y1)], [Sym("xy"), _r(x2), _r(y2)]],
             [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
             [Sym("uuid"), self._next("wire")]]
        )

    def _label(self, net, x, y, direction):
        angle = {"left": 180, "right": 0, "up": 90, "down": 270}[direction]
        if net in self.hier_nets:
            justify = "right" if direction in ("left", "down") else "left"
            self.items.append(
                [Sym("hierarchical_label"), net, [Sym("shape"), Sym(self.hier_nets[net])],
                 [Sym("at"), _r(x), _r(y), angle], _effects(1.27, justify),
                 [Sym("uuid"), self._next("hlabel")]]
            )
        elif net in self.global_nets:
            justify = "right" if direction in ("left", "down") else "left"
            self.items.append(
                [Sym("global_label"), net, [Sym("shape"), Sym("passive")],
                 [Sym("at"), _r(x), _r(y), angle], _effects(1.27, justify),
                 [Sym("uuid"), self._next("glabel")],
                 [Sym("property"), "Intersheetrefs", "${INTERSHEET_REFS}",
                  [Sym("at"), _r(x), _r(y), 0], _effects(1.27, None, hide=True)]]
            )
        else:
            justify = "right bottom" if direction in ("left", "down") else "left bottom"
            self.items.append(
                [Sym("label"), net, [Sym("at"), _r(x), _r(y), angle], _effects(1.27, justify),
                 [Sym("uuid"), self._next("label")]]
            )

    def connect(self, x, y, pin_angle, net):
        """Attach `net` (or NC) to a pin end at (x, y) in sheet coordinates.

        pin_angle is the direction the pin runs from its end toward the body,
        in sheet orientation (0 = to the right, 90 = up the page).
        """
        key = (snap(x), snap(y))
        x, y = key
        if key in self._at:
            if self._at[key] is not net and self._at[key] != net:
                raise ValueError(f"two nets at {key}: {self._at[key]} and {net}")
            return
        self._at[key] = net
        if net is NC:
            self.items.append([Sym("no_connect"), [Sym("at"), key[0], key[1]],
                               [Sym("uuid"), self._next("nc")]])
            return
        direction = {0: "left", 180: "right", 90: "down", 270: "up"}[pin_angle % 360]
        dx, dy = {"left": (-STUB, 0), "right": (STUB, 0), "up": (0, -STUB), "down": (0, STUB)}[direction]
        self._wire(x, y, x + dx, y + dy)
        self._label(net, x + dx, y + dy, direction)

    # --- parts ---
    def place(self, lib_id, ref, value, x, y, nets, rot=0, footprint=None, fields=None,
              unit=1, dnp=False, on_board=True, in_bom=True):
        """Place one unit of a symbol and connect its pins.

        nets: {pin_number: net_name or NC}. Every pin of the unit must appear.
        ref: a reference string, or a list with one reference per sheet instance.
        """
        x, y = snap(x), snap(y)
        if lib_id not in self.lib_symbols:
            self.lib_symbols[lib_id] = load_symbol(lib_id)
        symbol = self.lib_symbols[lib_id]
        pins = [p for p in symbol_pins(symbol) if p[5] in (0, unit)]
        refs = ref if isinstance(ref, list) else [ref]
        missing = {p[0] for p in pins} - set(nets)
        extra = set(nets) - {p[0] for p in pins}
        if missing or extra:
            raise ValueError(f"{refs[0]} ({lib_id}): unassigned pins {sorted(missing)}, unknown pins {sorted(extra)}")

        rad = math.radians(rot)
        cos, sin = round(math.cos(rad)), round(math.sin(rad))
        for number, _name, px, py, angle, _unit in pins:
            rx, ry = px * cos - py * sin, px * sin + py * cos
            self.connect(x + rx, y - ry, angle + rot, nets[number])
            if nets[number] is not NC:
                self.netlist[(tuple(refs), number)] = nets[number]

        props = {p[1]: p for p in sexpr.find_all(symbol, "property")}

        def prop(name, val, dx, dy, hide=False, justify=None):
            # A field's angle is relative to its symbol, so a part turned 90
            # degrees needs 90 here for its text to read horizontally.
            return [Sym("property"), name, val, [Sym("at"), _r(x + dx), _r(y + dy), rot % 180],
                    _effects(1.27, justify, hide)]

        def lib_offset(name, default):
            if rot or name not in props:
                return default
            at = sexpr.find(props[name], "at")
            return float(at[1]), -float(at[2])

        if rot:
            ref_off, val_off = (0, -2.6), (0, 2.6)
        else:
            ref_off, val_off = lib_offset("Reference", (0, -5)), lib_offset("Value", (0, 5))
        lib_fp = props["Footprint"][2] if "Footprint" in props else ""
        node = [
            Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), x, y, rot], [Sym("unit"), unit],
            [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes" if in_bom else "no")],
            [Sym("on_board"), Sym("yes" if on_board else "no")], [Sym("dnp"), Sym("yes" if dnp else "no")],
            [Sym("uuid"), self._next("sym")],
            prop("Reference", refs[0], *ref_off),
            prop("Value", value, *val_off),
            prop("Footprint", footprint if footprint is not None else lib_fp, 0, 0, hide=True),
            prop("Datasheet", props["Datasheet"][2] if "Datasheet" in props else "", 0, 0, hide=True),
            prop("Description", props["Description"][2] if "Description" in props else "", 0, 0, hide=True),
        ]
        for name, val in (fields or {}).items():
            node.append(prop(name, val, 0, 0, hide=True))
        for number in sorted({p[0] for p in pins}):
            node.append([Sym("pin"), number, [Sym("uuid"), self._next("pin")]])
        self.parts.append((refs, unit, node))
        return node

    def flag(self, net, x, y):
        """Add a PWR_FLAG so ERC knows this net is powered from off-sheet."""
        self.pwr_flags += 1
        self.place("power:PWR_FLAG", f"#FLG{self.pwr_flags:02d}", "PWR_FLAG", x, y, {"1": net},
                   on_board=False, in_bom=False)
        del self.netlist[((f"#FLG{self.pwr_flags:02d}",), "1")]

    # --- output ---
    def render(self, instance_paths, extra_items=(), root=False):
        """instance_paths: one hierarchical path per sheet instance."""
        out = [
            Sym("kicad_sch"), [Sym("version"), 20260101], [Sym("generator"), "smartbraille_gen"],
            [Sym("generator_version"), "10.0"], [Sym("uuid"), self.uuid], [Sym("paper"), self.paper],
            [Sym("title_block"), [Sym("title"), self.title], [Sym("rev"), "A draft"],
             [Sym("company"), "SmartBraille, ECE 498B"],
             [Sym("comment"), 1, "Generated by hardware/pcb/gen/gen_schematic.py. Edit the script, not this file."]],
            [Sym("lib_symbols")] + [self.lib_symbols[k] for k in sorted(self.lib_symbols)],
        ]
        out += self.items
        for refs, unit, node in self.parts:
            node = list(node)
            paths = []
            for i, path in enumerate(instance_paths):
                ref = refs[i] if len(refs) > 1 else refs[0]
                paths.append([Sym("path"), path, [Sym("reference"), ref], [Sym("unit"), unit]])
            node.append([Sym("instances"), [Sym("project"), self.project] + paths])
            out.append(node)
        out += list(extra_items)
        if root:
            out.append([Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]])
        out.append([Sym("embedded_fonts"), Sym("no")])
        return sexpr.dump(out) + "\n"


def sheet_symbol(project, root_uuid, sheet_uuid, name, filename, x, y, w, h, pins, page):
    """A hierarchical sheet box. pins: [(name, shape, side, offset)]."""
    x, y, w, h = snap(x), snap(y), snap(w), snap(h)
    node = [
        Sym("sheet"), [Sym("at"), x, y], [Sym("size"), w, h],
        [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
        [Sym("dnp"), Sym("no")],
        [Sym("stroke"), [Sym("width"), 0.1524], [Sym("type"), Sym("solid")]],
        [Sym("fill"), [Sym("color"), 0, 0, 0, 0.0]],
        [Sym("uuid"), sheet_uuid],
        [Sym("property"), "Sheetname", name, [Sym("at"), x, _r(y - 0.7), 0], _effects(1.27, "left bottom")],
        [Sym("property"), "Sheetfile", filename, [Sym("at"), x, _r(y + h + 0.6), 0], _effects(1.27, "left top")],
    ]
    for pin_name, shape, side, offset in pins:
        px = x if side == "left" else _r(x + w)
        angle = 180 if side == "left" else 0
        node.append([Sym("pin"), pin_name, Sym(shape), [Sym("at"), px, snap(y + offset), angle],
                     [Sym("uuid"), uid(project, sheet_uuid, "pin", pin_name)],
                     _effects(1.27, "left" if side == "left" else "right")])
    node.append([Sym("instances"), [Sym("project"), project,
                                    [Sym("path"), "/" + root_uuid, [Sym("page"), str(page)]]]])
    return node
