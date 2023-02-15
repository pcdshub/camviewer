#include<stdio.h>

struct color {
    double r, g, b;
} out[65536];

struct interp {
    double pos;
    double r, g, b;
};

struct interp jet[] = {
    { 0.000, 0.0, 0.0, 0.5 },
    { 1./8., 0.0, 0.0, 1.0 },
    { 2./8., 0.0, 0.5, 1.0 },
    { 3./8., 0.0, 1.0, 1.0 },
    { 4./8., 0.5, 1.0, 0.5 },
    { 5./8., 1.0, 1.0, 0.0 },
    { 6./8., 1.0, 0.5, 0.0 },
    { 7./8., 1.0, 0.0, 0.0 },
    { 1.000, 0.5, 0.0, 0.0 },
};

struct interp cool[] = {
    { 0.000, 0.0, 1.0, 1.0 },
    { 1.000, 1.0, 0.0, 1.0 },
};

struct interp hot[] = {
    { 0.000, 0.0, 0.0, 0.0 },
    { 1./3., 1.0, 0.0, 0.0 },
    { 2./3., 1.0, 1.0, 0.0 },
    { 1.000, 1.0, 1.0, 1.0 },
};

struct interp hsv[] = {
    { 0.000, 1.0, 0.0, 0.0 },
    { 1./6., 1.0, 1.0, 0.0 },
    { 2./6., 0.0, 1.0, 0.0 },
    { 3./6., 0.0, 1.0, 1.0 },
    { 4./6., 0.0, 0.0, 1.0 },
    { 5./6., 1.0, 0.0, 1.0 },
    { 1.000, 1.0, 0.0, 0.0 },
};

void do_interp(struct interp *interp, char *file, int len)
{
    int i, p;
    double f;
    FILE *fp = fopen(file, "w");

    for (i = 0, p = 0; i <= len; i++) {
        if (i >= interp[p].pos * len)
            p++;
        f = ((double) i) / len;
        out[i].r = (interp[p-1].r + (interp[p].r - interp[p-1].r) * (f - interp[p-1].pos) /
                    (interp[p].pos - interp[p-1].pos));
        out[i].g = (interp[p-1].g + (interp[p].g - interp[p-1].g) * (f - interp[p-1].pos) /
                    (interp[p].pos - interp[p-1].pos));
        out[i].b = (interp[p-1].b + (interp[p].b - interp[p-1].b) * (f - interp[p-1].pos) /
                    (interp[p].pos - interp[p-1].pos));
    }
    for (i = 0; i <= len; i++) {
        fprintf(fp, "   %13.7e   %13.7e   %13.7e\n", out[i].r, out[i].g, out[i].b);
    }
    fclose(fp);
}

int main(int argc, char **argv)
{
    do_interp(jet,  "jet.txt",  65535);
    do_interp(cool, "cool.txt", 65535);
    do_interp(hot,  "hot.txt",  65535);
    do_interp(hsv,  "hsv.txt",  65535);
}
