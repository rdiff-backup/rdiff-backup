import io
import unittest
import os
import subprocess
import sys
from commontest import (old_test_dir, abs_test_dir, re_init_rpath_dir,
                        MakeOutputDir, rdiff_backup, iter_equal, iter_map)
import commontest as comtst
import fileset
from rdiff_backup.selection import Select, GlobbingError, FilePrefixError
from rdiff_backup import Globals, rpath


class MatchingTest(unittest.TestCase):
    """Test matching of file names against various selection functions"""
    def makerp(self, path):
        return rpath.RPath(Globals.local_connection, path)

    def makeext(self, path):
        return self.root.new_index(tuple(path.split("/")))

    def setUp(self):
        # we need to change directory to be able to work with relative paths
        os.chdir(old_test_dir)
        os.chdir(os.pardir)  # chdir one level up
        self.root = rpath.RPath(Globals.local_connection,
                                "rdiff-backup_testfiles/select")
        self.Select = Select(self.root)

    def testRegexp(self):
        """Test regular expression selection func"""
        sf1 = self.Select._regexp_get_sf(".*\\.py", 1)
        self.assertEqual(sf1(self.makeext("1.py")), 1)
        self.assertEqual(sf1(self.makeext("usr/foo.py")), 1)
        self.assertIsNone(sf1(self.root.append("1.doc")))

        sf2 = self.Select._regexp_get_sf("hello", 0)
        self.assertEqual(sf2(self.makerp("hello")), 0)
        self.assertEqual(sf2(self.makerp("foohello_there")), 0)
        self.assertIsNone(sf2(self.makerp("foo")))

    def testTupleInclude(self):
        """Test include selection function made from a regular filename"""
        self.assertRaises(FilePrefixError, self.Select._glob_get_filename_sf,
                          b"foo", 1)
        self.assertRaises(FilePrefixError, self.Select._glob_get_filename_sf,
                          b"rdiff-backup_testfiles/sel", 1)
        self.assertRaises(FilePrefixError, self.Select._glob_get_filename_sf,
                          b"rdiff-backup_testfiles/selection", 1)

        sf2 = self.Select._glob_get_sf(
            "rdiff-backup_testfiles/select/usr/local/bin/", 1)
        self.assertEqual(sf2(self.makeext("usr")), 1)
        self.assertEqual(sf2(self.makeext("usr/local")), 1)
        self.assertEqual(sf2(self.makeext("usr/local/bin")), 1)
        self.assertIsNone(sf2(self.makeext("usr/local/doc")))
        self.assertEqual(sf2(self.makeext("usr/local/bin/gzip")), 1)
        self.assertIsNone(sf2(self.makeext("usr/local/bingzip")))

    def testTupleExclude(self):
        """Test exclude selection function made from a regular filename"""
        self.assertRaises(FilePrefixError, self.Select._glob_get_filename_sf,
                          b"foo", 0)
        self.assertRaises(FilePrefixError, self.Select._glob_get_filename_sf,
                          b"rdiff-backup_testfiles/sel", 0)
        self.assertRaises(FilePrefixError, self.Select._glob_get_filename_sf,
                          b"rdiff-backup_testfiles/selection", 0)

        sf2 = self.Select._glob_get_sf(
            "rdiff-backup_testfiles/select/usr/local/bin/", 0)
        self.assertIsNone(sf2(self.makeext("usr")))
        self.assertIsNone(sf2(self.makeext("usr/local")))
        self.assertEqual(sf2(self.makeext("usr/local/bin")), 0)
        self.assertIsNone(sf2(self.makeext("usr/local/doc")))
        self.assertEqual(sf2(self.makeext("usr/local/bin/gzip")), 0)
        self.assertIsNone(sf2(self.makeext("usr/local/bingzip")))

    def testGlobStarInclude(self):
        """Test a few globbing patterns, including **"""
        sf1 = self.Select._glob_get_sf("**", 1)
        self.assertEqual(sf1(self.makeext("foo")), 1)
        self.assertEqual(sf1(self.makeext("")), 1)

        sf2 = self.Select._glob_get_sf("**.py", 1)
        self.assertEqual(sf2(self.makeext("foo")), 2)
        self.assertEqual(sf2(self.makeext("usr/local/bin")), 2)
        self.assertEqual(sf2(self.makeext("what/ever.py")), 1)
        self.assertEqual(sf2(self.makeext("what/ever.py/foo")), 1)

    def testGlobStarExclude(self):
        """Test a few glob excludes, including **"""
        sf1 = self.Select._glob_get_sf("**", 0)
        self.assertEqual(sf1(self.makeext("/usr/local/bin")), 0)

        sf2 = self.Select._glob_get_sf("**.py", 0)
        self.assertIsNone(sf2(self.makeext("foo")))
        self.assertIsNone(sf2(self.makeext("usr/local/bin")))
        self.assertEqual(sf2(self.makeext("what/ever.py")), 0)
        self.assertEqual(sf2(self.makeext("what/ever.py/foo")), 0)

    def testFilelistInclude(self):
        """Test included filelist"""
        fp = io.BytesIO(b"""
rdiff-backup_testfiles/select/1/2
rdiff-backup_testfiles/select/1
rdiff-backup_testfiles/select/1/2/3
rdiff-backup_testfiles/select/3/3/2""")
        sf = self.Select._filelist_get_sf(fp, 1, "test")
        self.assertEqual(sf(self.root), 1)
        self.assertEqual(sf(self.makeext("1")), 1)
        self.assertIsNone(sf(self.makeext("1/1")))
        self.assertEqual(sf(self.makeext("1/2/3")), 1)
        self.assertIsNone(sf(self.makeext("2/2")))
        self.assertEqual(sf(self.makeext("3")), 1)
        self.assertEqual(sf(self.makeext("3/3")), 1)
        self.assertIsNone(sf(self.makeext("3/3/3")))

    def testFilelistWhitespaceInclude(self):
        """Test included filelist, with some whitespace"""
        fp = io.BytesIO(b"""
+ rdiff-backup_testfiles/select/1  
- rdiff-backup_testfiles/select/2  
rdiff-backup_testfiles/select/3\t""")  # noqa: W291 trailing whitespaces
        sf = self.Select._filelist_get_sf(fp, 1, "test")
        self.assertEqual(sf(self.root), 1)
        self.assertEqual(sf(self.makeext("1  ")), 1)
        self.assertEqual(sf(self.makeext("2  ")), 0)
        if not sys.platform.startswith("win"):  # can't succeed
            self.assertEqual(sf(self.makeext("3\t")), 1)
        self.assertIsNone(sf(self.makeext("4")))

    def testFilelistIncludeNullSep(self):
        """Test included filelist but with null_separator set"""
        fp = io.BytesIO(
            b"""\0rdiff-backup_testfiles/select/1/2\0rdiff-backup_testfiles/select/1\0rdiff-backup_testfiles/select/1/2/3\0rdiff-backup_testfiles/select/3/3/2\0rdiff-backup_testfiles/select/hello\nthere\0"""
        )
        Globals.null_separator = 1
        sf = self.Select._filelist_get_sf(fp, 1, "test")
        self.assertEqual(sf(self.root), 1)
        self.assertEqual(sf(self.makeext("1")), 1)
        self.assertIsNone(sf(self.makeext("1/1")))
        self.assertEqual(sf(self.makeext("1/2/3")), 1)
        self.assertIsNone(sf(self.makeext("2/2")))
        self.assertEqual(sf(self.makeext("3")), 1)
        self.assertEqual(sf(self.makeext("3/3")), 1)
        self.assertIsNone(sf(self.makeext("3/3/3")))
        if not sys.platform.startswith("win"):  # can't succeed
            self.assertEqual(sf(self.makeext("hello\nthere")), 1)
        Globals.null_separator = 0

    def testFilelistExclude(self):
        """Test included filelist"""
        fp = io.BytesIO(b"""
rdiff-backup_testfiles/select/1/2
rdiff-backup_testfiles/select/1
this is a badly formed line which should be ignored

rdiff-backup_testfiles/select/1/2/3
rdiff-backup_testfiles/select/3/3/2""")
        sf = self.Select._filelist_get_sf(fp, 0, "test")
        self.assertIsNone(sf(self.root))
        self.assertEqual(sf(self.makeext("1")), 0)
        self.assertEqual(sf(self.makeext("1/1")), 0)
        self.assertEqual(sf(self.makeext("1/2/3")), 0)
        self.assertIsNone(sf(self.makeext("2/2")))
        self.assertIsNone(sf(self.makeext("3")))
        self.assertEqual(sf(self.makeext("3/3/2")), 0)
        self.assertIsNone(sf(self.makeext("3/3/3")))

    def testFilelistInclude2(self):
        """testFilelistInclude2 - with modifiers"""
        fp = io.BytesIO(b"""
rdiff-backup_testfiles/select/1/1
- rdiff-backup_testfiles/select/1/2
+ rdiff-backup_testfiles/select/1/3
- rdiff-backup_testfiles/select/3""")
        sf = self.Select._filelist_get_sf(fp, 1, "test1")
        self.assertEqual(sf(self.makeext("1")), 1)
        self.assertEqual(sf(self.makeext("1/1")), 1)
        self.assertIsNone(sf(self.makeext("1/1/2")))
        self.assertEqual(sf(self.makeext("1/2")), 0)
        self.assertEqual(sf(self.makeext("1/2/3")), 0)
        self.assertEqual(sf(self.makeext("1/3")), 1)
        self.assertIsNone(sf(self.makeext("2")))
        self.assertEqual(sf(self.makeext("3")), 0)

    def testFilelistExclude2(self):
        """testFilelistExclude2 - with modifiers"""
        fp = io.BytesIO(b"""
rdiff-backup_testfiles/select/1/1
- rdiff-backup_testfiles/select/1/2
+ rdiff-backup_testfiles/select/1/3
- rdiff-backup_testfiles/select/3""")
        sf = self.Select._filelist_get_sf(fp, 0, "test1")
        sf_val1 = sf(self.root)
        self.assertTrue(sf_val1 == 1 or sf_val1 is None)
        sf_val2 = sf(self.makeext("1"))
        self.assertTrue(sf_val2 == 1 or sf_val2 is None)
        self.assertEqual(sf(self.makeext("1/1")), 0)
        self.assertEqual(sf(self.makeext("1/1/2")), 0)
        self.assertEqual(sf(self.makeext("1/2")), 0)
        self.assertEqual(sf(self.makeext("1/2/3")), 0)
        self.assertEqual(sf(self.makeext("1/3")), 1)
        self.assertIsNone(sf(self.makeext("2")))
        self.assertEqual(sf(self.makeext("3")), 0)

    def testGlobRE(self):
        """testGlobRE - test translation of shell pattern to regular exp"""

        def cmp_glob_to_re(src_glob, ref_re, old_ref_re=None, ver_limit=(3, 7)):
            """Helper function to compare a glob and the resulting regexp"""
            res_re = self.Select._glob_to_re(os.fsencode(src_glob))
            # in case something has changed between Python versions
            if old_ref_re and sys.version_info < ver_limit:
                ref_re = old_ref_re
            self.assertEqual(res_re, ref_re,
                             "Regexp '%s' from '%s' doesn't equal to %s" % (
                                 res_re, src_glob, ref_re))

        cmp_glob_to_re("hello", b"hello")
        cmp_glob_to_re(".e?ll**o", b"\\.e[^/]ll.*o")
        # since Python 3.7 only characters special to reg expr are quoted
        # it seems that also non-ASCII characters were quoted before
        cmp_glob_to_re("*/é", os.fsencode("[^/]*/é"), os.fsencode("[^/]*\\/\\é"))
        cmp_glob_to_re("[abc]el[^de][!fg]h", b"[abc]el[^de][^fg]h")
        # since Python 3.7 only characters special to reg expr are quoted
        cmp_glob_to_re("/usr/*/bin/", b"/usr/[^/]*/bin/", b"\\/usr\\/[^/]*\\/bin\\/")
        cmp_glob_to_re("[a.b/c]", b"[a.b/c]")
        cmp_glob_to_re("[a*b-c]e[!]]", b"[a*b-c]e[^]]")

    def testGlobSFException(self):
        """testGlobSFException - see if globbing errors returned"""
        self.assertRaises(GlobbingError, self.Select._glob_get_normal_sf,
                          b"rdiff-backup_testfiles/select/hello//there", 1)
        self.assertRaises(FilePrefixError, self.Select._glob_get_sf,
                          b"rdiff-backup_testfiles/whatever", 1)
        self.assertRaises(FilePrefixError, self.Select._glob_get_sf,
                          b"rdiff-backup_testfiles/?hello", 0)
        self.assertTrue(self.Select._glob_get_normal_sf(b"**", 1))

    def testIgnoreCase(self):
        """testIgnoreCase - try a few expressions with ignorecase:"""
        sf = self.Select._glob_get_sf(
            "ignorecase:rdiff-backup_testfiles/SeLect/foo/bar", 1)
        self.assertEqual(sf(self.makeext("FOO/BAR")), 1)
        self.assertEqual(sf(self.makeext("foo/bar")), 1)
        self.assertEqual(sf(self.makeext("fOo/BaR")), 1)
        self.assertRaises(FilePrefixError, self.Select._glob_get_sf,
                          b"ignorecase:testfiles/sect/foo/bar", 1)

    @unittest.skipIf(sys.platform.startswith("win"), "can't work with Windows")
    def testDev(self):
        """Test device and special file selection"""
        dir = self.root.append("filetypes")
        fifo = dir.append("fifo")
        self.assertTrue(fifo.isfifo())
        sym = dir.append("symlink")
        self.assertTrue(sym.issym())
        reg = dir.append("regular_file")
        self.assertTrue(reg.isreg())
        sock = dir.append("replace_with_socket")
        if not sock.issock():
            if sock.lstat():
                sock.delete()
            sock.mksock()
            self.assertTrue(sock.issock())
        dev = dir.append("ttyS1")
        # only root can create a (tty) device hence must exist
        # sudo mknod ../rdiff-backup_testfiles/select/filetypes/ttyS1 c 4 65
        self.assertTrue(dev.isdev())

        sf = self.Select._devfiles_get_sf(0)
        self.assertIsNone(sf(dir))
        self.assertEqual(sf(dev), 0)
        self.assertIsNone(sf(sock))

        sf2 = self.Select._special_get_sf(0)
        self.assertIsNone(sf2(dir))
        self.assertIsNone(sf2(reg))
        self.assertEqual(sf2(dev), 0)
        self.assertEqual(sf2(sock), 0)
        self.assertEqual(sf2(fifo), 0)
        self.assertEqual(sf2(sym), 0)

        sf3 = self.Select._symlinks_get_sf(0)
        self.assertIsNone(sf3(dir))
        self.assertIsNone(sf3(reg))
        self.assertIsNone(sf3(dev))
        self.assertIsNone(sf3(sock))
        self.assertIsNone(sf3(fifo))
        self.assertEqual(sf3(sym), 0)

    def testRoot(self):
        """testRoot - / may be a counterexample to several of these.."""
        root = rpath.RPath(Globals.local_connection, "/")
        select = Select(root)

        self.assertEqual(select._glob_get_sf("/", 1)(root), 1)
        self.assertEqual(select._glob_get_sf("/foo", 1)(root), 1)
        self.assertEqual(select._glob_get_sf("/foo/bar", 1)(root), 1)
        self.assertEqual(select._glob_get_sf("/", 0)(root), 0)
        self.assertIsNone(select._glob_get_sf("/foo", 0)(root))

        self.assertEqual(select._glob_get_sf("**.py", 1)(root), 2)
        self.assertEqual(select._glob_get_sf("**", 1)(root), 1)
        self.assertEqual(select._glob_get_sf("ignorecase:/", 1)(root), 1)
        self.assertIsNone(select._glob_get_sf("**.py", 0)(root))
        self.assertEqual(select._glob_get_sf("**", 0)(root), 0)
        self.assertIsNone(select._glob_get_sf("/foo/*", 0)(root))

        self.assertEqual(
            select._filelist_get_sf(io.BytesIO(b"/"), 1, "test")(root), 1)
        self.assertEqual(
            select._filelist_get_sf(io.BytesIO(b"/foo/bar"), 1, "test")(root), 1)
        self.assertEqual(
            select._filelist_get_sf(io.BytesIO(b"/"), 0, "test")(root), 0)
        self.assertIsNone(
            select._filelist_get_sf(io.BytesIO(b"/foo/bar"), 0, "test")(root))

    @unittest.skipIf(sys.platform.startswith("win"), "can't work with Windows")
    def testOtherFilesystems(self):
        """Test to see if --exclude-other-filesystems works correctly"""
        root = rpath.RPath(Globals.local_connection, "/")
        select = Select(root)
        sf = select._other_filesystems_get_sf(0)
        self.assertIsNone(sf(root))
        self.assertIsNone(
            sf(rpath.RPath(Globals.local_connection, "/usr/bin")),
            "Assumption: /usr/bin is on the same filesystem as /")
        self.assertEqual(
            sf(rpath.RPath(Globals.local_connection, "/proc")), 0,
            "Assumption: /proc is on a different filesystem")
        for check_dir in (b'/boot', b'/boot/efi', b'/tmp'):
            if (b' ' + check_dir + b' ') in subprocess.check_output('mount'):
                self.assertEqual(
                    sf(rpath.RPath(Globals.local_connection, check_dir)), 0,
                    "Assumption: {dir} is on a different filesystem".format(
                        dir=check_dir))


class ParseSelectionArgsTest(unittest.TestCase):
    """Test argument parsing as well as filelist globbing"""
    root = None

    def ParseTest(self, tuplelist, indices, filelists=[]):
        """No error if running select on tuple goes over indices"""
        def tuple_fsencode(filetuple):
            return tuple(map(os.fsencode, filetuple))

        if not self.root:
            self.root = rpath.RPath(Globals.local_connection,
                                    "rdiff-backup_testfiles/select")
        self.Select = Select(self.root)
        self.Select.parse_selection_args(tuplelist, self.remake_filelists(filelists))
        self.assertTrue(
            iter_equal(iter_map(lambda dsrp: dsrp.index,
                                self.Select.get_select_iter()),
                       map(tuple_fsencode, indices), verbose=1))

    def remake_filelists(self, filelist):
        """Turn strings in filelist into fileobjs"""
        new_filelists = []
        for f in filelist:
            if isinstance(f, str) or isinstance(f, bytes):
                new_filelists.append(io.BytesIO(os.fsencode(f)))
            else:
                new_filelists.append(f)
        return new_filelists

    def testParse(self):
        """Test just one include, all exclude"""
        self.ParseTest([("--include", "rdiff-backup_testfiles/select/1/1"),
                        ("--exclude", "**")],
                       [(), ('1', ), ("1", "1"), ("1", '1', '1'),
                        ('1', '1', '2'), ('1', '1', '3')])

    def testParse2(self):
        """Test three level include/exclude"""
        self.ParseTest([("--exclude", "rdiff-backup_testfiles/select/1/1/1"),
                        ("--include", "rdiff-backup_testfiles/select/1/1"),
                        ("--exclude", "rdiff-backup_testfiles/select/1"),
                        ("--exclude", "**")], [(), ('1', ), ('1', '1'),
                                               ('1', '1', '2'),
                                               ('1', '1', '3')])

    def test_globbing_filelist(self):
        """Filelist glob test similar to above testParse2"""
        self.ParseTest([("--include-globbing-filelist", "file")],
                       [(), ('1', ), ('1', '1'), ('1', '1', '2'),
                        ('1', '1', '3')], [
                            """
- rdiff-backup_testfiles/select/1/1/1
rdiff-backup_testfiles/select/1/1
- rdiff-backup_testfiles/select/1
- **
"""])

    def test_globbing_filelist_winending(self):
        """Filelist glob test with Windows/DOS endings"""
        # the \r's are used to test Windows/DOS endings
        self.ParseTest([("--include-globbing-filelist", "file")],
                       [(), ('1', ), ('1', '1'), ('1', '1', '2'),
                        ('1', '1', '3')], [
                            """
- rdiff-backup_testfiles/select/1/1/1\r
rdiff-backup_testfiles/select/1/1\r
- rdiff-backup_testfiles/select/1\r
- **\r
"""])

    def testGlob(self):
        """Test globbing expression"""
        self.ParseTest([("--exclude", "**[3-5]"),
                        ("--include", "rdiff-backup_testfiles/select/1"),
                        ("--exclude", "**")],
                       [(), ('1', ), ('1', '1'), ('1', '1', '1'),
                        ('1', '1', '2'), ('1', '2'), ('1', '2', '1'),
                        ('1', '2', '2')])
        self.ParseTest([("--include", "rdiff-backup_testfiles/select**/2"),
                        ("--exclude", "**")],
                       [(), ('1', ), ('1', '1'), ('1', '1', '2'), ('1', '2'),
                        ('1', '2', '1'), ('1', '2', '2'), ('1', '2', '3'),
                        ('1', '3'), ('1', '3', '2'), ('2', ), ('2', '1'),
                        ('2', '1', '1'), ('2', '1', '2'), ('2', '1', '3'),
                        ('2', '2'), ('2', '2', '1'), ('2', '2', '2'),
                        ('2', '2', '3'), ('2', '3'), ('2', '3', '1'),
                        ('2', '3', '2'), ('2', '3', '3'), ('3', ), ('3', '1'),
                        ('3', '1', '2'), ('3', '2'), ('3', '2', '1'),
                        ('3', '2', '2'), ('3', '2', '3'), ('3', '3'),
                        ('3', '3', '2')])

    def test_globbing_filelist2(self):
        """Filelist glob test similar to above testGlob"""
        self.ParseTest([("--exclude-globbing-filelist", "asoeuth")],
                       [(), ('1', ), ('1', '1'), ('1', '1', '1'),
                        ('1', '1', '2'), ('1', '2'), ('1', '2', '1'),
                        ('1', '2', '2')],
                       ["""
**[3-5]
+ rdiff-backup_testfiles/select/1
**
"""])
        self.ParseTest([("--include-globbing-filelist", "file")],
                       [(), ('1', ), ('1', '1'), ('1', '1', '2'), ('1', '2'),
                        ('1', '2', '1'), ('1', '2', '2'), ('1', '2', '3'),
                        ('1', '3'), ('1', '3', '2'), ('2', ), ('2', '1'),
                        ('2', '1', '1'), ('2', '1', '2'), ('2', '1', '3'),
                        ('2', '2'), ('2', '2', '1'), ('2', '2', '2'),
                        ('2', '2', '3'), ('2', '3'), ('2', '3', '1'),
                        ('2', '3', '2'), ('2', '3', '3'), ('3', ), ('3', '1'),
                        ('3', '1', '2'), ('3', '2'), ('3', '2', '1'),
                        ('3', '2', '2'), ('3', '2', '3'), ('3', '3'),
                        ('3', '3', '2')],
                       ["""
rdiff-backup_testfiles/select**/2
- **
"""])

    def testGlob2(self):
        """Test more globbing functions"""
        self.ParseTest(
            [("--include", "rdiff-backup_testfiles/select/*foo*/p*"),
             ("--exclude", "**")], [(), ('efools', ), ('efools', 'ping'),
                                    ('foobar', ), ('foobar', 'pong')])
        self.ParseTest([("--exclude", "rdiff-backup_testfiles/select/1/1/*"),
                        ("--exclude", "rdiff-backup_testfiles/select/1/2/**"),
                        ("--exclude", "rdiff-backup_testfiles/select/1/3**"),
                        ("--include", "rdiff-backup_testfiles/select/1"),
                        ("--exclude", "**")], [(), ('1', ), ('1', '1'),
                                               ('1', '2')])

    def testGlob3(self):
        """Test for bug when **is in front"""
        self.ParseTest([("--include", "**NOTEXIST"),
                        ("--exclude", "**NOTEXISTEITHER"),
                        ("--include", "rdiff-backup_testfiles/select/efools"),
                        ("--exclude", "**")], [(), ('efools', ),
                                               ('efools', 'ping')])

    def testAlternateRoot(self):
        """Test select with different root"""
        self.root = rpath.RPath(Globals.local_connection,
                                "rdiff-backup_testfiles/select/1")
        self.ParseTest([("--exclude", "rdiff-backup_testfiles/select/1/[23]")],
                       [(), ('1', ), ('1', '1'), ('1', '2'), ('1', '3')])

        if sys.platform.startswith("win"):
            self.root = rpath.RPath(Globals.local_connection, "C:/")
            self.ParseTest([("--exclude", "C:/Users/*"),
                            ("--include", "C:/Users"),
                            ("--exclude", "C:/")], [(), ("Users", )])
        else:
            self.root = rpath.RPath(Globals.local_connection, "/")
            self.ParseTest([("--exclude", "/home/*"), ("--include", "/home"),
                            ("--exclude", "/")], [(), ("home", )])


class SelectionIfPresentTest(unittest.TestCase):
    """
    Test that rdiff-backup really restores what has been backed-up
    """

    def setUp(self):
        self.base_dir = os.path.join(comtst.abs_test_dir,
                                     b"select_if_present")
        self.from1_struct = {
            "from1": {"subs": {
                "dirWith": {
                    "subs": {
                        "check_for_me": {"content": "whatever"},
                        "fileWithin": {"content": "initial"},
                        "emptyDir": {"type": "dir"},
                    },
                },
                "dirWithout": {
                    "subs": {
                        "fileWithout": {"content": "initial"},
                        "nonEmptyDir": {
                            "subs": {
                                "check_for_me": {"content": "whatever"},
                                "fileWithin": {"content": "initial"},
                                "anotherEmptyDir": {"type": "dir"},
                            },
                        },
                    }
                },
            }}
        }
        self.from1_path = os.path.join(self.base_dir, b"from1")
        fileset.create_fileset(self.base_dir, self.from1_struct)
        fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})
        self.bak_path = os.path.join(self.base_dir, b"bak")
        self.success = False

    def test_exclude_if_present(self):
        """Test that --exclude-if-present works properly"""
        self.assertEqual(comtst.rdiff_backup_action(
            False, False, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"backup", ("--exclude-if-present", "check_for_me")), 0)
        self.assertTrue(
            os.path.exists(os.path.join(self.bak_path, b"dirWithout")))
        self.assertTrue(
            os.path.exists(
                os.path.join(self.bak_path, b"dirWithout", b"fileWithout")))
        self.assertFalse(
            os.path.exists(os.path.join(self.bak_path, b"dirWith")))
        self.assertFalse(
            os.path.exists(
                os.path.join(self.bak_path, b"dirWithout", b"nonEmptyDir")))
        self.success = True

    def test_include_if_present(self):
        """Test that --include-if-present works properly"""
        self.assertEqual(comtst.rdiff_backup_action(
            True, True, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"backup", ("--include-if-present", "check_for_me",
                        "--exclude", "**")), 0)
        self.assertTrue(
            os.path.exists(os.path.join(self.bak_path, b"dirWith")))
        self.assertTrue(
            os.path.exists(
                os.path.join(self.bak_path, b"dirWith", b"fileWithin")))
        self.assertFalse(
            os.path.exists(os.path.join(self.bak_path, b"dirWithout")))
        self.assertFalse(
            os.path.exists(
                os.path.join(self.bak_path, b"dirWith", b"emptyDir")))

        # this fails because the last include statement is redundant
        self.assertNotEqual(comtst.rdiff_backup_action(
            True, True, self.from1_path, self.bak_path,
            ("--api-version", "201"),
            b"backup", ("--include-if-present", "check_for_me")), 0)

        self.success = True

    def tearDown(self):
        # we clean-up only if the test was successful
        if self.success:
            fileset.remove_fileset(self.base_dir, self.from1_struct)
            fileset.remove_fileset(self.base_dir, {"bak": {"type": "dir"}})


class CommandTest(unittest.TestCase):
    """Test rdiff-backup on actual directories"""
    def testEmptyDirInclude(self):
        """
        Make sure empty directories are included with **xx exps

        This checks for a bug present in 1.0.3/1.1.5 and similar.
        """
        outrp = MakeOutputDir()
        # we need to change directory to be able to work with relative paths
        os.chdir(abs_test_dir)
        os.chdir(os.pardir)  # chdir one level up
        selrp = rpath.RPath(Globals.local_connection, 'testfiles/seltest')
        re_init_rpath_dir(selrp)
        emptydir = selrp.append('emptydir')
        emptydir.mkdir()

        rdiff_backup(1,
                     1,
                     selrp.path,
                     outrp.path,
                     extra_options=(b"--include **XX "
                                    b"--exclude testfiles/seltest/YYYY"))

        outempty = outrp.append('emptydir')
        self.assertTrue(outempty.isdir())

    def test_overlapping_dirs(self):
        """
        Test if we can backup a directory containing the backup repo
        while ignoring this repo
        """

        testrp = rpath.RPath(Globals.local_connection,
                             abs_test_dir).append('selection_overlap')
        re_init_rpath_dir(testrp)
        backuprp = testrp.append('backup')
        emptyrp = testrp.append('empty')  # just to have something to backup
        emptyrp.mkdir()

        rdiff_backup(1, 1, testrp.path, backuprp.path,
                     extra_options=b"--exclude %s" % backuprp.path,
                     expected_ret_code=Globals.RET_CODE_WARN)

        self.assertTrue(
            backuprp.append('rdiff-backup-data').isdir()
            and backuprp.append('empty').isdir(),
            "Backup to {rp} didn't happen properly.".format(rp=backuprp))


if __name__ == "__main__":
    unittest.main()
