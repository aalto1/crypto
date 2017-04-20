# -*- coding: utf-8 -*-
#
# Copyright 2008 VIFF Development Team.
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

import operator
from itertools import imap
from viff import shamir
from viff.runtime import Runtime, Share, gatherShares
from viff.inlinecb import viffinlinecb, returnValue, declareReturn
from viff.prss import prss, prss_double
from viff.field import GF, FieldElement
from gmpy2 import legendre

class PassiveRuntime(Runtime):
    """Passively secure VIFF runtime.

    The runtime is used for sharing values (:meth:`shamir_share` or
    :meth:`prss_share`) into :class:`~viff.runtime.Share` object and
    opening such shares (:meth:`open`) again. Calculations on shares
    is normally done through overloaded arithmetic operations, but it
    is also possible to call :meth:`add`, :meth:`mul`, etc. directly
    if one prefers.

    Each player in the protocol uses a :class:`~viff.runtime.Runtime`
    object. To create an instance and connect it correctly with the
    other players, please use the :func:`~viff.runtime.create_runtime`
    function instead of instantiating a :class:`~viff.runtime.Runtime`
    directly. The :func:`~viff.runtime.create_runtime` function will
    take care of setting up network connections and return a
    :class:`Deferred` which triggers with the
    :class:`~viff.runtime.Runtime` object when it is ready.
    """

    def __init__(self, player, options):
        """Initialize runtime."""
        Runtime.__init__(self, player, options)

    def output(self, a, receivers=None, threshold=None):
        return self.open(a, receivers, threshold)

    @viffinlinecb
    def open(self, a, receivers=None, threshold=None):
        """Open a secret sharing.

        The *receivers* are the players that will eventually obtain the 
        opened result. The default is to let everybody know the result. 
        
        Communication cost: every player sends one share to each
        receiving player.
        """
        assert isinstance(a, Share)
        yield declareReturn(self, a.field)

        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()
        if threshold is None:
            threshold = self.threshold

        a = yield a
        # Send share to all receivers.
        for peer_id in receivers:
            if peer_id != self.id:
                self._send_share(peer_id, a)
        # Receive and recombine shares if this player is a receiver.
        if self.id in receivers:
            shares = []
            for peer_id in self.players:
                field = type(a)
                if peer_id == self.id:
                    s = Share(self, field, (field(peer_id), a))
                else:
                    s = self._expect_share(peer_id, field)
                    s.addCallback(lambda s, peer_id: (field(peer_id), s), peer_id)
#                    s.df.addCallback(lambda s, peer_id: (field(peer_id), s), peer_id)
                shares.append(s)
            shares = yield shares[:threshold+1] #ToDo wait for t+1 shares only.
            returnValue(shamir.recombine(shares))
#            returnValue(Share(self, field, shamir.recombine(shares)))

    def __share_recombine(self, a):
        input_shares = shamir.share(a, self.threshold, len(self.players))
        output_shares = self._exchange_shares(input_shares)
        # Recombine the first 2t+1 output_shares.
        result = gatherShares(output_shares[:2*self.threshold+1])
        result.addCallback(shamir.recombine)
        return result
#        return Share(self, a.field, result)


    def equal_public(self, a, b):
        """Public equality test.

        Communication cost: 1 opening (ie. each player sends a share)."""
        return self.equal_zero_public(a-b)

    @viffinlinecb
    def equal_zero_public(self, a):
        """Public zero test.

        Communication cost: 1 opening (ie. each player sends a share)."""
        field = a.field
        yield declareReturn(self, field)
        r = self.random(field)
        a, r = yield a, r
        field = type(a)
        c = yield self.open(Share(self, field, a * r), None, 2*self.threshold)
        returnValue(c == 0)
        
    @viffinlinecb
    def neg(self, a):
        """Negation of a.

        Communication cost: none.
        """
        yield declareReturn(self, a.field)
        a = yield a
        returnValue(-a)

    @viffinlinecb
    def add(self, a, b):
        """Addition of a to b.

        Communication cost: none.
        """

        yield declareReturn(self, a.field)

        if not isinstance(b, Share):
            a = yield a
            returnValue(a + b)

        a, b = yield a, b
        returnValue(a + b)

    @viffinlinecb
    def sub(self, a, b):
        """Subtraction of a and b.

        Communication cost: none.
        """
        if not isinstance(a, Share):
            a = Share(self, b.field, a)
        if not isinstance(b, Share):
            b = Share(self, a.field, b)

        yield declareReturn(self, a.field)

        a, b = yield a, b
        returnValue(a - b)
        
    @viffinlinecb
    def mul(self, a, b):
        """Multiplication of a and b.
 
         Communication cost: 1 Shamir sharing.
        """
        yield declareReturn(self, a.field)

        if not isinstance(b, Share):
            a = yield a
            returnValue(a * b)

        a, b = yield a, b
        c =  self.__share_recombine(a * b)
        c = yield c
        #c = yield c
        returnValue(c)

    @viffinlinecb
    def invert(self, a):
        """Multiplicative inverse of a, assuming a!=0.
 
         Communication cost: 1 opening (ie. each player sends a share).
        """
        field = a.field
        yield declareReturn(self, field)
        r = self.random(field)
        a, r = yield a, r
        ar = yield self.open(Share(self, field, a * r), None, 2*self.threshold)
        if ar == 0: returnValue(self.invert(a))
        returnValue(~ar * r)

    def pow(self, a, n):
        """Exponentation of a to an integer n by square-and-multiply."""

        assert isinstance(n, (int, long)), "Exponent must be an integer"
        assert n >= 0, "Exponent must be non-negative"

        if n == 0:
            return 1
        elif n % 2 == 0:
            t = a ** (n / 2)
            return t * t
        else:
            return a * (a ** (n-1))

    def xor(self, a, b):
        if not isinstance(b, Share):
            if not isinstance(b, FieldElement):
                b = a.field(b)
            b = Share(self, a.field, b)
        return a + b - 2 * a * b

    def equal(self, a, b):
        if self.options.bit_length < 2 * self.options.security_parameter:
            return self.sgn(a - b, EQ=True)
        else:
            return self._equal(a, b)
    
    def greater_than_equal(self, a, b):
        return self.sgn(a - b, GE=True)

    @viffinlinecb
    def _equal(self, a, b):
        """Equality testing with secret shared result.
        
        This is the probabilistic method based on quadratic
        reciprocity described in: "Constant-Round Multiparty
        Computation for Interval Test, Equality Test, and Comparison"
        by Takashi Nishide and Kazuo Ohta, and fails with probability
        1/(2**k) where k is the security parameter of the runtime.
        """
        Zp = a.field
        yield declareReturn(self, Zp)

        d = a - b # We will check if d == 0
        k = self.options.security_parameter
        x = [None] * k
        i = 0
        while i<k:
            z = self.random_bit(Zp)
            r = self.random(Zp)
            rp = self.random(Zp)
            # If 1 - 2z == 1, c will always be a square modulo p if d == 0
            # and with probability 1/2 otherwise (except if rp == 0).
            # If 1 - 2z == -1 it will be non-square.
            c = yield self.open(d * r + (1 - 2*z) * rp * rp)
            if c == 0: continue
            x[i] = 1- z if legendre(c.value, Zp.modulus) == 1 else z
            i+=1
                        
        e = self.prod(x)
        e = yield e
        #e = yield e
        returnValue(e)

    @viffinlinecb
    def sgn(self, a, EQ=False, GE=False):
        Zp = a.field
        yield declareReturn(self, Zp)

        l = self.options.bit_length
        k = self.options.security_parameter
        r_bits = [self.random_bit(Zp) for _ in xrange(l)]
        r_modl = self.bin_comb(r_bits)
        r_divl = self.random_max(Zp, 2**k)
        a_rmodl = a + 2**l + r_modl
        c = yield self.open(a_rmodl + 2**l*r_divl)
        
        xors = [r_bits[i] ^ c.bit(i) for i in xrange(l)]
        if not EQ:
            s_bit = self.random_bit(Zp)
            s_sign = 1 - 2 * s_bit
            # mask: uniformly random -- should be non-zero, failure prob. 1/2^(k+l)
            mask = self.random(Zp) 
            #BS mask = mask * mask + 1, assuming -1 is in NQR. 
            
            E = [mask]
            sumXors = 0
            for i in xrange(l-1, -1, -1):
                E.append(s_sign + r_bits[i] - c.bit(i) + 3*sumXors)
                sumXors += xors[i]
            E.append(s_sign - 1 + 3*sumXors)

            f = yield self.open(self.prod(E))
            UF = (f != 0) ^ s_bit
            z = (a_rmodl - (c.value % 2**l + UF * 2**l)) * ~Zp(2**l)
        if not GE:
            h = self.prod([1 - b for b in xors])
            if EQ:
                z = h
            else:
                z = (1 - h) * (2 * z - 1)
        z = yield z
        #z = yield z
        returnValue(z)     
        
    @viffinlinecb
    def lsb(self, a):
        """ Least Significant Bit Gate [ST06] """
        Zp = a.field
        yield declareReturn(self, Zp)
        
        l = self.options.bit_length
        k = self.options.security_parameter
        b = self.random_bit(Zp)
        r = self.random_max(Zp, 2**(l+k))
        a, b, r = yield a, b, r
        c = yield self.open(Share(self, Zp, a + b + 2 * r))
        returnValue(c.bit(0) + b - 2 * c.bit(0) * b) #xor

    @viffinlinecb
    def sum(self, x):
        """Sum of all elements in x.
        
        Communication cost: none."""
        yield declareReturn(self, x[0].field)
        x = yield x
        returnValue(sum(x))

    @viffinlinecb
    def prod(self, x):
        """Product of all elements in x.
        
        Communication cost: n Shamir sharings in log_2 n rounds."""
        yield declareReturn(self, x[0].field)
        x = yield x 
        while len(x) > 1:
            h = []
            while len(x) > 1: 
                h.append(self.__share_recombine(x.pop() * x.pop()))
            h = yield h
            h.extend(x)
            x = h
        returnValue(x[0])

    @viffinlinecb
    def lin_comb(self, a, x):
        """Linear combination: dot product of public a and shared x.

        Communication cost: none. Saves the construction of unnecessary shares
        compared to using add() and mul()."""

        yield declareReturn(self, x[0].field)
        x = yield x
        if isinstance(a, Share):
            a = yield a
        returnValue(sum(imap(operator.mul, a, x)))

    @viffinlinecb
    def bin_comb(self, x):
        """Binary combination: dot product of powers of 2 and shared x."""

        yield declareReturn(self, x[0].field)
        x = yield x
        s = 0
        for i in xrange(len(x)-1, -1, -1):
            s = s*2 + x[i] 
        returnValue(s)

    @viffinlinecb
    def in_prod(self, x, y):
        """Computing dot product of x and y
        using only one round of communication."""
        
        yield declareReturn(self, x[0].field)
        if x is y:
            x = yield x
            s = sum(imap(lambda a: a*a, x))
        else:
            x, y = yield x, y
            s = sum(imap(operator.mul, x, y))
        s = self.__share_recombine(s)
        s = yield s
#        s = yield s
        returnValue(s)

    @viffinlinecb
    def scalar_mul(self, a, x):
        """Scalar multiplication of scalar a with vector x.

        Communication cost: n Shamir sharings.
        """
        yield declareReturn(self, a.field, len(x))
        a, x = yield a, x
        for i in xrange(len(x)):
            x[i] = self.__share_recombine(a * x[i])
        #x = yield x
        returnValue(x)

    @viffinlinecb
    def schur_prod(self, x, y):
        """Entrywise multiplication of vectors x and y

        Communication cost: n Shamir sharings.
        """
        yield declareReturn(self, x[0].field, len(x))
        
        x, y = yield x, y
        for i in xrange(len(x)): 
            x[i] = self.__share_recombine(x[i] * y[i])
        #x = yield x
        returnValue(x)

    @viffinlinecb
    def matrix_prod(self, A, B):
        """Computing matrix product of A with transposed B
        using only one round of communication."""

        yield declareReturn(self, A[0][0].field, len(A), len(B))

        A, B = yield A, B
        C = [None] * len(A)
        for ia in xrange(len(A)):
            C[ia] = [None] * len(B)
            for ib in xrange(len(B)):
                s = sum(imap(operator.mul, A[ia], B[ib]))
                C[ia][ib] = self.__share_recombine(s)
        #C = yield C
        returnValue(C)

    @viffinlinecb
    def gauss(self, A, d, b, c):
        """Gaussian elimination A:= A d - b c
    
        Communication cost: m * n Shamir sharings.
        """
        
        yield declareReturn(self, A[0][0].field, len(A), len(A[0]))
        A, d, b, c  = yield A, d, b, c
        for i in xrange(len(A)):
            for j in xrange(len(A[0])):
                    A[i][j] = self.__share_recombine(A[i][j] * d - b[i] * c[j])
        #A = yield A
        returnValue(A)

    def prss_key(self):
        """Create unique key for PRSS.

        This increments the program counter and returns it as a tuple.
        Each straight-line program (typically a callback attached to
        some :class:`Deferred`) is executed in a context with unique
        starting program counter. This ensures that consecutive calls
        to PRSS-related methods will use unique program counters.
        """

        # This is called by every function using PRSS, so do it here.
        # If the assertion is not met, things go wrong, i.e. the PRSS
        # functions generate shares with higher degrees than what
        # open() and mul() expect.
        assert self.threshold >= \
               len(self.players) - len(self.players[self.id].keys.keys()[0]), \
               "PRSS functions have higher threshold than the runtime."

        self.increment_pc()
        return tuple(self.program_counter)

    @viffinlinecb
    def random_bit(self, field):
        """Generate shares of a uniformly random bit over the field given.

        Communication cost: 1 open.
        """
        yield declareReturn(self, field)

        prss_key = self.prss_key()
        prfs = self.players[self.id].prfs(field.modulus)
        a = prss(len(self.players), self.id, field, prfs, prss_key)
        # Open the square and compute a square-root
        a2 = yield self.open(Share(self, field, a**2), None, 2*self.threshold)
        if a2 == 0:
            returnValue(self.random_bit(field))
        else:
            returnValue((a/a2.sqrt() + 1) / 2)

    def random(self, field):
        return self.random_max(field, field.modulus)

    def random_max(self, field, max):
        prss_key = self.prss_key()
        prfs = self.players[self.id].prfs(max)
        share = prss(len(self.players), self.id, field, prfs, prss_key)
        return Share(self, field, share)

    def random_double_max(self, field1, field2, max):
        prss_key = self.prss_key()
        prfs = self.players[self.id].prfs(max)
        share1, share2 = prss_double(len(self.players), self.id, field1, field2, prfs, prss_key)
        return Share(self, field1, share1), Share(self, field2, share2)
                
    def input(self, inputters, field, number=None, threshold=None):
        """Input *number* to the computation.

        The input is shared using the :meth:`shamir_share` method.
        """
        return self.shamir_share(inputters, field, number, threshold)

    def shamir_share(self, inputters, field, number=None, threshold=None):
        """Secret share *number* over *field* using Shamir's method.

        The number is shared using polynomial of degree *threshold*
        (defaults to :attr:`threshold`). Returns a list of shares
        unless there is only one inputter in which case the
        share is returned directly.

        In code it is used like this::

            a, b, c = runtime.shamir_share([1, 2, 3], Zp, x)

        where ``Zp`` is a field and ``x`` is a Python integer holding
        the input of each player (three inputs in total).

        If only a subset of the players provide input it looks like
        this::

            if runtime.id == 1:
                a = runtime.shamir_share([1], Zp, x)
            else:
                a = runtime.shamir_share([1], Zp)

        Instead of branching when calling :meth:`shamir_share`, one
        can give ``None`` as input::

            if runtime.id == 1:
                x = int(raw_input("Input x: "))
            else:
                x = None
            a = runtime.shamir_share([1], Zp, x)

        which might be practical in some cases.

        Communication cost: n elements transmitted.
        """
        assert number is None or self.id in inputters
        if threshold is None:
            threshold = self.threshold

        results = []
        for peer_id in inputters:
            # Unique program counter per input.
            self.increment_pc()
            if peer_id == self.id:
                shares = shamir.share(field(number), threshold,
                                      len(self.players))
                for other_id, share in shares:
                    if other_id.value == self.id:
                        results.append(Share(self, field, share))
                    else:
                        self._send_share(other_id.value, share)
            else:
                results.append(self._expect_share(peer_id, field))
        # Unpack a singleton list.
        if len(results) == 1:
            return results[0]
        else:
            return results
