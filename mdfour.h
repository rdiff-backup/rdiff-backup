#ifndef _MDFOUR_H
#define _MDFOUR_H

struct mdfour {
	uint32_t A, B, C, D;
	uint32_t totalN;
};

void mdfour(unsigned char *out, unsigned char const *in, int n);
void mdfour_begin(struct mdfour *md);
void mdfour_update(struct mdfour *md, unsigned char const *in, int n);
void mdfour_result(struct mdfour *md, unsigned char *out);

#endif
