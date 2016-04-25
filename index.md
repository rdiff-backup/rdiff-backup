--- 
layout: default 
--- 

## rdiff-backup is reverse differential backup ## 
rdiff-backup backs up one directory to another, possibly over a network. The target directory ends up a copy of the source directory, but extra reverse diffs are stored in a special subdirectory of that target directory, so you can still recover files lost some time ago. The idea is to combine **the best features of a mirror and an incremental backup**. rdiff-backup also preserves subdirectories, hard links, dev files, permissions, uid/gid ownership (if it is running as root), modification times, extended attributes, acls, resource forks etc. Finally rdiff-backup can operate in a **bandwidth efficient** manner over a pipe, like rsync. Thus you can use rdiff-backup and ssh to securely back a hard drive up to a remote location, and only the differences will be transmitted. Finally, rdiff-backup is **easy to use** and settings have sensical defaults. 

[Sol1][sol1gh] has officially taken over stewardship of rdiff-backup from February 2016. [Sol1][sol1gh] has long been a contributor and user of rdiff-backup, and will maintain the open source nature of rdiff-backup, while bringing it into the modern era.

## Usage ##

The wiki contains documentation on use cases, and serves as a respository of scripts for people to contribute to. These scripts do many things for and around rdiff-backup.

## Authors and Contributors ## 

[@sol1][sol1gh] is the current maintainer of rdiff-backup

Project Lead / Maintainer History:

* Edward Ned Harvey, maintainer 2012 to 2016 
* Andrew Ferguson, maintainer 2008 to 2012
* Dean Gaudet, maintainer 2006 to 2007
* Ben Escoto, original author, maintainer 2001 to 2005

Other code contributors are:

* Daniel Hazelbaker, who contributed Mac OS X resource fork support. (July 2003)
* Dean Gaudet, for checking in many patches, and for finding and fixing many bugs.
* Andrew Ferguson, for improving Mac OS X support and fixing many user-reported bugs.
* Josh Nisly, for contributing native Windows support. (June 2008)
* Fred Gansevles, for contributing Windows ACLs support. (July 2008)

[sol1gh]: https://github.com/sol1

Thanks also to:

* The [Free Software Foundation][fsf] for previously hosting rdiff-backup with their [Savannah][sav] system.
* Andrew Tridgell and Martin Pool for writing rdiff, and also for rsync, which gave me the idea
* Martin Pool and Donovan Baarda for their work on librsync, which rdiff-backup needs.
* Michael Friedlander for initially acting interested in the idea
        and giving me accounts for testing
* Lots of people on the mailing list for their helpful comments,
        advice, and patches, particularly Alberto Accomazzi, Donovan Baarda,
* Jeb Campbell, Greg Freemyer, Jamie Heilman, Marc Dyksterhouse, and Ralph Lehmann.

[fsf]: http://www.fsf.org
[sav]: http://savannah.nongnu.org

## Support or Contact ##

Please use the [GitHub issue tracker][ghtracker]. The [mailing list][mail] will also remain active for the time being.

[ghtracker]: https://github.com/sol1/rdiff-backup/issues
[mail]: https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users]
