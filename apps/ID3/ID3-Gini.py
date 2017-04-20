import os, string, operator, sys
sys.setrecursionlimit(2**20 - 1)
from viff.field import GF
from viff.runtime import Runtime, Share, start
from viff.config import load_config
from viff.inlinecb import viffinlinecb, returnValue, declareReturn
from viff.util import find_prime
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-f", "--file", help="Filename for data and info.")
parser.set_defaults(file = "Tennis")
Runtime.add_options(parser)
options, args = parser.parse_args()
if len(args) == 0:
    parser.error("You must specify a config file.")
else:
    id, players = load_config(args[0])

def load_file(filename):
    T = []
    comment_sign = "#"
    separator = ","
    for line in open(os.path.join("data",filename), "r"):
        # strip whitespace and comments
        tmp = string.split(line, comment_sign)[0]
        tmp = string.strip(tmp)
        if tmp and not tmp.startswith(comment_sign):
            # skip comments and empty lines.
            parsed_line = string.split(tmp, separator)
            T.append(map(int, parsed_line))
    return T

def argmax(xs, gte_max):
    n = len(xs)
    if n==1: return (xs[0], Share(tv, Zp, Zp(0)))
    max0, i0 = argmax(xs[:n/2], gte_max)   
    max1, i1 = argmax(xs[n/2:], gte_max)
    b, max = gte_max(max0, max1)
    return max, i0 + b * (n/2 + i1 - i0)

def int_max(xs):
    def int_gte_max(x0, x1):
        b = x0 <= x1
        max = b * (x1 - x0) + x0
        return (b, max)
    return argmax(xs, int_gte_max)

def frac_max(xs):
    def frac_gte_max((n0, d0), (n1, d1)):
        b = tv.in_prod([n0, d0], [d1, -n1]) <= 0
        h = tv.scalar_mul(b, [n1 - n0, d1 - d0])
        return (b, (h[0] + n0, h[1] + d0))
    return argmax(xs, frac_gte_max)[1]

@viffinlinecb
def main(rt):
    global tv, Zp, S, C
    tv = rt
    k = tv.options.security_parameter
    l = tv.options.bit_length
    ln = len(tv.players).bit_length()
    Zp = GF(find_prime(2**(l + k + ln + 1), blum=True))
    yield declareReturn(tv, Zp) 
    transactions = load_file(tv.options.file + ".data")
    attributes = load_file(tv.options.file + ".info")[0]
    n = len(attributes[1:])
    S = [[[Share(tv, Zp, Zp(int(t[i]==j))) 
            for t in transactions] 
            for j in xrange(attributes[1:][i])] 
            for i in xrange(n)]
    C = attributes[0] % n
    T = [Share(tv, Zp, Zp(1))] * len(transactions)
    tree = yield id3(T, frozenset(xrange(n)).difference([C]))
    print "Tree = ", tree
    height = lambda t: max(map(height, t[1]))+1 if isinstance(t,tuple) else 0
    print "Tree height = ", height(tree)
    size = lambda t: sum(map(size, t[1]))+1 if isinstance(t,tuple) else 1
    print "Tree size = ", size(tree)
    tv.shutdown()

@viffinlinecb
def id3(T, R):
    yield declareReturn(tv, Zp)
    sizes = [tv.in_prod(T, v) for v in S[C]]
    max, i = int_max(sizes)
    sizeT = tv.sum(sizes)
    stop = (sizeT <= int(0.05*len(T))) + (max == sizeT)
    if len(R) == 0 or not(yield tv.equal_zero_public(stop)):
        i = (yield tv.open(i)).value
        print "Leaf node label ", i
        returnValue(int(i))
    else:
        T_R = [[tv.schur_prod(T, v) for v in S[A]] for A in R]
        gains = [GI(tv.matrix_prod(T_A, S[C])) for T_A in T_R]
        k = (yield tv.open(frac_max(gains))).value
        A = list(R)[k]
        print "Attribute node ", A
        trees = yield [id3(t, R.difference([A])) for t in T_R[k]]
        returnValue((A, trees))
        
def GI(x):
    y = map(lambda s: 8 * s + 1, map(tv.sum, x)) #lambda s: s + (s==0)
    D = tv.prod(y)
    G = tv.in_prod(map(tv.in_prod, x, x), map(operator.invert, y))
    return (D * G, D)

start(main, id, players, options)
