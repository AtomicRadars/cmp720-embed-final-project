#ifndef EDF_SCHEDULER_H
#define EDF_SCHEDULER_H

#include "FreeRTOS.h"
#include "task.h"
#include <stdint.h>

#include "core/IScheduler.h"

class EDFScheduler : public IScheduler 
{
    public:
        EDFScheduler() = default;
        virtual ~EDFScheduler() = default;

        virtual void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) override;
        const char* GetSchedulerName() const override;

    private:
        void UpdatePriorities();
};

#endif // EDF_SCHEDULER_H
