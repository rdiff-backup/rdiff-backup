sites=front.linuxcare.com.au:/var/www/projects/rproxy \
	rproxy.sourceforge.net:/home/groups/rproxy/htdocs \
	rproxy.samba.org:/space/httpd/rproxy/htdocs

upload-doxy:
	for i in $(sites); do \
	rsync --delete -avz html/ $$i/doxygen/libhsync; \
	done

