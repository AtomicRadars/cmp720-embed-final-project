#include "app_main.h"
#include "main.h" // Gives you access to HAL functions and auto-generated pins
#include <cstring>
#include <cstdio>

#include "core/TaskConfig.h"
#include "core/EDFScheduler.h"
#include "core/NativeScheduler.h"
#include "core/ContextAwareScheduler.h"

void ClearConsole();

// Tell the compiler to look for this variable in the auto-generated C files
extern UART_HandleTypeDef huart2;

void TaskInit(void) 
{
	// Initialization code goes here
    IScheduler* pActiveScheduler = new EDFScheduler();
    // IScheduler* pActiveScheduler = new NativeScheduler();
    //IScheduler* pActiveScheduler = new ContextAwareScheduler(1.0f, 0.15f, 2);
	auto* pTaskConfig = new TaskConfig(pActiveScheduler);

	// 1. Initialize hardware profiling (ARM DWT counter)
	pTaskConfig->DWT_Init();

	// 2. Register the mixed-criticality workload with the RTOS
	if (pTaskConfig->CreateTasks())
	{
		char msg[128];
		snprintf(msg, sizeof(msg), "Tasks created successfully. Activating [%s]...\r\n\r\n", pActiveScheduler->GetSchedulerName());
		HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);
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
