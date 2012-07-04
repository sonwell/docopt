#!/usr/bin/env python


# TODO:
# 1. special symbols
#   o ...
#   o [ foo ]
#   o ( bar )
#   o foo | bar
# 2. construct something like TokenStream
# 3. generate patterns from docstring


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
        self.name = name
        self.next = []
        self.value = NodeValue()

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name)
        other.value = self.value
        return other

    def extend(self, tokens, parents):
        if not tokens:
            return self
        for node in self.next:
            res = node.extend(tokens, parents)
            if res is not None:
                return res
        name = tokens[0]
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


class Graph(Node):

    def __init__(self, name=None, parent=None):
        Node.__init__(self, name)
        self.symbols = {} if parent is None else parent.symbols
        self.internal = Node()
        self.result = []

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name, self)
        return Node.copy(self, other)

    def get(self, symbol):
        if symbol in self.symbols:
            old = self.symbols[symbol]
            return old.copy()
        if symbol.startswith('-'):
            new = Option(symbol, [])
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
            self.value.push(tok)
            res[self.name] = self.value
            return res
        tokens.insert(0, tok)
        return None


class Option(Graph):

    def __init__(self, name, args=None):
        Graph.__init__(self, name)
        self.args = args or []

    def  __ne__(self, token):
        return token != self.name

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name, self.args)
        return Graph.copy(self, other)

    def extend(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return self
        if self != tok:
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

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name)
        return Graph.copy(self, other)

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
    A.extend('sudo rm C -v'.split(), [])

    print A.match(sys.argv[1:], [])
