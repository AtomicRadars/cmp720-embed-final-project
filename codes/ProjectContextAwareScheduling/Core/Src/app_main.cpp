#include "app_main.h"
#include "main.h" // Gives you access to HAL functions and auto-generated pins
#include <cstring>

// Tell the compiler to look for this variable in the auto-generated C files
extern UART_HandleTypeDef huart2;

void app_main(void) {
	// Initialization code goes here
	
	const char *msg = "Hello UART!\r\n";

	// Your main loop (replaces the while(1) in main.c)
	while(1) {
		HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
		HAL_Delay(1000);
	}
}