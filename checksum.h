/* ========================================

   Things to do with searching through the hashtable of blocks from
   downstream.  */

int             _hs_find_in_hash(rollsum_t * rollsum,
				 char const *inbuf, int block_len,
				 hs_sum_set_t const *sigs, hs_stats_t *);

int             _hs_build_hash_table(hs_sum_set_t *sums);

/*@null@*/ hs_sum_set_t *_hs_read_sum_set(hs_read_fn_t, void *, int block_len);
void            _hs_free_sum_struct(/*@only@*/ hs_sum_set_t *);

