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

macro(add_spatz_test_oneParam_cfma name file param1 use_vfcmacc)
  set(target_name ${name}_M${param1})
  add_snitch_test(${target_name} ${file})
  target_link_libraries(test-${SNITCH_TEST_PREFIX}${target_name} benchmark ${SNITCH_RUNTIME})
  target_compile_definitions(test-${SNITCH_TEST_PREFIX}${target_name} PUBLIC DATAHEADER="data/data_${param1}.h" SNRT_NFPU_PER_CORE=${SNRT_NFPU_PER_CORE} SPATZ_USE_VFCMACC=${use_vfcmacc} __SNRT_USE_PRINT)
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
add_spatz_test_oneParam(dp-caxpy dp-caxpy/main.c 4096)

# dp-caxpy with vfcmacc instruction
add_spatz_test_oneParam(dp-caxpy_vfcmacc dp-caxpy/main.c 256)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-caxpy_vfcmacc_M256 PUBLIC SPATZ_USE_VFCMACC=1)
add_spatz_test_oneParam(dp-caxpy_vfcmacc dp-caxpy/main.c 1024)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-caxpy_vfcmacc_M1024 PUBLIC SPATZ_USE_VFCMACC=1)
add_spatz_test_oneParam(dp-caxpy_vfcmacc dp-caxpy/main.c 4096)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-caxpy_vfcmacc_M4096 PUBLIC SPATZ_USE_VFCMACC=1)

add_spatz_test_oneParam(dp-cdotp dp-cdotp/main.c 128)
add_spatz_test_oneParam(dp-cdotp dp-cdotp/main.c 4096)
add_spatz_test_oneParam_cfma(dp-cdotp_old dp-cdotp/main.c 128 0)
add_spatz_test_oneParam_cfma(dp-cdotp_vfcmacc dp-cdotp/main.c 128 1)
add_spatz_test_oneParam_cfma(dp-cdotp_old dp-cdotp/main.c 1024 0)
add_spatz_test_oneParam_cfma(dp-cdotp_vfcmacc dp-cdotp/main.c 1024 1)
add_spatz_test_oneParam_cfma(dp-cdotp_scalar dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_scalar_M128 PUBLIC SPATZ_CDOTP_SCALAR_DIAG=1)
target_compile_options(test-${SNITCH_TEST_PREFIX}dp-cdotp_scalar_M128 PUBLIC -ffp-contract=off)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_load dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_load_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=1 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_mac dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_mac_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=2 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_reduce_real dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_reduce_real_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=3 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_reduce_imag dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_reduce_imag_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=4 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_reduce_both dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_reduce_both_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=5 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_reduce_noextract dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_reduce_noextract_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=6 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_extract_drop dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_extract_drop_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=7 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_extract_nocollect dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_extract_nocollect_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=7 SPATZ_CDOTP_SKIP_VERIFY=1 SPATZ_CDOTP_SKIP_COLLECT=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_extract_nosummary dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_extract_nosummary_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=7 SPATZ_CDOTP_SKIP_VERIFY=1 SPATZ_CDOTP_SKIP_SUMMARY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_extract_noprint dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_extract_noprint_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=7 SPATZ_CDOTP_SKIP_VERIFY=1 SPATZ_CDOTP_SKIP_PRINT=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_store_scalar dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_store_scalar_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=8 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vec_store_scalar_m1 dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vec_store_scalar_m1_M128 PUBLIC SPATZ_CDOTP_VECTOR_DIAG_STAGE=9 SPATZ_CDOTP_SKIP_VERIFY=1)
add_spatz_test_oneParam_cfma(dp-cdotp_old_singlecore dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_old_singlecore_M128 PUBLIC SPATZ_CDOTP_SINGLE_CORE=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vfcmacc_singlecore dp-cdotp/main.c 128 1)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vfcmacc_singlecore_M128 PUBLIC SPATZ_CDOTP_SINGLE_CORE=1)
add_spatz_test_oneParam_cfma(dp-cdotp_old_direct_singlecore dp-cdotp/main.c 128 0)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_old_direct_singlecore_M128 PUBLIC SPATZ_CDOTP_SINGLE_CORE=1 SPATZ_CDOTP_DIRECT_ACC_ASSIGN=1)
add_spatz_test_oneParam_cfma(dp-cdotp_vfcmacc_direct_singlecore dp-cdotp/main.c 128 1)
target_compile_definitions(test-${SNITCH_TEST_PREFIX}dp-cdotp_vfcmacc_direct_singlecore_M128 PUBLIC SPATZ_CDOTP_SINGLE_CORE=1 SPATZ_CDOTP_DIRECT_ACC_ASSIGN=1)
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
