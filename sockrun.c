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
 * sockrun.c -- Run a program with input and output filtered through
 * sockets.
 *
 * In a perfectly functional program this will prove nothing.
 * However, in one which has bugs to do with packetization causing
 * short reads and writes, this might shake out some bugs.
 *
 * This program is called with the arguments for a subsidiary command
 * (leaving aside some options.)  On execution, it forks into three parts:
 *
 *    stdin --INPUT--> COMMAND --OUTPUT--> stdout
 *
 * The program creates two localhost sockets.  The middle part execs
 * the specified command.  The two outer parts copy to and from
 * stdout.  When eof or SIGPIPE is reached on any file, that part
 * terminates: they do not necessarily all finish together.  The main
 * program waits for them all to complete, and exits successfully only
 * if all the parts exited successfully.
 *
 * On Linux you can change the loopback MTU to fiddle with this. */

/* TODO: Let the input and output parts proceed more slowly, or with
 * randomly limited lengths, so that it's more likely fragmentation will be
 * seen in the middle. */


#include "includes.h"

static int no_nagle = 0;
static pid_t            in_pid, cmd_pid, out_pid;
static int              out_svr_sock, in_svr_sock;
static int              cmd_argc;
static char           **cmd_argv;
int                     out_port, in_port;


static void
show_usage()
{
    printf("Usage: sockcli COMMAND [ARG ...]\n"
           "Connect to a local TCP port and copy data in and out\n"
           "  -N    don't Nagle me; send packets immediately\n"
           "  -D    turn on trace, if enabled in library\n");
}


static int
open_client_socket(int *psock, int port)
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

    if (setsockopt(sock, SOL_TCP, TCP_NODELAY, &no_nagle,
                   sizeof no_nagle) < 0) {
        _hs_error("error setting TCP_NODELAY=%d: %s",
                  no_nagle, strerror(errno));
    }

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
bind_any_socket(int *psock, int *pport)
{
    struct sockaddr_in addr;
    int             sock;
    socklen_t           len;

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

    if (setsockopt(sock, SOL_TCP, TCP_NODELAY, &no_nagle,
                   sizeof no_nagle) < 0) {
        _hs_error("error setting TCP_NODELAY=%d: %s",
                  no_nagle, strerror(errno));
    }

    /* Listen for connections. */
    if (listen(sock, 10) < 0) {
        _hs_error("listen failed: %s", strerror(errno));
        return -1;
    }

    return 1;
}



static int
out_main(void)
{
    int         out_sock;

    int ret;
    _hs_trace("output process waiting for connection");
    if ((out_sock = accept(out_svr_sock, NULL, 0)) < 0) {
        _hs_error("can't accept connection to output: %s",
                  strerror(errno));
        return 1;
    }
    close(out_svr_sock);

    ret = _hs_file_copy_all(out_sock, STDOUT_FILENO);
    if (close(out_sock) < 0) {
        _hs_error("close write socket: %s", strerror(errno));
        return -1;
    }

    return 0;
}


static int
in_main(void)
{
    int         in_sock;
    int ret;

    if (open_client_socket(&in_sock, in_port) < 0) {
        return 1;
    }

    ret = _hs_file_copy_all(STDIN_FILENO, in_sock);
    close(in_sock);
    
    return 0;
}

static int
fork_run(int *new_pid, int (*fn)(void))
{
    pid_t               pid;

    pid = fork();
    if (pid < 0) {
        _hs_error("error forking child: %s", strerror(errno));
        return -1;
    } else if (pid == 0) {
        exit(fn());
    } else {
        _hs_trace("forked child %d", pid);
        *new_pid = pid;
        return pid;
    }
}


static int
start_output(void)
{
    if (bind_any_socket(&out_svr_sock, &out_port ) < 0)
        return -1;

    if (fork_run(&out_pid, out_main) < 0)
        return -1;

    close(out_svr_sock);        /* in parent */

    return 0;
}


static int
cmd_main(void)
{
    int         cmd_out_sock, cmd_in_sock;

    if (open_client_socket(&cmd_out_sock, out_port) < 0) {
        return 1;
    }
    
    _hs_trace("command process waiting for connection");
    if ((cmd_in_sock = accept(in_svr_sock, NULL, 0)) < 0) {
        _hs_error("can't accept connection to command: %s",
                  strerror(errno));
        return 1;
    }
    close(in_svr_sock);
    
    if (dup2(cmd_out_sock, STDOUT_FILENO) < 0) {
        _hs_error("can't redirect command output to socket: %s",
                  strerror(errno));
        return 1;
    }
    if (dup2(cmd_in_sock, STDIN_FILENO) < 0) {
        _hs_error("can't redirect command input from socket: %s",
                  strerror(errno));
        return 1;
    }

    if (execvp(cmd_argv[0], cmd_argv) < 0) {
        _hs_error("can't start %s: %s",
                  cmd_argv[0], strerror(errno));
        return 1;
    }

    return 0;                   /* should be unreachable */
}


static int
start_command(void)
{
    if (bind_any_socket(&in_svr_sock, &in_port) < 0)
        return -1;
    
    if (fork_run(&cmd_pid, cmd_main) < 0)
        return -1;

    close(in_svr_sock);         /* in parent */
    return 0;
}


static int
start_input(void)
{
    if (fork_run(&in_pid, in_main) < 0)
        return -1;
    return 0;
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
        _hs_error("child %d exited with status %#x",
                  pid, status);
        return -1;
    } else {
        _hs_trace("child %d exited with status %#x",
                  pid, status);
        return 0;
    }
}

    

int
main(int argc, char **argv)
{
    int                 c;

    /* may turn it on later */
    while ((c = getopt(argc, argv, "DN")) != -1) {
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
        case 'N':
            no_nagle = 1;
            break;
        default:
            abort();
	}
    }

    signal(SIGPIPE, SIG_IGN);

    if (optind >= argc) {
        show_usage();
        return 1;
    }

    cmd_argc = argc - optind;
    cmd_argv = argv + optind;

    if (start_output() < 0) {
        return 1;
    }

    if (start_command() < 0) {
        kill(out_pid, SIGHUP);
        return 1;
    }

    if (start_input() < 0) {
        kill(out_pid, SIGHUP);
        kill(cmd_pid, SIGHUP);
        return 1;
    }

    reap_child(out_pid);
    reap_child(cmd_pid);
    reap_child(in_pid);

    return 0;
}

