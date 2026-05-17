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
        virtual float GetLastExecutedMemoryIntensity() const;
        virtual const char* GetSchedulerName() const = 0;
        
        virtual float GetTaskJitter(ETaskID task_id) const;
        virtual uint32_t GetTotalContentionPenalty() const;
        virtual uint32_t GetAverageOverheadCycles() const;

    protected:
        TaskStruct tasks[TASK_COUNT];
        ETaskID m_last_executed_task{eMotorControl};
        
        // Jitter tracking per task (Welford's algorithm)
        uint32_t m_jitter_count[TASK_COUNT]{0};
        float m_jitter_mean[TASK_COUNT]{0.0f};
        float m_jitter_m2[TASK_COUNT]{0.0f};
        
        // Total cache contention penalty (ms)
        uint32_t m_total_contention_penalty_ms{0};
        
        // Scheduler decision overhead (cycles)
        uint32_t m_total_overhead_cycles{0};
        uint32_t m_overhead_call_count{0};
};

#endif // ISCHEDULER_H
