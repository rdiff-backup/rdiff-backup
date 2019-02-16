#include <stdio.h>
#include <rsync.h>

main()
{
  FILE *basis_file, *sig_file;
  char filename[50];
  rs_stats_t stats;
  rs_result result;
  long i;

  for(i=0; i<=100000; i++) {
	basis_file = fopen("a", "r");
	sig_file = fopen("sig", "w");
  
	result = rs_sig_file(basis_file, sig_file,
						 RS_DEFAULT_BLOCK_LEN, RS_DEFAULT_STRONG_LEN,
						 &stats);
	if (result != RS_DONE) exit(result);
	fclose(basis_file);
	fclose(sig_file);
  }
}
