#include "app_main.h"
#include "main.h" // Gives you access to HAL functions and auto-generated pins
#include <cstring>

#include "core/TaskConfig.h"

void ClearConsole();

// Tell the compiler to look for this variable in the auto-generated C files
extern UART_HandleTypeDef huart2;

void app_main(void) {
	// Initialization code goes here
	ClearConsole();

	auto* pTaskConfig = new TaskConfig();

	// 1. Initialize hardware profiling (ARM DWT counter)
	pTaskConfig->DWT_Init();

	const char* cpMsg = "ERROR! Tasks cannot be created, exiting...\r\n";
	// 2. Register the mixed-criticality workload with the RTOS
	if (!pTaskConfig->CreateTasks())
	{
		HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);
		return;
	}
	
	cpMsg = "Tasks created successfully!\r\n";
	HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);

	const char* cpMsg2 = "Hello UART!\r\n";
	HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg2, static_cast<uint16_t>(std::strlen(cpMsg2)), HAL_MAX_DELAY);

}

void ClearConsole()
{
	const char* cpClearConsole = "\033[2J\033[H";
	HAL_UART_Transmit(&huart2, (uint8_t*)cpClearConsole, static_cast<uint16_t>(std::strlen(cpClearConsole)), HAL_MAX_DELAY);
}
