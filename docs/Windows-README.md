# Using rdiff-backup under Windows

## Installation

Thank you for trying *rdiff-backup* on Windows. Native support for the Windows
environment is quite new in *rdiff-backup*. Please read the manual page, FAQ and
the Wiki thorougly.

To install the provided binary, simply copy *rdiff-backup.exe* to someplace in
your **PATH**. Everything is included in the binary (including Python) for local
operation. For remote operation, you will need to install a Windows SSH
program. You will also need to install *rdiff-backup* on the remote system(s).

You will need the Microsoft Visual C++ 2008 redistributables. If these are
not installed on your system, *rdiff-backup* will be unable to run and Windows
will display a message such as *"The system cannot execute the specified
program"*. To install the redistributables for all users, install the package
available from Microsoft.com (search for *"visual c 2008 redistributable"*).

Alternatively, you can install the redistributable in a "side-by-side"
configuration, which does not require administrator privileges. Simply
download the DLL package from:
[https://download.savannah.gnu.org/releases/rdiff-backup/Microsoft.VC90.zip](https://download.savannah.gnu.org/releases/rdiff-backup/Microsoft.VC90.zip)
and copy the four enclosed files to the same directory as *rdiff-backup.exe*.

You will need to follow either method only once.

## Additional Issues

Currently, *rdiff-backup*'s `--include` and `--exclude` options do not support
Windows paths with `\` as the directory separator. Instead, it is necessary to
use `/` which is the Unix directory separator.

Additionally, you may need to run *rdiff-backup* from the same directory as the
source of your backup, eg:

    > cd c:\
    > rdiff-backup.exe --include "c:/My Stuff" --exclude "c:/**" c:/ c:/Backup

will work to backup `"c:\My Stuff"` to `"c:\Backup"`, but:

    > cd "c:\My Stuff"
    > rdiff-backup.exe --include "c:/My Stuff" --exclude "c:/**" c:/ c:/Backup

will not work.

**UPDATE:** With appropriate escaping, it looks like it is
possible for this to work. Follow this example:

    > mkdir c:\foo
    > cd "c:\Documents and Settings"
    > rdiff-backup.exe --include c:\\/foo --exclude c:\\/** c:\/ c:\bar

The `\\` is necessary in the `--include` and `--exclude` options because those
options permit regular-expressions, and `\` is the escape character in
regular-expressions, and thus needs to be escaped itself.

## Troubleshooting

If you have everything installed properly, and it still doesn't work,
see the enclosed manual, FAQ, the web page at
[https://rdiff-backup.net](https://rdiff-backup.net),
and/or the mailing list. You can subscribe to the mailing list at:
[https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users](https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users)

You can also try searching the mailing list archives:
[https://lists.nongnu.org/archive/html/rdiff-backup-users/](https://lists.nongnu.org/archive/html/rdiff-backup-users/)

## Tips and Tricks

### Using Putty as SSH client

If you have Putty installed (and configured) and don't want to fiddle with
OpenSSH, add the following parameter to your rdiff-backup call:

```
--remote-schema "plink.exe -i D:\backup-key.ppk -batch %s rdiff-backup --server"
```

* `-batch` avoids having to press enter to open the session
* `-i` lets you specify a puttygen-generated private key

### Using Microsoft's OpenSSH client on Windows 10

If rdiff-backup can't seem to find the native SSH client offered by Windows,
even if it is definitely in your PATH (as proven by `where ssh`), and even if
you use the full path `C:\Windows\System32\OpenSSH\ssh.exe`, it's most probably
because you're using the 32 bits version of rdiff-backup on a 64 bits Windows,
they just don't see this path.

You have two solutions:

1. install the 64 bits version of rdiff-backup (at time of writing, it will
   _soon_ be available).
2. add the remote schema option to your call of rdiff-backup with something
   like `--remote-schema "C:\Windows\SysNative\OpenSSH\ssh.exe %s rdiff-backup --server"`
   (adding the path to the front of your PATH environment variable might also
   be an option).

### Create a bat script to call rdiff-backup

Create a file `rdiff-backup.bat` somewhere in your `PATH`. The content can be
as simple as the following:

```
C:\FULLPATH\rdiff-backup.exe -v5 -b --exclude-globbing-file "%~dpn0.txt" source target
```

so that you can put your exclusion patterns in a file called `rdiff-backup.txt`
placed in the same directory as your bat-script.

> **TIP:** if you set the remote-schema in your bat-script, don't forget to
  duplicate the percentage sign to `%%s`, so that the bat-interpreter doesn't
  "interpret" it as variable.
