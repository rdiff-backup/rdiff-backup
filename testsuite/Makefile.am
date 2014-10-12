## Process this file with automake to produce Makefile.in

# Copyright (C) 2002 by Ben Elliston <bje@redhat.com>
# Copyright (C) 2014 by Martin Pool <mbp@sourcefrog.net>

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# as published by the Free Software Foundation; either version 2.1 of
# the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

MAINTAINERCLEANFILES = Makefile.in

check_PROGRAMS = isprefix.driver

INCLUDES = -I $(srcdir)/..
isprefix_driver_SOURCES = isprefix.driver.c
isprefix_driver_LDADD = ../isprefix.o # XXX: should link replaced functions

# NB: tests should exit with code 77 if they can't be run but haven't
# failed.  Generally these tests should be ordered so that more basic
# tests are run first.

TESTS = \
	signature.test mutate.test sources.test isprefix.test	\
	delta.test mksum.test triple.test changes.test

noinst_SCRIPTS = testcommon.sh mutate.pl $(TESTS)

test_data = dot \
	changes.input/01.in changes.input/02.in \
	changes.input/03.in changes.input/04.in \
	delta.input/01.delta delta.input/01.expect \
	delta.input/02.delta delta.input/02.expect \
	delta.input/03.delta delta.input/03.expect \
	mdfour.input/01.expect mdfour.input/01.data \
	mksum.input/COPYING.sig \
	triple.input/copying.in triple.input/half.in \
	triple.input/hello.in triple.input/zero.in \
	signature.input/01.in signature.input/01.sig

EXTRA_DIST = $(noinst_SCRIPTS) $(test_data)
