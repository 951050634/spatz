#include "cdotp.h"

#ifndef SPATZ_USE_VFCMACC
#define SPATZ_USE_VFCMACC 0
#endif

#ifndef SPATZ_CDOTP_SCALAR_DIAG
#define SPATZ_CDOTP_SCALAR_DIAG 0
#endif

#ifndef SPATZ_CDOTP_VECTOR_DIAG_STAGE
#define SPATZ_CDOTP_VECTOR_DIAG_STAGE 0
#endif

#if SPATZ_CDOTP_SCALAR_DIAG
#define SPATZ_CDOTP_KERNEL_NAME "scalar"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 0
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 0
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 1
#define SPATZ_CDOTP_KERNEL_NAME "vec_load"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 3
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 0
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 2
#define SPATZ_CDOTP_KERNEL_NAME "vec_mac"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 3
#define SPATZ_CDOTP_KERNEL_NAME "vec_reduce_real"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 4
#define SPATZ_CDOTP_KERNEL_NAME "vec_reduce_imag"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 5
#define SPATZ_CDOTP_KERNEL_NAME "vec_reduce_both"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 6
#define SPATZ_CDOTP_KERNEL_NAME "vec_reduce_noextract"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 7
#define SPATZ_CDOTP_KERNEL_NAME "vec_extract_drop"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 8
#define SPATZ_CDOTP_KERNEL_NAME "vec_store_scalar"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 9
#define SPATZ_CDOTP_KERNEL_NAME "vec_store_scalar_m1"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#elif SPATZ_USE_VFCMACC
#define SPATZ_CDOTP_KERNEL_NAME "vfcmacc"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 4
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 1
#define VFCMACC_VV_VM1(vd, vs1, vs2)                                           \
    asm volatile(".insn r 0x57, 0x1, 0x75, " vd ", " vs1 ", " vs2)
#else
#define SPATZ_CDOTP_KERNEL_NAME "old"
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#endif

// sum += x[i] * y[i]
cdouble cdotp_v64b(const cdouble *x, const cdouble *y, unsigned int avl)
{
#if SPATZ_CDOTP_SCALAR_DIAG
    cdouble acc = {0.0, 0.0};

    for (unsigned int i = 0; i < avl; ++i)
    {
        const double xr = x[i].real;
        const double xi = x[i].imag;
        const double yr = y[i].real;
        const double yi = y[i].imag;
        volatile double real_prod0 = xr * yr;
        volatile double real_prod1 = xi * yi;
        volatile double imag_prod0 = xr * yi;
        volatile double imag_prod1 = xi * yr;
        volatile double real_delta = real_prod0 - real_prod1;
        volatile double imag_delta = imag_prod0 + imag_prod1;
        acc.real += real_delta;
        acc.imag += imag_delta;
    }

    return acc;
#else
    unsigned int vl;
    double red_real, red_imag;

    // LMUL=4
    // v16-v19: Real
    // v20-v23: Imag
    asm volatile("vsetvli %0, %1, e64, m4, ta, ma" : "=r"(vl) : "r"(avl));
    asm volatile("vmv.v.i v16, 0"); // Acc_Real = 0
    asm volatile("vmv.v.i v20, 0"); // Acc_Imag = 0

    do
    {
        asm volatile("vsetvli %0, %1, e64, m4, ta, ma" : "=r"(vl) : "r"(avl));

        // v0=Xr, v4=Xi
        asm volatile("vlseg2e64.v v0, (%0)" ::"r"(x));

        // v8=Yr, v12=Yi
        asm volatile("vlseg2e64.v v8, (%0)" ::"r"(y));

#if SPATZ_CDOTP_VECTOR_DIAG_STAGE == 1
        asm volatile("" ::: "memory");
#elif SPATZ_USE_VFCMACC
        VFCMACC_VV_VM1("v16", "v0", "v8");
#else
        asm volatile("vfmacc.vv v16, v0, v8");   // v16 += Xr * Yr
        asm volatile("vfnmsac.vv v16, v4, v12"); // v16 -= Xi * Yi
        asm volatile("vfmacc.vv v20, v0, v12");  // v20 += Xr * Yi
        asm volatile("vfmacc.vv v20, v4, v8");   // v20 += Xi * Yr
#endif

        x += vl;
        y += vl;
        avl -= vl;
    } while (avl > 0);

#if SPATZ_CDOTP_VECTOR_DIAG_STAGE == 1 || SPATZ_CDOTP_VECTOR_DIAG_STAGE == 2
    cdouble res = {0.0, 0.0};
    return res;
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 3
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfmv.f.s %0, v16" : "=f"(red_real));
    cdouble res = {red_real, 0.0};
    return res;
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 4
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v20, v20, v24");
    asm volatile("vfmv.f.s %0, v20" : "=f"(red_imag));
    cdouble res = {0.0, red_imag};
    return res;
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 6
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfredusum.vs v20, v20, v24");
    cdouble res = {0.0, 0.0};
    return res;
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 7
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfmv.f.s %0, v16" : "=f"(red_real));
    asm volatile("vfredusum.vs v20, v20, v24");
    asm volatile("vfmv.f.s %0, v20" : "=f"(red_imag));
    asm volatile("" : : "f"(red_real), "f"(red_imag));
    cdouble res = {0.0, 0.0};
    return res;
#elif SPATZ_CDOTP_VECTOR_DIAG_STAGE == 8 || SPATZ_CDOTP_VECTOR_DIAG_STAGE == 9
    const unsigned int one = 1;
    volatile double red_buf[2] = {0.0, 0.0};
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfredusum.vs v20, v20, v24");
#if SPATZ_CDOTP_VECTOR_DIAG_STAGE == 9
    asm volatile("vsetvli zero, %0, e64, m1, ta, ma" ::"r"(one));
#else
    asm volatile("vsetvli zero, %0, e64, m4, ta, ma" ::"r"(one));
#endif
    asm volatile("vse64.v v16, (%0)" ::"r"(&red_buf[0]) : "memory");
    asm volatile("vse64.v v20, (%0)" ::"r"(&red_buf[1]) : "memory");
    cdouble res = {red_buf[0], red_buf[1]};
    return res;
#else
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfmv.f.s %0, v16" : "=f"(red_real));
    asm volatile("vfredusum.vs v20, v20, v24");
    asm volatile("vfmv.f.s %0, v20" : "=f"(red_imag));
    cdouble res = {red_real, red_imag};
    return res;
#endif
#endif
}

cfloat cdotp_v32b(const cfloat *x, const cfloat *y, unsigned int avl)
{
    unsigned int vl;
    float red_real, red_imag;

    asm volatile("vsetvli %0, %1, e32, m4, ta, ma" : "=r"(vl) : "r"(avl));
    asm volatile("vmv.v.i v16, 0");
    asm volatile("vmv.v.i v20, 0");

    do
    {
        asm volatile("vsetvli %0, %1, e32, m4, ta, ma" : "=r"(vl) : "r"(avl));

        asm volatile("vlseg2e32.v v0, (%0)" ::"r"(x)); // v0=Xr, v4=Xi
        asm volatile("vlseg2e32.v v8, (%0)" ::"r"(y)); // v8=Yr, v12=Yi

        asm volatile("vfmacc.vv v16, v0, v8");
        asm volatile("vfnmsac.vv v16, v4, v12");
        asm volatile("vfmacc.vv v20, v0, v12");
        asm volatile("vfmacc.vv v20, v4, v8");

        x += vl;
        y += vl;
        avl -= vl;
    } while (avl > 0);

    asm volatile("vmv.s.x v24, zero"); // Clear base
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfmv.f.s %0, v16" : "=f"(red_real));
    asm volatile("vfredusum.vs v20, v20, v24");
    asm volatile("vfmv.f.s %0, v20" : "=f"(red_imag));

    cfloat res = {red_real, red_imag};
    return res;
}

chalf cdotp_v16b(const chalf *x, const chalf *y, unsigned int avl)
{
    unsigned int vl;
    _Float16 red_real, red_imag;

    asm volatile("vsetvli %0, %1, e16, m4, ta, ma" : "=r"(vl) : "r"(avl));
    asm volatile("vmv.v.i v16, 0");
    asm volatile("vmv.v.i v20, 0");

    do
    {
        asm volatile("vsetvli %0, %1, e16, m4, ta, ma" : "=r"(vl) : "r"(avl));

        asm volatile("vlseg2e16.v v0, (%0)" ::"r"(x));
        asm volatile("vlseg2e16.v v8, (%0)" ::"r"(y));

        asm volatile("vfmacc.vv v16, v0, v8");
        asm volatile("vfnmsac.vv v16, v4, v12");
        asm volatile("vfmacc.vv v20, v0, v12");
        asm volatile("vfmacc.vv v20, v4, v8");

        x += vl;
        y += vl;
        avl -= vl;
    } while (avl > 0);

    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfmv.f.s %0, v16" : "=f"(red_real));
    asm volatile("vfredusum.vs v20, v20, v24");
    asm volatile("vfmv.f.s %0, v20" : "=f"(red_imag));

    chalf res = {red_real, red_imag};
    return res;
}
