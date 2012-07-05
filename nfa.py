#!/usr/bin/env python


# TODO:
# 1. special symbols
#   o ...
#   o [ foo ]
#   o ( bar )
#   o foo | bar
# 2. generate patterns from docstring

class TokenStream(list):

    def __init__(self, stream):
        if type(stream) is list:
            list.__init__(self, stream)
            self.stream = ''
        else:
            list.__init__(self)
            self.stream = stream.strip()
        self.scopes = []

    def __getitem__(self, key):
        if key >= len(self):
            for i in xrange(key - len(self) + 1):
                self.append(self.pop(0)) 
        return list.__getitem__(self, key)

    def enter(self, parent):
        self.scopes.insert(0, parent)
        return self

    def exit(self):
        self.scopes.pop(0)
        return self

    def multichar(self, stream):
        l, i = len(stream), 0
        if stream[0] == '.':
            while i < l and i < 3 and stream[i] == '.':
                i += 1
            token, stream = stream[:i], stream[i:]
            self.append(token)
            return stream
        while i < l and stream[i].lstrip():
            if stream[i] in '[]()|' or stream[i:i + 3] == '...':
                break
            if stream[i] == '=':
                stream = stream[:i] + stream[i+1:]
                break
            i += 1
        token, stream = stream[:i], stream[i:]
        self.append(token)
        return stream

    def pop(self, index=0):
        stream = self.stream
        if len(self) > index:
            return list.pop(self, index)
        elif stream:
            stream = stream.lstrip()
            l = len(stream)
            if stream[0] in '[]()|':
                self.append(stream[0])
                self.stream = stream[1:]
            elif stream[0] == '-':
                if l == 1 or not stream[1].lstrip():
                    self.append('-')
                    self.stream = stream[1:]
                    return self.pop(index)

                if stream[1] == '-':
                    self.stream = self.multichar(stream)
                else:
                    token = stream[:2]
                    symbol = self.scopes[0].get(token)
                    self.append(token)
                    if len(symbol.args) == 0:
                        if l < 3:
                            self.stream = ''
                        elif stream[2] in '[]()|-.':
                            self.stream = stream[2:]
                        elif ord(stream[2]) <= 32:
                            self.stream = stream[2:]
                        else:
                            self.stream = '-' + stream[2:]
            else:
                self.stream = self.multichar(stream)
        else:
            self.append(None)
        return self.pop(index)


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
        name = tokens[0]
        if name is None:
            return self
        for node in self.next:
            res = node.extend(tokens, parents)
            if res is not None:
                return res
        new = parents[0].get(name)
        self.next.append(new)
        return new.extend(tokens, parents)

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
            tokens.exit()
            return self.exit(tokens, parents)
        else:
            tokens.enter(self)
            return self.entry(tokens, parents)


class Argument(Node):

    def extend(self, tokens, parents):
        tok = tokens.pop(0)
        if tok is None:
            return self
        if self.name != tok:
            tokens.insert(0, tok)
            return None
        return Node.extend(self, tokens, parents)

    def match(self, tokens, parents):
        tok = tokens.pop(0)
        if tok is None:
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
        tok = tokens.pop(0)
        if tok is None:
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
        tok = tokens.pop(0)
        if tok is None:
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
    for line in ('sudo rm C B --v', 'sudo rm C -v'):
        ts = TokenStream(line)
        ts.enter(A)
        A.extend(ts, [])
        ts.exit()

    print A.match(TokenStream(sys.argv[1:]), [])
