import unittest
import os
import io
import time
from commontest import old_test_dir, abs_output_dir, iter_equal, xcopytree
from rdiff_backup import rpath, Globals, selection
from rdiff_backup.metadata import MetadataFile, PatchDiffMan, \
    quote_path, unquote_path, RorpExtractor

tempdir = rpath.RPath(Globals.local_connection, abs_output_dir)


class MetadataTest(unittest.TestCase):
    def make_temp(self):
        """Make temp directory testfiles/output"""
        global tempdir
        if tempdir.lstat():
            tempdir.delete()
        tempdir.mkdir()

    def testQuote(self):
        """Test quoting and unquoting"""
        filenames = [
            b"foo", b".", b"hello\nthere", b"\\", b"\\\\\\", b"h\no\t\x87\n",
            b" "
        ]
        for filename in filenames:
            quoted = quote_path(filename)
            self.assertNotIn(b"\n", quoted)
            result = unquote_path(quoted)
            self.assertEqual(result, filename)

    def get_rpaths(self):
        """Return list of rorps"""
        vft = rpath.RPath(Globals.local_connection,
                          os.path.join(old_test_dir, b"various_file_types"))
        rpaths = [vft.append(x) for x in vft.listdir()]
        extra_rpaths = [
            rpath.RPath(Globals.local_connection, x)
            for x in [b'/bin/ls', b'/dev/ttyS0', b'/dev/hda', b'aoeuaou']
        ]
        return [vft] + rpaths + extra_rpaths

    def testRORP2Record(self):
        """Test turning RORPs into records and back again"""
        for rp in self.get_rpaths():
            record = MetadataFile._object_to_record(rp)
            new_rorp = RorpExtractor._record_to_object(record)
            self.assertEqual(new_rorp, rp)

    def testIterator(self):
        """Test writing RORPs to file and iterating them back"""

        def write_rorp_iter_to_file(rorp_iter, file):
            for rorp in rorp_iter:
                file.write(MetadataFile._object_to_record(rorp))

        rplist = self.get_rpaths()
        fp = io.BytesIO()
        write_rorp_iter_to_file(iter(rplist), fp)
        fp.seek(0)
        fp.read()
        fp.seek(0)
        outlist = list(RorpExtractor(fp).iterate())
        self.assertEqual(len(rplist), len(outlist))
        for i in range(len(rplist)):
            self.assertTrue(rplist[i]._equal_verbose(outlist[i]))
        fp.close()

    def write_metadata_to_temp(self):
        """If necessary, write metadata of bigdir to file metadata.gz"""
        global tempdir
        temprp = tempdir.append(
            "mirror_metadata.2005-11-03T14:51:06-06:00.snapshot.gz")
        if temprp.lstat():
            return temprp

        self.make_temp()
        rootrp = rpath.RPath(Globals.local_connection,
                             os.path.join(old_test_dir, b"bigdir"))
        rpath_iter = selection.Select(rootrp).set_iter()

        start_time = time.time()
        mf = MetadataFile(temprp, 'w')
        for rp in rpath_iter:
            mf.write_object(rp)
        mf.close()
        print("Writing metadata took %s seconds" % (time.time() - start_time))
        return temprp

    def testSpeed(self):
        """Test testIterator on 10000 files"""
        temprp = self.write_metadata_to_temp()
        mf = MetadataFile(temprp, 'r')

        start_time = time.time()
        i = 0
        for rorp in mf.get_objects():
            i += 1
        print("Reading %s metadata entries took %s seconds." %
              (i, time.time() - start_time))

        start_time = time.time()
        blocksize = 32 * 1024
        with temprp.open("rb", compress=1) as tempfp:
            while 1:
                buf = tempfp.read(blocksize)
                if not buf:
                    break
        print("Simply decompressing metadata file took %s seconds" %
              (time.time() - start_time))

    def testIterate_restricted(self):
        """Test getting rorps restricted to certain index

        In this case, get assume subdir (subdir3, subdir10) has 50
        files in it.

        """
        temprp = self.write_metadata_to_temp()
        mf = MetadataFile(temprp, 'rb')
        start_time = time.time()
        i = 0
        for rorp in mf.get_objects((b"subdir3", b"subdir10")):
            i += 1
        print("Reading %s metadata entries took %s seconds." %
              (i, time.time() - start_time))
        self.assertEqual(i, 51)

    def test_write(self):
        """Test writing to metadata file, then reading back contents"""
        global tempdir
        temprp = tempdir.append(
            "mirror_metadata.2005-11-03T12:51:06-06:00.snapshot.gz")
        if temprp.lstat():
            temprp.delete()

        self.make_temp()
        rootrp = rpath.RPath(Globals.local_connection,
                             os.path.join(old_test_dir, b"various_file_types"))
        # the following 3 lines make sure that we ignore incorrect files
        sel = selection.Select(rootrp)
        sel.parse_selection_args((), ())
        rps = list(sel.set_iter())

        self.assertFalse(temprp.lstat())
        write_mf = MetadataFile(temprp, 'w')
        for rp in rps:
            write_mf.write_object(rp)
        write_mf.close()
        self.assertTrue(temprp.lstat())

        reread_rps = list(MetadataFile(temprp, 'r').get_objects())
        self.assertEqual(len(reread_rps), len(rps))
        for i in range(len(reread_rps)):
            self.assertEqual(reread_rps[i], rps[i])

    def test_patch(self):
        """Test combining 3 iters of metadata rorps"""
        self.make_temp()
        xcopytree(os.path.join(old_test_dir, b"various_file_types"),
                  tempdir.path, content=True)

        rp1 = tempdir.append('regular_file')
        rp2 = tempdir.append('subdir')
        rp3 = rp2.append('subdir_file')
        rp4 = tempdir.append('test')

        rp1new = tempdir.append('regular_file')
        rp1new.chmod(0)
        zero = rpath.RORPath(('test', ))

        current = [rp1, rp2, rp3]
        diff1 = [rp1, rp4]
        diff2 = [rp1new, rp2, zero]

        Globals.rbdir = tempdir
        output = PatchDiffMan()._iterate_patched_meta(
            [iter(current), iter(diff1),
             iter(diff2)])
        out1 = next(output)
        self.assertIs(out1, rp1new)
        out2 = next(output)
        self.assertIs(out2, rp2)
        out3 = next(output)
        self.assertIs(out3, rp3)
        self.assertRaises(StopIteration, output.__next__)

    def test_meta_patch_cycle(self):
        """Create various metadata rorps, diff them, then compare"""

        def write_dir_to_meta(manager, rp, time):
            """Record the metadata under rp to a mirror_metadata file"""
            metawriter = man._get_meta_writer(b'snapshot', time)
            sel = selection.Select(rp)
            sel.parse_selection_args((), ())  # make sure incorrect files are filtered out
            for rorp in sel.set_iter():
                metawriter.write_object(rorp)
            metawriter.close()

        def compare(man, rootrp, time):
            sel = selection.Select(rootrp)
            sel.parse_selection_args((), ())  # make sure incorrect files are filtered out
            self.assertTrue(iter_equal(
                sel.set_iter(), man.get_meta_at_time(time, None)))

        self.make_temp()
        Globals.rbdir = tempdir
        man = PatchDiffMan()
        inc1 = rpath.RPath(Globals.local_connection,
                           os.path.join(old_test_dir, b"increment1"))
        inc2 = rpath.RPath(Globals.local_connection,
                           os.path.join(old_test_dir, b"increment2"))
        inc3 = rpath.RPath(Globals.local_connection,
                           os.path.join(old_test_dir, b"increment3"))
        inc4 = rpath.RPath(Globals.local_connection,
                           os.path.join(old_test_dir, b"increment4"))
        write_dir_to_meta(man, inc1, 10000)
        compare(man, inc1, 10000)
        write_dir_to_meta(man, inc2, 20000)
        compare(man, inc2, 20000)
        man.ConvertMetaToDiff()
        man = PatchDiffMan()
        write_dir_to_meta(man, inc3, 30000)
        compare(man, inc3, 30000)
        man.ConvertMetaToDiff()
        man = PatchDiffMan()
        man.max_diff_chain = 3
        write_dir_to_meta(man, inc4, 40000)
        compare(man, inc4, 40000)
        man.ConvertMetaToDiff()

        man = PatchDiffMan()
        rplist = man.sorted_prefix_inclist(b'mirror_metadata')
        self.assertEqual(rplist[0].getinctype(), b'snapshot')
        self.assertEqual(rplist[0].getinctime(), 40000)
        self.assertEqual(rplist[1].getinctype(), b'snapshot')
        self.assertEqual(rplist[1].getinctime(), 30000)
        self.assertEqual(rplist[2].getinctype(), b'diff')
        self.assertEqual(rplist[2].getinctime(), 20000)
        self.assertEqual(rplist[3].getinctype(), b'diff')
        self.assertEqual(rplist[3].getinctime(), 10000)

        compare(man, inc1, 10000)
        compare(man, inc2, 20000)
        compare(man, inc3, 30000)
        compare(man, inc4, 40000)


if __name__ == "__main__":
    unittest.main()
