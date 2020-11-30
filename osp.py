# Off-Side Parser

import re

LWS = re.compile(r'[ \t]*')

DEDENT = object()
INDENT = object()

def tokenize(lines, tabs=4):
    lev_stack = [0]
    only_tabbed = True
    for line in lines:
        mt = LWS.match(line)
        span = mt.group(0)
        if not span:
            lev = 0
        else:
            if ' ' in span:
                only_tabbed = False
            t = tabs
            if only_tabbed:
                t = 1
            lev = span.count(' ')
            if '\t' in span:
                if t is None:
                    raise ValueError(f'cannot calculate length of span {span!r}')
                lev += span.count('\t') * t

        if lev > lev_stack[-1]:
            lev_stack.append(lev)
            yield INDENT
        elif lev < lev_stack[-1]:
            while lev_stack and lev_stack[-1] > lev:
                lev_stack.pop()
                yield DEDENT
            if lev_stack[-1] < lev:
                raise ValueError(f'level {lev} corresponds to no outer indent level (nearest {lev_stack})')

        yield line[mt.span()[1]:].strip()

    while len(lev_stack) > 1:
        lev_stack.pop()
        yield DEDENT

def read_block(tok, callback=None):
    lev = 0
    for t in tok:
        if t is INDENT:
            lev += 1
        if t is DEDENT:
            lev -= 1
            if lev == 0:
                break
        if callback is not None:
            callback(t)

if __name__ == '__main__':
    import sys

    olev = 0
    for op in tokenize(sys.stdin):
        if op is INDENT:
            print(f'{olev * "  "}INDENT')
            olev += 1
        elif op is DEDENT:
            olev -= 1
            print(f'{olev * "  "}DEDENT')
        else:
            print(f'{olev * "  "}{op!r}')

