/* ========================================

   Net IO functions */

int             _hs_read_loop(hs_read_fn_t, void *readprivate,
			      char *buf, size_t len);

size_t             _hs_write_loop(hs_write_fn_t, void *writeprivate,
			       char const *buf, size_t len);

int             hs_must_write(hs_write_fn_t write_fn, void *write_priv,
			      void const *buf, int len);
\
int             _hs_must_read(hs_read_fn_t, void *, char *, ssize_t);

int             _hs_read_netint(hs_read_fn_t read_fn, void *read_priv,
				/*@out@*/ uint32_t * result);

int             _hs_read_netshort(hs_read_fn_t read_fn, void *read_priv,
				  /*@out@*/ uint16_t * result);


int             _hs_read_netbyte(hs_read_fn_t read_fn, void *read_priv,
				 /*@out@*/ uint8_t * result);

int             _hs_write_netint(hs_write_fn_t write_fn, void *write_priv,
				 uint32_t out);

int             _hs_write_netshort(hs_write_fn_t write_fn, void *write_priv,
				   uint16_t out);

int             _hs_write_netbyte(hs_write_fn_t write_fn, void *write_priv,
				  uint8_t out);

int             _hs_write_netvar(hs_write_fn_t write_fn, void *write_priv,
				 uint32_t value, int type);
