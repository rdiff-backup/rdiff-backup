/* -*- mode: c; c-file-style: "bsd" -*- */

void            comp_init(void);
ssize_t         comp_write(ssize_t(*fn) (void *, char const *, size_t),
			   void *private, char const *buf, size_t len);
void            comp_flush(ssize_t(*fn) (void *, char const *, size_t),

			   void *private);
void            decomp_init(void);
ssize_t         decomp_read(ssize_t(*fn) (void *, char *, size_t),
			    void *private, char *buf, size_t len);
ssize_t         decomp_finish(ssize_t(*fn) (void *, char *, size_t),

			      void *private);
