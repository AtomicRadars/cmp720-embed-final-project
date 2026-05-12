#ifndef NATIVE_SCHEDULER_H
#define NATIVE_SCHEDULER_H

#include "FreeRTOS.h"
#include "task.h"
#include <stdint.h>

#include "core/IScheduler.h"

class NativeScheduler : public IScheduler 
{
    public:
        NativeScheduler() = default;
        virtual ~NativeScheduler() = default;

        void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) override;
        const char* GetSchedulerName() const override;
};

#endif // NATIVE_SCHEDULER_H
