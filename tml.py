import io, sys, math
from xml.etree import ElementTree as ET

import osp

SVGNS = 'http://www.w3.org/2000/svg'

DOC_TEMPLATE_HEAD = b'''<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8"/>
        <title>Timeline</title>
        <style type="text/css">
svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
line.event { stroke: #700; stroke-width: 0.5; }
text.event { fill: #700; }
line.child { stroke: #00f; stroke-width: 0.5; }
line.time { stroke: #aaa; stroke-width: 0.5; }
text.time { fill: #777; }
rect { stroke: #000; fill: none; }
.name { opacity: 0.5; }
rect.human { fill: #c73; }
rect.dragon { stroke: #f70; }
rect.dragon.gold { fill: #ff3; }
rect.dragon.silver { fill: #aaa; }
rect.dragon.bronze { fill: #770; stroke: #070; }
rect.dragon.copper { fill: #740; }
rect.dragon.green { fill: #070; }
rect.dragon.red { fill: #c00; }
rect.dragon.black { fill: #222; }
.dragon.black { opacity: 1; }
rect.dragon.white { fill: #fff; stroke: #000; }
rect.dragon.platinum { fill: #aff; }
rect.dragon.polychromatic { fill: url(#all_chromatic); }
text.dragon.polychromatic { fill: #fff; stroke: #000; stroke-width: 0.25; }
rect.deity { stroke: #f00; stroke-width: 1.5; }
.deity { opacity: 1; }
rect.dragon.silver_green { fill: url(#gs_hatch); }
rect.owlkin { fill: url(#bg_hatch); }
text.dragon.black, text.dragon.red, text.owlkin { fill: #fff; }
line.event.death { stroke: #f00; }
text.event.death { fill: #f00; }
line.event.raise { stroke: #00f; }
text.event.raise { fill: #00f; }
line.event.world { stroke: #077; }
text.event.world { fill: #077; }
line.event.world.konis { stroke: #0a0; }
text.event.world.konis { fill: #0a0; }
line.event.world.present { stroke: #000; stroke-width: 1.5; }
text.event.world.present { fill: #000; }
line.event.short { stroke: #770; stroke-width: 1.5; }
text.event.short { fill: #770; }
        </style>
    </head>
    <body>
'''

DOC_TEMPLATE_FOOT = b'''
    </body>
</html>'''

DEFS = ET.XML('''
<defs>
    <pattern id="gs_hatch" width="50" height="50" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
        <rect x="0" y="0" width="50" height="50" style="stroke: none; fill: #070;"/>
        <rect x="0" y="0" width="30" height="50" style="stroke: none; fill: #aaa;"/>
    </pattern>
    <pattern id="bg_hatch" width="50" height="50" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
        <rect x="0" y="0" width="50" height="50" style="stroke: none; fill: #620;"/>
        <rect x="0" y="0" width="10" height="50" style="stroke: none; fill: #aa0;"/>
    </pattern>
    <pattern id="all_chromatic" width="50" height="50" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
        <rect x="0" y="0" width="10" height="50" style="stroke: none; fill: #c00;"/>
        <rect x="10" y="0" width="10" height="50" style="stroke: none; fill: #222;"/>
        <rect x="20" y="0" width="10" height="50" style="stroke: none; fill: #070;"/>
        <rect x="30" y="0" width="10" height="50" style="stroke: none; fill: #fff;"/>
        <rect x="40" y="0" width="10" height="50" style="stroke: none; fill: #007;"/>
    </pattern>
</defs>''')

class Timeline(object):
    def __init__(self):
        self.ranges = {}
        self.events = []
        self.constraints = set()
        self.groups = {}

    def add(self, obj):
        if isinstance(obj, Range):
            if obj.name in self.ranges:
                print(f'Warning: range {obj.name} overwrites a previous entry', file=sys.stderr)
            self.ranges[obj.name] = obj
        elif isinstance(obj, Event):
            self.events.append(obj)
        elif isinstance(obj, Constraint):
            self.constraints.add(obj)
        elif isinstance(obj, Group):
            self.groups[obj.name] = obj
        elif isinstance(obj, list):
            for o in obj:
                self.add(o)
        else:
            raise TypeError(type(obj))

    @classmethod
    def from_tokens(cls, tok):
        # Constructed here because the classes aren't yet in scope
        handlers = {
            'char': Character,
            'event': Event,
            'constraint': Constraint,
            'sequence': Sequence,
            'group': Group,
        }
        inst = cls()
        for t in tok:
            if t is osp.INDENT:
                print('Warning: unexpected root indent', file=sys.stderr)
            elif t is osp.DEDENT:
                print('Warning: unexpected root dedent', file=sys.stderr)
            else:
                if not t:
                    continue
                parts = t.split()
                if parts[0] == 'comment':
                    osp.read_block(tok)
                    continue
                handler = handlers.get(parts[0])
                if not handler:
                    print(f'Warning: unknown block kind {parts[0]}, skipping', file=sys.stderr)
                    osp.read_block(tok)
                    continue
                if next(tok) is not osp.INDENT:
                    print(f'Warning: block for {parts[0]} didn\'t start, parser may desynchronize', file=sys.stderr)
                    continue
                result = handler.from_tokens(tok, parts)
                inst.add(result)
        return inst

    def link(self):
        for idx, rg in enumerate(self.ranges.values()):
            rg.link(self)
            rg.idx = idx
        ol = len(self.events)
        self.events = sorted([ev for ev in self.events if ev.is_valid()], key = lambda ev: ev.time)
        if len(self.events) != ol:
            print(f'Warning: culled {ol - len(self.events)} events for invalidity', file=sys.stderr)
        for ev in self.events:
            ev.link(self)
        idx = 0
        for ev in reversed(self.events):
            if ev.is_universal():
                ev.idx = idx
                idx += 1
        self.universal_evs = idx
        for rg in self.ranges.values():
            if hasattr(rg, 'parents') and rg.parents is not None:
                for par in rg.parents:
                    self.constraints.add(Constraint(f'{rg.name}_born_after_{par.name}', [par.name], [rg.name]))
                    self.constraints.add(Constraint(f'{rg.name}_born_predeath_{par.name}', [rg.name], [par.name, -1, 'end']))

    def layout(self):
        self.current_y = 0
        for rg in self.ranges.values():
            rg.layout(self)
        for ev in reversed(self.events):
            if ev.is_universal():
                ev.layout(self, None)
        self.height = self.current_y

    def dump(self):
        print('Timeline:', file=sys.stderr)
        for rg in self.ranges.values():
            rg.dump()
        for ev in self.events:
            ev.dump()
        for con in self.constraints:
            con.dump()

    def check(self):
        good = True
        for con in self.constraints:
            if not con.is_valid():
                print(f'Check: invalid: {con}', file=sys.stderr)
                continue
            if not con.verify(self):
                print(f'Check: unsatisfied: {con}', file=sys.stderr)
                good = False
        if good:
            print('All valid constraints passed.', file=sys.stderr)

    def time_bounds(self):
        tms = set()
        for rg in self.ranges.values():
            for sp in rg.spans:
                tms.add(sp.start)
                tms.add(sp.end)
        for ev in self.events:
            tms.add(ev.time)
        return min(tms), max(tms)

    def render(self, xmul = 10, ts = 10, ym = 50):
        mnt, mxt = self.time_bounds()
        mxt += ym
        height = self.height
        svg = ET.Element('svg', xmlns = SVGNS, style = f'width: {(mxt - mnt) * xmul}px; height: {height}px;', viewBox = f'{mnt * xmul} 0 {(mxt - mnt) * xmul} {height}')
        svg.append(DEFS)
        for t in range(math.floor(mnt), math.ceil(mxt) + 1, ts):
            ln = ET.SubElement(svg, 'line', x1 = str(xmul * t), x2 = str(xmul * t), y1 = '0', y2 = str(height))
            ln.set('class', 'time')
            lb = ET.SubElement(svg, 'text', x = str(xmul * t), y = str(height))
            lb.text = str(t)
            lb.set('class', 'time')
        for rg in self.ranges.values():
            rg.render(svg, xmul, self)
        for ev in self.events:
            ev.render(svg, xmul, self)
        buf = io.BytesIO()
        tree = ET.ElementTree(svg)
        tree.write(buf, 'utf8', False)
        sys.stdout.buffer.write(DOC_TEMPLATE_HEAD + buf.getvalue() + DOC_TEMPLATE_FOOT)


class Range(object):
    def __init__(self, name = None, dispname = None, classes = None):
        self.name = name
        self.dispname = dispname
        self.classes = set() if classes is None else classes
        self.spans = []
        self.idx = None
        self.ambient = False
        self.hanging_events = []

    BEGIN_WORDS = {'begin'}
    END_WORDS = {'end'}

    @classmethod
    def from_tokens(cls, tok, hdr):
        nm = ' '.join(hdr[1:])
        inst = cls(nm)
        cur_span = None
        for t in tok:
            if t is osp.INDENT:
                print('Warning: unexpected range indent', file=sys.stderr)
            elif t is osp.DEDENT:
                inst.spans.sort(key=lambda sp: sp.start)
                return inst
            else:
                if not t:
                    continue
                parts = t.split()
                cmd = parts[0]
                if cmd in cls.BEGIN_WORDS:
                    if cur_span is not None:
                        print(f'Warning: range {inst.name} overwriting previous beginning of range span {cur_span.sword} {cur_span.start}', file=sys.stderr)
                    cur_span = Span(float(parts[1]), parts[0], None, None)
                elif cmd in cls.END_WORDS:
                    if cur_span is None:
                        print(f'Warning: no previous span for directive {parts}', file=sys.stderr)
                    else:
                        cur_span.eword = parts[0]
                        cur_span.end = float(parts[1])
                        inst.spans.append(cur_span)
                        cur_span = None
                elif cmd == 'class':
                    for p in parts[1:]:
                        inst.classes.add(p)
                elif cmd == 'name':
                    inst.dispname = ' '.join(parts[1:])
                elif cmd == 'ambient':
                    inst.ambient = True
                else:
                    cls.unhandled_directive(inst, parts)
        print('Warning: interpreting EOF as ending block', file=sys.stderr)
        inst.spans.sort(key=lambda sp: sp.start)
        return inst

    @classmethod
    def unhandled_directive(cls, inst, parts):
        print(f'Warning: unhandled directive for class {cls}: {parts}', file=sys.stderr)

    def link(self, tml):
        if self.ambient:
            mnt, mxt = tml.time_bounds()
            self.spans = [
                Span(mnt, 'begin', mxt, 'end'),
            ]

    def layout(self, tml):
        self.y = tml.current_y
        tml.current_y += Span.HEIGHT
        for ev in self.hanging_events:
            ev.layout(tml, self)

    def dump(self):
        print(f'  {self!r}', file=sys.stderr)
        for sp in self.spans:
            sp.dump()

    def __repr__(self):
        return f'<{type(self).__name__} {self.name} classes {self.classes} idx {self.idx}{self.additional_repr()}>'

    def additional_repr(self):
        return ''

    def render(self, svg, xmul, tml):
        for sp in self.spans:
            rect = sp.render(svg, self.y, xmul)
            rect.set('class', rect.get('class') +' ' + ' '.join(self.classes))
            lb = ET.SubElement(svg, 'text', x = rect.get('x'), y = str(float(rect.get('y')) + float(rect.get('height')) / 2.0))
            lb.set('class', rect.get('class'))
            lb.text = self.dispname


class Span(object):
    def __init__(self, start, sword, end, eword):
        self.start = start
        self.sword = sword
        self.end = end
        self.eword = eword

    def dump(self):
        print(f'    {self!r}', file=sys.stderr)

    def __repr__(self):
        return f'<Span {self.sword} {self.start}, {self.eword} {self.end}>'

    HEIGHT = 50
    GAP = 20

    def render(self, svg, y, xmul):
        rect = ET.SubElement(svg, 'rect', x = str(self.start * xmul), y = str(y), width = str((self.end - self.start) * xmul), height = str(self.HEIGHT))
        rect.set('class', f'start_{self.sword} end_{self.eword}')
        return rect

class Event(object):
    def __init__(self, desc = None, time = None, from_rg = None, with_rg = None, name = None):
        self.desc = desc
        self.time = time
        self.from_rg = set() if from_rg is None else from_rg
        self.with_rg = set() if with_rg is None else with_rg
        self.classes = set()
        self.name = name

    @classmethod
    def from_tokens(cls, tok, hdr):
        inst = cls()
        if len(hdr) > 1:
            inst.name = ' '.join(hdr[1:])
        for t in tok:
            if t is osp.INDENT:
                print('Warning: unexpected event indent', file=sys.stderr)
            elif t is osp.DEDENT:
                return inst
            else:
                if not t:
                    continue
                parts = t.split()
                cmd = parts[0]
                if cmd == 'at':
                    inst.time = float(parts[1])
                elif cmd == 'desc':
                    inst.desc = ' '.join(parts[1:])
                elif cmd == 'from':
                    for p in parts[1:]:
                        inst.from_rg.add(p)
                elif cmd == 'with':
                    for p in parts[1:]:
                        inst.with_rg.add(p)
                elif cmd == 'class':
                    for p in parts[1:]:
                        inst.classes.add(p)
                else:
                    print(f'Warning: unhandled event directive {parts}', file=sys.stderr)
        print('Warning: interpreting EOF as ending event block', file=sys.stderr)
        return inst

    def is_valid(self):
        return self.time is not None

    def link(self, tml):
        for sname in ('from_rg', 'with_rg'):
            sval = getattr(self, sname)
            nval = set(
                tml.ranges[nm] for nm in sval if nm in tml.ranges
            )
            diff = sval - set(rg.name for rg in nval)
            if diff:
                print(f'Warning: link for {sname} failed on ranges with keys: {diff}', file=sys.stderr)
            setattr(self, sname, nval)
        if self.with_rg:
            last = sorted(self.with_rg, key = lambda rg: rg.idx)[-1]
            last.hanging_events.append(self)

    def layout(self, tml, rg):
        self.y = tml.current_y
        tml.current_y += Span.GAP

    def is_universal(self):
        return not (self.from_rg or self.with_rg)

    def is_directional(self):
        return (self.from_rg and self.with_rg)

    def dump(self):
        print(f'  {self!r}', file=sys.stderr)

    def __repr__(self):
        return f'<Event {self.name} at {self.time} desc {self.desc!r} from {self.from_rg} with {self.with_rg}>'

    BOX_HEIGHT = 70
    TEXT_HEIGHT = 20

    def render(self, svg, xmul, tml):
        ln = ET.SubElement(svg, 'line')
        ln.set('class', 'event ' + ' '.join(self.classes))
        lb = ET.SubElement(svg, 'text')
        lb.text = self.desc
        lb.set('class', 'event ' + ' '.join(self.classes))
        x = str(self.time * xmul)
        ln.set('x1', x)
        ln.set('x2', x)
        lb.set('x', x)
        if self.is_universal():
            ln.set('y1', '0')
            ln.set('y2', str(self.y))
            lb.set('y', str(self.y + self.TEXT_HEIGHT))
        else:
            yn = {self.y}
            yx = {self.y}
            for rg in self.from_rg | self.with_rg:
                yn.add(rg.y)
                yx.add(rg.y + Span.HEIGHT)
            yl = min(yn)
            yh = max(yx)
            ln.set('y1', str(yl))
            ln.set('y2', str(yh))
            lb.set('y', str(yh + self.TEXT_HEIGHT))


class Character(Range):
    def __init__(self, name = None, dispname = None, classes = None, gender = None, parents = None):
        super().__init__(name, dispname, classes)
        self.gender = gender
        self.parents = set() if parents is None else parents

    BEGIN_WORDS = Range.BEGIN_WORDS | {'born', 'raised'}
    END_WORDS = Range.END_WORDS | {'died', 'living'}

    @classmethod
    def unhandled_directive(cls, inst, parts):
        cmd = parts[0]
        if cmd == 'gender':
            inst.gender = parts[1]
        elif cmd == 'parent':
            for p in parts[1:]:
                inst.parents.add(p)

    def link(self, tml):
        super().link(tml)
        old_par = self.parents
        self.parents = set(
            tml.ranges[nm] for nm in self.parents if nm in tml.ranges
        )
        diff = old_par - set(rg.name for rg in self.parents)
        if diff:
            print(f'Warning: link for parents for {self.name} failed on ranges with keys: {diff}', file=sys.stderr)

    def additional_repr(self):
        return f' parents {self.parents} gender {self.gender}'

    def render(self, svg, xmul, tml):
        super().render(svg, xmul, tml)
        if not (self.spans and self.parents):
            return
        x = self.spans[0].start * xmul
        yn, yx = set(), set()
        yn.add(self.y)
        yx.add(self.y + Span.HEIGHT)
        for par in self.parents:
            yn.add(par.y)
            yx.add(par.y + Span.HEIGHT)
        yl, yh = min(yn), max(yx)
        ln = ET.SubElement(svg, 'line', x1 = str(x), x2 = str(x), y1 = str(yl), y2 = str(yh))
        ln.set('class', 'child')


class Constraint(object):
    def __init__(self, name = None, before = None, after = None, offset = 0, strict = False):
        self.name = name
        self.before = before
        self.after = after
        self.offset = offset
        self.strict = strict

    def is_valid(self):
        return (self.before is not None) and (self.after is not None)

    @classmethod
    def from_tokens(cls, tok, hdr):
        inst = cls()
        if len(hdr) > 1:
            inst.name = ' '.join(hdr[1:])
        for t in tok:
            if t is osp.INDENT:
                print('Warning: unexpected constraint indent', file=sys.stderr)
            elif t is osp.DEDENT:
                return inst
            else:
                if not t:
                    continue
                parts = t.split()
                cmd = parts[0]
                if cmd == 'before':
                    inst.before = parts[1:]
                elif cmd == 'after':
                    inst.after = parts[1:]
                elif cmd == 'offset':
                    inst.offset = float(parts[1])
                elif cmd == 'strict':
                    inst.strict = True
                else:
                    print(f'Warning: unhandled constraint directive {parts}', file=sys.stderr)
        print('Warning: interpreting EOF as ending constraint block', file=sys.stderr)
        return inst

    @classmethod
    def select(cls, sel, tml):
        grp = tml.groups.get(sel[0])
        if grp is not None:
            return grp.into_result(tml)
        rg = tml.ranges.get(sel[0])
        if rg is not None:
            idx = 0
            prop = 'start'
            if len(sel) > 1:
                prop = sel[-1]
            if len(sel) > 2:
                idx = int(sel[1])
            return GroupResult(sel[0], {getattr(rg.spans[idx], prop)})
        for ev in tml.events:
            if ev.name == sel[0]:
                return GroupResult(sel[0], {ev.time})

    def verify(self, tml):
        bft = self.select(self.before, tml)
        aft = self.select(self.after, tml)
        if bft is None:
            print(f'Warning: selector {self.before} did not resolve', file=sys.stderr)
            return False
        if aft is None:
            print(f'Warning: selector {self.after} did not resolve', file=sys.stderr)
            return False
        if self.strict:
            cond = bft.max() < aft.min() + self.offset
        else:
            cond = bft.max() <= aft.min() + self.offset
        if not cond:
            print(f'Warning: constraint violated: {self.before} = {bft} (max {bft.max()}), {self.after} = {aft} (min {aft.min()}, offset {self.offset} gives {aft.min() + self.offset}), strict {self.strict}', file=sys.stderr)
        return cond

    def __repr__(self):
        return f'<Constraint {self.name} on {self.before} {"<" if self.strict else "<="} {self.after} + {self.offset}>'

    def dump(self):
        print(f'  {self!r}', file=sys.stderr)


class Group(object):
    def __init__(self, name = None, evs = None):
        self.name = name
        self.evs = set() if evs is None else evs

    @classmethod
    def from_tokens(cls, tok, hdr):
        inst = cls()
        if len(hdr) > 1:
            inst.name = ' '.join(hdr[1:])
        for t in tok:
            if t is osp.INDENT:
                print('Warning: unexpected group indent', file=sys.stderr)
            elif t is osp.DEDENT:
                return inst
            else:
                if not t:
                    continue
                parts = t.split()
                cmd = parts[0]
                if cmd == 'event':
                    inst.evs.add(tuple(parts[1:]))
                else:
                    print(f'Warning: unhandled group directive {parts}', file=sys.stderr)
        print('Warning: interpreting EOF as ending group block')
        return inst

    def into_result(self, tml):
        times = set()
        for ev in self.evs:
            tm = Constraint.select(ev, tml)
            if tm is None:
                print(f'Warning: unresolvable name in group {self.name}: {ev}', file=sys.stderr)
                continue
            if isinstance(tm, GroupResult):
                times.update(tm.times)
            else:
                times.add(tm)
        return GroupResult(self.name, times)

class GroupResult(object):
    def __init__(self, name, times):
        self.name = name
        self.times = times

    def min(self):
        return min(self.times)

    def max(self):
        return max(self.times)

    def __repr__(self):
        return f'<GroupResult {self.name} {sorted(self.times)}>'


class Sequence(object):
    @classmethod
    def from_tokens(cls, tok, hdr):
        cons = []
        nm = None
        idx = 0
        if len(hdr) > 1:
            nm = ' '.join(hdr[1:])
        lastev = None
        for t in tok:
            if t is osp.INDENT:
                print('Warning: unexpected sequence indent', file=sys.stderr)
            elif t is osp.DEDENT:
                return cons
            else:
                if not t:
                    continue
                parts = t.split()
                cmd = parts[0]
                if cmd == 'event':
                    ev = parts[1:]
                    if lastev is not None:
                        cons.append(Constraint(f'{nm}_{idx}', lastev, ev))
                        idx += 1
                    lastev = ev
                else:
                    print(f'Warning: unhandled sequence directive {parts}', file=sys.stderr)
        print('Warning: interpreting EOF as ending sequence block')
        return cons


if __name__ == '__main__':
    import sys

    tml = Timeline.from_tokens(osp.tokenize(sys.stdin))
    tml.link()
    tml.layout()
    tml.dump()
    tml.check()
    tml.render()
