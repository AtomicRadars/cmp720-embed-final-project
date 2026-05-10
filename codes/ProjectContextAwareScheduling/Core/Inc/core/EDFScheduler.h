#ifndef EDF_SCHEDULER_H
#define EDF_SCHEDULER_H

#include "FreeRTOS.h"
#include "task.h"
#include <stdint.h>

#include "core/TaskConfig.h"

class EDFScheduler 
{
    public:
        static void Initialize();
        static void RegisterTask(ETaskID task_id, TaskHandle_t handle, uint32_t period);
        static void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id);

    private:
        static void UpdatePriorities();
        static TaskStruct tasks[TASK_COUNT];
};

#endif // EDF_SCHEDULER_H
