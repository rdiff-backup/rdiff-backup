

Migration from v1.2.8 to v2.0.0
-------------------------------

  

This document is a guide to help you migrate from rdiff-backup v1.2.8
(legacy version) to rdiff-backup v2.0.0 (new version).

  

This new version of rdiff-backup is compatible with repositories created
with the legacy version. In other words, the data on the disk is fully
compatible between the two.

**The network protocol of the legacy version is NOT compatible with the new version.**
In other words, you must be running the same version of rdiff-backup locally
and remotely. For this reason, you might need to have a plan to transition
from the legacy version to the new version depending of your use case.


You have two options for your migration:

1. Upgrade all instances of rdiff-backup to the new version. This option
is recommended for **small deployment**. If this is your case, just
[follow the installation instructions](https://github.com/rdiff-backup/rdiff-backup#installation).

2. Upgrade rdiff-backup progressively to the new version. This option is
recommended for **large deployment**. If this is your case, just
continue reading.

  

If your rdiff-backup deployment is large, upgrading all instances at the
same time might not be possible. The following section describes a way
for you to mitigate this problem. By installing both versions side by
side. We recommend installing the new rdiff-backup version in a virtualenv.

Use Case: Local to Local
------------------------

You are using rdiff-backup locally if you are running a command line
where the source and the destination are defined as a path on the same
computer. e.g.:

       rdiff-backup /source /destination

`/source` and `/destination` are paths that reside on the same computer.
/source or /destination might be remote mounted filesystem like NFS or
SSHFS.

With this use case to migrate to the latest version, we recommend you to
simply upgrade your existing installation of rdiff-backup “in-place”.

[Follow the installation instructions](https://github.com/rdiff-backup/rdiff-backup#installation).

Use Case: Local to Remote (push)
--------------------------------

You are using rdiff-backup Local to Remote if you are running a command
line where the source is local and the destination is remote. e.g.:

       rdiff-backup /source user@10.255.1.102:/destination

  

**Notice:** With this use case you must be careful as rdiff-backup
legacy version is not compatible with the new version due to the
migration to Python 3.

  

### On Remote

Start by installing the new rdiff-backup
side-by-side on the remote server as follows:

**On Debian**

        $ sudo apt update
        $ sudo apt install python3-dev libacl1-dev virtualenv build-essential curl  
        $ curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        $ sudo python3 get-pip.py
        $ sudo virtualenv -p python3 /opt/rdiff-backup2
        $ sudo /opt/rdiff-backup2/bin/pip3 install rdiff-backup pyxattr pylibacl
        $ sudo ln -s /opt/rdiff-backup2/bin/rdiff-backup /usr/bin/rdiff-backup2
        $ rdiff-backup2 –version
        rdiff-backup 2.0.0
        $ rdiff-backup –version
        rdiff-backup 1.2.8

**On CentOS/Redhat**

TODO

### On Local

Once the remote server is supporting both versions, you may then start
upgrading local instances to the new version by
[following the installation instructions](https://github.com/rdiff-backup/rdiff-backup#installation). This
will upgrade rdiff-backup to the new version.

Next, you will need to tweak the command line used to run your backup to
something similar:

	rdiff-backup --remote-schema “ssh %s rdiff-backup2 –server” ...


**Use Case: Remote to Local (pull)**
------------------------------------

You are using rdiff-backup Remote to local if you are running a command
line where the source is remote and the destination is local. e.g.:

       rdiff-backup user@10.255.1.102:/source /destination

**Notice:** With this use case you must be careful as rdiff-backup
legacy version is not compatible with the new version due to the
migration to Python 3.


### On Local

Start by installing the new rdiff-backup
side-by-side on the local server as follows. Then install the wrapper script to auto
detect the version of rdiff-backup.

**On Debian (Stretch/Buster)**

        $ sudo apt update
        $ sudo apt install python3-dev libacl1-dev virtualenv build-essential curl rdiff-backup openssh-client
        $ curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        $ sudo python3 get-pip.py
        $ sudo virtualenv -p python3 /opt/rdiff-backup2
        $ sudo /opt/rdiff-backup2/bin/pip3 install rdiff-backup pyxattr pylibacl
        $ sudo ln -s /opt/rdiff-backup2/bin/rdiff-backup /usr/bin/rdiff-backup2
        $ rdiff-backup2 --version
        rdiff-backup 2.0.0
        $ rdiff-backup --version
        rdiff-backup 1.2.8
        $ curl https://raw.githubusercontent.com/rdiff-backup/rdiff-backup/master/tools/misc/rdiff-backup-wrap -o /usr/bin/rdiff-backup-wrap
        $ chmod +x /usr/bin/rdiff-backup-wrap

**On CentOS**

TODO

Once both version of rdiff-backup are installed side-by-side, you need
to adapt your command line to make use of the rdiff-backup-wrap script
that is used to auto-detect the version of rdiff-backup to be used.

     rdiff-backup-wrap user@10.255.1.102:/source /destination

### On Remote

Once the local server is supporting both versions, you may then start
upgrading remote instances to the new version by 
[following the installation instruction](https://github.com/rdiff-backup/rdiff-backup#installation).
This will upgrade rdiff-backup to the new version.

When this happen, the wrapper script deployed on the local server will
detect the right version of ridff-backup to be used.
