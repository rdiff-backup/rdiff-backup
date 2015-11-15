#! /usr/bin/perl -w

# librsync -- the library for network deltas
# $Id$
#
# Copyright (C) 1999, 2000 by Martin Pool <mbp@sourcefrog.net>
# Copyright (C) 1999 by Andrew Tridgell <tridge@samba.org>
#
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

# mutate: makes a random smalll change to an input file and writes it
# to stdout.

use strict;

if ($#ARGV != 1) {
  print STDERR "usage: mutate.pl SEED MUTATIONS <BASIS\n";
  exit 1;
}

srand shift @ARGV;
my $n_muts = 1 + int rand shift @ARGV;

undef $/;                       # slurp whole file
my $corpus = <STDIN>;

printf STDERR "%d mutations\n", $n_muts;

while ($n_muts-- > 0) {
  my $in_len = length($corpus);

  my $from_off = int rand $in_len;
  my $from_len = int(rand(1.0) * rand($in_len));
  my $to_off = int rand $in_len;
  my $to_len = int(rand(1.0) * rand($in_len));

  my $op = rand 3;
  if ($op < 1.0) {
    printf STDERR "copy and overwrite";
    substr($corpus, $to_off, $to_len) = substr($corpus, $from_off, $from_len);
  } elsif ($op < 2.0) {
    print STDERR "copy and insert";
    substr($corpus, $to_off, 0) = substr($corpus, $from_off, $from_len);
  } else {
    print STDERR "delete";
    substr($corpus, $to_off, $to_len) = '';
  }

  printf STDERR " (%d, %d) -> (%d, %d)\n", $from_off, $from_len, $to_off, $to_len;
}

print $corpus;

