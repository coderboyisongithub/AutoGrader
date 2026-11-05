/* Reference solution (instructor's): reads one line and prints it reversed. */
#include <stdio.h>
#include <string.h>

#define MAX_LINE 1024   /* the statement allows at most 1000 characters */

/* Reverse the first len characters of text in place. */
static void reverse_in_place(char *text, size_t len)
{
    for (size_t left = 0, right = len; left + 1 < right; left++, right--) {
        char tmp = text[left];
        text[left] = text[right - 1];
        text[right - 1] = tmp;
    }
}

int main(void)
{
    char line[MAX_LINE + 2];

    if (fgets(line, sizeof line, stdin) == NULL) {
        return 1;                              /* no input line at all */
    }
    size_t len = strcspn(line, "\r\n");        /* drop the line ending (LF or CRLF) */
    line[len] = '\0';

    reverse_in_place(line, len);
    printf("%s", line);
    return 0;
}