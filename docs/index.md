# rdiff-backup

Rdiff-backup backs up one directory to another, possibly over a network. The target directory ends up a copy of the source directory, but extra reverse diffs are stored in a special subdirectory of that target directory, so you can still recover files lost some time ago. The idea is to combine the best features of a mirror and an incremental backup. Rdiff-backup also preserves subdirectories, hard links, dev files, permissions, uid/gid ownership (if it is running as root), modification times, acls, eas, resource forks, etc. Finally, rdiff-backup can operate in a bandwidth efficient manner over a pipe, like rsync. Thus you can use rdiff-backup and ssh to securely back a hard drive up to a remote location, and only the differences will be transmitted.

Read further:

* [Usage examples](examples.md)
* [Frequently asked questions](FAQ.md)
* [Authors and credits](credits.md)
* [Developer documentation](DEVELOP.md)
* [Windows specific documentation](Windows-README.md) - possibly outdated
* [Windows specific Developer documentation](Windows-DEVELOP.md)


## Support or Contact

If you have everything installed properly, and it still doesn't work,
see the enclosed [FAQ](docs/FAQ.md), the [rdiff-backup web page](https://rdiff-backup.net/)
and/or the [rdiff-backup-users mailing list](https://lists.nongnu.org/mailman/listinfo/rdiff-backup-users).

We're also happy to help if you create an issue to our
[GitHub repo](https://github.com/rdiff-backup/rdiff-backup/issues). The most
important is probably to explain what happened with which version of rdiff-backup,
with which command parameters on which operating system version, and attach the output
of rdiff-backup run with the very verbose option `-v9`.

This is an open source project and contributions are welcome!


## History

Rdiff-backup has been around for almost 20 years now and has proved to be a very solid solution for backups and it is still unique in its model of unlimited incrementals with no need to space consuming regular full backups.

Current lead developers are Eric Lavarde, Patric Dufresene and Otto Kekäläinen. Full list of core developers available at [rdiff-backup Github page](https://github.com/rdiff-backup/rdiff-backup/people) and on the [credits page](credits.md).

The original author and maintainer was **Ben Escoto** from 2001 to 2005. Key contributors from 2005 to 2016 were Dean Gaudet, Andrew Ferguson and Edward Ned Harvey. After some hibernation time Sol1 took over the stewardship of rdiff-backup from February 2016 but there were no new releases. In August 2019 [Eric Lavarde](https://www.lavar.de/) with the support of Otto Kekäläinen from [Seravo](https://seravo.com/) and Patrik Dufresne from [Minarca](http://www.patrikdufresne.com/en/minarca/) took over, completed the Python 3 rewrite and finally released rdiff-backup 2.0 in March 2020.
