#ifndef ISCHEDULER_H
#define ISCHEDULER_H

#include "FreeRTOS.h"
#include "task.h"
#include "core/TaskConfig.h"

class IScheduler 
{
    public:
        virtual ~IScheduler() = default;
        virtual void Initialize() = 0;
        virtual void RegisterTask(ETaskID task_id, TaskHandle_t handle, uint32_t period) = 0;
        virtual void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) = 0;
};

#endif // ISCHEDULER_H
