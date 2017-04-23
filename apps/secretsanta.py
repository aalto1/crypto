# Secret Santa by Berry Schoenmakers
import operator
from viff.field import GF
from viff.runtime import Runtime, Share, start
from viff.config import load_config
from viff.util import find_prime
from viff.inlinecb import viffinlinecb, returnValue, declareReturn
from optparse import OptionParser
import random

import itertools

parser = OptionParser()
Runtime.add_options(parser)
options, args = parser.parse_args()
print options,args
if len(args) == 0:
    parser.error("You must specify a config file.")
else:
    id, players = load_config(args[0])
    print id, players

@viffinlinecb
def main(runtime):
    print "################\n"
    print(dir(runtime))
    print "################\n"
    global tv, Zp
    tv = runtime
    k = tv.options.security_parameter
    l = tv.options.bit_length
    ln = len(tv.players).bit_length()
    Zp = GF(find_prime(2**(l + k + ln + 1), blum=True))
    print "Galois"
    print Zp(0)
    yield declareReturn(tv, Zp)
    for n in xrange(10,11):
        a = random_derangement_3(n)
        #a = random_unit_vector(n)
        print("############################## STEP", n ,"\n")
        #a = random_permutation(n)
        a = yield map(tv.open, a)
        #print "finito!"
        print map(lambda v:int(v.value), a) #time/object - this is the function that prints the values on the terminal
    tv.shutdown()

def superPrint(announcement, b = None, x= None, y=None, extra=None):
    return
    print(announcement)
    print("B-VALUE:", b)
    print("X-VALUE:", x)
    print("Y-VALUE:", y)
    print("EXTRA:", extra)

    
@viffinlinecb
def random_unit_vector(n):
    yield declareReturn(tv, Zp, n)
    if n==1: returnValue([Zp(1)]) #base step
    b = tv.random_bit(Zp) #                                                         1 SHARE
    x = random_unit_vector((n+1)/2)
    ##############################
    if n%2==0:
        y = tv.scalar_mul(b, x) # scalar-vector product b_scalar, x_vector --       N SHAMIR SHARING
        superPrint(["######EVEN - RECURSION DEPTH",n], b, x, y, ["SUB-VALUE:",  map(operator.sub, x, y)])
        returnValue(y + map(operator.sub, x, y)) #with list the + symbol is concat  0 SHARMIR
    ##############################
    elif (yield tv.equal_zero_public(b * x[0] - 1)): #a==0 just if b=0 and x[0]=0   1 OPENING - if B PALAYERS B SHARINGS
        superPrint(["######AGAIN - RECURSION DEPTH", n], tv.equal_zero_public(b * x[0] - 1))
        returnValue(random_unit_vector(n))
    ##############################
    else:
        y = tv.scalar_mul(b, x[1:]) # scalar-vector product b_scalar, x_vector --   N SHAMIR SHARING
        superPrint(["######OTHER - RECURSION DEPTH", n], b, x, y, ["LENGTH:", len(y), len(map(operator.sub, x[1:], y)), len(x[:1]), len(y + map(operator.sub, x[1:], y) + x[:1])])
        returnValue(y + map(operator.sub, x[1:], y) + x[:1]) #                      0 SHAMIR
    
def random_permutation(n):
    a = [Share(tv, Zp, Zp(i)) for i in xrange(n)]
    #print("SHARE LIST", a)
    for i in xrange(n-1):
        x = random_unit_vector(n-i) #                                                                           # nlogn
        a_x = tv.in_prod(a[i-n:], x) # VECTOR PRODUCT - VECTOR HAS THE SAME LENGTH - randomly select element    # 1 share(?)
        #print("pupazzo", a_x, i-n)
        d = tv.scalar_mul(a[i] - a_x, x) #vector + (previous-now)*tutti + sparse array                          # n share
        #print("D-VECTOR:", a[i], a_x, a[i] - a_x)
        a[i] = a_x
        for j in xrange(n-i): #length of the random vector + starts to add to the non fixed ones
            a[i+j] += d[j]                                                                                      # zero shares
        #print("TEMPORARY VECTOR:", a)
    return a
    
@viffinlinecb
def random_derangement(n):
    #basic derangement, not strictly related to an actual array -> jasper
    yield declareReturn(tv, Zp, n)
    a = random_permutation(n)
    #print("WASNIO", int(str(a[0].result)[1]))
    t = tv.prod([a[i]-i for i in xrange(n)])
    if (yield tv.equal_zero_public(t)): #if self-loop get another derangement
        print"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        returnValue(random_derangement(n))                                                                      # expected value(?)
    else:
        returnValue(a)

@viffinlinecb
def random_derangement_2(n):
    yield declareReturn(tv, Zp, n)
    a = random_permutation(n)
    t = tv.prod([a[i]-i if a[int(str(a[0].result)[1:-1])]-i else 0 for i in xrange(n)]) #CORRECT but not OBLIVIOUS!
    print("test", a)
    if (yield tv.equal_zero_public(t)):
        returnValue(random_derangement(n))
    else:
        returnValue(a)

@viffinlinecb
def random_derangement_3(n):
    yield declareReturn(tv, Zp, n)
    a = random_permutation(n)
    t = tv.prod([a[i]-i for i in xrange(n)])                                #n logn
    if (yield tv.equal_zero_public(t)):
        print("CIAO")
        returnValue(random_derangement_3(n))

    good_derangements = get_no_two_cycle_derangements(n)
    print("Type:", type(good_derangements))
    for good_derangement in good_derangements:
        if( yield tv.prod([a[i] - good_derangement[i] for i in range(n)])):         #!n n logn n
            print"FINE"
            returnValue(a)
    print"hola"
    returnValue(random_derangement_3(n))


def get_no_two_cycle_derangements(n):
    no_two_cycle_derangements = [list(perm) for perm in itertools.permutations(range(n)) if all((perm[p] != indx & indx!=p) for indx, p in enumerate(perm)) ]
    random.shuffle(no_two_cycle_derangements)
    print("NUMBER OF NO 2-CYCLE DERANGEMENT:", len(no_two_cycle_derangements))
    return no_two_cycle_derangements


start(main, id, players, options)


