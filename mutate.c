/*= -*- c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * librsync -- the library for network deltas
 * $Id$
 * 
 * Copyright (C) 2001 by Martin Pool <mbp@samba.org>
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


/*
 * mutate -- generate random test files that make rsync's life
 * difficult.
 *
 * mutate is passed a single basis file, and it generates a series of
 * output files that are related but different.
 *
 * -n NUMBER specifies the number of output files to generate.
 *
 * -o PATTERN specifies an output filename pattern, the default being
 * "mutate%06d.tmp".
 *
 * Possible operations include
 *
 * - delete a region
 * - copy a region and insert it elsewhere
 * - copy a region and overwrite it 
 */

#include <config.h>

#include <stdlib.h>
#include <stdio.h>
#include <fcntl.h>
#include <popt.h>
#include <errno.h>
#include <string.h>

#include "rsync.h"
#include "trace.h"


#define PROGRAM "mutate"


static int n_tests = 1;
static char const *output_pattern = "mutate%06d.tmp";
static char const *basis_name;


const struct poptOption opts[] = {
    { "help",     'h', POPT_ARG_NONE },
    { 0,          'n', POPT_ARG_INT,    &n_tests },
    { 0,          'o', POPT_ARG_STRING, &output_pattern },
    {}
};


static void usage(void)
{
    printf("Usage: mutate [ -n TESTS ] [ -o PATTERN ] BASIS\n");
}


static void
process_args(int argc, const char **argv)
{
    poptContext     opcon;
    int             c;

    opcon = poptGetContext(PROGRAM, argc, argv, opts, 0);

    while ((c = poptGetNextOpt(opcon)) != -1) {
        switch (c) {
        default:
            usage();
            exit(1);
        }
    }

    basis_name = poptGetArg(opcon);
    if (!basis_name) {
        usage();
        exit(1);
    }
}


static void
mutate_overwrite(FILE *in, FILE *out)
{
}


static void
mutate_insert(FILE *in, FILE *out)
{
}


static void
mutate_delete(FILE *in, FILE *out)
{
}


int main(int argc, char **argv)
{
    char out_name[FILENAME_MAX];
    FILE *in_file, *out_file;
    int             i;
    
    process_args(argc, (const char **) argv);

    in_file = fopen(basis_name, "rb");
    if (!in_file) {
        rs_log(RS_LOG_ERR, "error opening basis %s: %s",
               basis_name, strerror(errno));
        exit(2);
    }
    
    /* TODO: Open basis */
    for (i = 0; i < n_tests; i++) {
        /* Open output */
        snprintf(out_name, FILENAME_MAX, output_pattern, i);
        out_file = fopen(out_name, "wb+");
        if (!out_file) {
            rs_log(RS_LOG_ERR, "error opening output %s: %s",
                   out_name, strerror(errno));
            exit(2);
        }
        rs_log(RS_LOG_INFO | RS_LOG_NONAME, "write to %s", out_name);
        
        /* Choose and effect mutation */
        if (rand() & 1) {
            mutate_insert(in_file, out_file);
        } else if (rand() & 1) {
            mutate_overwrite(in_file, out_file);
        } else {
            mutate_delete(in_file, out_file);
        }
        
        /* Close previous input; use this as new input; rewind. */
        fclose(in_file);
        in_file = out_file;
        if (fseek(in_file, 0, SEEK_SET)) {
            rs_log(RS_LOG_ERR, "error rewinding input file: %s",
                   strerror(errno));
        }
    }
    
    return 0;
}
