#ifndef TASK_INITS_H
#define TASK_INITS_H

#include <cstddef>
#include <cstdint>

// Target constraint: Use a large contiguous buffer (4-10 KB) allocated 
// statically to avoid runtime dynamic allocation [3, 4].
constexpr size_t CRYPTO_BUFFER_SIZE = 8192; 
static uint8_t crypto_buffer[CRYPTO_BUFFER_SIZE];

#endif // TASK_INITS_H