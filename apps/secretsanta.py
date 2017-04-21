# Secret Santa by Berry Schoenmakers
import operator
from viff.field import GF
from viff.runtime import Runtime, Share, start
from viff.config import load_config
from viff.util import find_prime
from viff.inlinecb import viffinlinecb, returnValue, declareReturn
from optparse import OptionParser

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
    for n in xrange(1,3):
        #a = random_derangement(n)
        a = random_unit_vector(n)
        print a
        #a = random_permutation(n)
        a = yield map(tv.open, a)
        #print "finito!"
        print map(lambda v:int(v.value), a) #time/object - this is the function that prints the values on the terminal
    tv.shutdown()
    
@viffinlinecb
def random_unit_vector(n):
    yield declareReturn(tv, Zp, n)
    if n==1: returnValue([Zp(1)]) #base step
    print "ciao"
    b = tv.random_bit(Zp)
    print str(b) + "questo e' b"
    x = random_unit_vector((n+1)/2)
    if n%2==0:
        y = tv.scalar_mul(b, x)
        returnValue(y + map(operator.sub, x, y))
    elif (yield tv.equal_zero_public(b * x[0] - 1)):
        returnValue(random_unit_vector(n))
    else:
        y = tv.scalar_mul(b, x[1:])
        returnValue(y + map(operator.sub, x[1:], y) + x[:1])
    
def random_permutation(n):
    a = [Share(tv, Zp, Zp(i)) for i in xrange(n)]
    for i in xrange(n-1):
        x = random_unit_vector(n-i)
        a_x = tv.in_prod(a[i-n:], x)
        d = tv.scalar_mul(a[i]-a_x, x)
        a[i] = a_x
        for j in xrange(n-i):
            a[i+j] += d[j]
    return a
    
@viffinlinecb
def random_derangement(n):
    yield declareReturn(tv, Zp, n)
    a = random_permutation(n)
    t = tv.prod([a[i]-i for i in xrange(n)])
    if (yield tv.equal_zero_public(t)):
        returnValue(random_derangement(n))
    else:
        returnValue(a)

@viffinlinecb
def random_derangement_2(n):
    yield declareReturn(tv, Zp, n)
    a = random_permutation(n)
    t = tv.prod([a[i]-i for i in xrange(n)])
    if (yield tv.equal_zero_public(t)):
        returnValue(random_derangement(n))
    else:
        returnValue(a)


start(main, id, players, options)


