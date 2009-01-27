INSTALLATION:

Thank you for trying rdiff-backup on Windows. Native support for the Windows
environment is quite new in rdiff-backup. Please read the manual page, FAQ and
the Wiki thorougly.

To install the provided binary, simply copy rdiff-backup.exe to someplace in
your PATH. Everything is included in the binary (including Python) for local
operation. For remote operation, you will need to install a Windows SSH
program. You will also need to install rdiff-backup on the remote system(s).

You will need the Microsoft Visual C++ 2008 redistributables. If these are
not installed on your system, rdiff-backup will be unable to run and Windows
will display a message such as "The system cannot execute the specified
program". To install the redistributables for all users, install the package
available from Microsoft.com (search for "visual c 2008 redistributable").

Alternatively, you can install the redistributable in a "side-by-side"
configuration, which does not require administrator privelges. Simply
download the DLL package from:
http://download.savannah.gnu.org/releases/rdiff-backup/Microsoft.VC90.zip
and copy the four enclosed files to the same directory as rdiff-backup.exe.

You will need to follow either method only once.


ADDITIONAL ISSUES:

Currently, rdiff-backup's --include and --exclude options do not support
Windows paths with \ as the directory separator. Instead, it is necessary to
use / which is the Unix directory separator.

Additionally, you may need to run rdiff-backup from the same directory as the
source of your backup, eg:

> cd c:\
> rdiff-backup.exe --include "c:/My Stuff" --exclude "c:/**" c:/ c:/Backup

will work to backup "c:\My Stuff" to "c:\Backup", but:

> cd "c:\My Stuff"
> rdiff-backup.exe --include "c:/My Stuff" --exclude "c:/**" c:/ c:/Backup

will not work. UPDATE: With appropriate escaping, it looks like it is
possible for this to work. Follow this example:

> mkdir c:\foo
> cd "c:\Documents and Settings"
> rdiff-backup.exe --include c:\\/foo --exclude c:\\/** c:\/ c:\bar 

The \\ is necessary in the --include and --exclude options because those
options permit regular-expressions, and \ is the escape character in
regular-expressions, and thus needs to be escaped itself.


TROUBLESHOOTING:

If you have everything installed properly, and it still doesn't work,
see the enclosed manual, FAQ, the web page at http://rdiff-backup.nongnu.org,
the Wiki at: http://wiki.rdiff-backup.org, and/or the mailing list. You can
subscribe to the mailing list at:
http://lists.nongnu.org/mailman/listinfo/rdiff-backup-users

Recommended Wiki entries:
http://wiki.rdiff-backup.org/wiki/index.php/BackupFromWindowsToLinux

You can also try searching the mailing list archives:
http://lists.nongnu.org/archive/html/rdiff-backup-users/
