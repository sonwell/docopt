#!/usr/bin/env python

"""
TODO:
    1. Graph.get chooses the correct type e.g. Command, Option, Argument
    2. Options
"""

class NodeValue(object):

    def __init__(self):
        self.value = None

    def push(self, value):
        if self.value is None:
            self.value = value
        elif type(self.value) is list:
            self.value.insert(0, value)
        else:
            self.value = [value, self.value]

    def __repr__(self):
        return repr(self.value)


class Node(object):

    def __init__(self, name=None):
        self.reprd = False
        self.name = name
        self.next = []
        self.value = NodeValue()

    def push(self, other):
        self.value.push(other)

    def extend(self, tokens, parents):
        if not tokens:
            return self
        name = tokens[0]
        for node in self.next:
            res = node.extend(tokens, parents)
            if res is not None:
                return res
        new = parents[0].get(name)
        self.next.append(new)
        return new.extend(tokens, parents)

    def match(self, tokens, parents):
        if not tokens and not self.next:
            return {}
        for node in self.next:
            res = node.match(tokens, parents)
            if res is not None:
                return res
        return None

    def __repr__(self):
        next = ''.join(str(self.next)[1:-1].split(','))
        children = '\n  '.join(next.split('\n')[:-1])
        repl = "<%s(%r)->%r @ %x>:\n  %s" % \
            (self.__class__.__name__, self.name, self.value,
             id(self.value), children)
        return repl


class Graph(Node):

    def __init__(self, name=None, parent=None):
        Node.__init__(self, name)
        self.symbols = {} if parent is None else parent.symbols
        self.internal = Node()
        self.result = []

    def get(self, symbol):
        if symbol in self.symbols:
            old = self.symbols[symbol]
            new = old.__class__(symbol)
            new.value = old.value
            return new
        if symbol.startswith('-'):
            if symbol[1] == '-':
                new = Option(None, symbol, [])
            else:
                new = Option(symbol, None, [])
        elif symbol.isupper() or \
           (symbol[0] == '<' and symbol[-1] == '>'):
            new = Argument(symbol)
        else:
            new = Command(symbol)
        self.symbols[symbol] = new
        return new

    def extend(self, tokens, parents):
        parents.insert(0, self)
        tail = self.internal.extend(tokens, parents)
        if self not in tail.next:
            tail.next.append(self)
        tail.next.append(Node())
        parents.pop(0)
        return self

    def exit(self, tokens, parents):
        parents.pop(0)
        res = Node.match(self, tokens, parents)
        if res is not None:
            return res
        parents.insert(0, self)
        return None
        
    def entry(self, tokens, parents):
        if self.name:
            try:
                tok = tokens.pop(0)
            except:
                return None
            if self != tok:
                tokens.insert(0, tok)
                return None
        parents.insert(0, self)
        return self.internal.match(tokens, parents)

    def match(self, tokens, parents):
        if parents and parents[0] is self:  # we've been here before...
            return self.exit(tokens, parents)
        else:
            return self.entry(tokens, parents)

    def __repr__(self):
        start = str(self.internal).strip().split('\n  ')
        end = (Node.__repr__(self)).split('\n  ')
        repl = "<%s(%s)->%r @ %x>:\n  %s\n  %s\n" % \
            (self.__class__.__name__, self.name, self.value,
             id(self.value), '\n   |'.join(start), '\n    '.join(end))
        return repl


class Argument(Node):

    def extend(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return self
        if self.name != tok:
            tokens.insert(0, tok)
            return None
        return Node.extend(self, tokens, parents)

    def match(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return None
        res = Node.match(self, tokens, parents)
        if res is not None:
            self.push(tok)
            res[self.name] = self.value
            return res
        tokens.insert(0, tok)
        return None


class Option(Graph):

    def __init__(self, short, long, args):
        Graph.__init__(self, long or short)
        self.long = long
        self.short = short
        self.args = args

    def  __ne__(self, token):
        return token not in (self.short, self.long)

    def extend(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return self
        if tok not in (self.long, self.short):
            tokens.insert(0, tok)
            return None
        tail = self.internal
        for arg in self.args:
            new = Argument(arg)
            tail.next.append(new)
            tail = new
        tail.next.append(self)
        return self

    def exit(self, tokens, parents):
        parents.pop(0)
        res = Node.match(self, tokens, parents)
        if res is not None:
            self.result.insert(0, res)
            return {}
        parents.insert(0, self)
        return None

    def entry(self, tokens, parents):
        res = Graph.entry(self, tokens, parents)
        if res is not None:
            if self.args:
                for arg in self.args:
                    self.value.push(res[arg])
            else:
                self.value.push(True)
            result = self.result.pop(0)
            result[self.name] = self.value
            return result
        return None


class Command(Option):
    
    def __init__(self, name):
        Graph.__init__(self, name, None)

    def __ne__(self, token):
        return self.name != token

    def extend(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return self
        if self != tok:
            tokens.insert(0, tok)
            return None
        return Graph.extend(self, tokens, parents)

    def entry(self, tokens, parents):
        res = Graph.entry(self, tokens, parents)
        if res is not None:
            result = self.result.pop(0)
            result[self.name] = res
            return result
        return None


if __name__ == '__main__':
    import sys
    A = Command('sudo')
    A.extend('sudo rm C B -v'.split(), [])

    print A.match(sys.argv[1:], [])
