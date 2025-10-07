%Module(name=pycaqtimage)

%Import QtGui/QtGuimod.sip

%ModuleCode

#include <Qt/qimage.h>
#include <fcntl.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include "arrayobject.h"

static const unsigned int   MAX_INDEX_PLUS1 = 65536;
static const uint32_t       ALPHA_VALUE     = 0xff000000;
static uint32_t             gColorMap[MAX_INDEX_PLUS1];

#define PYC_IB  "pycaqtimage.IB"
#define PYC_CB  "pycaqtimage.CB"
#define UNUSED(s) (void)(s)

/*
 * Read in a colormap file and scale it so it fits the specified range using the specified function
 * (linear, exp, log, etc.)
 */
void pydspl_setup_color_map(const char* colormap, int iLimitLow, int iLimitHigh, int iScaleIndex)
{
    static uint32_t gTempColorMap[MAX_INDEX_PLUS1];
    memset(gTempColorMap, 0, MAX_INDEX_PLUS1*sizeof(gColorMap[0]));
    FILE* fp = fopen(colormap, "r");
    if (fp) {
        float rf,gf,bf;
        int nitems;
        uint32_t row = 0;
        do {
            nitems = fscanf(fp, "%f %f %f", &rf, &gf, &bf);
            uint32_t r = static_cast<uint32_t>(rf * 255);
            uint32_t g = static_cast<uint32_t>(gf * 255);
            uint32_t b = static_cast<uint32_t>(bf * 255);
            gTempColorMap[row++] = ALPHA_VALUE |
                ((r & 0xff) << 16) |
                ((g & 0xff) <<  8) |
                ((b & 0xff)      );
        } while (nitems == 3 && row < MAX_INDEX_PLUS1);
        fclose(fp);
        if (row != MAX_INDEX_PLUS1) {
            fprintf(stderr, "*** couldn't read %d entries from %s\n",
                    MAX_INDEX_PLUS1, colormap);
        }
    } else {
        fprintf(stderr, "*** couldn't open %s for reading: %s\n",
                colormap, strerror(errno));
        return;
    }

    const uint32_t u32LowValue = gTempColorMap[0];
    int i = 0;
    for (; i<= iLimitLow; ++i)
        gColorMap[i]   = u32LowValue;

    const int     iLimitRange = iLimitHigh - iLimitLow;
    const float  fLimitRange = (float) iLimitRange;
    for (; i<iLimitHigh; ++i) {
        int iIndex;
        /*
         * This switch needs to match the order in comboBoxScale in camviewer.ui!
         */
        switch (iScaleIndex) {
        case 1: /* Log2 */
            iIndex = (int) ( log2( 1 + (i - iLimitLow) / fLimitRange) * (MAX_INDEX_PLUS1-1) + 0.5);
            break;
        case 2: /* LogE */
            iIndex = (int) ( log( 1 + (M_E - 1) * (i - iLimitLow) / fLimitRange) * (MAX_INDEX_PLUS1-1) + 0.5);
            break;
        case 3: /* Log10 */
            iIndex = (int) ( log10( 1 + (10. - 1) * (i - iLimitLow) / fLimitRange) * (MAX_INDEX_PLUS1-1) + 0.5);
            break;
        case 4: /* Exp2 */
            iIndex = (int) ( (exp2( (i - iLimitLow) / fLimitRange) - 1 ) * (MAX_INDEX_PLUS1-1) + 0.5);
            break;
        case 5: /* ExpE */
            iIndex = (int) ( (exp( (i - iLimitLow) / fLimitRange) - 1 )/(M_E - 1) * (MAX_INDEX_PLUS1-1) + 0.5);
            break;
        case 6: /* Exp10 */
            iIndex = (int) ( (exp10( (i - iLimitLow) / fLimitRange) - 1 )/(10. - 1) * (MAX_INDEX_PLUS1-1) + 0.5);
            break;
        case 0: /* Linear */
        default:
            iIndex = (i - iLimitLow) * (MAX_INDEX_PLUS1-1) / iLimitRange;
            break;
        }
        uint32_t colorVal  = gTempColorMap[iIndex];
        gColorMap[i] = colorVal;
    }

    const uint32_t u32HighValue = gTempColorMap[MAX_INDEX_PLUS1-1];
    for (; i < (int) MAX_INDEX_PLUS1; ++i)
        gColorMap[i]   = u32HighValue;
}

/*
 * Setup an 8-bit grayscale color map.
 */
void pydspl_setup_gray(int iLimitLow, int iLimitHigh, int iScaleIndex)
{
    const uint32_t u32LowValue = ALPHA_VALUE;
    int i = 0;
    for (; i<= iLimitLow; ++i)
        gColorMap[i]   = u32LowValue;

    const int iLimitRange = iLimitHigh - iLimitLow;
    const float  fLimitRange = (float) iLimitRange;
    for (; i<iLimitHigh; ++i) {

        uint8_t  u8Gray;
        switch (iScaleIndex) {
        case 1: /* Log2 */
            u8Gray = (int) ( log2( 1 + (i - iLimitLow) / fLimitRange) * 255 + 0.5);
            break;
        case 2: /* LogE */
            u8Gray = (int) ( log( 1 + (M_E - 1) * (i - iLimitLow) / fLimitRange) * 255 + 0.5);
            break;
        case 3: /* Log10 */
            u8Gray = (int) ( log10( 1 + (10. - 1) * (i - iLimitLow) / fLimitRange) * 255 + 0.5);
            break;
        case 4: /* Exp2 */
            u8Gray = (int) ( (exp2( (i - iLimitLow) / fLimitRange) - 1 ) * 255 + 0.5);
            break;
        case 5: /* ExpE */
            u8Gray = (int) ( (exp( (i - iLimitLow) / fLimitRange) - 1 )/(M_E - 1) * 255 + 0.5);
            break;
        case 6: /* Exp10 */
            u8Gray = (int) ( (exp10( (i - iLimitLow) / fLimitRange) - 1 )/(10. - 1) * 255 + 0.5);
            break;
        case 0: /* Linear */
        default:
            u8Gray = (i - iLimitLow) * 255 / iLimitRange;
            break;
        }

        uint32_t grayval  = ALPHA_VALUE | (u8Gray << 16) | (u8Gray << 8) | u8Gray;
        gColorMap[i] = grayval;
    }

    const uint32_t u32HighValue = ALPHA_VALUE | 0xFFFFFF;
    for (; i < (int) MAX_INDEX_PLUS1; ++i)
        gColorMap[i]   = u32HighValue;
}

/*
 * Note: all of these are now oriented!!
 */
struct ImageBuffer
{
    QImage*   imageDisp;

    uint32_t* imageData;
    double*   projSumX;
    double*   projSumY;
    int       srcwidth, srcheight;
    int       imgwidth, imgheight;
    int       size;
    int       iRoiW, iRoiH;
    uint32_t  max_px, min_px;

    int32_t  iProjXmin, iProjXmax;
    int32_t  iProjYmin, iProjYmax;

    float fRoiPixelMean;
    float fRoiPixelVar;

    // Frame averaging function
    float*    imageDataF;
    int       iAverage;
    int       iNumAveraged;

    int       isColor;
    int       useGray;
    int       orientation;
};

/* These must match param.py!! */
#define ORIENT0    0
#define ORIENT90   1
#define ORIENT180  2
#define ORIENT270  3
#define ORIENT0F   4
#define ORIENT90F  5
#define ORIENT180F 6
#define ORIENT270F 7

static void _pyFreeImageBuffer(PyObject* pyImageBuffer)
{
    ImageBuffer* imageBuffer = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);

    free(imageBuffer->imageDataF);
    free(imageBuffer);
}

/*
 * Parameters:
 *    imageDisp - The oriented, false-colored QImage to return.
 *    px_, py_ - numpy arrays (float64) to hold the (oriented) projections.
 *    image_ - numpy array (uint32) to hold the current (oriented) image.
 *    orientation - The orientation constant.
 *
 * The new regime is that we *immediately* reorient whatever we are
 * reading in, and all calculations are on the transformed image.
 */
PyObject* pyCreateImageBuffer(QImage* imageDisp, PyObject *px_, PyObject *py_, PyObject *image_, int srcwidth, int srcheight, int orientation)
{
    PyArrayObject *px = NULL;
    PyArrayObject *py = NULL;
    PyArrayObject *image = NULL;
    int lenx, leny;
    static int first = 1;
    if (first) {
        first = 0;
        _import_array(); /* SIP chokes on import_array, so directly call the internal routine. */
    }
    if (imageDisp == NULL)
        Py_RETURN_NONE;
    if (px_ != NULL && PyArray_Check(px_))
        px = (PyArrayObject *)px_;
    if (py_ != NULL && PyArray_Check(py_))
        py = (PyArrayObject *)py_;
    if (image_ != NULL && PyArray_Check(image_))
        image = (PyArrayObject *)image_;

    ImageBuffer* imageBuffer = (ImageBuffer*) malloc(sizeof(ImageBuffer));
    imageBuffer->srcwidth    = srcwidth;
    imageBuffer->srcheight   = srcheight;
    if (orientation & 2) {
        imageBuffer->imgwidth  = lenx = srcheight;
        imageBuffer->imgheight = leny = srcwidth;
    } else {
        imageBuffer->imgwidth  = lenx = srcwidth;
        imageBuffer->imgheight = leny = srcheight;
    }
    imageBuffer->size        = lenx * leny;
    imageBuffer->imageDisp   = imageDisp;
    if (px != NULL && PyArray_NDIM(px) == 1 &&
        PyArray_DIM(px, 0) == lenx && PyArray_TYPE(px) == NPY_DOUBLE) {
        imageBuffer->projSumX    = (double *)PyArray_DATA(px);
    } else {
        fprintf(stderr, "pyCreateImageBuffer: px is not a double numpy array of length %d!\n", lenx);
        free(imageBuffer);
        Py_RETURN_NONE;
    }
    if (py != NULL && PyArray_NDIM(py) == 1 &&
        PyArray_DIM(py, 0) == leny && PyArray_TYPE(py) == NPY_DOUBLE) {
        imageBuffer->projSumY    = (double *)PyArray_DATA(py);
    } else {
        fprintf(stderr, "pyCreateImageBuffer: py is not a double numpy array of length %d!\n", leny);
        free(imageBuffer);
        Py_RETURN_NONE;
    }
    if (image != NULL && PyArray_NDIM(image) == 2 &&
        PyArray_DIM(image, 0) == leny && PyArray_DIM(image, 1) == lenx &&
        PyArray_TYPE(image) == NPY_UINT) {
        imageBuffer->imageData   = (uint32_t *)PyArray_DATA(image);
    } else {
        fprintf(stderr, "pyCreateImageBuffer: image is not properly sized numpy uint array!\n");
        free(imageBuffer);
        Py_RETURN_NONE;
    }
    imageBuffer->imageDataF  = (float*)    malloc( imageBuffer->size * sizeof(float) );
    imageBuffer->iAverage     = 1;
    imageBuffer->iNumAveraged = 0;
    imageBuffer->isColor      = 0;
    imageBuffer->useGray      = 0;
    imageBuffer->orientation  = orientation;
    memset(imageBuffer->projSumX, 0, lenx * sizeof(double) );
    memset(imageBuffer->projSumY, 0, leny * sizeof(double) );
    memset(imageBuffer->imageData, 0, imageBuffer->size * sizeof(uint32_t) );
    memset(imageBuffer->imageDataF, 0, imageBuffer->size * sizeof(float) );
    imageBuffer->max_px = 0;
    imageBuffer->min_px = 0;

    PyObject* pyImageBuffer = PyCapsule_New(imageBuffer, PYC_IB, _pyFreeImageBuffer);
    return pyImageBuffer;
}

PyObject* pySetImageBufferGray(PyObject* pyImageBuffer, int gray)
{
    ImageBuffer* imageBuffer = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);
    imageBuffer->useGray = gray;
    Py_RETURN_NONE;
}

PyObject* pySetFrameAverage(int iAverage, PyObject* pyImageBuffer)
{
    if ( iAverage == 0 )
	iAverage = 1;

    ImageBuffer* imageBuffer  = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);

    if ( iAverage != imageBuffer->iAverage )
	imageBuffer->iAverage = iAverage;
    imageBuffer->iNumAveraged = 0;

    Py_RETURN_NONE;
}

/*
 * Copy the imageData into the QImage, possibly false coloring it!
 */
static void _pyCopyToQImage(ImageBuffer* imageBuffer, int doFC)
{
    uint32_t* src = imageBuffer->imageData;
    uint32_t* dst = reinterpret_cast<uint32_t*>(imageBuffer->imageDisp->bits());

    if (imageBuffer->imageDisp->height() != imageBuffer->imgheight ||
	imageBuffer->imageDisp->width() != imageBuffer->imgwidth) {
	fprintf(stderr, "Bad dimensions for imageDisp?!?\n");
	return;
    }

    if (doFC) {
	for (int i = 0; i < imageBuffer->size; i++) {
	    *dst++ = (*src < MAX_INDEX_PLUS1) ? gColorMap[*src] : 0;
	    src++;
	}
    } else {
	for (int i = 0; i < imageBuffer->size; i++) {
	    *dst++ = *src++;
	}
    }
}

/*
 * We've just changed color maps.  Output the current image again.
 */
PyObject* pyRecolorImageBuffer(PyObject* pyImageBuffer)
{
    ImageBuffer* imageBuffer = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);
    // Skip color images, which causes a black image flash
    if (!imageBuffer->isColor || imageBuffer->useGray) {
	    _pyCopyToQImage(imageBuffer, 1);
    }
    Py_RETURN_NONE;
}

#define GRAY(rgb) ((rgb)[0] + (rgb)[1] + (rgb)[2])
#define RGB(rgb)  (ALPHA_VALUE | ((rgb)[0] << 16) | ((rgb)[1] << 8) | (rgb)[2])
/*                             0   0F   90   90F  180 180F  270 270F */
static int initMult1[8]   = {  0,   0,   0,   0,   1,   1,   1,   1}; /* Scaled by size */
static int initMult2[8]   = {  0,   1,   1,   0,   0,  -1,  -1,   0}; /* Scaled by srcwidth */
static int initK[8]       = {  0,  -1,  -1,   0,  -1,   0,   0,  -1}; /* Constant */

static int colIncMult[8]  = {  0,   0,   1,   1,   0,   0,  -1,  -1}; /* Scaled by srcwidth */
static int colIncK[8]     = {  1,  -1,   0,   0,  -1,   1,   0,   0}; /* Constant */

static int rowIncMult1[8] = {  0,   0,  -1,  -1,   0,   0,   1,   1}; /* Scaled by size */
static int rowIncMult2[8] = {  0,   2,   0,   0,   0,  -2,   0,   0}; /* Scaled by srcwidth */
static int rowIncK[8]     = {  0,   0,  -1,   1,   0,   0,   1,  -1}; /* Constant */

template <class T>
void _pyDoAvg(ImageBuffer *imageBuffer, T *cadata)
{
    T *src           = cadata;
    uint32_t *dst    = imageBuffer->imageData;
    float *dstF      = imageBuffer->imageDataF;
    int orientation  = imageBuffer->orientation;
    int init_offset  = imageBuffer->size * initMult1[orientation] +
	               imageBuffer->srcwidth * initMult2[orientation] +
	               initK[orientation];
    int row_inc      = imageBuffer->size * rowIncMult1[orientation] +
                       imageBuffer->srcwidth * rowIncMult2[orientation] +
                       rowIncK[orientation];
    int col_inc      = imageBuffer->srcwidth * colIncMult[orientation] +
                       colIncK[orientation];
    int iNewAverage  = imageBuffer->iNumAveraged + 1;

    src += init_offset;
    if (iNewAverage == 1) {
	for (int iRow = 0; iRow < imageBuffer->imgheight; ++iRow) {
	    for (int iCol = 0; iCol < imageBuffer->imgwidth; ++iCol) {
		*dstF++ = *src;
		*dst++ = *src;
		src += col_inc;
	    }
	    src += row_inc;
	}
    } else {
	for (int iRow = 0; iRow < imageBuffer->imgheight; ++iRow) {
	    for (int iCol = 0; iCol < imageBuffer->imgwidth; ++iCol) {
		*dstF += (*src - *dstF) / iNewAverage;
		*dst++ = *dstF++;
		src += col_inc;
	    }
	    src += row_inc;
	}
    }
    imageBuffer->iNumAveraged = iNewAverage % imageBuffer->iAverage;

    if (iNewAverage == imageBuffer->iAverage)
	_pyCopyToQImage(imageBuffer, 1);
}

template <class T>
void _pyDoAvgColor(ImageBuffer *imageBuffer, T *cadata)
{
    T*  src    = cadata; /* R, G, B! */
    uint32_t *dst    = imageBuffer->imageData;
    float    *dstF   = imageBuffer->imageDataF;
    int orientation  = imageBuffer->orientation;
    int init_offset  = imageBuffer->size * initMult1[orientation] +
	               imageBuffer->srcwidth * initMult2[orientation] +
                       initK[orientation];
    int row_inc      = imageBuffer->size * rowIncMult1[orientation] +
                       imageBuffer->srcwidth * rowIncMult2[orientation] +
                       rowIncK[orientation];
    int col_inc      = imageBuffer->srcwidth * colIncMult[orientation] +
                       colIncK[orientation];
    int iNewAverage  = imageBuffer->iNumAveraged + 1;

    /* If we're using the color image, don't average, just copy and we're done! */
    if (!imageBuffer->useGray) {
        src += 3 * init_offset;
	for (int iRow = 0; iRow < imageBuffer->imgheight; ++iRow) {
	    for (int iCol = 0; iCol < imageBuffer->imgwidth; ++iCol) {
		*dst++ = RGB(src);
		src += 3 * col_inc;
	    }
	    src += 3 * row_inc;
	}
	_pyCopyToQImage(imageBuffer, 0);
    } else {
	if (iNewAverage == 1) {
            src += 3 * init_offset;
	    for (int iRow = 0; iRow < imageBuffer->imgheight; ++iRow) {
		for (int iCol = 0; iCol < imageBuffer->imgwidth; ++iCol) {
		    *dstF = GRAY(src);
		    *dst++ = *dstF++;
		    src += 3 * col_inc;
		}
		src += 3 * row_inc;
	    }
	} else {
            src += 3 * init_offset;
	    for (int iRow = 0; iRow < imageBuffer->imgheight; ++iRow) {
		for (int iCol = 0; iCol < imageBuffer->imgwidth; ++iCol) {
		    *dstF += (GRAY(src) - *dstF) / iNewAverage;
		    *dst++ = *dstF++;
		    src += 3 * col_inc;
		}
		src += 3 * row_inc;
	    }
	}
	imageBuffer->iNumAveraged = iNewAverage % imageBuffer->iAverage;

	if (iNewAverage == imageBuffer->iAverage)
	    _pyCopyToQImage(imageBuffer, 1);
    }
}

static void _pyColorImagePvCallback(void* cadata, long count, size_t size, void* usr)
{
    ImageBuffer*  imageBuffer = reinterpret_cast<ImageBuffer*>(usr);

    if (count != imageBuffer->size * 3) {
        fprintf(stderr, "Wrong data size %d, expected %d. unsafe to continue\n", count, imageBuffer->size * 3);
        return;
    }

    switch (size) {
        // size 4 will crash the rgb accumulator
        case 2:
        _pyDoAvgColor(imageBuffer, reinterpret_cast<uint16_t*>(cadata));
            break;
        case 1:
        _pyDoAvgColor(imageBuffer, reinterpret_cast<uint8_t*>(cadata));
            break;
        default:
            fprintf(stderr, "Image pixel size is %d bytes, must be 1 or 2.\n", (int) size);
        break;
    }
}

static void _pyImagePvCallback(void* cadata, long count, size_t size, void* usr)
{
  ImageBuffer*  imageBuffer = reinterpret_cast<ImageBuffer*>(usr);

  if (count != imageBuffer->size) {
    fprintf(stderr, "Wrong data size %d, expected %d. unsafe to continue\n", count, imageBuffer->size);
    return;
  }

  switch (size) {
    case 4:
	_pyDoAvg(imageBuffer, reinterpret_cast<uint32_t*>(cadata));
        break;
    case 2:
	_pyDoAvg(imageBuffer, reinterpret_cast<uint16_t*>(cadata));
        break;
    case 1:
	_pyDoAvg(imageBuffer, reinterpret_cast<uint8_t*>(cadata));
        break;
    default:
        fprintf(stderr, "Image pixel size is %d bytes, must be 1, 2, or 4.\n", (int) size);
	break;
  }
}

PyObject* pyCreateImagePvCallbackFunc(PyObject* pyImageBuffer)
{
  // reinterpret_cast not allowed between func ptr and void* by ISO C++
  void* func        = (void*)_pyImagePvCallback;
  ImageBuffer* imageBuffer = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);

  imageBuffer->isColor      = 0;

  PyObject* pyfunc = PyCapsule_New(func, PYC_CB, NULL);
  PyCapsule_SetContext(pyfunc, (void *)imageBuffer);
  return pyfunc;
}

PyObject* pyCreateColorImagePvCallbackFunc(PyObject* pyImageBuffer)
{
  // reinterpret_cast not allowed between func ptr and void* by ISO C++
  void* func        = (void*)_pyColorImagePvCallback;
  ImageBuffer* imageBuffer = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);

  imageBuffer->isColor      = 1;

  PyObject* pyfunc = PyCapsule_New(func, PYC_CB, NULL);
  PyCapsule_SetContext(pyfunc, (void *)imageBuffer);
  return pyfunc;
}

static void _computeRoiProj(ImageBuffer* imageBuffer, QRectF* rectRoi, bool bProjAutoRange)
{
    double*   projSumX  = imageBuffer->projSumX;
    double*   projSumY  = imageBuffer->projSumY;
    int       width     = imageBuffer->imgwidth;
    int       height    = imageBuffer->imgheight;
    uint32_t  max_px    = 0;
    uint32_t  min_px    = std::numeric_limits<uint32_t>::max();

    for (int iX = 0; iX < width;  projSumX[iX++] = 0);
    for (int iY = 0; iY < height; projSumY[iY++] = 0);

    /*
     * Arrange that x1 < x2 and y1 < y2 and they are all in bounds!
     */
    int x1  = (int) rectRoi->x();
    int x2  = x1 + (int) rectRoi->width() - 1;
    if ( x1 > x2 ) { int xtmp = x1; x1 = x2; x2 = xtmp; }
    if ( x1 < 0 )
        x1 = 0;
    else if ( x1 >= width )
	x1 = width-1;
    if ( x2 < 0 )
	x2 = 0;
    else if ( x2 >= width )
	x2 = width-1;

    int y1  = (int) rectRoi->y();
    int y2  = y1 + (int) rectRoi->height() - 1;
    if ( y1 > y2 ) { int ytmp = y1; y1 = y2; y2 = ytmp; }
    if ( y1 < 0 )
	y1 = 0;
    else if ( y1 >= height )
	y1 = height-1;
    if ( y2 < 0 )
	y2 = 0;
    else if ( y2 >= height )
	y2 = height-1;

    uint32_t* const pImgValue       = imageBuffer->imageData;
    uint64_t  u64PixelSum           = 0;
    uint64_t  u64PixelSqSum         = 0;
    uint32_t* pPixelLineStart       = pImgValue + y1 * width + x1;
    int isColor = imageBuffer->isColor && !imageBuffer->useGray;

    for (int iY = y1; iY <= y2; ++iY, pPixelLineStart += width) {
	uint32_t* pPixel = pPixelLineStart;
	for (int iX = x1; iX <= x2; ++iX, ++pPixel) {
#define SUMRGB(x) (((x)&0xff)+(((x)>>8)&0xff)+(((x)>>16)&0xff))
	    uint32_t iValue = isColor ? SUMRGB(*pPixel) : *pPixel;
	    if ( iValue >= 0x10000) {
		fprintf(stderr, "Pixel value (%d,%d) too large: value 0x%x\n", iX, iY, iValue);
		continue;
	    }
	    projSumX[iX]  += iValue;
	    projSumY[iY]  += iValue;
	    u64PixelSum   += iValue;
	    /* Sigh... if iValue > 49000 or so, the square of an int will be negative! */
	    u64PixelSqSum += iValue*(uint64_t) iValue;
        max_px = std::max(iValue, max_px);
        min_px = std::min(iValue, min_px);
	}
    }

    imageBuffer->max_px = max_px;
    imageBuffer->min_px = min_px;

    imageBuffer->iRoiW = x2 - x1 + 1;
    imageBuffer->iRoiH = y2 - y1 + 1;
    const float w = imageBuffer->iRoiW;
    const float h = imageBuffer->iRoiH;
    const float fNumRoiPixels = w * h;

    /* Scale it down! */
    for (int iX = x1; iX <= x2; iX++)
	if (projSumX[iX] > 0)
	    projSumX[iX] /= h;
    for (int iY = y1; iY <= y2; iY++)
	if (projSumY[iY] > 0)
	    projSumY[iY] /= w;

    if ( fNumRoiPixels > 0 ) {
	imageBuffer->fRoiPixelMean = u64PixelSum   / fNumRoiPixels;
	imageBuffer->fRoiPixelVar  = u64PixelSqSum / fNumRoiPixels - imageBuffer->fRoiPixelMean * imageBuffer->fRoiPixelMean;
    } else {
	imageBuffer->fRoiPixelMean  = 0;
	imageBuffer->fRoiPixelVar   = 0;
    }

    if (bProjAutoRange) {
	imageBuffer->iProjXmin = 1<<15;
	imageBuffer->iProjXmax = -1;
	imageBuffer->iProjYmin = 1<<15;
	imageBuffer->iProjYmax = -1;

	for (int iX=x1; iX < x2; ++iX) {
	    int iValue = imageBuffer->projSumX[iX];
	    if (iValue < imageBuffer->iProjXmin)
		imageBuffer->iProjXmin = iValue;
	    if (iValue > imageBuffer->iProjXmax)
		imageBuffer->iProjXmax = iValue;
	}

	for (int iY=y1; iY < y2; ++iY) {
	    int iValue = imageBuffer->projSumY[iY];
	    if (iValue < imageBuffer->iProjYmin)
		imageBuffer->iProjYmin = iValue;
	    if (iValue > imageBuffer->iProjYmax)
		imageBuffer->iProjYmax = iValue;
	}

	if ( imageBuffer->iProjXmax == -1 ) {
	    imageBuffer->iProjXmin = 0;
	    imageBuffer->iProjXmax = 1;
        } else {
            if ( imageBuffer->iProjXmin > 0 )
	        --imageBuffer->iProjXmin;
            ++imageBuffer->iProjXmax;
        }

        if ( imageBuffer->iProjYmax == -1 ) {
	    imageBuffer->iProjYmin = 0;
	    imageBuffer->iProjYmax = 1;
        } else {
            if ( imageBuffer->iProjYmin > 0 )
	        --imageBuffer->iProjYmin;
	    ++imageBuffer->iProjYmax;
        }
    }
}

PyObject* pyUpdateProj(PyObject* pyImageBuffer, bool bProjAutoRange,
		       int uMin, int uMax, QRectF* rectRoi)
{
    ImageBuffer* imageBuffer = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);

    /*
     * Compute the ROI projection values, and also update the mean/variance
     */
    _computeRoiProj(imageBuffer, rectRoi, bProjAutoRange);

    if (!bProjAutoRange) {
        imageBuffer->iProjXmin = uMin;
        imageBuffer->iProjXmax = uMax;
        imageBuffer->iProjYmin = uMin;
        imageBuffer->iProjYmax = uMax;
    }

    return Py_BuildValue(
        "ffiiiiii",
        imageBuffer->fRoiPixelMean,
        imageBuffer->fRoiPixelVar,
        imageBuffer->iProjXmin,
        imageBuffer->iProjXmax,
        imageBuffer->iProjYmin,
        imageBuffer->iProjYmax,
        imageBuffer->max_px,
        imageBuffer->min_px
    );
}

/*
 * Given a QPointF p and an array of image data s, assign d to the value at the point.
 */
#define GPX(p, d, s)                                                 \
    if ((p)->x() < 0 || (p)->x() >= imageBuffer->imgwidth ||         \
        (p)->y() < 0 || (p)->y() >= imageBuffer->imgheight)          \
	d = -1;                                                      \
    else                                                             \
	d = (s)[(int)((p)->y() * imageBuffer->imgwidth + (p)->x())]


PyObject* pyGetPixelValue(PyObject* pyImageBuffer, QPointF* cursor, QPointF* marker1, QPointF* marker2,
			  QPointF* marker3, QPointF* marker4)
{
    ImageBuffer* imageBuffer = (ImageBuffer*) PyCapsule_GetPointer(pyImageBuffer, PYC_IB);
    uint32_t*    pImgValue   = (uint32_t*) imageBuffer->imageData;

    uint32_t     u32ValueCursor, u32Value1, u32Value2, u32Value3, u32Value4;
    GPX(cursor,  u32ValueCursor, pImgValue);
    GPX(marker1, u32Value1,      pImgValue);
    GPX(marker2, u32Value2,      pImgValue);
    GPX(marker3, u32Value3,      pImgValue);
    GPX(marker4, u32Value4,      pImgValue);

    return Py_BuildValue("iiiiii", u32ValueCursor, u32Value1, u32Value2, u32Value3, u32Value4,
			 (imageBuffer->iNumAveraged == 0 ? 1 : imageBuffer->iNumAveraged));
}

%End

void pydspl_setup_color_map(const char* colormap, int iLimitLow, int iLimitHigh, int iScaleIndex);
void pydspl_setup_gray(int iLimitLow, int iLimitHigh, int iScaleIndex);

SIP_PYOBJECT pyCreateImageBuffer(QImage* imageDisp, SIP_PYOBJECT px_, SIP_PYOBJECT py_, SIP_PYOBJECT image_, int w, int h, int orientation);
SIP_PYOBJECT pySetImageBufferGray(SIP_PYOBJECT pyImageBuffer, int gray);
SIP_PYOBJECT pySetFrameAverage  (int iAverage, SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyRecolorImageBuffer(SIP_PYOBJECT pyImageBuffer);

SIP_PYOBJECT pyCreateImagePvCallbackFunc(SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyCreateColorImagePvCallbackFunc(SIP_PYOBJECT pyImageBuffer);

SIP_PYOBJECT pyUpdateProj       (SIP_PYOBJECT pyImageBuffer, bool bProjAutoRange,
				 int uMin, int uMax, QRectF* rectRoi);
SIP_PYOBJECT pyGetPixelValue    (SIP_PYOBJECT pyImageBuffer, QPointF* cursor,
                                  QPointF* marker1, QPointF* marker2,
                                  QPointF* marker3, QPointF* marker4);
