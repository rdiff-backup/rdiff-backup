#! /usr/bin/python

# Generate a dangerous command stream for testing libhsync.
# $Id$

# Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
   
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
   
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA 

# This should catch every boundary case
byte_vals = [1, 2, 3, 10, 20, 100, 200, 250, 251, 252, 253,
        254, 255]
short_vals = byte_vals + [256, 257, 258, 259, 260, 261, 300,
        1000, 2000, 1<<16 - 1]
vals = short_vals + \
       [1<<16, 1<<16 + 1, 1<<18, 1<<20, 1<<22, int(1<<31L - 1)]

for i in vals:
    print 'LITERAL', i

for i in vals:
    print 'SIGNATURE', i

for offset in [0] + vals:
    for length in vals:
        print 'COPY', offset, length

for i in short_vals:
    print 'CHECKSUM', i

print 'EOF'
        

# Local variables:
# mode: python
# End:
