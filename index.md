--- 
layout: default 
--- 
_A remote incremental backup of all your files could be as easy as "rdiff-backup / host.net::/target-dir"_

## What is it? ## 
rdiff-backup backs up one directory to another, possibly over a network. The target directory ends up a copy of the source directory, but extra reverse diffs are stored in a special subdirectory of that target directory, so you can still recover files lost some time ago. The idea is to combine **the best features of a mirror and an incremental backup**. rdiff-backup also preserves subdirectories, hard links, dev files, permissions, uid/gid ownership, modification times, extended attributes, acls, and resource forks. Also, rdiff-backup can operate in a **bandwidth efficient** manner over a pipe, like rsync. Thus you can use rdiff-backup and ssh to securely back a hard drive up to a remote location, and only the differences will be transmitted. Finally, rdiff-backup is **easy to use** and settings have sensical defaults. 

## Download: ## 
rdiff-backup is GPLed (anyone can download it, redistribute it, etc.). 

* Version 1.2.8, released March 16th 2009, is the new stable version. 
	* [rdiff-backup-1.2.8.tar.gz](https://github.com/sol1/rdiff-backup/archive/r1-2-8.tar.gz)
	* [rdiff-backup-1.2.8-win32.zip](https://github.com/sol1/rdiff-backup/archive/r1-2-8.zip)
* Version 1.3.3, released March 16th 2009, is the new development/unstable version.
	* [rdiff-backup-1.3.3.tar.gz](http://savannah.nongnu.org/download/rdiff-backup/rdiff-backup-1.3.3.tar.gz)
	* [rdiff-backup-1.3.3-win32.zip](http://savannah.nongnu.org/download/rdiff-backup/rdiff-backup-1.3.3-win32.zip)

## Current Status: ## 
The earliest releases of rdiff-backup are more than seven years old. Since then there have been more than 70 releases fixing bugs and adding features. The basic functionality on unix platforms has been tested by many people over this time and can be considered stable.

Many users seem to use rdiff-backup on MS Windows but this configuration is less well tested. Also, features such as Mac OS X resource forks, Extended Attributes, and Access Control Lists were only released about five years ago. There are no known bugs in these newer features, but they are not as thoroughly tested as the basic functionality. Native Windows support was first released six months ago.

Using rdiff-backup to backup files to a server mounted via smbfs or CIFS has been a troublesome configuration for some users. Mounting via smbfs tends to be more reliable than CIFS, although it is deprecated on Linux and does not support files greater than 2 GB. See [the FAQ](FAQ.html) for more on this setup.

## Support or Contact ##

Please use the [GitHub issue tracker][ghtracker]. The [mailing list][mail] will also remain active for the time being.

[ghtracker]: https://github.com/sol1/rdiff-backup/issues
[mail]: https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users]

## Requirements: ##

*   A POSIX operating system, like Linux, Mac OS X or Cygwin
*   Python v2.2 or later (see [http://www.python.org](http://www.python.org/))
*   [librsync](http://librsync.sourceforge.net) v0.9.7 or later (note there is a [known bug with patch](http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=355178) for large file support)
*   On Windows, rdiff-backup requires the Visual C++ 2008 redistributable. To install for all users, [download the package from Microsoft](http://www.microsoft.com/downloads/details.aspx?FamilyID=9B2DA534-3E03-4391-8A4D-074B9F2BC1BF&displaylang=en). Alternatively, the C++ libraries can be installed in a "side-by-side" configuration by downloading [the DLL package](http://download.savannah.gnu.org/releases/rdiff-backup/Microsoft.VC90.zip) and copying the four files into the same directory as rdiff-backup.exe. The side-by-side method does not require administrator access.
*   To build rdiff-backup from source on Windows, the [Python for Windows extensions](http://sourceforge.net/projects/pywin32/) are required. The standalone binary requires neither Python nor librsync.
*   The python module [pylibacl](http://pylibacl.sourceforge.net/) is optional, but necessary for POSIX access control list support. Download [here](http://sourceforge.net/project/showfiles.php?group_id=69935). Note: there is no support for ACLs on Mac OS Xs.
*   The python module [pyxattr](http://pyxattr.sourceforge.net/) is optional, but necessary for extended attribute support. Download [here](http://sourceforge.net/project/showfiles.php?group_id=69931). Mac OS X users require a different [xattr library](http://undefined.org/python/#xattr), which can be downloaded from [here](http://cheeseshop.python.org/pypi/xattr).

**Note:** `rdiff-backup-statistics` requires Python v2.4 or later
