sites=front.linuxcare.com.au:/var/www/projects/rproxy \
	rproxy.sourceforge.net:/home/groups/rproxy/htdocs \
	rproxy.samba.org:/space/httpd/rproxy/htdocs

upload-doxy: latex/refman.ps.gz
	for i in $(sites); do \
	rsync --delete -avz html/ latex/refman.ps.gz ./rproxy-small-logo.png $$i/doxygen/libhsync; \
	done

latex/refman.ps.gz:
	$(MAKE) -C latex refman.ps
	gzip -9vf latex/refman.ps

