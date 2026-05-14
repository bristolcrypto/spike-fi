#include "test.h"

const uint64_t TRANSCRIPT_SIZE = 8; // power of 2
const uint64_t NUM_QUERIES;
const uint64_t FIELD_MODULUS = (1 << 61) - 1;
volatile uint64_t TRANSCRIPT[TRANSCRIPT_SIZE] = {1, 1, 2, 3, 5, 8, 13, 21};

// TODO: is there a way to use a macro to specify the fault insertion? I.e.
// printf the spec required?

int main( int argc, char* argv[] ) {
	// Polynomial interpolation
	uint64_t domain[TRANSCRIPT_SIZE] = {0, 1, 2, 3, 4, 5, 6, 7};
}
