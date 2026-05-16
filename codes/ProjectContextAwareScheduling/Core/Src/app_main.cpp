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
#if defined(SCHEDULER_NATIVE)
    IScheduler* pActiveScheduler = new NativeScheduler();
#elif defined(SCHEDULER_EDF)
    IScheduler* pActiveScheduler = new EDFScheduler();
#elif defined(SCHEDULER_CONTEXT_AWARE)
    IScheduler* pActiveScheduler = new ContextAwareScheduler(ALPHA, MEMORY_INTENSITY_THRESHOLD, SAFETY_MARGIN_MS);
#else
    #error "No scheduler type defined! Please define SCHEDULER_NATIVE, SCHEDULER_EDF, or SCHEDULER_CONTEXT_AWARE."
#endif
	
	auto* pTaskConfig = new TaskConfig(pActiveScheduler);

	// 1. Initialize hardware profiling (ARM DWT counter)
	pTaskConfig->DWT_Init();

	// 2. Register the mixed-criticality workload with the RTOS
	if (pTaskConfig->CreateTasks())
	{
		char msg[512];
		snprintf(msg, sizeof(msg), 
			"--- System Configuration ---\r\n"
			"T1 (Motor):  Prio: %lu, Period: %lu ms, MemIntensity: %.2f\r\n"
			"T2 (Sensor): Prio: %lu, Period: %lu ms, MemIntensity: %.2f\r\n"
			"T3 (Crypto): Prio: %lu, Period: %lu ms, MemIntensity: %.2f\r\n"
			"T4 (Vision): Prio: %lu, Period: %lu ms, MemIntensity: %.2f\r\n"
			"Alpha: %.2f, Safety Margin: %lu ms, Threshold: %.2f\r\n"
			"---------------------------\r\n\r\n",
			TASK1_PRIORITY, TASK1_PERIOD_MS, TASK1_MEMORY_INTENSITY,
			TASK2_PRIORITY, TASK2_PERIOD_MS, TASK2_MEMORY_INTENSITY,
			TASK3_PRIORITY, TASK3_PERIOD_MS, TASK3_MEMORY_INTENSITY,
			TASK4_PRIORITY, TASK4_PERIOD_MS, TASK4_MEMORY_INTENSITY,
			ALPHA, SAFETY_MARGIN_MS, MEMORY_INTENSITY_THRESHOLD
		);
		HAL_UART_Transmit(&huart2, (uint8_t*)msg, static_cast<uint16_t>(std::strlen(msg)), HAL_MAX_DELAY);

		snprintf(msg, sizeof(msg), "Tasks created successfully. Activating [%s]...\r\n", pActiveScheduler->GetSchedulerName());
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
