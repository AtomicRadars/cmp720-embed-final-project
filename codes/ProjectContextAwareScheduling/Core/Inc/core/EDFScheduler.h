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

        void Initialize() override;
        void RegisterTask(ETaskID task_id, TaskHandle_t handle, uint32_t period) override;
        void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) override;

        uint32_t GetTotalJobs(ETaskID task_id) const override;
        uint32_t GetMissedDeadlines(ETaskID task_id) const override;
        float GetDeadlineMissRatio(ETaskID task_id) const override;

    private:
        void UpdatePriorities();
        TaskStruct tasks[TASK_COUNT];
};

#endif // EDF_SCHEDULER_H
