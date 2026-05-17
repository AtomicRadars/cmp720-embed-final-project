cmake_minimum_required(VERSION 3.22)

#
# This file is generated only once,
# and is not re-generated if converter is called multiple times.
#
# User is free to modify the file as much as necessary
#

# Setup compiler settings
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)


# Define the build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Release")
endif()

# Set the project name
set(CMAKE_PROJECT_NAME ProjectContextAwareScheduling)

# Set the default STM32 toolchain if no toolchain file was supplied
if(NOT CMAKE_TOOLCHAIN_FILE)
    set(CMAKE_TOOLCHAIN_FILE "${CMAKE_SOURCE_DIR}/cmake/gcc-arm-none-eabi.cmake" CACHE FILEPATH "STM32 toolchain file")
endif()

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME} LANGUAGES C CXX ASM)
message("Build type: " ${CMAKE_BUILD_TYPE})

# Enable CMake support for ASM, C and C++ languages
# (project() already enables the requested languages)

# Create an executable object type
add_executable(${CMAKE_PROJECT_NAME})

# Add STM32CubeMX generated sources
add_subdirectory(cmake/stm32cubemx)

# Link directories setup
target_link_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined library search paths
)

# Add sources to executable
target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user sources here
    Core/Src/app_main.cpp
    Core/Src/core/TaskConfig.cpp
    Core/Src/core/IScheduler.cpp
    Core/Src/core/EDFScheduler.cpp
    Core/Src/core/NativeScheduler.cpp
    Core/Src/core/ContextAwareScheduler.cpp
    Core/Src/test/SchedulerTest.cpp
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined include paths
    Core/Inc
    Core/Inc/core
)

# Add project symbols (macros)
if(ACTIVE_SCHEDULER STREQUAL "NATIVE")
    target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE SCHEDULER_NATIVE)
elseif(ACTIVE_SCHEDULER STREQUAL "EDF")
    target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE SCHEDULER_EDF)
elseif(ACTIVE_SCHEDULER STREQUAL "CONTEXT_AWARE")
    target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE SCHEDULER_CONTEXT_AWARE)
else()
    # Default to Context Aware if not specified via command line
    target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE SCHEDULER_CONTEXT_AWARE)
endif()

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx

    # Add user defined libraries
)

# Enable float support for printf/snprintf
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE "-u" "_printf_float")
