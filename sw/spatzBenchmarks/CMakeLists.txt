# Copyright 2020 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.13)

# Defines
set(SNRT_NFPU_PER_CORE "0" CACHE STRING "Number of FPUs per Spatz")

# Allow spatzBenchmarks to be built as a standalone library.
if (CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/../cmake)
    set(CMAKE_TOOLCHAIN_FILE toolchain-gcc CACHE STRING "Toolchain to use")

    project(Benchmarks LANGUAGES C ASM)
    include(SnitchUtilities)

    # Build the runtime.
    add_subdirectory(../snRuntime snRuntime)
endif()

include_directories(include)
include_directories(${SNRUNTIME_INCLUDE_DIRS})

add_compile_options(-O3 -g -ffunction-sections)


# Macro to regenerate the golden values and compile a module
macro(add_spatz_test_oneParam name file param1)
  set(target_name ${name}_M${param1})
  add_snitch_test(${target_name} ${file})
  target_link_libraries(test-${SNITCH_TEST_PREFIX}${target_name} benchmark ${SNITCH_RUNTIME})
  target_compile_definitions(test-${SNITCH_TEST_PREFIX}${target_name} PUBLIC DATAHEADER="data/data_${param1}.h" SNRT_NFPU_PER_CORE=${SNRT_NFPU_PER_CORE})
endmacro()

macro(add_spatz_test_oneParam_with_data name file data_dir param1)
  set(target_name ${name}_M${param1})
  add_snitch_test(${target_name} ${file})
  target_link_libraries(test-${SNITCH_TEST_PREFIX}${target_name} benchmark ${SNITCH_RUNTIME})
  target_compile_definitions(test-${SNITCH_TEST_PREFIX}${target_name} PUBLIC DATAHEADER="${data_dir}/data_${param1}.h" SNRT_NFPU_PER_CORE=${SNRT_NFPU_PER_CORE})
endmacro()

macro(add_spatz_test_twoParam name file param1 param2)
  set(target_name ${name}_M${param1}_N${param2})
  add_snitch_test(${target_name} ${file})
  target_link_libraries(test-${SNITCH_TEST_PREFIX}${target_name} benchmark ${SNITCH_RUNTIME})
  target_compile_definitions(test-${SNITCH_TEST_PREFIX}${target_name} PUBLIC DATAHEADER="data/data_${param1}_${param2}.h" SNRT_NFPU_PER_CORE=${SNRT_NFPU_PER_CORE})
endmacro()

macro(add_spatz_test_threeParam name file param1 param2 param3)
  set(target_name ${name}_M${param1}_N${param2}_K${param3})
  add_snitch_test(${target_name} ${file})
  target_link_libraries(test-${SNITCH_TEST_PREFIX}${target_name} benchmark ${SNITCH_RUNTIME})
  target_compile_definitions(test-${SNITCH_TEST_PREFIX}${target_name} PUBLIC DATAHEADER="data/data_${param1}_${param2}_${param3}.h" SNRT_NFPU_PER_CORE=${SNRT_NFPU_PER_CORE})
endmacro()

macro(add_spatz_test_threeParam_with_data name file data_dir param1 param2 param3)
  set(target_name ${name}_M${param1}_N${param2}_K${param3})
  add_snitch_test(${target_name} ${file})
  target_link_libraries(test-${SNITCH_TEST_PREFIX}${target_name} benchmark ${SNITCH_RUNTIME})
  target_compile_definitions(test-${SNITCH_TEST_PREFIX}${target_name} PUBLIC DATAHEADER="${data_dir}/data_${param1}_${param2}_${param3}.h" SNRT_NFPU_PER_CORE=${SNRT_NFPU_PER_CORE})
endmacro()

# Benchmark library
add_library(benchmark benchmark/benchmark.c)

# Kernels
add_library(dp-fmatmul dp-fmatmul/kernel/dp-fmatmul.c)
add_library(sp-fmatmul sp-fmatmul/kernel/sp-fmatmul.c)
add_library(hp-fmatmul hp-fmatmul/kernel/hp-fmatmul.c)

add_library(widening-hp-fmatmul widening-hp-fmatmul/kernel/widening-fmatmul.c)
add_library(widening-bp-fmatmul widening-bp-fmatmul/kernel/widening-fmatmul.c)

add_library(sdotp-hp-fmatmul sdotp-hp-fmatmul/kernel/sdotp-fmatmul.c)
add_library(sdotp-bp-fmatmul sdotp-bp-fmatmul/kernel/sdotp-fmatmul.c)

add_library(dp-faxpy dp-faxpy/kernel/faxpy.c)

add_library(dp-fdotp dp-fdotp/kernel/fdotp.c)

add_library(dp-fconv2d dp-fconv2d/kernel/fconv2d.c)

add_library(dp-fft dp-fft/kernel/fft.c)
add_library(sp-fft sp-fft/kernel/fft.c)

# Tests
enable_testing()
set(SNITCH_TEST_PREFIX spatzBenchmarks-)

set(ONLINE_MERGE_N "1" CACHE STRING
    "Online merge experiment row count")
set(ONLINE_MERGE_D "1" CACHE STRING
    "Online merge experiment vector dimension")
set(ONLINE_MERGE_SEED "1" CACHE STRING
    "Online merge experiment input seed")
set(ONLINE_MERGE_CASE_KIND "main" CACHE STRING
    "Online merge experiment input class")
set(ONLINE_MERGE_REPEATS "5" CACHE STRING
    "Online merge measured repetitions after one warm-up")
set(ONLINE_MERGE_TRACE_PROXY "0" CACHE STRING
    "Gate trace markers to B2-R/B3 repeat zero")
if(NOT PYTHON)
  find_program(PYTHON python3 REQUIRED)
endif()
string(CONCAT ONLINE_MERGE_CASE_SLUG
    "N${ONLINE_MERGE_N}_D${ONLINE_MERGE_D}_S${ONLINE_MERGE_SEED}"
    "_${ONLINE_MERGE_CASE_KIND}_R${ONLINE_MERGE_REPEATS}")
string(CONCAT ONLINE_MERGE_GENERATED_DIR
    "${CMAKE_CURRENT_BINARY_DIR}/online_merge_generated/"
    "${ONLINE_MERGE_CASE_SLUG}")
set(ONLINE_MERGE_CASE_HEADER
    "${ONLINE_MERGE_GENERATED_DIR}/online_merge_case_data.h")
add_custom_command(
  OUTPUT "${ONLINE_MERGE_CASE_HEADER}"
  COMMAND "${PYTHON}"
          "${CMAKE_CURRENT_SOURCE_DIR}/online-softmax-merge/generate_case.py"
          --n ${ONLINE_MERGE_N}
          --d ${ONLINE_MERGE_D}
          --seed ${ONLINE_MERGE_SEED}
          --case-kind ${ONLINE_MERGE_CASE_KIND}
          --repeats ${ONLINE_MERGE_REPEATS}
          --output "${ONLINE_MERGE_CASE_HEADER}"
  DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/online-softmax-merge/generate_case.py"
  VERBATIM)
set_source_files_properties("${ONLINE_MERGE_CASE_HEADER}"
    PROPERTIES GENERATED TRUE)
add_snitch_test(online-softmax-merge
    online-softmax-merge/main.c
    online-softmax-merge/rtl_reference.c
    online-softmax-merge/rvv_update.c
    ${ONLINE_MERGE_CASE_HEADER})
target_include_directories(
    test-${SNITCH_TEST_PREFIX}online-softmax-merge
    PRIVATE ${ONLINE_MERGE_GENERATED_DIR}
            ${CMAKE_CURRENT_SOURCE_DIR}/online-softmax-merge)
target_compile_definitions(
    test-${SNITCH_TEST_PREFIX}online-softmax-merge
    PRIVATE ONLINE_MERGE_TRACE_PROXY=${ONLINE_MERGE_TRACE_PROXY})
target_link_libraries(test-${SNITCH_TEST_PREFIX}online-softmax-merge
    benchmark ${SNITCH_RUNTIME})

add_snitch_test(online-softmax-merge-concurrency
    online-softmax-merge/concurrency.c
    online-softmax-merge/concurrency_workloads.S
    ${ONLINE_MERGE_CASE_HEADER})
target_include_directories(
    test-${SNITCH_TEST_PREFIX}online-softmax-merge-concurrency
    PRIVATE ${ONLINE_MERGE_GENERATED_DIR}
            ${CMAKE_CURRENT_SOURCE_DIR}/online-softmax-merge)
target_link_libraries(
    test-${SNITCH_TEST_PREFIX}online-softmax-merge-concurrency
    benchmark ${SNITCH_RUNTIME})

add_snitch_test(attnres-baselines attnres-baselines/main.c)
target_link_libraries(test-${SNITCH_TEST_PREFIX}attnres-baselines benchmark ${SNITCH_RUNTIME})

add_spatz_test_threeParam(dp-fmatmul dp-fmatmul/main.c 64  64  64 )
add_spatz_test_threeParam(dp-fmatmul dp-fmatmul/main.c 64  128 64 )
add_spatz_test_threeParam(dp-fmatmul dp-fmatmul/main.c 128 128 128)

add_spatz_test_threeParam(sp-fmatmul sp-fmatmul/main.c 64  64  64 )
add_spatz_test_threeParam(sp-fmatmul sp-fmatmul/main.c 64  128 64 )

add_spatz_test_threeParam(hp-fmatmul hp-fmatmul/main.c 64  64  64 )
add_spatz_test_threeParam(hp-fmatmul hp-fmatmul/main.c 64  128 64 )
add_spatz_test_threeParam(hp-fmatmul hp-fmatmul/main.c 128 128 128)

add_spatz_test_threeParam(widening-hp-fmatmul widening-hp-fmatmul/main.c 64  64  64 )
add_spatz_test_threeParam(widening-hp-fmatmul widening-hp-fmatmul/main.c 64  128 64 )
add_spatz_test_threeParam(widening-hp-fmatmul widening-hp-fmatmul/main.c 128 128 128)

add_spatz_test_threeParam(widening-bp-fmatmul widening-bp-fmatmul/main.c 64  64  64 )
add_spatz_test_threeParam(widening-bp-fmatmul widening-bp-fmatmul/main.c 64  128 64 )
add_spatz_test_threeParam(widening-bp-fmatmul widening-bp-fmatmul/main.c 128 128 128)
add_spatz_test_threeParam(widening-bp-fmatmul widening-bp-fmatmul/main.c 128 256 128)

add_spatz_test_threeParam(sdotp-hp-fmatmul sdotp-hp-fmatmul/main.c 64  64  64 )
add_spatz_test_threeParam(sdotp-hp-fmatmul sdotp-hp-fmatmul/main.c 64  128 64 )
add_spatz_test_threeParam(sdotp-hp-fmatmul sdotp-hp-fmatmul/main.c 128 128 128)

add_spatz_test_threeParam(sdotp-bp-fmatmul sdotp-bp-fmatmul/main.c 64  64  64 )
add_spatz_test_threeParam(sdotp-bp-fmatmul sdotp-bp-fmatmul/main.c 64  128 64 )
add_spatz_test_threeParam(sdotp-bp-fmatmul sdotp-bp-fmatmul/main.c 128 128 128)
add_spatz_test_threeParam(sdotp-bp-fmatmul sdotp-bp-fmatmul/main.c 128 256 128)

add_spatz_test_oneParam(dp-faxpy dp-faxpy/main.c 256)
add_spatz_test_oneParam(dp-faxpy dp-faxpy/main.c 1024)

add_spatz_test_oneParam(dp-fdotp dp-fdotp/main.c 128)
add_spatz_test_oneParam(dp-fdotp dp-fdotp/main.c 1024)
add_spatz_test_oneParam(dp-fdotp dp-fdotp/main.c 2048)

add_spatz_test_threeParam(dp-fconv2d dp-fconv2d/main.c 32 32 7)
add_spatz_test_threeParam(dp-fconv2d dp-fconv2d/main.c 64 64 7)

add_spatz_test_twoParam(dp-fft dp-fft/main.c 128 2)

add_spatz_test_twoParam(sp-fft sp-fft/main.c 256 2)
add_spatz_test_twoParam(sp-fft sp-fft/main.c 512 2)


# for complex number tests (f->c)

add_spatz_test_oneParam(dp-caxpy dp-caxpy/main.c 256)
add_spatz_test_oneParam(dp-caxpy dp-caxpy/main.c 1024)

add_spatz_test_oneParam(dp-cdotp dp-cdotp/main.c 128)
add_spatz_test_oneParam(dp-cdotp dp-cdotp/main.c 4096)
add_spatz_test_oneParam_with_data(dp-cdotp_ver2 dp-cdotp_ver2/main.c ../dp-cdotp/data 128)
add_spatz_test_oneParam_with_data(dp-cdotp_ver2 dp-cdotp_ver2/main.c ../dp-cdotp/data 1024)
add_spatz_test_oneParam_with_data(dp-cdotp_ver2 dp-cdotp_ver2/main.c ../dp-cdotp/data 2048)

add_spatz_test_oneParam_with_data(dp-fdotp_aligned dp-fdotp_aligned/main.c ../dp-fdotp/data 128)
add_spatz_test_oneParam_with_data(dp-fdotp_aligned dp-fdotp_aligned/main.c ../dp-fdotp/data 1024)
add_spatz_test_oneParam_with_data(dp-fdotp_aligned dp-fdotp_aligned/main.c ../dp-fdotp/data 2048)

add_spatz_test_oneParam_with_data(dp-cdotp_aligned dp-cdotp_aligned/main.c ../dp-cdotp/data 128)
add_spatz_test_oneParam_with_data(dp-cdotp_aligned dp-cdotp_aligned/main.c ../dp-cdotp/data 1024)
add_spatz_test_oneParam_with_data(dp-cdotp_aligned dp-cdotp_aligned/main.c ../dp-cdotp/data 2048)
add_spatz_test_threeParam(dp-cmatmul dp-cmatmul/main.c 64 64 64)
add_spatz_test_threeParam(dp-cmatmul dp-cmatmul/main.c 64 128 64)
add_spatz_test_threeParam(dp-cmatmul dp-cmatmul/main.c 128 128 128)
add_spatz_test_threeParam_with_data(dp-cmatmul_ver2 dp-cmatmul_ver2/main.c ../dp-cmatmul/data 64 64 64)
add_spatz_test_threeParam_with_data(dp-cmatmul_ver2 dp-cmatmul_ver2/main.c ../dp-cmatmul/data 64 128 64)
add_spatz_test_threeParam_with_data(dp-cmatmul_ver2 dp-cmatmul_ver2/main.c ../dp-cmatmul/data 128 128 128)
