#!/usr/bin/env python

class TokenStream(list):

    def __init__(self, stream, parse_equals=True):
        if type(stream) is list:
            list.__init__(self, stream)
            self.stream = ''
        else:
            for sub in tuple('[]()|') + ('...',):
                stream = stream.replace(sub, ' %s ' % sub)
            list.__init__(self, stream.split())
        self.parsed = []
        self.scopes = []
        self.parse_equals = parse_equals

    def __getitem__(self, key):
        while len(self.parsed) <= key:
            self.parsed.append(self.parse())
        return self.parsed[key]
   
    def __repr__(self):
        return repr(self.parsed) + ' ' + list.__repr__(self)

    def enter(self, parent):
        self.scopes.insert(0, parent)
        return self

    def exit(self):
        self.scopes.pop(0)
        return self

    def push(self, other):
        self.parsed.insert(0, other)

    def pop(self):
        if len(self.parsed) > 0:
            return self.parsed.pop(0)
        return self.parse()

    def parse(self):
        if len(self) == 0:
            return None
        tok = list.pop(self, 0)
        if len(tok) <= 2 or tok[0] != '-':
            return tok
        if tok[1] != '-':
            symbol = self.scopes[0].get(tok[:2])
            if len(symbol.args) > 0:
                self.insert(0, tok[2:])
            else:
                self.insert(0, '-' + tok[2:])
            tok = tok[:2]
        elif len(tok) > 3:
            pos = tok.find('=')
            if pos > 2:
                tok, arg = tok[:pos], tok[pos+1:]
                self.insert(0, arg)
        return tok


class NodeValue(object):

    def __init__(self, default=None):
        self.value = None
        self.default = default

    def push(self, value):
        if self.value is None:
            self.value = value
        elif type(self.value) is list:
            self.value.insert(0, value)
        else:
            self.value = [value, self.value]

    def __repr__(self):
        return repr(self.value or self.default)


class Node(object):

    def __init__(self, name=None):
        self.name = name
        self.next = []
        self.value = NodeValue()

    def __repr__(self):
        return repr(self.name) + ', ' + repr(self.next)

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name)
        other.value = self.value
        return other

    def extend(self, tokens, parents, last):
        name = tokens[0]
        if name is None or name in '|)]':
            return self
        if name == '...':
            for node in self.next:
                if node.name == self.name:
                    return node.extend(tokens, parents, last)
            tokens.pop()
            new = last.copy()
            join = Node()
            self.next.append(new)
            self.next.append(join)
            new.next.append(new)
            new.next.append(join)
            return join.extend(tokens, parents, new)
        if name in '([':
            tokens.pop()
            new = Graph()
            new.symbols = parents[0].symbols
            new.extend(tokens, parents, last)
            tok = tokens.pop()
            while tok == '|':
                new.extend(tokens)
                tok = tokens.pop()
            if (name == '(' and tok != ')') or (name == '[' and tok != ']'):
                raise ValueError('Unmatched closing bracket or paren')
            self.next.append(new)
            join = Node()
            new.next.append(join)
            if name == '[':
                self.next.append(join)
            return join.extend(tokens, parents, new)
        for node in self.next:
            res = node.extend(tokens, parents, last)
            if res is not None:
                return res
        new = parents[0].get(name)
        self.next.append(new)
        return new.extend(tokens, parents, last)

    def match(self, tokens, parents):
        if tokens[0] is None and not self.next:
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

    def __repr__(self):
        return repr(self.name) + ', (' + repr(self.internal) + ') ' + repr(self.next)

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name, self)
        other.internal = self.internal
        return Node.copy(self, other)

    def get(self, symbol):
        if symbol in self.symbols:
            old = self.symbols[symbol]
            return old.copy()
        if symbol.startswith('-'):
            new = Option(symbol, [])
        elif symbol.isupper() or (symbol[0] == '<' and symbol[-1] == '>'):
            new = Argument(symbol)
        else:
            new = Command(symbol)
        self.symbols[symbol] = new
        return new

    def extend(self, tokens, parents, last):
        parents.insert(0, self)
        tail = self.internal.extend(tokens, parents, self)
        if self not in tail.next:
            tail.next.append(self)
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
            tok = tokens.pop()
            if tok is None:
                return None
            if self != tok:
                tokens.push(tok)
                return None
        parents.insert(0, self)
        res = self.internal.match(tokens, parents)
        if res is None:
            parents.pop(0)
            return None
        return res

    def match(self, tokens, parents):
        if parents and parents[0] is self:  # we've been here before...
            tokens.exit()
            res = self.exit(tokens, parents)
            if res is None:
                tokens.enter(self)
            return res
        else:
            tokens.enter(self)
            return self.entry(tokens, parents)


class Argument(Node):

    def extend(self, tokens, parents, last):
        tok = tokens.pop()
        if tok is None:
            return self
        if self.name != tok:
            tokens.push(tok)
            return None
        return Node.extend(self, tokens, parents, self)

    def match(self, tokens, parents):
        tok = tokens.pop()
        if tok is None:
            return None
        res = Node.match(self, tokens, parents)
        if res is not None:
            self.value.push(tok)
            res[self.name] = self.value
            return res
        tokens.push(tok)
        return None


class Option(Graph):

    def __init__(self, name, args=None):
        Graph.__init__(self, name)
        self.args = args if args is not None else []

    def  __ne__(self, token):
        return token != self.name

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name, self.args)
        return Graph.copy(self, other)

    def extend(self, tokens, parents, last):
        tok = tokens.pop()
        if tok is None:
            return self
        if self != tok:
            tokens.push(tok)
            return None
        tail = self.internal
        for arg in self.args:
            new = Argument(arg)
            tail.next.append(new)
            tail = new
        tail.next.append(self)
        return Node.extend(self, tokens, parents, self)

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

    def copy(self, other=None):
        if other is None:
            other = self.__class__(self.name)
        return Graph.copy(self, other)

    def extend(self, tokens, parents, last):
        tok = tokens.pop()
        if tok is None:
            return self
        if self != tok:
            tokens.push(tok)
            return None
        return Graph.extend(self, tokens, parents, self)

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
    for line in ('sudo (add C B ...) --v', 'sudo (rm [C]) -vc'):
        ts = TokenStream(line)
        ts.enter(A)
        A.extend(ts, [], None)
        ts.exit()

    print A.match(TokenStream(sys.argv[1:], False), [])
