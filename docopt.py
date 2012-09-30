#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from operator import attrgetter

'''
Weighting nodes achieves the same effect as Pattern.either in the old versions,
without resorting to determining types, etc. Lighter nodes will be tested first
when we run through the NFA.

Weight classes:
 ^          0    -- We should never match against '^'.
 Command    1
 Option(s)  1
 Argument   2
 $          0    -- I think it's cheap to check if we're at the end, and
                    will avoid a problem with infinite loops via '...'.
'''

def debug_msg(*msg):
    if len(msg) == 1:
        msg = msg[0]
    if DEBUG:
        sys.stderr.write(str(msg) + '\n')


class orderedset(list):

    def __init__(self, vals=None):
        list.__init__(self)
        if vals is not None:
            for val in vals:
                self.add(val)

    def add(self, new):
        if new not in self:
            self.append(new)


class Node(object):

    def __init__(self, name, symbols):
        self.name = name
        self.symbols = symbols
        self.next = orderedset()
        self.value = []
        self.collapsed = False
        self.repred = False

    def extend(self, stream, last):
        if not stream:
            self.next.add(DOLLAR)
            return DOLLAR
        name = stream[0]
        if name in ')]|':
            return self
        for node in self.next:
            tail = node.extend(stream, last)
            if tail is not None:
                return tail
        if name in '([':
            stream.pop(0)
            start, end = Epsilon(), Epsilon()
            self.next.add(start)
            next = '|'
            while next == '|':
                tail = start.extend(stream, start)
                tail.next.add(end)
                next = stream.pop(0)
            if next not in ')]':
                raise ValueError('Unbalanced parentheses or brackets.')
            if name == '[':
                self.next.add(end)
            return end.extend(stream, start)
        elif name == '...':
            self.next.add(last)
            stream.pop(0)
            return Node.extend(self, stream, self)
        else:
            new = self.get(name)
            self.next.add(new)
            return new.extend(stream, new)

    def set(self, value):
        self.value.append(value)

    def get(self, name):
        if name in self.symbols:
            return self.symbols[name].copy()
        if name.isupper() or (name[0] == '<' and name[-1] == '>'):
            new = Argument(name, self.symbols)
        elif name.startswith('-'):
            new = Option(name, {})
        else:
            new = Command(name, {})
        self.symbols[name] = new
        return new.copy()

    def collapse(self):
        if not self.collapsed:
            self.collapsed = True
            self.next = sorted(orderedset(node for next in self.next 
                                          for node in next.collapse()),
                               key=attrgetter('weight'))
        return [self]

    def match(self, stream):
        for node in self.next:
            try:
                res = node.match(stream)
                if res is not None:
                    return res
            except:
                continue
        return None

    def copy(self):
        new = self.__class__(self.name, self.symbols)
        new.value = self.value
        new.next = orderedset(self.next)
        return new

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        info = self.__class__.__name__, self.name
        if not self.repred:
            self.repred = True
            next = '\n  '.join(line for node in self.next
                               for line in repr(node).split('\n'))
            return '%s(%r, ...)\n  %s' % (info + (next,))
        return '%s(%r, ...)\n  ...' % info


class Epsilon(Node):

    weight = 1000

    def __init__(self):
        Node.__init__(self, 'ε', {})

    def collapse(self):
        if not self.collapsed:
            self.collapsed = True
            self.next = orderedset(node for next in self.next
                                   for node in next.collapse())
        return self.next

    def __repr__(self):
        if not self.repred:
            self.repred = True
            if self.next:
                next = '\n  '.join(line for node in self.next
                                   for line in repr(node).split('\n'))
                return 'ε\n  %s' % next
            else:
                return 'ε'
        return 'ε'


class Argument(Node):

    weight = 2

    def extend(self, stream, last):
        if not stream:
            return DOLLAR
        name = stream[0]
        if name != self.name:
            return None
        stream.pop(0)
        return Node.extend(self, stream, self)

    def match(self, stream):
        tok = stream.pop(0)
        res = Node.match(self, stream)
        if res is not None:
            self.set(tok)
            res[self.name] = self.value
            return res
        stream.insert(0, tok)
        return None


class Option(Argument):

    weight = 1

    def match(self, stream):
        if not stream:
            return None
        name = stream.pop(0)
        if name == self.name:
            res = Node.match(self, stream)
            if res is not None:
                self.set(True)
                res[self.name] = self.value
                return res
        stream.insert(0, name)
        return None


class Command(Argument):

    weight = 1


    def match(self, stream):
        if not stream:
            return None
        name = stream.pop(0)
        if name == self.name:
            res = Node.match(self, stream)
            if res is not None:
                self.set(True)
                res[self.name] = self.value
                return res
        stream.insert(0, name)
        return None


class Beginning(Node): # In typical notation, ^

    weight = 0

    def __init__(self):
        Node.__init__(self, '^', {})

    def __repr__(self):
        next = '\n  '.join(line for node in self.next
                           for line in repr(node).split('\n'))
        return '%s\n  %s' % (self.name, next)


class Terminus(Node): # In typical notation, $
    
    weight = 0

    def __init__(self):
        Node.__init__(self, '$', {})

    def __repr__(self):
        return self.name

    def match(self, stream):
        if not stream:
            return {}
        return None


CARET = Beginning()
DOLLAR = Terminus()
DEBUG = 1
if __name__ == '__main__':
    import sys
    tokens = ['test', '[', 'y', '[', '--opt', 'Z',']', ']', '...', 'W']
    CARET.extend(tokens, None)
    CARET.collapse()
    print CARET.match(['test', 'y', '--opt', 1, 'y', 'X'])
