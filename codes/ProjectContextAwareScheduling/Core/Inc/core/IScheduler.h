#ifndef ISCHEDULER_H
#define ISCHEDULER_H

#include "FreeRTOS.h"
#include "task.h"
#include "core/TaskConfig.h"

class IScheduler 
{
    public:
        virtual ~IScheduler() = default;
        virtual void Initialize();
        virtual void RegisterTask(ETaskID task_id, TaskHandle_t handle, uint32_t period, uint32_t wcet, float memory_intensity);
        virtual void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) = 0;
        
        virtual uint32_t GetTotalJobs(ETaskID task_id) const;
        virtual uint32_t GetMissedDeadlines(ETaskID task_id) const;
        virtual float GetDeadlineMissRatio(ETaskID task_id) const;
        virtual const char* GetSchedulerName() const = 0;

    protected:
        TaskStruct tasks[TASK_COUNT];
};

#endif // ISCHEDULER_H
