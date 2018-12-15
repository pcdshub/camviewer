%Module pycaqtimage 0

%Import QtGui/QtGuimod.sip

%ModuleCode

#include <Qt/qimage.h>
#include <fcntl.h>

extern "C" 
{
  
static const unsigned int   MAX_INDEX_PLUS1 = 65536;
static const uint32_t       ALPHA_VALUE     = 0xff000000;
static uint32_t             gColorMap[MAX_INDEX_PLUS1];

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

struct ImageBuffer
{
  QImage*   imageDisp;
  uint32_t* imageData;
  uint32_t* projSumX;
  uint32_t* projSumY;
  int       iRoiW, iRoiH;
  
  // min/max, for GUI zoom
  //int32_t  iFrameMin, iFrameMax;
  int32_t  iProjXmin, iProjXmax;
  int32_t  iProjYmin, iProjYmax;
  
  float fRoiPixelMean;
  float fRoiPixelVar;
  
  // Frame averaging function
  float*    imageDataF;
  int       iAverage;
  int       iNumAveraged;

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

static void _pyFreeImageBuffer(void* buffer)
{
  ImageBuffer* imageBuffer = (ImageBuffer*) buffer;
    
  free( imageBuffer->imageData   );
  free( imageBuffer->imageDataF  );
  free( imageBuffer->projSumX    );
  free( imageBuffer->projSumY    );
}  

PyObject* pyCreateImageBuffer(QImage* imageDisp, int orientation)
{
  if (imageDisp == NULL)
    Py_RETURN_NONE;

  ImageBuffer* imageBuffer = (ImageBuffer*) malloc(sizeof(ImageBuffer));
  imageBuffer->imageDisp   = imageDisp;
  imageBuffer->imageData   = (uint32_t*) malloc( imageDisp->width () * imageDisp->height() * sizeof(uint32_t) );
  imageBuffer->imageDataF  = (float*)    malloc( imageDisp->width () * imageDisp->height() * sizeof(float) );
  imageBuffer->projSumX    = (uint32_t*) malloc( imageDisp->width () * sizeof(uint32_t) );
  imageBuffer->projSumY    = (uint32_t*) malloc( imageDisp->height() * sizeof(uint32_t) );
  imageBuffer->iAverage    = 1;
  imageBuffer->iNumAveraged= 0;
  imageBuffer->useGray     = 0;
  imageBuffer->orientation = orientation;
  if (orientation & 2) {
      imageBuffer->projSumX    = (uint32_t*) malloc( imageDisp->height() * sizeof(uint32_t) );
      imageBuffer->projSumY    = (uint32_t*) malloc( imageDisp->width()  * sizeof(uint32_t) );
      memset(imageBuffer->projSumX, 0, imageDisp->height() * sizeof(uint32_t) );
      memset(imageBuffer->projSumY, 0, imageDisp->width () * sizeof(uint32_t) );
  } else {
      imageBuffer->projSumX    = (uint32_t*) malloc( imageDisp->width () * sizeof(uint32_t) );
      imageBuffer->projSumY    = (uint32_t*) malloc( imageDisp->height() * sizeof(uint32_t) );
      memset(imageBuffer->projSumX, 0, imageDisp->width () * sizeof(uint32_t) );
      memset(imageBuffer->projSumY, 0, imageDisp->height() * sizeof(uint32_t) );
  }
  memset(imageBuffer->imageData, 0, imageDisp->width () * imageDisp->height() * sizeof(uint32_t) );
  memset(imageBuffer->imageDataF, 0, imageDisp->width () * imageDisp->height() * sizeof(float) );

  PyObject* pyImageBuffer = PyCObject_FromVoidPtr(imageBuffer, _pyFreeImageBuffer);    
  return pyImageBuffer;
}

PyObject* pySetImageBufferGray(PyObject* pyImageBuffer, int gray)
{
  ImageBuffer* imageBuffer = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  imageBuffer->useGray = gray;
  Py_RETURN_NONE;
}

PyObject* pyRecolorImageBuffer(PyObject* pyImageBuffer)
{
  ImageBuffer* imageBuffer = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  /* If the image is supposed to be color, just leave it alone! */
  if (imageBuffer->useGray || imageBuffer->iAverage != 1) {
      const uint32_t* pui32Pixel = (const uint32_t*) imageBuffer->imageData;
      QImage*         image      = imageBuffer->imageDisp;
      const int       width      = image->width();
      const int       height     = image->height();
      uint32_t*       data       = reinterpret_cast<uint32_t*>(image->bits());
      for (int iPixel = 0; iPixel < width*height; ++iPixel, ++data, ++pui32Pixel)
          *data = (*pui32Pixel < MAX_INDEX_PLUS1) ? gColorMap[*pui32Pixel] : 0;
    }
  Py_RETURN_NONE;
}

#define GRAY(rgb) ((rgb)[0] + (rgb)[1] + (rgb)[2])
#define RGB(rgb)  (ALPHA_VALUE | ((rgb)[0] << 16) | ((rgb)[1] << 8) | (rgb)[2])
/*                             0   0F   90   90F  180 180F  270 270F */
static int initMult1[8]   = {  0,   0,   0,   0,   1,   1,   1,   1}; /* Scaled by width*height */
static int initMult2[8]   = {  0,   1,   1,   0,   0,  -1,  -1,   0}; /* Scaled by width */
static int initK[8]       = {  0,  -1,  -1,   0,  -1,   0,   0,  -1}; /* Constant */

static int colIncMult[8]  = {  0,   0,   1,   1,   0,   0,  -1,  -1}; /* Scaled by width */
static int colIncK[8]     = {  1,  -1,   0,   0,  -1,   1,   0,   0}; /* Constant */

static int rowIncMult1[8] = {  0,   0,  -1,  -1,   0,   0,   1,   1}; /* Scaled by width*height */
static int rowIncMult2[8] = {  0,   2,   0,   0,   0,  -2,   0,   0}; /* Scaled by width */
static int rowIncK[8]     = {  0,   0,  -1,   1,   0,   0,   1,  -1}; /* Constant */

/* width and height are the target QImage sizes!! */
static void _pyCopyToQImage(ImageBuffer* imageBuffer, int width, int height)
{
    if (imageBuffer->iNumAveraged == imageBuffer->iAverage - 1) {
        const uint32_t* pui32Pixel = (const uint32_t*) imageBuffer->imageData;
        uint32_t*       data       = reinterpret_cast<uint32_t*>(imageBuffer->imageDisp->bits());
        int orientation = imageBuffer->orientation;
        int srcwidth  = (orientation&2) ? height : width;
        int srcheight = (orientation&2) ? width : height;
        int init_offset  = srcwidth * srcheight * initMult1[orientation] + 
                           srcwidth * initMult2[orientation] +
                           initK[orientation];
        int row_inc      = srcwidth * srcheight * rowIncMult1[orientation] +
                           srcwidth * rowIncMult2[orientation] +
                           rowIncK[orientation];
        int col_inc      = srcwidth * colIncMult[orientation] +
                           colIncK[orientation];

        pui32Pixel += init_offset;
        for (int iRow = 0; iRow < height; ++iRow) {
            for (int iCol = 0; iCol < width; ++iCol) {
                *data++ = (*pui32Pixel < MAX_INDEX_PLUS1) ? gColorMap[*pui32Pixel] : 0;
                pui32Pixel += col_inc;
            }
            pui32Pixel += row_inc;
        }
    }
}

static void _pyColorImagePvCallback(void* cadata, long count, size_t size, void* usr)
{
    ImageBuffer*  imageBuffer = reinterpret_cast<ImageBuffer*>(usr);
    QImage*       image       = imageBuffer->imageDisp;
    const int     width       = image->width();
    const int     height      = image->height();

    uint8_t* cadata8 = static_cast<uint8_t*>(cadata); /* R, G, B! */

    /* If we're using the color image, don't average, scale, or anything, just copy and we're done! */
    if (!imageBuffer->useGray) {
        const uint8_t*  pui8new  = cadata8;
        uint32_t*       data       = reinterpret_cast<uint32_t*>(image->bits());
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++data, pui8new += 3)
            *data = RGB(pui8new);
        return;
    }

    /* Average the new data into imageDataF/imageData */
    if (imageBuffer->iNumAveraged == 0) {
        const uint8_t*  pui8new  = cadata8;
        float*          pfcur    = imageBuffer->imageDataF;

        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, pui8new += 3) {
            imageBuffer->imageData[iPixel] = GRAY(pui8new);
            *pfcur = GRAY(pui8new);
        }
    } else {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint8_t*  pui8new = cadata8;
        int             iNewAverage = imageBuffer->iNumAveraged + 1;
        
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, pui8new += 3) {
            *pfcur    += (GRAY(pui8new) - *pfcur) / iNewAverage;
            *pui32cur  = (unsigned int) *pfcur;
        }
    }
    imageBuffer->iNumAveraged = (imageBuffer->iNumAveraged + 1) % imageBuffer->iAverage;

    /* Copy imageData into the array, false coloring as we go. */
    _pyCopyToQImage(imageBuffer, width, height);
}
 
static void _pyImagePvCallback(void* cadata, long count, size_t size, void* usr)
{
  ImageBuffer*  imageBuffer = reinterpret_cast<ImageBuffer*>(usr);
  QImage*       image       = imageBuffer->imageDisp;
  const int     width       = image->width();
  const int     height      = image->height();

  if (size != 1 && size != 2 && size != 4) {
    printf("Image pixel size is %d bytes?\n", (int) size);
    return;
  }
  /* Average the new data into imageDataF/imageData */
  switch (size) {
    case 4: {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint32_t* pui32new  = static_cast<uint32_t*>(cadata);

        if (imageBuffer->iNumAveraged == 0) {
            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui32new) {
                *pui32cur = (int) *pui32new;
                *pfcur = *pui32cur;
            }
        } else {
            int             iNewAverage = imageBuffer->iNumAveraged + 1;

            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui32new) {
                *pfcur    += (((int) *pui32new) - *pfcur) / iNewAverage;
                *pui32cur  = (unsigned int) *pfcur;
            }
        }
        break;
    }
    case 2: {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint16_t* pui16new = static_cast<uint16_t*>(cadata);

        if (imageBuffer->iNumAveraged == 0) {
            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui16new) {
                *pui32cur = (int) *pui16new;
                *pfcur = *pui32cur;
            }
        } else {
            int             iNewAverage = imageBuffer->iNumAveraged + 1;

            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui16new) {
                *pfcur    += (((int) *pui16new) - *pfcur) / iNewAverage;
                *pui32cur  = (unsigned int) *pfcur;
            }
        }
        break;
    }
    case 1: {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint8_t*  pui8new  = static_cast<uint8_t*>(cadata);

        if (imageBuffer->iNumAveraged == 0) {
            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui8new) {
                *pui32cur = (int) *pui8new;
                *pfcur = *pui32cur;
            }
        } else {
            int             iNewAverage = imageBuffer->iNumAveraged + 1;
            
            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui8new) {
                *pfcur    += (((int) *pui8new) - *pfcur) / iNewAverage;
                *pui32cur  = (unsigned int) *pfcur;
            }
        }
        break;
    }
  }    
  imageBuffer->iNumAveraged = (imageBuffer->iNumAveraged + 1) % imageBuffer->iAverage;

  /* Copy imageData into the array, false coloring as we go. */
  _pyCopyToQImage(imageBuffer, width, height);
}

PyObject* pyCreateImagePvCallbackFunc(PyObject* pyImageBuffer)
{
  // reinterpret_cast not allowed between func ptr and void* by ISO C++
  void* func        = (void*)_pyImagePvCallback;
  void* imageBuffer = PyCObject_AsVoidPtr( pyImageBuffer );

  //printf( "pyCreateImagePvCallbackFunc(): imagedata %p\n", imageBuffer ); //!!debug
  
  PyObject* pyfunc = PyCObject_FromVoidPtrAndDesc(func, imageBuffer, NULL);    
  return pyfunc;
}        

PyObject* pyCreateColorImagePvCallbackFunc(PyObject* pyImageBuffer)
{
  // reinterpret_cast not allowed between func ptr and void* by ISO C++
  void* func        = (void*)_pyColorImagePvCallback;
  void* imageBuffer = PyCObject_AsVoidPtr( pyImageBuffer );

  //printf( "pyCreateColorImagePvCallbackFunc(): imagedata %p\n", imageBuffer ); //!!debug
  
  PyObject* pyfunc = PyCObject_FromVoidPtrAndDesc(func, imageBuffer, NULL);    
  return pyfunc;
}        

void findMinMax(ImageBuffer* imageBuffer, bool bProjRoi, int xmin, int xmax, int ymin, int ymax)
{
  imageBuffer->iProjXmin = 1<<15;
  imageBuffer->iProjXmax = -1;
  imageBuffer->iProjYmin = 1<<15;
  imageBuffer->iProjYmax = -1;
  
  if ( bProjRoi ) {                  
    for (int iX=xmin; iX < xmax; ++iX) {
      if ( imageBuffer->projSumX[iX] == 0xFFFFFFFF )
        continue;
        
      int iValue = (int) (imageBuffer->projSumX[iX] / imageBuffer->iRoiH);      
      if (iValue < imageBuffer->iProjXmin)
        imageBuffer->iProjXmin = iValue;
      if (iValue > imageBuffer->iProjXmax)
        imageBuffer->iProjXmax = iValue;      
    }
        
    for (int iY=ymin; iY < ymax; ++iY) {
      if ( imageBuffer->projSumY[iY] == 0xFFFFFFFF )
        continue;
        
      int iValue = (int) (imageBuffer->projSumY[iY] / imageBuffer->iRoiW);      
      if (iValue < imageBuffer->iProjYmin)
        imageBuffer->iProjYmin = iValue;
      if (iValue > imageBuffer->iProjYmax)
        imageBuffer->iProjYmax = iValue;
    }        
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

void computeRoiProj(ImageBuffer* imageBuffer, QRectF* rectRoi)
{
  QImage*   imageDisp = imageBuffer->imageDisp;               
  uint32_t* projSumX  = imageBuffer->projSumX;
  uint32_t* projSumY  = imageBuffer->projSumY;
  int width  = (imageBuffer->orientation&2) ? imageDisp->height() : imageDisp->width();
  int height = (imageBuffer->orientation&2) ? imageDisp->width() : imageDisp->height();
  memset(projSumX, 0xFF, width  * sizeof(uint32_t));
  memset(projSumY, 0xFF, height * sizeof(uint32_t));
  
  int x1  = (int) rectRoi->x();
  int x2  = x1 + (int) rectRoi->width() - 1;
  if ( x1 > x2 ) {int xtmp = x1; x1 = x2; x2 = xtmp;}
  if ( x1 < 0 ) x1 = 0;
  else if ( x1 >= width ) x1 = width-1;
  if ( x2 < 0 ) x2 = 0;
  else if ( x2 >= width ) x2 = width-1;    

  int y1  = (int) rectRoi->y();
  int y2  = y1 + (int) rectRoi->height() - 1;
  if ( y1 > y2 ) {int ytmp = y1; y1 = y2; y2 = ytmp;}
  if ( y1 < 0 ) y1 = 0;
  else if ( y1 >= height ) y1 = height-1;
  if ( y2 < 0 ) y2 = 0;
  else if ( y2 >= height ) y2 = height-1;
  
  uint32_t* const pImgValue       = imageBuffer->imageData;
  const int iLinePixelsOrg        = width;
  uint64_t  u64PixelSum           = 0;
  uint64_t  u64PixelSqSum         = 0;
  uint32_t* pPixelLineStart       = pImgValue + y1 * iLinePixelsOrg + x1;

  for (int iY = y1; iY <= y2; ++iY, pPixelLineStart += iLinePixelsOrg) {
    if (iY < 0)
      continue;
    if (iY >= height)
      break;
      
    uint32_t* pPixel = pPixelLineStart;
    for (int iX = x1; iX <= x2; ++iX, ++pPixel)
    {
      if (iX < 0)
        continue;
      if (iX >= width)
        break;
        
      const int iValue = *pPixel;
      if ( iValue >= 0x10000) {
        printf("Pixel value (%d,%d) too large: value 0x%x\n", iX, iY, iValue);
        continue;
      }
      projSumX[iX]  += iValue;
      projSumY[iY]  += iValue;
      u64PixelSum   += iValue;
      /* Sigh... if iValue > 49000 or so, the square of an int will be negative! */
      u64PixelSqSum += iValue*(uint64_t) iValue;
    }
  }
      
  imageBuffer->iRoiW = x2 - x1 + 1;
  imageBuffer->iRoiH = y2 - y1 + 1;
  const float w = imageBuffer->iRoiW;
  const float h = imageBuffer->iRoiH;
  const float fNumRoiPixels = w * h;
  
  //printf("computeRoiProj(): Pixel Sum %Ld  SqSum %Ld  x2 %d x1 %d y2 %d y1 %d NumPixels %f\n",
  //	   (long long int) u64PixelSum, (long long int) u64PixelSqSum, x2, x1, y2, y1, fNumRoiPixels ); // !! for debug
  if ( fNumRoiPixels > 0 ) {
    imageBuffer->fRoiPixelMean = u64PixelSum   / fNumRoiPixels;
    imageBuffer->fRoiPixelVar  = u64PixelSqSum / fNumRoiPixels - imageBuffer->fRoiPixelMean * imageBuffer->fRoiPixelMean;
  } else {
    imageBuffer->fRoiPixelMean  = 0;
    imageBuffer->fRoiPixelVar   = 0;             
  }
}

static void _pyDoProj(uint32_t *pImgProj, int imin, int imax, uint32_t *projSum, int iRoi, 
                      int iScaleIndex, int projmin, int projmax, float scale, uint32_t u32ColorProj,
                      int limit, int offset, int iLineI, int iLineIdx, int dir)
{
    for (int idx=imin; idx < imax; ++idx) {
        if (projSum[idx] == 0xFFFFFFFF)
            continue;
        
        float fValue = projSum[idx] / iRoi;
      
        if (fValue < 0) {
            printf("_pyDoProj(): Invalid ProjSum[%d] : %lf\n", idx, fValue);
            continue;
        }
      
        int iProjValue;
        if (fValue <= projmin)
            iProjValue = limit - 1;
        else if (fValue >= projmax)
            iProjValue = 0;
        else {
            float fIndex;
            switch (iScaleIndex) {
            case 1: /* Log2 */
                fIndex = log2(1 + (fValue - projmin) / scale);
                break;
            case 2: /* LogE */
                fIndex = log(1 + (M_E - 1) * (fValue - projmin) / scale);
                break;
            case 3: /* Log10 */
                fIndex = log10(1 + (10. - 1) * (fValue - projmin) / scale);
                break;
            case 4: /* Exp2 */
                fIndex = (exp2((fValue - projmin) / scale) - 1);
                break;
            case 5: /* ExpE */
                fIndex = (exp((fValue - projmin) / scale) - 1)/(M_E - 1);
                break;
            case 6: /* Exp10 */
                fIndex = (exp10((fValue - projmin) / scale) - 1)/(10. - 1);
                break;
            case 0: /* Linear */
            default:
                fIndex = (fValue - projmin) / scale;
                break;
            }
            iProjValue = (int) ((limit-1) * (1.0 - fIndex));
        }

        for (int i = iProjValue; i < limit; i++)
            *(pImgProj + ( iLineI * i + iLineIdx * (offset + dir * idx) )) = u32ColorProj;
    }
}

/*                    0   0F  90  90F 180 180F 270 270F*/
static int Xdir[8] = { 1, -1, -1,  1, -1,   1,  1,  -1 };
static int Ydir[8] = { 1,  1,  1,  1, -1,  -1, -1,  -1 };

PyObject* pyUpdateProj( PyObject* pyImageBuffer, int iOrientation, int iScaleIndex, 
                        bool bProjRoi, bool bProjAutoRange,
                        unsigned int uMin, unsigned int uMax, 
                        QRectF* rectRoi, QRectF* rectZoom, 
                        QImage* imageProjX, QImage* imageProjY )
{  
    ImageBuffer* imageBuffer = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  
    /*
     * Compute the ROI projection values, and also update the mean/variance
     */
    computeRoiProj(imageBuffer, rectRoi);
  
    QImage*         imageDisp     = imageBuffer->imageDisp;             
    int width  = (imageBuffer->orientation&2) ? imageDisp->height() : imageDisp->width();
    int height = (imageBuffer->orientation&2) ? imageDisp->width() : imageDisp->height();

    const int       xmin      = (int) (rectZoom->x() < 0 ? 0 : rectZoom->x());
    const int       xmax      = (int) (rectZoom->x() + rectZoom->width() > width 
                                       ? width : rectZoom->x() + rectZoom->width());
    const int       ymin      = (int) (rectZoom->y() < 0 ? 0 : rectZoom->y());
    const int       ymax      = (int) (rectZoom->y() + rectZoom->height() > height
                                       ? height : rectZoom->y() + rectZoom->height());
    
    /*
     * Look at the Zoom region to find the min/max values of ProjX/ProjY/ROI
     */
   
    if (bProjAutoRange)
        findMinMax(imageBuffer, bProjRoi, xmin, xmax, ymin, ymax);
    else {
        imageBuffer->iProjXmin = uMin;
        imageBuffer->iProjXmax = uMax;
        imageBuffer->iProjYmin = uMin;
        imageBuffer->iProjYmax = uMax;
    }
  
    const float  fPixelValueRangeX = (float) ( (imageBuffer->iProjXmin != imageBuffer->iProjXmax) ? 
                                               imageBuffer->iProjXmax-imageBuffer->iProjXmin: 1);  
    const float  fPixelValueRangeY = (float) ( (imageBuffer->iProjYmin != imageBuffer->iProjYmax) ? 
                                               imageBuffer->iProjYmax-imageBuffer->iProjYmin: 1);  
  
    int iOffsetX    = ( imageProjX->width()  - width ) /2;
    int iOffsetY    = ( imageProjY->height() - height ) /2;    
  
    const int       iLinePixelsPx   = imageProjX->width();
    const int       iLinePixelsPy   = imageProjY->width();
  
    imageProjX->fill( 0xFFFFFFFF );
    imageProjY->fill( 0xFFFFFFFF );   
    
    const uint32_t  u32ColorProj  = 0xFF00CC00;

    int xd = Xdir[imageBuffer->orientation];
    int yd = Ydir[imageBuffer->orientation];
    if (xd < 0)
        iOffsetX += width - 1;
    if (yd < 0)
        iOffsetY += height - 1;

    if ( bProjRoi ) {
        if (imageBuffer->orientation&2) {
            _pyDoProj((uint32_t*) imageProjY->bits(), xmin, xmax, imageBuffer->projSumX, imageBuffer->iRoiH,
                      iScaleIndex, imageBuffer->iProjXmin, imageBuffer->iProjXmax, fPixelValueRangeX, u32ColorProj, 
                      imageProjY->width(), iOffsetX, 1, iLinePixelsPy, xd);
            _pyDoProj((uint32_t*) imageProjX->bits(), ymin, ymax, imageBuffer->projSumY, imageBuffer->iRoiW,
                      iScaleIndex, imageBuffer->iProjYmin, imageBuffer->iProjYmax, fPixelValueRangeY, u32ColorProj, 
                      imageProjX->height(), iOffsetY, iLinePixelsPx, 1, yd);
        } else {
            _pyDoProj((uint32_t*) imageProjX->bits(), xmin, xmax, imageBuffer->projSumX, imageBuffer->iRoiH,
                      iScaleIndex, imageBuffer->iProjXmin, imageBuffer->iProjXmax, fPixelValueRangeX, u32ColorProj, 
                      imageProjX->height(), iOffsetX, iLinePixelsPx, 1, xd);
            _pyDoProj((uint32_t*) imageProjY->bits(), ymin, ymax, imageBuffer->projSumY, imageBuffer->iRoiW,
                      iScaleIndex, imageBuffer->iProjYmin, imageBuffer->iProjYmax, fPixelValueRangeY, u32ColorProj, 
                      imageProjY->width(), iOffsetY, 1, iLinePixelsPy, yd);
        }
    }

    return Py_BuildValue("ffiiii", imageBuffer->fRoiPixelMean, imageBuffer->fRoiPixelVar, 
                         imageBuffer->iProjXmin, imageBuffer->iProjXmax, imageBuffer->iProjYmin, imageBuffer->iProjYmax);
}
  
PyObject* pyGetPixelValue( PyObject* pyImageBuffer, QPointF* cursor, QPointF* marker1, QPointF* marker2, 
  QPointF* marker3, QPointF* marker4)
{
  ImageBuffer* imageBuffer = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  uint32_t*    pImgValue   = (uint32_t*) imageBuffer->imageData;     
  QImage*      imageDisp   = imageBuffer->imageDisp;           
  int orientation = imageBuffer->orientation;
  int srcwidth  = (orientation&2) ? imageDisp->height() : imageDisp->width();
  int srcheight = (orientation&2) ? imageDisp->width() : imageDisp->height();
  
  uint32_t     u32ValueCursor;
  if (cursor->x() < 0 || cursor->x() >= srcwidth || cursor->y() < 0 || cursor->y() >= srcheight)
    u32ValueCursor = -1;
  else
    u32ValueCursor = pImgValue[ (int) cursor->y() * srcwidth + (int) cursor->x() ];    

  uint32_t     u32Value1;
  if (marker1->x() < 0 || marker1->x() >= srcwidth || marker1->y() < 0 || marker1->y() >= srcheight)
    u32Value1 = -1;
  else
    u32Value1 = pImgValue[ (int) marker1->y() * srcwidth + (int) marker1->x() ];    

  uint32_t     u32Value2;
  if (marker2->x() < 0 || marker2->x() >= srcwidth || marker2->y() < 0 || marker2->y() >= srcheight)
    u32Value2 = -1;
  else
    u32Value2 = pImgValue[ (int) marker2->y() * srcwidth + (int) marker2->x() ];    

  uint32_t     u32Value3;
  if (marker3->x() < 0 || marker3->x() >= srcwidth || marker3->y() < 0 || marker3->y() >= srcheight)
    u32Value3 = -1;
  else
    u32Value3 = pImgValue[ (int) marker3->y() * srcwidth + (int) marker3->x() ];    

  uint32_t     u32Value4;
  if (marker4->x() < 0 || marker4->x() >= srcwidth || marker4->y() < 0 || marker4->y() >= srcheight)
    u32Value4 = -1;
  else
    u32Value4 = pImgValue[ (int) marker4->y() * srcwidth + (int) marker4->x() ];    
    
  return Py_BuildValue("iiiiii", u32ValueCursor, u32Value1, u32Value2, u32Value3, u32Value4, 
                       (imageBuffer->iNumAveraged == 0 ? 1 : imageBuffer->iNumAveraged));
}

PyObject* pySetFrameAverage(int iAverage, PyObject* pyImageBuffer)
{
  if ( iAverage == 0 )
    iAverage = 1;
    
  ImageBuffer* imageBuffer  = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  
  if ( iAverage != imageBuffer->iAverage )
    imageBuffer->iAverage = iAverage;
  imageBuffer->iNumAveraged = 0;
  
  Py_RETURN_NONE;
}

PyObject* pyGetImageData( PyObject* pyImageBuffer, bool bPortrait )
{
  ImageBuffer*    imageBuffer  = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );    
  const int       iWidth       = imageBuffer->imageDisp->width();
  const int       iHeight      = imageBuffer->imageDisp->height(); 
  const int       iNumPixels   = iWidth * iHeight;    
  PyObject*       pyImageData  = PyTuple_New(iNumPixels);
  
  if ( bPortrait )
  {
    const uint32_t* pImageDataLine  = imageBuffer->imageData + iWidth * (iHeight-1);
    int             iPixel          = 0;
    for (int iX=0; iX < iWidth; ++iX, ++pImageDataLine) 
    {
      const uint32_t* pImageData = pImageDataLine;
      for (int iY=0; iY < iHeight; ++iY, ++iPixel, pImageData -= iWidth) 
        PyTuple_SetItem(pyImageData, iPixel, PyInt_FromLong(*pImageData));
    }
  }
  else
  {
    const uint32_t* pImageData  = imageBuffer->imageData;           
    for (int iPixel=0; iPixel<iNumPixels; iPixel++, ++pImageData) 
      PyTuple_SetItem(pyImageData, iPixel, PyInt_FromLong(*pImageData));
  }
  
  return pyImageData;
}

PyObject* pyGetImageData8bit( PyObject* pyImageBuffer, bool bPortrait, int depth )
{
  ImageBuffer*    imageBuffer  = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );    
  const int       iWidth       = imageBuffer->imageDisp->width();
  const int       iHeight      = imageBuffer->imageDisp->height(); 
  const int       iNumPixels   = iWidth * iHeight;
  const int       max_index1   = (1 << depth);
  PyObject*       pyImageData  = PyTuple_New(iNumPixels);
  
  if ( bPortrait )
  {
    const uint32_t* pImageDataLine  = imageBuffer->imageData + iWidth * (iHeight-1);
    int             iPixel          = 0;
    for (int iX=0; iX < iWidth; ++iX, ++pImageDataLine) 
    {
      const uint32_t* pImageData = pImageDataLine;
      for (int iY=0; iY < iHeight; ++iY, ++iPixel, pImageData -= iWidth) 
        PyTuple_SetItem(pyImageData, iPixel, PyInt_FromLong(*pImageData * 256/max_index1));
    }
  }
  else
  {
    const uint32_t* pImageData  = imageBuffer->imageData;           
    for (int iPixel=0; iPixel<iNumPixels; iPixel++, ++pImageData) 
      PyTuple_SetItem(pyImageData, iPixel, PyInt_FromLong(*pImageData * 256/max_index1));
  }
  
  return pyImageData;
}  

PyObject* pySaveRawImageData( PyObject* pyImageBuffer, bool bPortrait, const char* sFileName)
{
  ImageBuffer*    imageBuffer  = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  const int       iWidth       = imageBuffer->imageDisp->width();
  const int       iHeight      = imageBuffer->imageDisp->height(); 
  const int       iNumPixels   = iWidth * iHeight;    

  uint16_t*       pu16Data      = (uint16_t*) malloc( iNumPixels * sizeof(uint16_t));     
            
  if ( bPortrait )
  {
    uint16_t*       pu16DataUpdate  = pu16Data;
    const uint32_t* pImageDataLine  = imageBuffer->imageData + iWidth * (iHeight-1);
    for (int iX=0; iX < iWidth; ++iX, ++pImageDataLine) 
    {
      const uint32_t* pImageData = pImageDataLine;
      for (int iY=0; iY < iHeight; ++iY, ++pu16DataUpdate, pImageData -= iWidth) 
        *pu16DataUpdate = * (uint16_t*) pImageData;
    }
  }
  else
  {
    const uint32_t* pu32ImageData   = imageBuffer->imageData;     
    uint16_t*       pu16DataUpdate  = pu16Data;
    for (int iPixel=0; iPixel<iNumPixels; iPixel++, ++pu32ImageData, ++pu16DataUpdate) 
      *pu16DataUpdate = * (uint16_t*) pu32ImageData;      
  }
    
    
  int fd = open(sFileName, O_CREAT | O_WRONLY | O_TRUNC, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
  if (fd == -1)
    Py_RETURN_FALSE;
    
  write(fd, pu16Data, iNumPixels * sizeof(uint16_t));
  close(fd);
  Py_RETURN_TRUE;
}

} // extern "C"


%End

void pydspl_setup_color_map(const char* colormap, int iLimitLow, int iLimitHigh, int iScaleIndex);
void pydspl_setup_gray(int iLimitLow, int iLimitHigh, int iScaleIndex);
SIP_PYOBJECT pyCreateImagePvCallbackFunc(SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyCreateColorImagePvCallbackFunc(SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyCreateImageBuffer(QImage* imageDisp, int orientation);
SIP_PYOBJECT pySetImageBufferGray(SIP_PYOBJECT pyImageBuffer, int gray);
SIP_PYOBJECT pyRecolorImageBuffer(SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyUpdateProj       (SIP_PYOBJECT pyImageBuffer, int iOrientation, int iScaleIndex,
                                  bool bProjRoi, bool bProjAutoRange,
                                  int uMin, int uMax, QRectF* rectRoi, QRectF* rectZoom,
                                  QImage* imageProjX, QImage* imageProjY ); 
SIP_PYOBJECT pyGetPixelValue    (SIP_PYOBJECT pyImageBuffer, QPointF* cursor, 
                                  QPointF* marker1, QPointF* marker2, 
                                  QPointF* marker3, QPointF* marker4);
SIP_PYOBJECT pySetFrameAverage  (int iAverage, SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyGetImageData     (SIP_PYOBJECT pyImageBuffer, bool bPortrait);
SIP_PYOBJECT pyGetImageData8bit (SIP_PYOBJECT pyImageBuffer, bool bPortrait, int depth);
SIP_PYOBJECT pySaveRawImageData (SIP_PYOBJECT pyImageBuffer, bool bPortrait, const char* sFileName);
