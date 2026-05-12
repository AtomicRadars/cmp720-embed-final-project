#ifndef CONTEXT_AWARE_SCHEDULER_H
#define CONTEXT_AWARE_SCHEDULER_H

#include "FreeRTOS.h"
#include "task.h"
#include <stdint.h>

#include "core/IScheduler.h"

class ContextAwareScheduler : public IScheduler 
{
    public:
        ContextAwareScheduler(float alpha = 1.0f, float threshold = 0.15f, uint32_t safety_margin = 2);
        virtual ~ContextAwareScheduler() = default;

        void DelayUntil(TickType_t *pxPreviousWakeTime, TickType_t xTimeIncrement, ETaskID task_id) override;
        const char* GetSchedulerName() const override;

    private:
        void ApplyHeuristicAndUpdatePriorities();
        
        float m_alpha;
        float m_threshold;
        uint32_t m_safety_margin;
        ETaskID m_last_executed_task;
};

#endif // CONTEXT_AWARE_SCHEDULER_H
