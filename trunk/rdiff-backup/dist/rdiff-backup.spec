%define PYTHON_NAME %((rpm -q --quiet python2 && echo python2) || echo python)

Version: $version
Summary: Convenient and transparent local/remote incremental mirror/backup
Name: rdiff-backup
Release: 1
URL: http://www.stanford.edu/~bescoto/rdiff-backup/
Source: %{name}-%{version}.tar.gz
Copyright: GPL
Group: Applications/Archiving
BuildRoot: %{_tmppath}/%{name}-root
requires: librsync >= 0.9.5.1, %{PYTHON_NAME} >= 2.2
BuildPrereq: %{PYTHON_NAME}-devel >= 2.2, librsync-devel >= 0.9.5.1

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
%setup -q

%build
%{PYTHON_NAME} setup.py build

%install
%{PYTHON_NAME} setup.py install --prefix=$RPM_BUILD_ROOT/usr

%clean
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
/usr/bin/rdiff-backup
/usr/share/man/man1
/usr/lib
%doc CHANGELOG COPYING FAQ.html README

%changelog
* Sun Jan 19 2002 Troels Arvin <troels@arvin.dk>
- Builds, no matter if Python 2.2 is called python2-2.2 or python-2.2.

* Sun Nov 4 2001 Ben Escoto <bescoto@stanford.edu>
- Initial RPM
