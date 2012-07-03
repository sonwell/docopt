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


class Epsilon(object):

    def __init__(self):
        self.reprd = False
        self.name = None
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
#        if self.reprd:
#            return '...'
#        self.reprd = True
        next = ''.join(str(self.next)[1:-1].split(','))
        children = '\n  '.join(next.split('\n')[:-1])
        repl = "<%s(%r)->%r @ %x>:\n  %s" % \
            (self.__class__.__name__, self.name, self.value,
             id(self.value), children)
#        self.reprd = False
        return repl


class Node(Epsilon):

    def __init__(self, name):
        Epsilon.__init__(self)
        self.name = name

    def extend(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return self
        if self.name != tok:
            tokens.insert(0, tok)
            return None
        return Epsilon.extend(self, tokens, parents)

    def match(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return None
        res = Epsilon.match(self, tokens, parents)
        if res is not None:
            self.push(tok)
            res[self.name] = self.value
            return res
        tokens.insert(0, tok)
        return None


class Graph(Node):

    def __init__(self, parent=None):
        Node.__init__(self, None)
        self.symbols = {} if parent is None else parent.symbols
        self.start = Epsilon()
        self.end = Epsilon()
        self.next = self.end.next

    def get(self, symbol):
        if symbol in self.symbols:
            old = self.symbols[symbol]
            new = old.__class__(symbol)
            new.value = old.value
            return new
        new = Node(symbol)
        self.symbols[symbol] = new
        return new

    def extend(self, tokens, parents):
        parents.insert(0, self)
        tail = self.start.extend(tokens, parents)
        if self not in tail.next:
            tail.next.append(self)
#        tail.next.append(Epsilon())
        parents.pop(0)
        return self.end

    def match(self, tokens, parents):
        if parents and parents[0] is self:  # we've been here before...
            parents.pop(0)
            res = self.end.match(tokens, parents)
            if res is not None:
                return res
            parents.insert(0, self)
            return None
        else:
            parents.insert(0, self)
            return self.start.match(tokens, parents)

    def __repr__(self):
#        if self.reprd:
#            return '...'
#        self.reprd = True
        start = str(self.start).strip().split('\n  ')
        end = str(self.end).split('\n  ')
        repl = "<%s(%s)->%r @ %x>:\n  %s\n  %s\n" % \
            (self.__class__.__name__, self.name, self.value,
             id(self.value), '\n   |'.join(start), '\n    '.join(end))
#        self.reprd = False
        return repl


class Command(Graph):
    
    def __init__(self, name):
        Graph.__init__(self, None)
        self.name = name
        self.result = []

    def extend(self, tokens, parents):
        try:
            tok = tokens.pop(0)
        except:
            return self
        if self.name != tok:
            tokens.insert(0, tok)
            return None
        Graph.extend(self, tokens, parents)

    def match(self, tokens, parents):
        if parents and parents[0] is self:
            parents.pop(0)
            res = self.end.match(tokens, parents)
            if res is not None:
                self.result.insert(0, res)
                return {}
            parents.insert(0, self)
            return None
        else:
            if self.name is not None:
                tok = tokens.pop(0)
                if tok != self.name:
                    tokens.insert(0, tok)
                    return None
            parents.insert(0, self)
            res = self.start.match(tokens, parents)
            if res is not None and self.result is not None:
                result = self.result.pop(0)
                result[self.name] = res
                return result
            return None


A = Command('rm')
A.extend('rm C C'.split(), [])
A.extend('rm C B'.split(), [])

B = Command('sudo')
A.next.append(B)
B.start.next.append(A)

print str(B).strip()
print B.match(['sudo', 'rm', 'B', 'C'], [])
