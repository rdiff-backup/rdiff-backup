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

#include "includes.h"

static void
show_help(void)
{
    printf("Usage: hsyncinfo OPTION...\n"
           "Options:\n"
           "  -v    show library release\n"
           "  -l    show library libversion\n"
           "  -t    is library trace turned on?\n"
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


int
main(int argc, char **argv)
{
    int             c;

    if (argc <= 1) {
        show_help();
        return 1;
    }

    while ((c = getopt(argc, argv, "vthl")) != -1) {
        switch (c) {
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
