#include "test.h"

int main( int argc, char* argv[] ) {
  int n = 10, t = 0, A[ 10 ] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 };

  for( int i = 0; i < n; i++ ) {
    t += A[ i ];
  }

  printf( "%d\n", t );

  return 0;
}
