/**
 * @file random.c
 * @brief Random number generator interface
 */

#if defined(RANDOM_MKL)

#include <mkl_vsl.h>
#include "random.h"

void random_mkl_init(random_data* rdata, int seed) {
    vslNewStream(&rdata->r, RANDOM_MKL_RNG, seed);
}

double random_mkl_uniform(random_data* rdata) {
    double r;
    vdRngUniform(VSL_RNG_METHOD_UNIFORM_STD, rdata->r, 1, &r, 0.0, 1.0);
    return r;
}

double random_mkl_normal(random_data* rdata) {
    double r;
    vdRngGaussian(VSL_RNG_METHOD_GAUSSIAN_BOXMULLER, rdata->r, 1, &r, 0.0, 1.0);
    return r;
}

void random_mkl_uniform_simd(random_data* rdata, int n, double* r) {
    vdRngUniform(VSL_RNG_METHOD_UNIFORM_STD, rdata->r, n, r, 0.0, 1.0);
}

void random_mkl_normal_simd(random_data* rdata, int n, double* r) {
    vdRngGaussian(VSL_RNG_METHOD_GAUSSIAN_BOXMULLER2, rdata->r, n, r, 0.0, 1.0);
}


#elif defined(RANDOM_GSL)

#include <gsl/gsl_rng.h>
#include "random.h"

void random_gsl_init(random_data* rdata, int seed) {
    rdata->r = gsl_rng_alloc(gsl_rng_mt19937);
    gsl_rng_set(rdata->r, seed);
}

double random_gsl_uniform(random_data* rdata) {
    return gsl_rng_uniform(rdata->r);
}

double random_gsl_normal(random_data* rdata) {
    return gsl_ran_gaussian(rdata->r, 1.0);
}

void random_gsl_uniform_simd(random_data* rdata, int n, double* r) {
    #pragma omp simd
    for(int i = 0; i < n; i++) {
        r[i] = gsl_rng_uniform(rdata->r);
    }
}

void random_gsl_normal_simd(random_data* rdata, int n, double* r) {
    #pragma omp simd
    for(int i = 0; i < n; i++) {
        r[i] = gsl_ran_gaussian(rdata->r, 1.0);
    }
}


#elif defined(RANDOM_LCG)

#include <stdint.h>
#include <math.h>
#include "consts.h"
#include "random.h"

void random_lcg_init(random_data* rdata, uint64_t seed) {
    rdata->r = seed;
}

uint64_t random_lcg_integer(random_data* rdata) {
    /* parameters from https://nuclear.llnl.gov/CNP/rng/rngman/node4.html */
    uint64_t a = 2862933555777941757;
    uint64_t b = 3037000493;
    rdata->r = (a * rdata->r + b);
    return rdata->r;
}

double random_lcg_uniform(random_data* rdata) {
    double r;
    random_lcg_uniform_simd(rdata, 1, &r);
    return r;
}

double random_lcg_normal(random_data* rdata) {
    double r;
    random_lcg_normal_simd(rdata, 1, &r);
    return r;
}

void random_lcg_uniform_simd(random_data* rdata, int n, double* r) {
#ifndef GPU
#ifdef SIMD
    #pragma omp simd
#endif
#endif  
    for(int i = 0; i < n; i++) {
        r[i] = (double) random_lcg_integer(rdata) / UINT64_MAX;
    }
}

void random_lcg_normal_simd(random_data* rdata, int n, double* r) {
    double x1, x2, w; /* Helper variables */
    int isEven = (n+1) % 2; /* Indicates if even number of random numbers are requested */

#if A5_CCOL_USE_GEOBM == 1
    /* The geometric form */
    //#ifdef SIMD
    //    #pragma omp simd
    //#endif
    GPU_PARALLEL_LOOP_ALL_LEVELS
    for(int i = 0; i < n; i=i+2) {
        w = 2.0;
        while( w >= 1.0 ) {
            x1 = 2*random_lcg_uniform(rdata)-1;
            x2 = 2*random_lcg_uniform(rdata)-1;
            w = x1*x1 + x2*x2;
        }

        w = sqrt( (-2 * log( w ) ) / w );
        r[i] = x1 * w;
        if((i < n-2) || (isEven > 0)) {
            r[i+1] = x2 * w;
        }
    }
#else
    /* The common form */
    double s;
    //#ifdef SIMD
    //    #pragma omp simd
    //#endif
  GPU_PARALLEL_LOOP_ALL_LEVELS
    for(int i = 0; i < n; i=i+2) {
        x1 = random_lcg_uniform(rdata);
        x2 = random_lcg_uniform(rdata);
        w = sqrt(-2*log(x1));
        s = cos(CONST_2PI*x2);
        r[i] = w*s;
        if((i < n-2) || (isEven > 0) ) {
            if(x2 < 0.5) {
                r[i+1] = w*sqrt(1-s*s);
            }
            else {
                r[i+1] = -w*sqrt(1-s*s);
            }
        }
    }
#endif
}

#else /* No RNG lib defined, use drand48 */

#define _XOPEN_SOURCE 500 /**< rand48 requires POSIX 1995 standard */

#include <stdlib.h>
#include <math.h>
#include "consts.h"
#include "random.h"

double random_drand48_normal() {
    double r;
    random_drand48_normal_simd(1, &r);
    return r;
}

void random_drand48_uniform_simd(int n, double* r) {
    #pragma omp simd
    for(int i = 0; i < n; i++) {
        r[i] = drand48();
    }
}
#ifdef GPU
void random_drand48_normal_cuda(random_data* data, int n, double* r)
{
    // Generate random numbers on the host
    double x1, x2, w; /* Helper variables */
    int isEven = (n+1) % 2; /* Indicates if even number of random numbers are requested */
#pragma acc host_data use_device(data->r_cuda)
    {
      int status = curandGenerateUniformDouble(data->gen, data->r_cuda, n);
    }
#if A5_CCOL_USE_GEOBM == 1
    /* The geometric form */
#ifdef GPU
    GPU_PARALLEL_LOOP_ALL_LEVELS
#else
    #pragma omp simd
#endif
    for(int i = 0; i < n; i=i+2) {
        w = 2.0;
        while( w >= 1.0 ) {
            x1 = 2*data->r_cuda[i]  -1;
            x2 = 2*data->r_cuda[i+1]-1;
            w = x1*x1 + x2*x2;
        }

        w = sqrt( (-2 * log( w ) ) / w );
        r[i] = x1 * w;
        if((i < n-2) || (isEven > 0)) {
            r[i+1] = x2 * w;
        }
    }
#else
    /* The common form */
    double s;
#ifdef GPU
    GPU_PARALLEL_LOOP_ALL_LEVELS
#else
    #pragma omp simd
#endif
    for(int i = 0; i < n; i=i+2) {
        x1 = data->r_cuda[i]  ;
        x2 = data->r_cuda[i+1];
        w = sqrt(-2*log(x1));
        s = cos(CONST_2PI*x2);
        r[i] = w*s;
        if((i < n-2) || (isEven > 0) ) {
            if(x2 < 0.5) {
                r[i+1] = w*sqrt(1-s*s);
            }
            else {
                r[i+1] = -w*sqrt(1-s*s);
            }
        }
    }
#endif
}

void random_drand48_normal_cuda_init(random_data* data, int  n) {
  int status;
  data->r_cuda = malloc(n * sizeof(double));
  curandCreateGenerator(&data->gen, CURAND_RNG_PSEUDO_DEFAULT);
  curandSetPseudoRandomGeneratorSeed(data->gen,  1234ULL);
}
#endif
void random_drand48_normal_simd(int n, double* r) {
    double x1, x2, w; /* Helper variables */
    int isEven = (n+1) % 2; /* Indicates if even number of random numbers are requested */

#if A5_CCOL_USE_GEOBM == 1
    /* The geometric form */
    #pragma omp simd
    for(int i = 0; i < n; i=i+2) {
        w = 2.0;
        while( w >= 1.0 ) {
            x1 = 2*drand48()-1;
            x2 = 2*drand48()-1;
            w = x1*x1 + x2*x2;
        }

        w = sqrt( (-2 * log( w ) ) / w );
        r[i] = x1 * w;
        if((i < n-2) || (isEven > 0)) {
            r[i+1] = x2 * w;
        }
    }
#else
    /* The common form */
    double s;
    #pragma omp simd
    for(int i = 0; i < n; i=i+2) {
        x1 = drand48(rdata);
        x2 = drand48(rdata);
        w = sqrt(-2*log(x1));
        s = cos(CONST_2PI*x2);
        r[i] = w*s;
        if((i < n-2) || (isEven > 0) ) {
            if(x2 < 0.5) {
                r[i+1] = w*sqrt(1-s*s);
            }
            else {
                r[i+1] = -w*sqrt(1-s*s);
            }
        }
    }
#endif
}

#endif
