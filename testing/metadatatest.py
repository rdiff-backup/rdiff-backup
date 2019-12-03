import unittest
import os
import io
import time
from commontest import old_test_dir, abs_output_dir, iter_equal
from rdiff_backup import rpath, Globals, selection
from rdiff_backup.metadata import MetadataFile, PatchDiffMan, \
    quote_path, unquote_path, RORP2Record, Record2RORP, RorpExtractor, \
    meta_quote, meta_unquote

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
            assert b"\n" not in quoted, quoted
            result = unquote_path(quoted)
            assert result == filename, (quoted, result, filename)

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
            record = RORP2Record(rp)
            new_rorp = Record2RORP(record)
            assert new_rorp == rp, (new_rorp, rp, record)

    def testIterator(self):
        """Test writing RORPs to file and iterating them back"""

        def write_rorp_iter_to_file(rorp_iter, file):
            for rorp in rorp_iter:
                file.write(RORP2Record(rorp))

        rplist = self.get_rpaths()
        fp = io.BytesIO()
        write_rorp_iter_to_file(iter(rplist), fp)
        fp.seek(0)
        fp.read()
        fp.seek(0)
        outlist = list(RorpExtractor(fp).iterate())
        assert len(rplist) == len(outlist), (len(rplist), len(outlist))
        for i in range(len(rplist)):
            if not rplist[i].equal_verbose(outlist[i]):
                assert 0, (i, str(rplist[i]), str(outlist[i]))
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
        assert i == 51

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
        sel.ParseArgs((), ())
        rps = list(sel.set_iter())

        assert not temprp.lstat()
        write_mf = MetadataFile(temprp, 'w')
        for rp in rps:
            write_mf.write_object(rp)
        write_mf.close()
        assert temprp.lstat()

        reread_rps = list(MetadataFile(temprp, 'r').get_objects())
        assert len(reread_rps) == len(rps), (len(reread_rps), len(rps))
        for i in range(len(reread_rps)):
            assert reread_rps[i] == rps[i], i

    def test_patch(self):
        """Test combining 3 iters of metadata rorps"""
        self.make_temp()
        # shutil.copytree fails on the fifo file in the directory
        os.system(
            b'cp -a %s/* %s' %
            (os.path.join(old_test_dir, b"various_file_types"), tempdir.path))

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
        output = PatchDiffMan().iterate_patched_meta(
            [iter(current), iter(diff1),
             iter(diff2)])
        out1 = next(output)
        assert out1 is rp1new, out1
        out2 = next(output)
        assert out2 is rp2, out2
        out3 = next(output)
        assert out3 is rp3, out3
        self.assertRaises(StopIteration, output.__next__)

    def test_meta_patch_cycle(self):
        """Create various metadata rorps, diff them, then compare"""

        def write_dir_to_meta(manager, rp, time):
            """Record the metadata under rp to a mirror_metadata file"""
            metawriter = man.get_meta_writer(b'snapshot', time)
            sel = selection.Select(rp)
            sel.ParseArgs((), ())  # make sure incorrect files are filtered out
            for rorp in sel.set_iter():
                metawriter.write_object(rorp)
            metawriter.close()

        def compare(man, rootrp, time):
            sel = selection.Select(rootrp)
            sel.ParseArgs((), ())  # make sure incorrect files are filtered out
            assert iter_equal(sel.set_iter(), man.get_meta_at_time(time, None))

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
        assert rplist[0].getinctype() == b'snapshot'
        assert rplist[0].getinctime() == 40000
        assert rplist[1].getinctype() == b'snapshot'
        assert rplist[1].getinctime() == 30000
        assert rplist[2].getinctype() == b'diff'
        assert rplist[2].getinctime() == 20000
        assert rplist[3].getinctype() == b'diff'
        assert rplist[3].getinctime() == 10000

        compare(man, inc1, 10000)
        compare(man, inc2, 20000)
        compare(man, inc3, 30000)
        compare(man, inc4, 40000)

    def test_meta_quote(self):
        """Test meta_quote()"""
        expected = b'\\001\\002\\003\\004\\005\\006\\007\\010\\011\\012\\013\\014\\015\\016\\017\\020\\021\\022\\023\\024\\025\\026\\027\\030\\031\\032\\033\\034\\035\\036\\037\\040!"#$%&\'()*+,-./0123456789:;<\\075>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\134]^_`abcdefghijklmnopqrstuvwxyz{|}~\\177\\200\\201\\202\\203\\204\\205\\206\\207\\210\\211\\212\\213\\214\\215\\216\\217\\220\\221\\222\\223\\224\\225\\226\\227\\230\\231\\232\\233\\234\\235\\236\\237\\240\\241\\242\\243\\244\\245\\246\\247\\250\\251\\252\\253\\254\\255\\256\\257\\260\\261\\262\\263\\264\\265\\266\\267\\270\\271\\272\\273\\274\\275\\276\\277\\300\\301\\302\\303\\304\\305\\306\\307\\310\\311\\312\\313\\314\\315\\316\\317\\320\\321\\322\\323\\324\\325\\326\\327\\330\\331\\332\\333\\334\\335\\336\\337\\340\\341\\342\\343\\344\\345\\346\\347\\350\\351\\352\\353\\354\\355\\356\\357\\360\\361\\362\\363\\364\\365\\366\\367\\370\\371\\372\\373\\374\\375\\376\\377'
        assert expected == meta_quote(bytes(range(1, 256)))

    def test_meta_quoting(self):
        """Test the meta_quote and meta_unquote functions"""
        assert meta_quote(b'foo') == b'foo', meta_quote(b'foo')
        assert meta_quote(b'\n') == b'\\012', meta_quote(b'\n')
        assert meta_unquote(b'\\012') == b'\n'
        s = b'\\\n\t\145\n\01=='
        assert meta_unquote(meta_quote(s)) == s

    def test_meta_quoting2(self):
        """This string used to segfault the quoting code, try now"""
        s = b'\xd8\xab\xb1Wb\xae\xc5]\x8a\xbb\x15v*\xf4\x0f!\xf9>\xe2Y\x86\xbb\xab\xdbp\xb0\x84\x13k\x1d\xc2\xf1\xf5e\xa5U\x82\x9aUV\xa0\xf4\xdf4\xba\xfdX\x03\x82\x07s\xce\x9e\x8b\xb34\x04\x9f\x17 \xf4\x8f\xa6\xfa\x97\xab\xd8\xac\xda\x85\xdcKvC\xfa#\x94\x92\x9e\xc9\xb7\xc3_\x0f\x84g\x9aB\x11<=^\xdbM\x13\x96c\x8b\xa7|*"\\\'^$@#!(){}?+ ~` '
        quoted = meta_quote(s)
        assert meta_unquote(quoted) == s

    def test_meta_quoting_equals(self):
        """Make sure the equals character is quoted"""
        assert meta_quote(b'=') != b'='


if __name__ == "__main__":
    unittest.main()
