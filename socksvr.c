/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

/*
 * socksvr -- Accept connections on a TCP socket, and pass them
 * through to a server process as stdin/stdout.
 *
 * This is kind of like inetd and many other programs.  Why recreate
 * it?  A few reasons, all coming from the fact that we want to use
 * this in the libhsync automatic test suite.
 *
 * Firstly, we can't count on any particular TCP port being available
 * for use on any server, and we don't want to trouble the user to
 * choose one.  The kernel will assign a port for us if we want one,
 * and we write it out to stdout, so that the caller can see it and
 * send clients to it.
 *
 * Secondly, we don't want to require any human intervention, such as
 * inserting commands into /etc/inetd.conf.
 *
 * Thirdly, we don't want to require tools such as netcat that are
 * only available on some distributions.
 *
 * XXX: This is not secure!  Only use it for testing.  Never run a
 * shell.
 */

#include "includes.h"

#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

#include <netinet/in.h>
#include <netinet/tcp.h>

#include <sys/file.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/socket.h>

static void
show_usage(void)
{
    printf("Usage: socksvr OPTIONS COMMAND ...\n"
           "Bind and listen on a port; invoke COMMAND on each connection\n"
           "Options:\n"
           "  -1    serve just a single client, then exit\n"
           "  -D    turn on trace, if enabled in library\n");
}


static int
bind_any_socket(int *psock, int *pport)
{
    struct sockaddr_in addr;
    int             sock;
#ifdef HAVE_SOCKLEN_T
    socklen_t           len;
#else
    size_t		len;
#endif

    /* Create a socket */
    sock = socket(PF_INET, SOCK_STREAM, 0);
    if (sock == -1) {
        _hs_error("create socket failed: %s", strerror(errno));
	return -1;
    }

    /* Get an address.  Any address is fine. */
    hs_bzero((char *) &addr, sizeof addr);
#ifdef HAVE_SOCK_SIN_LEN 
    addr.sin_len = sizeof(addr);
#endif 
    addr.sin_port = 0;
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(sock, (struct sockaddr *) &addr, sizeof addr) < 0) {
        _hs_error("bind socket failed: %s", strerror(errno));
	return (-1);
    }

    /* where are we? */
    len = sizeof addr;
    if (getsockname(sock, (struct sockaddr *) &addr, &len) < 0) {
        _hs_error("getsockname failed: %s", strerror(errno));
        return -1;
    }

    _hs_trace("got socket on port %d", ntohs(addr.sin_port));

    *pport = ntohs(addr.sin_port);
    *psock = sock;

    /* Listen for connections. */
    if (listen(sock, 10) < 0) {
        _hs_error("listen failed: %s", strerror(errno));
        return -1;
    }

    return 1;
}


static int
accept_connection(int sock)
{
    struct sockaddr_in     client;
#ifdef HAVE_SOCKLEN_T
    socklen_t           len;
#else
    size_t len;
#endif
    int                 newsock;

    len = sizeof client;

    if ((newsock = accept(sock, (struct sockaddr *) &client, &len)) < 0) {
        _hs_error("accept failed: %s", strerror(errno));
        return -1;
    }

    return newsock;
}


static int
child_main(int newsock, char **argv)
{
    if ((dup2(newsock, STDIN_FILENO) < 0)
        || (dup2(newsock, STDOUT_FILENO) < 0)) {
        _hs_error("dup2 in child failed: %s", strerror(errno));
        return 1;
    }
           
    if (close(newsock) < 0) {
        _hs_error("close spare child socket: %s", strerror(errno));
        return -1;
    }


    if ((execvp(argv[0], argv)) < 0) {
        _hs_error("exec in child failed: %s", strerror(errno));
        return 1;
    }

    return 0;                   /* prob unreachable */
}


static int
fork_and_serve(int srvr_sock, int newsock, char **argv)
{
    int pid;

    pid = fork();
    if (pid < 0) {
        _hs_error("error forking child: %s", strerror(errno));
        return -1;
    } else if (pid == 0) {
        if (close(srvr_sock) < 0) {
            _hs_error("close listen socket: %s", strerror(errno));
            return -1;
        }
        exit(child_main(newsock, argv));
    } else {
        _hs_trace("forked child %d", pid);
        close(newsock);
        return 0;
    }
}


static void
sigchld_handler(int UNUSED(signum))
{
    int pid, status, serrno;
    serrno = errno;
    while (1) {
        pid = waitpid((pid_t) -1, &status, WNOHANG);
        if (pid < 0 && errno == ECHILD)
            break;
        else if (pid < 0) {
            _hs_error("waitpid failed: %s", strerror(errno));
            break;
        }
        else if (pid == 0)
            break;
        _hs_trace("child %d exited with status %d", pid, status);
    }
    errno = serrno;
}





int
main(int argc, char **argv)
{
    int                 sock;
    int                 port;
    int                 newsock;
    int                 c;
    int                 single = 0;

    		/* may turn it on later */
    while ((c = getopt(argc, argv, "1D")) != -1) {
	switch (c) {
	case '?':
	case ':':
	    return -1;
        case '1':
            single = 1;
            break;
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

    argc -= optind;
    argv += optind;
    if (argc <= 0) {
        show_usage();
        return 1;
    }

    signal(SIGCHLD, sigchld_handler);

    if (bind_any_socket(&sock, &port) < 0) {
        return 1;
    }

    /* print the port to stdout so it can be used by scripts. */
    printf("%d\n", port);
    fflush(stdout);
    
    while (1) {
        if ((newsock = accept_connection(sock)) < 0)
            return 1;
        if (single) {
            if (child_main(newsock, argv))
                return 1;
            else
                return 0;
        } else {
            if ((fork_and_serve(sock, newsock, argv)) < 0)
                return 1;
        }
    }

    return 0;                   /* probably unreached */
}
