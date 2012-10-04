#!/usr/bin/env python
# -*- encoding: utf-8 -*-

'''
Weighting the nodes helps speed up searching through the NFA by choosing paths
that will return immediately if it is wrong (e.g., to an option or command).
Lighter nodes will be tested first when we run through the NFA.

Weight classes:
 ^          0    -- We should never match against '^'.
 Command    1
 Option(s)  1
 Argument   2
 $          0    -- I think it's cheap to check if we're at the end, and
                    will avoid a problem with infinite loops via '...'.
'''

'''
A call to docopt will (eventually) perform the following:

Collect option definitions. This will create the basal symbol table that all
nodes inherit from (Node._sym).

Build an NFA (extend methods):
  Take for example the usage pattern
    test [y [Z]]... [W]
  The NFA will look like
  (test) -> ε'[' -> (y) -> ε'[' -> (Z) -> ε']' -> ε']' -> ε'[' -> (W) -> ε']'
   ^        |`.             `------>-------'      .'|      `------->------'|
   |        `. `--------------->-----------------' .'                      v
   ^          `<----------------------------------'                        $
  where ^ and $ and the above line are the starting and accepting nodes,
  respectively.

Collapse the NFA (collapse methods; remove epsilons):
                  .---<--.
  ^ -> (test) -> (y) -> (Z) -> (W) -> $
         `.      '-^----->------+-----'
           `---------->--------'
  where y has a has a path to itself (observe that this is true via the usage
  pattern).

Move through the NFA (match methods). If we reach the accepting ($) state with
an empty token stream, then we accept. As we return through the NFA, we will
pair nodes with values. Currently it is returning a dict just like the
reference implementation, but considering the things we get for free from the
NFA, and the possibility of delegating according to subcommand use, this may
not be the best choice.
'''

'''
TODO:
 * Collapse the following pattern into a single ε --> Options --> ε:
                                                 `------->-------'
                            .-------<?------.
   ε --> Options --> ε --> ε --> Options --> ε
    `------->-------'       `------>--------'
   which corresponds to
   [*options*] [*more options*] -> [*options* *more options*]
   with both sides followed optionally by ...
'''
from operator import attrgetter


class DocoptLanguageError(Exception):
    pass


class DocoptExit(SystemExit):

    message = None

    def __init__(self, message=None)
        SystemExit.__init__(self, message or DocoptExit.message)


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

    def __add__(self, new):
        return orderedset(list.__add__(self, new))

    def __sub__(self, new):
        return orderedset(a for a in self if a not in new)


class Node(object):

    weight = 1000
    count = 0

    def __repr__(self):
        info = (self.__class__.__name__, self.name, self.count)
        rep = '%s(%r, ...) [%d]' % info
        if not self.repred:
            self.repred = True
            for node in self.next:
                rep += '\n  ' + '\n  '.join(repr(node).split('\n'))
        elif self.next:
            rep += ' ...'
        return rep

    def __init__(self, name, symbols):
        self.name = name
        self.symbols = dict(symbols)
        self._sym = symbols
        self.next = orderedset()
        self.value = []
        self.collapsed = False
        self.repred = False
        self.count = Node.count
        Node.count += 1

    def extend(self, stream, last):
        if not stream:
            self.next.add(DOLLAR)
            return DOLLAR
        name = stream[0]
        if name in ')]|':
            return self
        elif name in '([':
            stream.pop(0)
            start, end = Epsilon(self._sym), Epsilon(self._sym)
            self.next.add(start)
            next = '|'
            while next == '|':
                tail = start.extend(stream, start)
                tail.next.add(end)
                next = stream.pop(0)
            if next != {'(': ')', '[': ']'}[name]:
                word = {'(': 'parentheses', '[': 'brackets'}[name]
                raise DocoptLanguageError('Unbalanced %s.' % word)
            if name == '[':
                self.next.add(end)
            return end.extend(stream, start)
        elif name == '...':
            self.next.add(last)
            stream.pop(0)
            return Node.extend(self, stream, self)
        for node in self.next:
            tail = node.extend(stream, last)
            if tail is not None:
                return tail
        new = self.get(name)
        self.next.add(new)
        return new.extend(stream, new)

    def set(self, value):
        self.value.append(value)

    def get(self, name):
        if Option.test(name):
            return Options(self._sym)
        elif name in self.symbols:
            old = self.symbols[name]
        elif Argument.test(name):
            old = Argument(name, self.symbols)
        else:
            old = Command(name, self._sym)
        self.symbols[name] = old
        new = old.copy()
        new.next = orderedset(old.next)
        return new

    def collapse(self):
        if not self.collapsed:
            self.collapsed = True
            self.next = sorted(orderedset(node for next in self.next
                                          for node in next.collapse()),
                               key=attrgetter('weight'))
        return [self]

    def match(self, stream, double_dash):
        for node in self.next:
            res = node.match(stream, double_dash)
            if res is not None:
                return res
        return None

    def copy(self):
        new = self.__class__(self.name, self.symbols)
        new.value = self.value
        new.next = orderedset(self.next)
        if self in new.next:
            new.next = (new.next - [self]) + [new]
        return new


class Epsilon(Node):

    def __init__(self, symbols):
        Node.__init__(self, 'ε', symbols)

    def collapse(self):
        if not self.collapsed:
            self.collapsed = True
            self.next = orderedset(node for next in self.next
                                   for node in next.collapse())
        return self.next

    def match(self, stream, double_dash):
        raise NotImplementedError("Somehow you've attempted to match " +
                                  "against an epsilon node. Contact the" +
                                  "devs at <https://github.com/docopt>.")
        return None


class Options(Epsilon):

    def __init__(self, symbols):
        Epsilon.__init__(self, symbols)
        self.options = orderedset()
        self.tracking = []

    def collapse(self):
        copies = orderedset([] if self.options - self.tracking
                            else Epsilon.collapse(self))
        for option in self.options - self.tracking:
            copy = option.copy()
            copies.add(copy)
            self.tracking.insert(0, option)
            copy.collapse()
            self.tracking.pop(0)
        return sorted(copies, key=attrgetter("weight"))

    def extend(self, stream, last):
        if not stream:
            self.next.add(DOLLAR)
            return DOLLAR
        while True:
            if not stream:
                break
            name = stream[0]
            if not Option.test(name):
                break
            curr = self.get(name)
            self.options.add(curr)
            tail = curr.extend(stream, self)
            if tail is not None:
                tail.next.add(self)
        return Node.extend(self, stream, self)

    def get(self, name):
        if name in self.symbols:
            new = self.symbols[name].copy()
        elif Option.test(name):
            new = Option(name, self._sym)
            #new.extend([name], self)
        else:
            return Node.get(self, name)
        self.symbols[name] = new
        return new


class Argument(Node):

    weight = 2

    def extend(self, stream, last):
        if not stream:
            return DOLLAR
        name = stream[0]
        if self.name == name:
            stream.pop(0)
            return Node.extend(self, stream, self)
        return None

    def match(self, stream, double_dash):
        if not stream:
            return None
        tok = stream.pop(0)
        res = Node.match(self, stream, double_dash)
        if res is not None:
            self.set(tok)
            res[self.name] = self.value
            return res
        stream.insert(0, tok)
        return None

    @classmethod
    def test(klass, token):
        if token[0] == '<' and token[-1] == '>':
            return True
        return token.isupper()


class Option(Argument):

    weight = 1

    def __init__(self, name, symbols):
        Argument.__init__(self, name, symbols)
        self.names = [name]

    def match(self, stream, double_dash):
        if not stream:
            return None
        name = stream.pop(0)
        if name in self.names:
            res = Node.match(self, stream, double_dash)
            if res is not None:
                self.set(True)
                for name in self.names:
                    res[name] = self.value
                return res
        stream.insert(0, name)
        return None

    def extend(self, stream, last):
        # Note: avoid this when creating Options from
        #       option descriptions
        stream.pop(0)
        if stream and stream[0] == '...':
            stream.pop(0)
            self.next.add(self)
        return self

    @classmethod
    def test(klass, token):
        if token in '--':
            return False
        if token[0] == '-':
            return True
        return False


class Command(Argument):

    weight = 1

    def match(self, stream, double_dash):
        if not stream:
            return None
        name = stream.pop(0)
        if self.name == name:
            res = Node.match(self, stream, name == '--')
            if res is not None:
                self.set(True)
                res[name] = self.value
                return res
        stream.insert(0, name)
        return None

    @classmethod
    def test(klass, token):
        return not Option.test(token) and not Argument.test(token)


class Beginning(Node):  # In typical notation, ^

    weight = 0

    def __init__(self, symbols):
        Node.__init__(self, '^', symbols)


class Terminus(Epsilon):  # In typical notation, $

    weight = 0

    def __init__(self, symbols):
        Node.__init__(self, '$', symbols)

    def match(self, stream, double_dash):
        if not stream:
            return {}
        return None

    def collapse(self):
        if self.next:
            return Epsilon.collapse(self)
        else:
            return Node.collapse(self)

    def extend(self, stream, last):
        if stream:
            return None
        return self


SYMBOLS = {}
CARET = Beginning(SYMBOLS)
DOLLAR = Terminus(SYMBOLS)
DEBUG = 1
if __name__ == '__main__':
    import sys
    tokens = ['-c', '-a', '...', '-b', 'Z']
    CARET.extend(tokens, None)
    CARET.collapse()
    print(CARET.match(['-c', '-b', '-a', '-a', 3], False))
