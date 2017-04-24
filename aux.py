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
        if(yield 1-tv.sum([a[i] - good_derangement[i] for i in range(n)])):         #!n
            print"FINE"
            returnValue(a)
    print"hola"
    returnValue(random_derangement_3(n))


def get_no_two_cycle_derangements(n):
    no_two_cycle_derangements = [list(perm) for perm in itertools.permutations(range(n)) if all((perm[p] != indx & indx != p) for indx, p in enumerate(perm)) ]
    random.shuffle(no_two_cycle_derangements)
    print("NUMBER OF NO 2-CYCLE DERANGEMENT:", len(no_two_cycle_derangements))
    return no_two_cycle_derangements
