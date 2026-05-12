#include "core/IScheduler.h"

void IScheduler::Initialize() 
{
    for (int i = 0; i < TASK_COUNT; ++i) 
    {
        tasks[i].is_registered = false;
    }
}

void IScheduler::RegisterTask(ETaskID task_id, TaskHandle_t handle, uint32_t period, uint32_t wcet, float memory_intensity) 
{
    if (task_id < TASK_COUNT) 
    {
        tasks[task_id].handle = handle;
        tasks[task_id].period = period;
        tasks[task_id].deadline = period;
        tasks[task_id].wcet = wcet;
        tasks[task_id].memory_intensity = memory_intensity;
        tasks[task_id].next_wake_time = 0;
        tasks[task_id].is_registered = true;
        tasks[task_id].total_jobs = 0;
        tasks[task_id].missed_deadlines = 0;
    }
}

uint32_t IScheduler::GetTotalJobs(ETaskID task_id) const
{
    if ((task_id < TASK_COUNT) && (tasks[task_id].is_registered)) 
    {
        return tasks[task_id].total_jobs;
    }
    return 0;
}

uint32_t IScheduler::GetMissedDeadlines(ETaskID task_id) const
{
    if ((task_id < TASK_COUNT) && (tasks[task_id].is_registered)) 
    {
        return tasks[task_id].missed_deadlines;
    }
    return 0;
}

float IScheduler::GetDeadlineMissRatio(ETaskID task_id) const
{
    if ((task_id < TASK_COUNT) && (tasks[task_id].is_registered) && (tasks[task_id].total_jobs > 0)) 
    {
        return static_cast<float>(tasks[task_id].missed_deadlines) / static_cast<float>(tasks[task_id].total_jobs);
    }
    return 0.0f;
}
