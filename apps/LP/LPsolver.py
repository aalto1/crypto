import os, operator, string
from viff.field import GF
from viff.runtime import Runtime, Share, start
from viff.config import load_config
from viff.inlinecb import viffinlinecb, returnValue, declareReturnNop
from gmpy2 import is_prime
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-f", "--tableau", help="Filename for tableau.")
parser.set_defaults(tableau="default")
Runtime.add_options(parser)
options, args = parser.parse_args()
if len(args) < 2:
    parser.error("You must specify a config file and a certificate filename.")
else:
    id, players = load_config(args[0])
    certificate_filename = args[1]

def load_tableau(filename):
    T = []
    comment_sign = "#"
    separator = "\t"
    for line in open(os.path.join("data",filename+".teau"), "r"):
        # strip whitespace and comments
        tmp = string.split(line, comment_sign)[0]
        tmp = string.strip(tmp)
        if tmp and not tmp.startswith(comment_sign):
            # skip comments and empty lines.
            parsed_line = string.split(tmp, separator)
            T.append(map(int, parsed_line))
    T[-1].append(0)
    return T

def pow_list(a, x, n):
    if n==1:
        return [a]
    xs = []
    x2s = pow_list(a, x**2, n/2)
    for x2 in x2s:
        xs.append(x2)
        xs.append(x2*x)
    if n%2 == 1:
        xs.append(xs[-1]*x)
    return xs
    
def argmin(xs, gte_min):
    n = len(xs)
    if n == 1:
        return (xs[0], [1])
    if n == 2:
        c, min = gte_min(xs[0], xs[1])
        return (min, [1-c, c])
    x2s = []
    c2s = []
    while len(xs) > 1:       
        a1 = xs.pop()
        a0 = xs.pop()
        c, min = gte_min(a0, a1)
        x2s.append(min)
        c2s.append(c)
    if n%2 == 1:
        x2s.append(xs.pop())
    min, index2 = argmin(x2s, gte_min)
    index = []
    if n%2 == 1:
        index.append(index2[n/2])
    for i in xrange(n/2-1, -1, -1):
        b = index2[i]*c2s[i]
        index.append(index2[i] - b)
        index.append(b)
    return (min, index)

def int_minimal(xs):
    def int_gte_min(x0, x1):
        c = x0 >= x1
        return (c, c * (x1 - x0) + x0)
    return argmin(xs, int_gte_min)

def frac_minimal(xs):
    def frac_gte_min((n0, d0), (n1, d1)):
        c = tv.in_prod([n0,d0],[d1,-n1]) >= 0
        h = tv.scalar_mul(c, [n1-n0, d1-d0])
        return (c, (h[0]+n0, h[1]+d0))
    return argmin(xs, frac_gte_min)

@viffinlinecb
def main(rt):
    global tv
    tv = rt
    T = load_tableau(tv.options.tableau)
    k = tv.options.security_parameter
    l = tv.options.bit_length
    m = len(T) - 1
    n = len(T[0]) - 1
    N = m + n
    if N%4 == 0: N += 1
    p = 1 + N*(1 + (N**2)%4 + 4*(2**(l+k+1)/N))
    while not is_prime(p):
        p += 4 * N
    Zp = GF(p)
    yield declareReturnNop(tv, Zp)

    for i in xrange(len(T)):
        for j in xrange(len(T[0])):
            T[i][j] = Share(tv, Zp, Zp(T[i][j]))

    w = Zp(2)**((p-1)/N)  # lucky choice 2
    w_powers = [Zp(1)]
    for _ in xrange(N-1):
        w_powers.append(w_powers[-1] * w)
    basis = [Share(tv, Zp, w_powers[-(i+n)]) for i in xrange(m)]
    cobasis = [Share(tv, Zp, w_powers[-j]) for j in xrange(n)]
    iter = 0
    prev_pivot = Share(tv, Zp, Zp(1))

    print "%d Termination?..." % iter
    min, p_col_index = int_minimal(T[-1][:-1])
    while (yield tv.open(min < 0)):
        iter += 1
        
        print "%d Determining pivot..." % iter
        p_col = [tv.in_prod(T[i][:-1], p_col_index) for i in xrange(m+1)]
        constraints = [(T[i][-1] + (p_col[i] <= 0), p_col[i]) for i in xrange(m)]
        (_, pivot), p_row_index = frac_minimal(constraints)
			
        print "%d Updating tableau..." % iter
        # swap basis entries
        minplus = map(operator.neg, p_row_index) + p_col_index
        row_col_ind = tv.in_prod(basis + cobasis, minplus)
        h = tv.scalar_mul(row_col_ind, minplus)
        for i in xrange(m):
            basis[i] -= h[i] 
        for j in xrange(n):
            cobasis[j] -= h[m+j]
        #  T[i,j] = T[i,j]*p/p' - (C[i]/p' - p_row_index[i])*(R[j] + p * p_col_index[j])
        prev_p_inv = ~prev_pivot
        p_col = tv.scalar_mul(prev_p_inv, p_col)
        for i in xrange(m):
            p_col[i] -= p_row_index[i]
        p_row = [tv.in_prod([T[i][j] for i in xrange(m)], p_row_index) for j in xrange(n+1)]
        delta_row = tv.scalar_mul(prev_pivot, p_col_index)
        for j in xrange(n):
            p_row[j] += delta_row[j]
        T = tv.gauss(T, pivot*prev_p_inv, p_col, p_row)
        prev_pivot = pivot
        
        print "%d Termination?..." % iter
        min, p_col_index = int_minimal(T[-1][:-1])
        
    print "Termination..."
    max = yield tv.open(T[-1][-1])
    cd = yield tv.open(prev_pivot)
    print " max(f) = %d / %d" % (max.value, cd.value)

    print "Computing solution..."
    solution = [0]*n
    for i in xrange(m):
        x_powers = pow_list(T[i][-1]*~Zp(N), basis[i], N)
        for j in xrange(n):
            coefs = [w_powers[(j*k)%N] for k in xrange(N)]
            solution[j] += tv.lin_comb(coefs,x_powers)
    solution = yield map(tv.open, solution)

    print "Computing dual solution..."
    dual_solution = [0]*m
    for j in xrange(n):
        x_powers = pow_list(T[-1][j]*~Zp(N), cobasis[j], N)
        for i in xrange(m):
            coefs = [w_powers[((n+i)*k)%N] for k in xrange(N)]
            dual_solution[i] += tv.lin_comb(coefs,x_powers)
    dual_solution = yield map(tv.open, dual_solution)
            
    file = open(os.path.join("data",certificate_filename), "w")
    file.write('# tableau = \n' + options.tableau + '\n')
    file.write('# modulus = \n' + str(p) + '\n')
    file.write('# bit-length = \n' + str(tv.options.bit_length) + '\n')
    file.write('# security param = \n' + str(tv.options.security_parameter) + '\n')
    file.write('# threshold = \n' + str(tv.threshold)+'\n')
    file.write('# common divisor = \n' + str(cd.value) + '\n')
    file.write('# Solution = \n')
    for j in xrange(len(solution)):
        file.write(str(solution[j].value)+'\t')
    file.write('\n')
    file.write('# Dual Solution = \n')
    for i in xrange(len(dual_solution)):
        file.write(str(dual_solution[i].value)+'\t')
    file.write('\n')
    file.close()
    
    tv.shutdown()

start(main, id, players, options)
