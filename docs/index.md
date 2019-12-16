# rdiff-backup

rdiff-backup backs up one directory to another, possibly over a network. The target directory ends up a copy of the source directory, but extra reverse diffs are stored in a special subdirectory of that target directory, so you can still recover files lost some time ago. The idea is to combine the best features of a mirror and an incremental backup. rdiff-backup also preserves subdirectories, hard links, dev files, permissions, uid/gid ownership (if it is running as root), modification times, acls, eas, resource forks, etc. Finally, rdiff-backup can operate in a bandwidth efficient manner over a pipe, like rsync. Thus you can use rdiff-backup and ssh to securely back a hard drive up to a remote location, and only the differences will be transmitted. 

Read further:

* [Usage examples](examples.md)
* [Frequently asked questions](FAQ.md)
* [Windows specific documentation](Windows-README.md) - possibly outdated
* [Developer documentation](DEVELOP.md)

## Authors and Contributors

[rdiff-backup](https://github.com/rdiff-backup) is the current maintainer of rdiff-backup. 

Project Lead / Maintainer History:

* From August 2019 onwards the main driver for the project is Eric L. supported by Seravo.
* Sol1 has officially taken over stewardship of rdiff-backup from February 2016.
* Edward Ned Harvey, maintainer 2012 to 2016
* Andrew Ferguson, maintainer 2008 to 2012
* Dean Gaudet, maintainer 2006 to 2007
* Ben Escoto, original author, maintainer 2001 to 2005.

Other code contributors are:

* Daniel Hazelbaker, who contributed Mac OS X resource fork support. (July 2003)
* Dean Gaudet, for checking in many patches, and for finding and fixing many bugs.
* Andrew Ferguson, for improving Mac OS X support and fixing many user-reported bugs.
* Josh Nisly, for contributing native Windows support. (June 2008)
* Fred Gansevles, for contributing Windows ACLs support. (July 2008)


Thanks also to:

* The [Free Software Foundation](http://www.fsf.org/), for previously hosting the rdiff-backup project via their Savannah system.
* Andrew Tridgell and Martin Pool for writing rdiff, and also for rsync, which gave Ben Escoto the idea
* Martin Pool and Donovan Baarda for their work on librsync, which rdiff-backup needs.
* Michael Friedlander for initially acting interested in the idea and giving me accounts for testing
* Lots of people on the mailing list for their helpful comments, advice, and patches, particularly Alberto Accomazzi, Donovan Baarda, Jeb Campbell, Greg Freemyer, Jamie Heilman, Marc Dyksterhouse, and Ralph Lehmann.


## Support or Contact

If you have everything installed properly, and it still doesn't work,
see the enclosed [FAQ](docs/FAQ.md), the [rdiff-backup web page](https://rdiff-backup.net/)
and/or the [rdiff-backup-users mailing list](https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users).

We're also happy to help if you create an issue to our
[GitHub repo](https://github.com/rdiff-backup/rdiff-backup/issues). The most
important is probably to explain what happened with which version of rdiff-backup,
with which command parameters on which operating system version, and attach the output
of rdiff-backup run with the very verbose option `-v9`.
