# Performance binary pebblers: rushing, speed-1, speed-2, optimal.
# Copyright (C) 2016 Berry Schoenmakers
import itertools

tR = lambda k, r: 0 if r < 2 ** k - 1 else 2 ** k - 1
t1 = lambda k, r: 1
t2 = lambda k, r: 0 if r < 2 ** (k - 1) else 2 if r < 2 ** k - 1 else 1
tS = lambda k, r: 0 if r < 2 ** (k - 1) else ((k + r) % 2 + k + 1 - (
(2 * r) % (2 ** (2 ** k - r).bit_length())).bit_length()) / 2


def P(k, t):
    i = k;
    g = 0
    for r in xrange(1, 2 ** k):
        yield (t(k, r), k - i + 1)
        for _ in xrange(t(k, r)):
            if g == 0: i -= 1; g = 2 ** i
            g -= 1
    yield (0, k + 1)
    for v in itertools.izip_longest(*(P(i - 1, t) for i in xrange(1, k + 1))):
        (a, b) = zip(*(u for u in v if u != None))
        yield (sum(a), sum(b))


k = input()
print "   k:{0:2}    rushing   speed-1   speed-2   optimal".format(k)
print "round r      T  S      T  S      T  S      T  S "
r = 1
for ((wR, sR), (w1, s1), (w2, s2), (wS, sS)) in itertools.izip(*(P(k, t) for t in (tR, t1, t2, tS))):
    if r == 2 ** k: wR = w1 = w2 = wS = "      W"
    print "{0:7}{1:7}{2:3}{3:7}{4:3}{5:7}{6:3}{7:7}{8:3}".format(r, wR, sR, w1, s1, w2, s2, wS, sS)
    r += 1