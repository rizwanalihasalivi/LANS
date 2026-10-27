#define _POSIX_C_SOURCE 200809L
#include <time.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>

static int64_t now(void) {
    struct timespec t;
    if(clock_gettime(CLOCK_MONOTONIC,&t))exit(2);
    return (int64_t)t.tv_sec*1000000000LL+t.tv_nsec;
}
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    int n=atoi(argv[1]);if(n<1||n>10000)return 2;
    int64_t *values=calloc((size_t)n,sizeof(int64_t));if(!values)return 3;
    FILE *f=fopen(argv[2],"w");if(!f)return 4;
    int64_t origin=now()+20000000LL;
    for(int i=0;i<n;i++) {
        int64_t target=origin+(int64_t)i*10000000LL;
        struct timespec t={target/1000000000LL,target%1000000000LL};
        int status;do {status=clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&t,0);}while(status==EINTR);
        if(status)return status;
        values[i]=now();
    }
    fprintf(f,"tick,target_ns,release_ns,deadline_miss\n");
    for(int i=0;i<n;i++) {
        int64_t target=origin+(int64_t)i*10000000LL;
        fprintf(f,"%d,%lld,%lld,%d\n",i,(long long)target,(long long)values[i],values[i]>target+10000000LL);
    }
    fclose(f);free(values);return 0;
}
