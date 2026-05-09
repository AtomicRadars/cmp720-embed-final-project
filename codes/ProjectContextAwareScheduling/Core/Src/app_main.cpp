#include "app_main.h"
#include "main.h" // Gives you access to HAL functions and auto-generated pins
#include <cstring>

#include "core/TaskConfig.h"

void ClearConsole();

// Tell the compiler to look for this variable in the auto-generated C files
extern UART_HandleTypeDef huart2;

void TaskInit(void) {
	// Initialization code goes here
	auto* pTaskConfig = new TaskConfig();

	// 1. Initialize hardware profiling (ARM DWT counter)
	pTaskConfig->DWT_Init();

	// 2. Register the mixed-criticality workload with the RTOS
	if (pTaskConfig->CreateTasks())
	{
		const char* cpMsg = "Tasks created successfully. Activating scheduler...\r\n\r\n";
		HAL_UART_Transmit(&huart2, (uint8_t*)cpMsg, static_cast<uint16_t>(std::strlen(cpMsg)), HAL_MAX_DELAY);
	}
	else 
	{
		const char* cpErrMsg = "ERROR! Tasks cannot be created! System halted.\r\n";
		HAL_UART_Transmit(&huart2, (uint8_t*)cpErrMsg, static_cast<uint16_t>(std::strlen(cpErrMsg)), HAL_MAX_DELAY);

		while(1) 
		{
            // Infinite loop prevents the scheduler from starting with missing tasks
        }
	}
}

void ClearConsole()
{
	const char* cpClearConsole = "\033[2J\033[H";
	HAL_UART_Transmit(&huart2, (uint8_t*)cpClearConsole, static_cast<uint16_t>(std::strlen(cpClearConsole)), HAL_MAX_DELAY);
}
