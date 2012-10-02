'''
If you have a list of possible commands, then we can rec.consider the nearest
one(s) a la git. This is an example based on my US keyboard.
'''

__all__ = ['PERCENT_ERROR', 'rec.consider']

PERCENT_ERROR = 0.5

class Recommendations(object):

    def __init__(self, stream):
        self.closest = []
        self.choices = []
        self.streaml = len(stream)
        self.stream = stream
        self.dist = 100000

    def consider(self, current, choices):
        l = len(self.stream)
        if l < self.streaml:
            self.closest = [current]
            self.choices = [choices]
            self.streaml = l
        elif l == self.streaml:
            dist = min(repl(current, c) for c in choices)
            if dist == 0:
                return
            elif dist < self.dist:
                self.closest = [current]
                self.choices = [choices]
                self.streaml = l
            elif current in self.closest:
                i = self.closest.index(current)
                self.choices[i] = tuple(set(self.choices[i]) + set(choices))
            else: 
                self.closest.append(current)
                self.choices.append(choices)

    def recommend(self):
        WS = '\n    '
        current, choices = self.closest, self.choices
        pairs = ((t, c) for t, ch in zip(current, choices) for c in ch)
        close = {}
        for current, choice in pairs:
            dist = repl(current, choice)
            if dist == 0:
                return
            if dist/len(choice) < PERCENT_ERROR:
                if current not in close:
                    close[current] = []
                close[current].append(choice)
        if not close:
            return
        for curr in close:
            l, sugg =  len(close[curr]), WS + WS.join(close[curr])
            print("There is no command called %s.\nDid you mean %s?%s" % 
                  (curr, "this" if l == 1 else "one of these", sugg))
        

def repl(a, b):
    al, bl = len(a), len(b)
    mat = [[i + j for i in xrange(al + 1)] for j in xrange(bl + 1)]
    for j in xrange(bl):
        for i in xrange(al):
            mat[j + 1][i + 1] = min(mat[j][i] + (a[i] != b[j]),
                                    mat[j][i + 1] + 1, 
                                    mat[j + 1][i] + 1)
    return float(mat[j + 1][i + 1])



if __name__ == '__main__':
    stream = []
    commands = ('rm', 'add', 'commit', 'tag', 'tab')
    rec = Recommendations(stream)
    rec.consider('remv', commands)
#    rec.consider('rm', commands)
    rec.consider('remove', commands)
    rec.consider('ad', commands)
    rec.consider('comit', commands)
    rec.consider('comet', commands)
    rec.consider('tav', commands)
    rec.recommend()
