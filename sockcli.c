/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

/*
 * TODO: If we get an `unreachable' message, assume that perhaps they
 * have firewalling rules and explain it.
 */

#include "includes.h"



static void
show_usage()
{
    printf("Usage: sockcli PORT ...\n"
           "Connect to a local TCP port and copy data in and out\n"
           "  -D    turn on trace, if enabled in library\n");
}


static int
open_socket(int *psock, int port)
{
    struct sockaddr_in addr;
    int             sock;

    /* Create a socket */
    sock = socket(PF_INET, SOCK_STREAM, 0);
    if (sock == -1) {
        _hs_error("create socket failed: %s", strerror(errno));
	return -1;
    }

    hs_bzero((char *) &addr, sizeof addr);
#ifdef HAVE_SOCK_SIN_LEN 
    addr.sin_len = sizeof(addr);
#endif 
    addr.sin_port = htons(port);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(0x7f000001);

    if (connect(sock, (struct sockaddr *) &addr, sizeof addr) < 0) {
        _hs_error("connect socket to localhost:%d failed: %s",
                  port, strerror(errno));
	return (-1);
    }

    _hs_trace("got socket %d on port %d", sock, ntohs(addr.sin_port));
    *psock = sock;

    return 1;
}


static int
child_main(int sock)
{
    int ret;

    ret = _hs_file_copy_all(sock, STDOUT_FILENO) < 0;
    if (close(sock) < 0) {
        _hs_error("close write socket: %s", strerror(errno));
        return -1;
    }
    _hs_trace("child finished");        
    return ret;
}

static int
fork_reader(int sock)
{
    int pid;

    pid = fork();
    if (pid < 0) {
        _hs_error("error forking child: %s", strerror(errno));
        return -1;
    } else if (pid == 0) {
        exit(child_main(sock));
    } else {
        _hs_trace("forked child %d", pid);
        return pid;
    }
}


static int
reap_child(int pid)
{
    int status;

    if (waitpid(pid, &status, 0) < 0) {
        _hs_error("wait error: %s", strerror(errno));
        return -1;
    }

    if (status) {
        _hs_error("child exited with status %#x", status);
        return -1;
    }

    return 0;
}


static int
writer(int sock)
{
    int ret;

    ret = _hs_file_copy_all(STDIN_FILENO, sock);
    if (close(sock) < 0) {
        _hs_error("close write socket: %s", strerror(errno));
        return -1;
    }

    return ret;
}


int
main(int argc, char **argv)
{
    int                 sock;
    int                 port;
    int                 c;
    int                 pid;

    /* may turn it on later */
    while ((c = getopt(argc, argv, "D")) != -1) {
	switch (c) {
	case '?':
	case ':':
	    return -1;
    	case 'D':
	    if (!hs_supports_trace()) {
		_hs_error("library does not support trace");
	    }
	    hs_trace_set_level(LOG_DEBUG);
	    break;
        default:
            abort();
	}
    }

    if (optind >= argc) {
        show_usage();
        return 1;
    }

    port = atoi(argv[optind]);
    if (!port) {
        show_usage();
        return 1;
    }

    if (open_socket(&sock, port) < 0) {
        return 1;
    }

    pid = fork_reader(sock);
    if (writer(sock) < 0)
        return 1;
    _hs_trace("writer finished!");

    if (reap_child(pid) < 0)
        return 1;

    return 0;
}

