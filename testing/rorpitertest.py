import unittest
import pickle
import os
from commontest import old_test_dir, abs_output_dir, CompareRecursive, iter_equal
from rdiff_backup import rpath, rorpiter, Globals
from functools import reduce


class index:
    """This is just used below to test the iter tree reducer"""

    def __init__(self, index):
        self.index = index


class RORPIterTest(unittest.TestCase):
    def setUp(self):
        self.lc = Globals.local_connection
        self.inc0rp = rpath.RPath(self.lc,
                                  os.path.join(old_test_dir, b"empty"), ())
        self.inc1rp = rpath.RPath(
            self.lc, os.path.join(old_test_dir, b"inc-reg-perms1"), ())
        self.inc2rp = rpath.RPath(
            self.lc, os.path.join(old_test_dir, b"inc-reg-perms2"), ())
        self.output = rpath.RPath(self.lc, abs_output_dir, ())

    def testCollateIterators(self):
        """Test basic collating"""
        indices = list(map(index, [0, 1, 2, 3]))

        helper = lambda i: indices[i]  # noqa: E731 use def instead of lambda
        makeiter1 = lambda: iter(indices)  # noqa: E731 use def instead of lambda
        makeiter2 = lambda: iter(map(helper, [0, 1, 3]))  # noqa: E731 use def instead of lambda
        makeiter3 = lambda: iter(map(helper, [1, 2]))  # noqa: E731 use def instead of lambda

        outiter = rorpiter.CollateIterators(makeiter1(), makeiter2())
        assert iter_equal(
            outiter,
            iter([(indices[0], indices[0]), (indices[1], indices[1]),
                  (indices[2], None), (indices[3], indices[3])]))

        assert iter_equal(
            rorpiter.CollateIterators(makeiter1(), makeiter2(), makeiter3()),
            iter([(indices[0], indices[0], None),
                  (indices[1], indices[1], indices[1]),
                  (indices[2], None, indices[2]),
                  (indices[3], indices[3], None)]))

        assert iter_equal(rorpiter.CollateIterators(makeiter1(), iter([])),
                          iter([(i, None) for i in indices]))
        assert iter_equal(iter([(i, None) for i in indices]),
                          rorpiter.CollateIterators(makeiter1(), iter([])))

    def compare_no_times(self, src_rp, dest_rp):
        """Compare but disregard directories attributes"""

        def equal(src_rorp, dest_rorp):
            return ((src_rorp.isdir() and dest_rorp.isdir())
                    or src_rorp == dest_rorp)

        return CompareRecursive(src_rp, dest_rp, None, equal)


class IndexedTupleTest(unittest.TestCase):
    def testTuple(self):
        """Test indexed tuple"""
        i = rorpiter.IndexedTuple((1, 2, 3), ("a", "b"))
        i2 = rorpiter.IndexedTuple((), ("hello", "there", "how are you"))

        assert i[0] == "a"
        assert i[1] == "b"
        assert i2[1] == "there"
        assert len(i) == 2 and len(i2) == 3
        assert i2 < i, i2 < i

    def testTupleAssignment(self):
        a, b, c = rorpiter.IndexedTuple((), (1, 2, 3))
        assert a == 1
        assert b == 2
        assert c == 3


class FillTest(unittest.TestCase):
    def test_fill_in(self):
        """Test fill_in_iter"""
        rootrp = rpath.RPath(Globals.local_connection, abs_output_dir)

        def get_rpiter():
            for int_index in [(1, 2), (1, 3), (1, 4), (2, ), (2, 1), (3, 4, 5),
                              (3, 6)]:
                index = tuple([str(i) for i in int_index])
                yield rootrp.new_index(index)

        filled_in = rorpiter.FillInIter(get_rpiter(), rootrp)
        rp_list = list(filled_in)
        index_list = [tuple(map(int, rp.index)) for rp in rp_list]
        assert index_list == [(), (1, ), (1, 2), (1, 3), (1, 4), (2, ), (2, 1),
                              (3, ), (3, 4), (3, 4, 5), (3, 6)], index_list


class ITRBadder(rorpiter.ITRBranch):
    def start_process(self, index):
        self.total = 0

    def end_process(self):
        if self.base_index:
            summand = self.base_index[-1]
            self.total += summand

    def branch_process(self, subinstance):
        self.total += subinstance.total


class ITRBadder2(rorpiter.ITRBranch):
    def start_process(self, index):
        self.total = 0

    def end_process(self):
        self.total += reduce(lambda x, y: x + y, self.base_index, 0)

    def can_fast_process(self, index):
        if len(index) == 3:
            return 1
        else:
            return None

    def fast_process(self, index):
        self.total += index[0] + index[1] + index[2]

    def branch_process(self, subinstance):
        self.total += subinstance.total


class TreeReducerTest(unittest.TestCase):
    def setUp(self):
        self.i1 = [(), (1, ), (2, ), (3, )]
        self.i2 = [(0, ), (0, 1), (0, 1, 0), (0, 1, 1), (0, 2), (0, 2, 1),
                   (0, 3)]

        self.i1a = [(), (1, )]
        self.i1b = [(2, ), (3, )]
        self.i2a = [(0, ), (0, 1), (0, 1, 0)]
        self.i2b = [(0, 1, 1), (0, 2)]
        self.i2c = [(0, 2, 1), (0, 3)]

    def testTreeReducer(self):
        """testing IterTreeReducer"""
        itm = rorpiter.IterTreeReducer(ITRBadder, [])
        for index in self.i1:
            val = itm(index)
            assert val, (val, index)
        itm.Finish()
        assert itm.root_branch.total == 6, itm.root_branch.total

        itm2 = rorpiter.IterTreeReducer(ITRBadder2, [])
        for index in self.i2:
            val = itm2(index)
            if index == ():
                assert not val
            else:
                assert val
        itm2.Finish()
        assert itm2.root_branch.total == 12, itm2.root_branch.total

    def testTreeReducerState(self):
        """Test saving and recreation of an IterTreeReducer"""
        itm1a = rorpiter.IterTreeReducer(ITRBadder, [])
        for index in self.i1a:
            val = itm1a(index)
            assert val, index
        itm1b = pickle.loads(pickle.dumps(itm1a))
        for index in self.i1b:
            val = itm1b(index)
            assert val, index
        itm1b.Finish()
        assert itm1b.root_branch.total == 6, itm1b.root_branch.total

        itm2a = rorpiter.IterTreeReducer(ITRBadder2, [])
        for index in self.i2a:
            val = itm2a(index)
            if index == ():
                assert not val
            else:
                assert val
        itm2b = pickle.loads(pickle.dumps(itm2a))
        for index in self.i2b:
            val = itm2b(index)
            if index == ():
                assert not val
            else:
                assert val
        itm2c = pickle.loads(pickle.dumps(itm2b))
        for index in self.i2c:
            val = itm2c(index)
            if index == ():
                assert not val
            else:
                assert val
        itm2c.Finish()
        assert itm2c.root_branch.total == 12, itm2c.root_branch.total


class CacheIndexableTest(unittest.TestCase):
    def get_iter(self):
        """Return iterator yielding indexed objects, add to dict d"""
        for i in range(100):
            it = rorpiter.IndexedTuple((i, ), list(range(i)))
            self.d[(i, )] = it
            yield it

    def testCaching(self):
        """Test basic properties of CacheIndexable object"""
        self.d = {}

        ci = rorpiter.CacheIndexable(self.get_iter(), 3)
        for i in range(3):  # call 3 times next
            next(ci)

        assert ci.get((1, )) == self.d[(1, )]
        assert ci.get((3, )) is None

        for i in range(3):  # call 3 times next
            next(ci)

        assert ci.get((3, )) == self.d[(3, )]
        assert ci.get((4, )) == self.d[(4, )]
        assert ci.get((3, 5)) is None
        self.assertRaises(AssertionError, ci.get, (1, ))

    def testEqual(self):
        """Make sure CI doesn't alter properties of underlying iter"""
        self.d = {}
        l1 = list(self.get_iter())
        l2 = list(rorpiter.CacheIndexable(iter(l1), 10))
        assert l1 == l2, (l1, l2)


if __name__ == "__main__":
    unittest.main()
