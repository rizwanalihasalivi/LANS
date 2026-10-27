#define _POSIX_C_SOURCE 200809L
#include <time.h>
#include <stdint.h>
#include <errno.h>

int64_t lans_monotonic_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    return (int64_t)t.tv_sec*1000000000LL+t.tv_nsec;
}
int lans_wait(int64_t target, int pure_spin) {
    if (!pure_spin) {
        int64_t value=target-100000;
        if (value>lans_monotonic_ns()) {
            struct timespec ts={value/1000000000LL,value%1000000000LL};
            int status;
            do {status=clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&ts,0);} while(status==EINTR);
            if(status)return status;
        }
    }
    while(lans_monotonic_ns()<target) {
#if defined(__x86_64__) || defined(__i386__)
        __asm__ __volatile__("pause");
#elif defined(__aarch64__)
        __asm__ __volatile__("yield");
#endif
    }
    return 0;
}
