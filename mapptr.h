/* ========================================

   map_ptr IO */

typedef struct hs_map hs_map_t;

hs_map_t       *_hs_map_file(int fd);

/*@null@*/ char const     *_hs_map_ptr(hs_map_t *, hs_off_t, ssize_t *len, int *reached_eof);

void            _hs_unmap_file(/*@only@*/ hs_map_t * map);

int             hs_file_open(char const *filename, int mode);
