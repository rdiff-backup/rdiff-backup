/*				       	-*- c-file-style: "bsd" -*-
 * libhsync -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
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

#include <unistd.h>
#include <stdio.h>
#include <sys/file.h>
#include <string.h>

#include <hsync.h>

static void
show_help(void)
{
    printf("Usage: hsyncinfo OPTION...\n"
           "Options:\n"
           "  -v    show library release\n"
           "  -l    show library libversion\n"
           "  -t    is library trace turned on?\n"
           "  -o    length of file offsets\n"
           "  -h    show help\n");
}


static void
show_version(char const *v)
{
    puts(v);
}


static void
show_trace_setting(void)
{
    printf("trace %s\n",
           hs_supports_trace() ? "enabled" : "disabled");
}


static void
show_offset_bits(void)
{
    printf("file offset type is %d bits\n",
           hs_libhsync_file_offset_bits);
}


int
main(int argc, char **argv)
{
    int             c;

    if (argc <= 1) {
        show_help();
        return 1;
    }

    while ((c = getopt(argc, argv, "ovthl")) != -1) {
        switch (c) {
        case 'o':
            show_offset_bits();
            break;
            
        case 'v':
            show_version(hs_libhsync_version);
            break;

        case 'l':
            show_version(hs_libhsync_libversion);
            break;            
        
        case 't':
            show_trace_setting();
            break;
        
        case 'h':
            show_help();
            break;
        
        case ':':
        case '?':
            return 1;
        }
    }

    return 0;
}
