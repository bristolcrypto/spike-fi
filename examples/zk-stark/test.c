#include "test.h"

#define TRANSCRIPT_SIZE 8
#define EXTENDED_LEN (TRANSCRIPT_SIZE * 2)
#define NUM_QUERIES (TRANSCRIPT_SIZE < 64 ? TRANSCRIPT_SIZE : 64)
const uint64_t FIELD_MODULUS = (1ULL << 61) - 1;
volatile uint64_t TRANSCRIPT[TRANSCRIPT_SIZE];

uint64_t modmul(uint64_t a, uint64_t b, uint64_t mod);

uint64_t modpow(uint64_t base, uint64_t exp, uint64_t mod) {
	uint64_t result = 1;
	base %= mod;
	while (exp > 0) {
		if (exp & 1)
			result = modmul(result, base, mod);
		exp >>= 1;
		base = modmul(base, base, mod);
	}
	return result;
}

uint64_t modmul(uint64_t a, uint64_t b, uint64_t mod) {
	uint64_t result = 0;
	a %= mod;
	while (b > 0) {
		if (b & 1) {
			result += a;
			if (result >= mod) result -= mod;
		}
		a <<= 1;
		if (a >= mod) a -= mod;
		b >>= 1;
	}
	return result;
}

uint64_t modinv(uint64_t a, uint64_t mod) {
	return modpow(a, mod - 2, mod);
}

void bit_reverse(uint64_t* a, size_t n) {
	for (size_t i = 1, j = 0; i < n; i++) {
		size_t bit = n >> 1;
		for (; j & bit; bit >>= 1)
			j ^= bit;
		j ^= bit;
		if (i < j) {
			uint64_t tmp = a[i];
			a[i] = a[j];
			a[j] = tmp;
		}
	}
}

void fft(uint64_t* a, size_t n, uint64_t root, uint64_t mod) {
	bit_reverse(a, n);
	for (size_t len = 2; len <= n; len *= 2) {
		uint64_t wlen = modpow(root, n / len, mod);
		for (size_t i = 0; i < n; i += len) {
			uint64_t w = 1;
			for (size_t j = 0; j < len / 2; j++) {
				uint64_t u = a[i + j];
				uint64_t v = modmul(a[i + j + len / 2], w, mod);
				a[i + j]           = (u + v) % mod;
				a[i + j + len / 2] = (u + mod - v) % mod;
				w = modmul(w, wlen, mod);
			}
		}
	}
}

void ifft(uint64_t* a, size_t n, uint64_t root, uint64_t mod) {
	uint64_t inv_root = modinv(root, mod);
	uint64_t inv_n    = modinv(n, mod);
	fft(a, n, inv_root, mod);
	for (size_t i = 0; i < n; i++)
		a[i] = modmul(a[i], inv_n, mod);
}

// tree is a flat array of 2*n digests (each SHA256_DIGEST_SIZE bytes).
// Leaves go at indices n..2n-1, internal nodes are built bottom-up, root at index 1.
void merkle_tree(uint8_t* tree, const uint8_t* leaf_hashes, size_t n) {
	for (size_t i = 0; i < n; i++)
		memcpy(tree + (n + i) * SHA256_DIGEST_SIZE, leaf_hashes + i * SHA256_DIGEST_SIZE, SHA256_DIGEST_SIZE);
	for (size_t i = n - 1; i >= 1; i--)
		sha256(tree + (2 * i) * SHA256_DIGEST_SIZE, 2 * SHA256_DIGEST_SIZE, tree + i * SHA256_DIGEST_SIZE);
}

uint8_t* get_merkle_root(uint8_t* tree) {
	return tree + SHA256_DIGEST_SIZE;
}

int main( int argc, char* argv[] ) {
	// Generate Fibonacci sequence transcript
	TRANSCRIPT[0] = 1;
	TRANSCRIPT[1] = 1;
	for (size_t i = 2; i < TRANSCRIPT_SIZE; i++)
		TRANSCRIPT[i] = TRANSCRIPT[i-1] + TRANSCRIPT[i-2];

	// Polynomial interpolation
	uint64_t root_of_unity = modpow(3, (FIELD_MODULUS - 1) / TRANSCRIPT_SIZE, FIELD_MODULUS);

	printf("transcript:\n");
	for (size_t i = 0; i < TRANSCRIPT_SIZE; i++)
		printf("  [%zu] = %lu\n", i, (unsigned long)TRANSCRIPT[i]);

	uint64_t coeffs[TRANSCRIPT_SIZE];
	for (size_t i = 0; i < TRANSCRIPT_SIZE; i++)
		coeffs[i] = TRANSCRIPT[i];
	ifft(coeffs, TRANSCRIPT_SIZE, root_of_unity, FIELD_MODULUS);

	printf("coeffs:\n");
	for (size_t i = 0; i < TRANSCRIPT_SIZE; i++)
		printf("  [%zu] = %lu\n", i, (unsigned long)coeffs[i]);

	// Evaluate on extended domain
	uint64_t extended_root = modpow(3, (FIELD_MODULUS - 1) / EXTENDED_LEN, FIELD_MODULUS);
	uint64_t evals[EXTENDED_LEN];
	for (size_t i = 0; i < TRANSCRIPT_SIZE; i++)
		evals[i] = coeffs[i];
	for (size_t i = TRANSCRIPT_SIZE; i < EXTENDED_LEN; i++)
		evals[i] = 0;
	fft(evals, EXTENDED_LEN, extended_root, FIELD_MODULUS);

	// Merkle commit
	uint8_t leaf_hashes[EXTENDED_LEN * SHA256_DIGEST_SIZE];
	for (size_t i = 0; i < EXTENDED_LEN; i++) {
		uint8_t bytes[32] = {0};
		for (int j = 0; j < 8; j++)
			bytes[j] = (uint8_t)(evals[i] >> (j * 8));
		sha256(bytes, 32, leaf_hashes + i * SHA256_DIGEST_SIZE);
	}
	uint8_t tree[2 * EXTENDED_LEN * SHA256_DIGEST_SIZE];
	merkle_tree(tree, leaf_hashes, EXTENDED_LEN);
	uint8_t* merkle_root = get_merkle_root(tree);

	printf("merkle root: ");
	for (int i = 0; i < SHA256_DIGEST_SIZE; i++)
		printf("%02x", merkle_root[i]);
	printf("\n");

	printf("evals:\n");
	for (size_t i = 0; i < EXTENDED_LEN; i++)
		printf("  [%zu] = %lu\n", i, (unsigned long)evals[i]);
}
