def _is_argument(name):
    return name[0] == '<' and name[-1] == '>' or name.isupper()

def _is_option(name):
    return name[0] == '-' and name not in '--'

class Node(object):

    def __init__(self, name, symbols):
        self.name = name
        self.next = []
        self.options = []
        self.follow = []
        self.symbols = symbols
        self.proto = self
        self.repred = 0

    def parse(self, tokens, prev):
        if not tokens:
            return DOLLAR.parse(tokens, prev)
        next = self.get(tokens)
        return next.parse(tokens, prev)

    def build(self, used):
        if set(used) - set(self.options):
            return None
            # break
        for option in self.options:
            if option not in used:
                copy = option.copy()
                new = self.copy()
#                copy.follow.append(self)
#                self.follow.append(copy)
                new.build(used + [option])
        for node in self.next:
            copy = node.copy()
            if copy not in self.follow:
                self.follow.append(copy)
            copy.build(used)

    def collapse(self):
        self.follow = [node for f in self.follow for node in f.collapse()]
        return [self]

    def match(self, tokens):
        for node in self.follow:
            res = node.match(tokens)
            if res is not None:
                return res
        return None

    def copy(self):
        copy = self.__class__(self.name, self.symbols)
        copy.next = self.next
        copy.options = self.options
        copy.proto = self.proto
        return copy

    def __eq__(self, other):
        return self.proto is other.proto

    def get(self, tokens):
        name = tokens.pop(0)
        if name in self.symbols:
            return self.symbols[name].copy
        if _is_option(name):
            if len(name) > 2:
                if name[1] == '-':  # -o<arg> format
                    name, arg = name[:2], name[2:]
                    tokens.insert(0, arg)
                elif '=' in name:   # --long=<arg> format
                    name, args = name.split('=', 1)
                    tokens.insert(0, arg)
            sym = Option(name, self.symbols)
        elif _is_argument(name):
            sym = Argument(name, self.symbols)
        else:
            sym = Command(name, self.symbols)
        self.symbols[name] = sym
        return sym.copy()

    def __repr__(self):
        if self.repred < 3:
            self.repred += 1
            items = self.follow
            cl = self.__class__.__name__
            if items:
                nexts = '\n  '.join('\n  '.join(repr(node).split('\n'))
                                                for node in items)
                return '%s(%r)\n  %s' % (cl, self.name, nexts) 
            return '%s(%r)' % (cl, self.name) 
            self.repred -= 1
        return '...'


class Literal(Node):

    def match(self, tokens):
        name = tokens.pop(0)
        if self.name == name:
            res = Node.match(self, tokens)
            if res is None:
                tokens.insert(0, name)
                return res
            res[name] = True
            return res
        return None

class Variable(Node):

    def match(self, tokens):
        name = tokens.pop(0)
        res = Node.match(self, tokens)
        if res is None:
            tokens.insert(0, tokens)
            return res
        res[self.name] = name
        return res

class Argument(Variable):

    weight = 1

    def parse(self, tokens, prev):
        next, options = Node.parse(self, tokens, prev)
        self.options = prev + options
        self.next.append(next)
        return self, options


class Command(Literal):

    weight = 2

    def parse(self, tokens, prev):
        next, options = Node.parse(self, tokens, [])
        self.options = options
        self.next.append(next)
        return self, []


class Option(Literal):

    weight = 2

    def parse(self, tokens, prev):
        next, options = Node.parse(self, tokens, prev + [self])
#        self.options = prev + options
#        self.next.append(next)
        return next, [self] + options

class Terminus(Command):

    weight = 3

    def parse(self, tokens, prev):
        self.options = prev
        return self, []

    def collapse(self):
        if self.follow:  # stuff follows this "Terminus"
            return self.follow #[node for f in self.follow for node in f.collapse()]
        return [DOLLAR]  # this is an accepting state of the NFA

    def match(self, tokens):
        return {} if not tokens else None

class Beginning(Command):

    weight = 3

    def match(self, tokens):
        return Node.match(self, tokens)


CARET = Beginning('^', {})
DOLLAR = Terminus('$', {})

if __name__ == '__main__':
    CARET.parse(['x', '-y', '<z>', '-a', '<x>'], [])
    CARET.build([])
    CARET.collapse()
    print CARET
    #print(CARET.match(['x', '-y', '-a', 1, 2]))
