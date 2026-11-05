/* Reference solution (instructor's): 64-bit sum, reads n and then n integers. */
#include <stdio.h>

int main(void)
{
    int n;
    long long sum = 0;

    if (scanf("%d", &n) != 1) {
        return 1;
    }
    for (int i = 0; i < n; i++) {
        long long value;
        if (scanf("%lld", &value) != 1) {
            return 1;
        }
        sum += value;
    }
    printf("%lld\n", sum);
    return 0;
}