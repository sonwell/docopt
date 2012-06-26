class Node(object):

    def __init__(self, name):
        self.name = name
        self.next = []
        self.value = None

    def push(self, other):
        if self.value is None:
            self.value = other
        elif type(self.value) is list:
            self.value.append(other)
        else:
            self.value = [self.value, other]

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.name, self.value)

    def __eq__(self, other):
        return self.name == other.name and \
            self.value is other.value

    def extend(self, tokens):
        try: tok = tokens.pop(0)
        except:
            node = Epsilon()
            self.next.append(node)
            return node
        for node in self.next:
            if node.name == tok:
                return node.extend(tokens)
        if tok == '...':
            '''
                   | * is the current node
                   |
                   |     | * is match, we need to separate it
                   |     | from the previous node in case of
                   v     v things like "A C ... | A C D".
                 +---------------+
                 |   +--<--+     |
             in  |   v     ^     | out
            ---->+-*-+-->*-+   +-+----->
                 |   v         | |
                 |   e         | |
                 |   +---------+ |
                 +---------------+
                     ^ epsilon is join
            '''
            join = Epsilon()
            match = Node(self.name)
            match.value = self.value = \
                self.value if type(self.value) is list else []
            match.next = [match, join]
            self.next.append(match)
            self.next.append(join)
            return join.extend(tokens)
        else:
            new = Node(tok)
            self.next.append(new)
            if tok == self.name:
                new.value = self.value = \
                    self.value if type(self.value) is list else []
            return new.extend(tokens)

    def match(self, tokens, parents):
        try: tok = tokens.pop(0)
        except: return None
        if tok != self.name:
            tokens.insert(0, tok)
            return None
        for node in self.next:
            res = node.match(tokens, parents)
            if res != None:
                self.push(tok)
                if not res or self.name not in res:
                    res[self.name] = self.value
                return res
        tokens.insert(0, tok)
        return None


class Epsilon(Node):

    def __init__(self):
        Node.__init__(self, None)

    def push(self, other):
        pass

    def match(self, tokens, parents):
        '''
        Epsilon move does no matching; we just test that it leads 
        to something that matches. Epsilons are the only legal $
        (end of input) token, anything else will result in None.

             +---+
         in  |   | out
        ---->+-e-+----->
             |   |
             +---+
               ^ epsilon simply forwards the incoming tokens
        '''
        for node in self.next:
            res = node.match(tokens, parents)
            if res != None:
                return res
        return None if self.next or tokens else {}


class Graph(Node):

    def __init__(self, name):
        Node.__init__(self, name)
        self.start = Epsilon()
        self.end   = Epsilon()
        self.next  = self.end.next

    def extend(self, tokens):
        tail = self.start.extend(tokens)
        if self.end not in tail.next:
            tail.next.append(self)
        return self.end

    def match(self, tokens, parents):
        '''
                        | There can be other nodes or graphs in the
                        | loop between start and end that must be
                        v validated before we fully pass through the graph.
             +--------------------+
             |         .*.        |
             |        /   \       |
         in  |        \   /       | out
        ---->+---------e e--------+----->
             |   start     end    |
             +--------------------+
                       ^ ^ end is the exit point (an epsilon).
                       |
                       | start is the entry point (an epsilon).

        If the first entry in the parents list is self, then we
        are obviously on our way out (at "out") of the graph,
        otherwise, we have either not visited the graph, or we are
        returning to the graph (via loop or something).
        '''
        if parents and parents[0] is self:
            parents.pop(0)
            res = self.end.match(tokens, parents)
            if res != None:
                if self.name is not None:
                    res[self.name] = self.value
                elif self.value is not None:
                    for node in self.value:
                        if node not in res:
                            res[node] = self.value[node]
                return res
            parents.insert(0, self)
            return None
        else:
            '''
            We are using the special name None to differentiate 
            between a *named graph* (e.g., a command or option)
            from an *unnamed graph*, which would be used as a sort
            of epsilon with (potential) checking.
            '''
            if self.name is not None:
                try: tok = tokens.pop(0)
                except: return None
                if tok != self.name:
                    tokens.insert(0, tok)
                    return None
            parents.insert(0, self)
            self.value = self.start.match(tokens, parents)
            return self.value
                

    def parse(self, stream):
        pass


def match(doc, args):
    args = args.split()
    A = Graph(None)
#    B = Graph('a')
#    B.extend('a C C ...'.split())
#    B.end.extend('C C'.split()).next.append(A)
#    A.start.next.append(B)

#    return A.match(args.split(), [])
    
    for line in doc.split('\n'):
        line = line.strip()
        if line:
            A.extend(line.split())
    return A.match(args, [])


if __name__ == '__main__':

    d = \
    """
    a C ... D
    a B C D D ...
    a B D
    a B <E>
    """

    print match(d, 'a C C C C C C C C C C C D')
    print match(d, 'a C B D')
    print match(d, 'a B <E>')
    print match(d, 'a B C D D')
