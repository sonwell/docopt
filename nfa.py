class NodeValue(object):

    def __init__(self):
        self.value = None

    def push(self, value):
        if self.value is None:
            self.value = value
        elif type(self.value) is list:
            self.value.append(value)
        else:
            self.value = [self.value, value]

    def __repr__(self):
        return repr(self.value)


class Epsilon(object):

    def __init__(self):
        self.name = None
        self.next = []
        self.value = NodeValue()

    def push(self, other):
        self.value.push(other)

    def extend(self, tokens, parents=[]):
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
        pass

    def __repr__(self):
        next = ''.join(str(self.next)[1:-1].split(','))
        children = '\n  '.join(next.split('\n')[:-1])
        return "<%s(%r)->%r @ %x>:\n  %s" % \
            (self.__class__.__name__, self.name, self.value, 
            id(self.value), children)


class Node(Epsilon):

    def __init__(self, name):
        self.name = name
        self.next = []
        self.value = NodeValue()

    def extend(self, tokens, parents=[]):
        try: tok = tokens.pop(0)
        except: return self
        if self.name != tok:
            tokens.insert(0, tok)
            return None
        return Epsilon.extend(self, tokens, parents)


class Graph(Node):

    def __init__(self, name):
        Node.__init__(self, name)
        self.symbols = {}
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

    def extend(self, tokens, parents=[]):
        parents.insert(0, self)
        tail = self.start.extend(tokens, parents)
        if self not in tail.next:
            tail.next.append(self)
        parents.pop(0)
        return self.end
   
    def __repr__(self):
        start = str(self.start).split('\n  ')
        end = str(self.end).split('\n  ')
        return "<%s(%s)->%r @ %x>:\n  %s\n  %s\n" % \
            (self.__class__.__name__, self.name, self.value, id(self.value),
            '\n   |'.join(start), '\n    '.join(end))

A = Graph(None)
A.extend('A C C'.split())
A.extend('A C B'.split())
A.extend('A C ... B'.split())

print A
