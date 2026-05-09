#ifndef APP_MAIN_H
#define APP_MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

// This functions will be called from main.c
void ClearConsole();

void TaskInit(void);

#ifdef __cplusplus
}
#endif

#endif // APP_MAIN_H