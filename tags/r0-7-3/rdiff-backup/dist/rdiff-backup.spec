Summary: Convenient and transparent local/remote incremental mirror/backup
Name: rdiff-backup
Release: 1
URL: http://www.stanford.edu/~bescoto/rdiff-backup/
Source: %{name}-%{version}.tar.gz
Copyright: GPL
Group: Applications/Archiving
BuildRoot: %{_tmppath}/%{name}-root
requires: librsync, python >= 2.2

%description
rdiff-backup is a script, written in Python, that backs up one
directory to another and is intended to be run periodically (nightly
from cron for instance). The target directory ends up a copy of the
source directory, but extra reverse diffs are stored in the target
directory, so you can still recover files lost some time ago. The idea
is to combine the best features of a mirror and an incremental
backup. rdiff-backup can also operate in a bandwidth efficient manner
over a pipe, like rsync. Thus you can use rdiff-backup and ssh to
securely back a hard drive up to a remote location, and only the
differences from the previous backup will be transmitted.

%prep
%setup

%build

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/bin
mkdir -p $RPM_BUILD_ROOT/usr/share/man/man1

install -m 755 rdiff-backup $RPM_BUILD_ROOT/usr/bin/rdiff-backup
install -m 644 rdiff-backup.1 $RPM_BUILD_ROOT/usr/share/man/man1/rdiff-backup.1
%clean

%files
%defattr(-,root,root)

/usr/bin/rdiff-backup
/usr/share/man/man1/rdiff-backup.1.gz
%doc CHANGELOG COPYING README FAQ.html

%changelog
* Sun Nov 4 2001 Ben Escoto <bescoto@stanford.edu>
- Initial RPM

