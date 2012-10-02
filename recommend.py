'''
If you have a list of possible commands, then we can recommend the nearest
one(s) a la git. This is an example based on my US keyboard.
'''

def repl(a, b):
    al, bl = len(a), len(b)
    mat = [[i + j for i in xrange(al + 1)] for j in xrange(bl + 1)]
    for j in xrange(bl):
        for i in xrange(al):
            mat[j + 1][i + 1] = min(mat[j][i] + (a[i] != b[j]),
                                    mat[j][i + 1] + 1, 
                                    mat[j + 1][i] + 1)
    return mat[j + 1][i + 1]


def did_you_mean(ipt):
    close = []
    commands = ('branch', 'commit', 'add', 'rm', 'tab', 'tag')
    beat_this = 0.5
    for c in commands:
        dist = repl(ipt, c)
        if 0 < float(dist)/len(c) < beat_this:
            close.append(c)
    if close:
        sugg = '\n\t'.join(close)
        print("There is no command called %s.\nDid you mean %s?\n\t%s" %
              (ipt, "this" if len(close) == 1 else "one of these", sugg))


did_you_mean('remv')
did_you_mean('rm')
did_you_mean('remove')
did_you_mean('ad')
did_you_mean('comit')
did_you_mean('comet')
did_you_mean('tav')
