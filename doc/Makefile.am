## Process this file with automake to produce Makefile.in

# Copyright (C) 2002 by Ben Elliston <bje@redhat.com>
# $Id$

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

man_MANS = rdiff.1 librsync.3
EXTRA_DIST = $(man_MANS)

# Doxygen API documentation

sites=front.linuxcare.com.au:/var/www/projects/rproxy \
	rproxy.sourceforge.net:/home/groups/rproxy/htdocs \
	rproxy.samba.org:/space/httpd/rproxy/htdocs

.PHONY: do-doxy upload-doxy

html latex do-doxy: Doxyfile
	doxygen

refman.pdf refman.ps.gz: latex
	cd latex && make refman.ps refman.pdf && gzip -9vf refman.ps

upload-doxy: html refman.pdf refman.ps.gz
	for i in $(sites); do \
	rsync -avz --delete --exclude '*~' \
		html/ latex/refman.pdf latex/refman.ps.gz \
		$(srcdir)/rproxy-small-logo.png $$i/doxygen/librsync; \
	done

converted_men = man_librsync_3.html man_librsync_3.ps \
	man_rdiff_1.html man_rdiff_1.ps

man_%_1.ps: %.1
	groff -mandoc -Tps $< >$@

man_%_3.ps: %.3
	groff -mandoc -Tps $< >$@

man_%_1.html: %.1
	groff -mandoc -Thtml $< >$@

man_%_3.html: %.3
	groff -mandoc -Thtml $< >$@

man_%_1.txt: %.1
	groff -mandoc -Tlatin1 $< >$@

man_%_3.txt: %.3
	groff -mandoc -Tlatin1 $< >$@

upload-men: $(converted_men)
	for i in $(sites); do \
		rsync -avz --delete $(converted_men) $(man_MANS) $$i/man; \
	done

upload-news: NEWS
	for i in $(sites); do \
		rsync -avz --delete $(srcdir)/NEWS $$i/librsync-NEWS; \
	done
