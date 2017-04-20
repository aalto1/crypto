# Copyright 2007, 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License (LGPL) as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General
# Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with VIFF. If not, see <http://www.gnu.org/licenses/>.

from viff.util import rand

def share(secret, threshold, num_players):
    """Shamir share secret.

    The *threshold* indicates the maximum number of shares that reveal
    nothing about *secret*. The return value is a list of ``(player
    id, share)`` pairs.

    It holds that sharing and recombination cancels each other:

    >>> from field import GF
    >>> Zp = GF(47)
    >>> secret = Zp(42)
    >>> recombine(share(secret, 7, 15)[:8]) == secret
    True

    The threshold can range from zero (for a dummy-sharing):

    >>> share(Zp(10), 0, 5)
    [({1}, {10}), ({2}, {10}), ({3}, {10}), ({4}, {10}), ({5}, {10})]

    up to but not including *num_players*:

    >>> share(Zp(10), 5, 5)
    Traceback (most recent call last):
      ...
    AssertionError: Threshold out of range
    """
    assert 0 <= threshold and threshold < num_players, "Threshold out of range"

    coef = [None] * threshold
    for j in xrange(threshold):
        coef[j] = rand.randint(0, secret.modulus - 1)

    shares = [None] * num_players
    field = type(secret)
    for i in xrange(num_players):
        x = field(i+1)
        y = 0
        for j in xrange(threshold - 1, -1, -1):
            y = coef[j] + x * y
        y = secret + x * y
        shares[i] = (x, y)
    return shares

#: The recombination vector used by `recombine` depends only on the
#: recombination point and the player IDs of the shares, and so it can
#: be cached for efficiency.
_recombination_vectors = {}

def recombine(shares, x_r=0):
    """Recombines list of ``(xi, yi)`` pairs.

    Recombination is done in the optional point *x_r*.
    """
    xs = tuple([s[0] for s in shares] + [x_r])
    try:
        vector = _recombination_vectors[xs]
    except KeyError:
        vector = []
        for i, x_i in enumerate(xs[:-1]):
            coefficient = 1
            for j, x_j in enumerate(xs[:-1]):
                if j != i:
                    coefficient *= (x_r - x_j) / (x_i - x_j)
            vector.append(coefficient)
        _recombination_vectors[xs] = vector
    sum = 0
    for i in xrange(len(shares)):
        sum += shares[i][1] * vector[i]
    return sum

