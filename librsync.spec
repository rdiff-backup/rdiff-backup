# This RPM supposes that you download the master.zip from github to SOURCES directory as librsync-master.zip

%define name librsync
%define version master
%define gitsource https://github.com/librsync/%{name}/archive/master.zip

Summary:  	Rsync libraries
Name:     	%{name}
Version:  	%{version}
Release:  	1%{?dist}
License:	LGPL
Group:    	System Environment/Libraries
Source0:	%{name}-master.zip
URL:       	http://librsync.sourcefrog.net/
BuildRoot:	%{_tmppath}/%{name}-%{version}-root
BuildRequires:  libtool perl zlib cmake popt-devel bzip2-devel doxygen

%description
librsync implements the "rsync" algorithm, which allows remote
differencing of binary files.  librsync computes a delta relative to a
file's checksum, so the two files need not both be present to generate
a delta.

%package devel
Summary: Headers and development libraries for librsync
Group: Development/Libraries
Requires: %{name} = %{version}

%description devel
librsync implements the "rsync" algorithm, which allows remote
differencing of binary files.  librsync computes a delta relative to a
file's checksum, so the two files need not both be present to generate
a delta.

This package contains header files necessary for developing programs
based on librsync.

%prep
#wget --no-check-certificate --timeout=5 -O %{_sourcedir}/%{name}-master.zip %{gitsource}
%setup
# The next line is only needed if there are any non-upstream patches.  In
# this distribution there are none.
#%patch
%build

# By default, cmake installs to /usr/local, need to tweak here
cmake -DCMAKE_INSTALL_PREFIX=%{_prefix}  -DCMAKE_BUILD_TYPE=Release .
make CFLAGS="$RPM_OPT_FLAGS"
make doc

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install

# Missing man ugly fix
mkdir --parents $RPM_BUILD_ROOT/usr/share/man/man3
mkdir --parents $RPM_BUILD_ROOT/usr/share/man/man1
cp %{_builddir}/librsync-%{version}/doc/rdiff.1 $RPM_BUILD_ROOT/usr/share/man/man1/rdiff.1
cp %{_builddir}/librsync-%{version}/doc/librsync.3 $RPM_BUILD_ROOT/usr/share/man/man3/librsync.3

%clean
rm -rf $RPM_BUILD_ROOT

%post -p /sbin/ldconfig

%postun -p /sbin/ldconfig

%files
%defattr(-,root,root)
%doc AUTHORS COPYING NEWS.md README.md
%{_bindir}/rdiff
%{_mandir}/man1/rdiff.1.gz
%{_libdir}/%{name}*
%{_mandir}/man3/librsync.3.gz

%files devel
%defattr(-,root,root)
%{_includedir}/%{name}*

%changelog
* Mon Feb 26 2018 Orsiris de Jong <ozy@netpower>
- Updated SPEC file for librsync 2.0.2
- Fixed cmake paths for RHEL 7 64 bits
- Fix bogus man page paths
- Added automatic source download using wget (for tests)
