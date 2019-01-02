#! /bin/bash -ex

# librsync -- the library for network deltas

# Copyright (C) 2016 by Martin Pool

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


# Bad command-line options return an error and print a message.

errout=`mktemp -t rdiff_bad_option_test_XXXXXXX`
trap "rm $errout" EXIT
! $1/rdiff --imaginary-option 2>"$errout"
cat "$errout"
grep 'unknown option: --imaginary-option' "$errout"
