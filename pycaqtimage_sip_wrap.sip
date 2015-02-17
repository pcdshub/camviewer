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
static int                  giSyntheticData  = 0;

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
    if ( iScaleIndex == 0 )
      u8Gray = (i - iLimitLow) * 255 / iLimitRange;
    else if ( iScaleIndex == 1 )
      u8Gray = (int) ( log2( 1 + (i - iLimitLow) / fLimitRange) * 255 + 0.5);
    else
      u8Gray = (int) ( (exp2( (i - iLimitLow) / fLimitRange) -1 ) * 255 + 0.5);
          
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
  uint32_t* circBuffer;
  int       iAverage;
  int       iNumAveraged;
  int       iFrameIndex;

  int       useGray;
};

static void _pyFreeImageBuffer(void* buffer)
{
  ImageBuffer* imageBuffer = (ImageBuffer*) buffer;

#if 0
  /*
   * When we change resolutions, we free the image and the imagebuffer,
   * but there is a race condition, since we don't know what python will free first.
   * If the image goes, this segfaults.  So let's not bother with it.
   */
  printf( "_pyFreeImageBuffer(): imageBuffer obj %p : imageDisp %p  data %p %p width %d height %d byte %d\n",
    imageBuffer, imageBuffer->imageDisp, imageBuffer->imageData, imageBuffer->imageDataF, 
    imageBuffer->imageDisp->width(), imageBuffer->imageDisp->height(), imageBuffer->imageDisp->byteCount() ); //!!debug
#endif
    
  free( imageBuffer->imageData   );
  free( imageBuffer->imageDataF  );
  free( imageBuffer->circBuffer  );
  free( imageBuffer->projSumX    );
  free( imageBuffer->projSumY    );
}  

PyObject* pyCreateImageBuffer(QImage* imageDisp, int iSyntheticData)
{
  if (imageDisp == NULL)
    Py_RETURN_NONE;

  giSyntheticData          = iSyntheticData;

  ImageBuffer* imageBuffer = (ImageBuffer*) malloc(sizeof(ImageBuffer));
  imageBuffer->imageDisp   = imageDisp;
  imageBuffer->circBuffer  = NULL;
  imageBuffer->imageData   = (uint32_t*) malloc( imageDisp->width () * imageDisp->height() * sizeof(uint32_t) );
  imageBuffer->imageDataF  = (float*)    malloc( imageDisp->width () * imageDisp->height() * sizeof(float) );
  imageBuffer->projSumX    = (uint32_t*) malloc( imageDisp->width () * sizeof(uint32_t) );
  imageBuffer->projSumY    = (uint32_t*) malloc( imageDisp->height() * sizeof(uint32_t) );
  imageBuffer->iAverage    = 1;
  imageBuffer->iNumAveraged= 0;
  imageBuffer->iFrameIndex = 0;
  imageBuffer->useGray     = 0;
  
  memset(imageBuffer->imageData, 0, imageDisp->width () * imageDisp->height() * sizeof(uint32_t) );
  memset(imageBuffer->imageDataF, 0, imageDisp->width () * imageDisp->height() * sizeof(float) );
  memset(imageBuffer->projSumX, 0, imageDisp->width () * sizeof(uint32_t) );
  memset(imageBuffer->projSumY, 0, imageDisp->height() * sizeof(uint32_t) );

#if 0
  printf( "pyCreateImageBuffer(): imageBuffer obj %p : imageDisp %p  data %p %p width %d height %d byte %d\n",
    imageBuffer, imageBuffer->imageDisp, imageBuffer->imageData, imageBuffer->imageDataF,
    imageBuffer->imageDisp->width(), imageBuffer->imageDisp->height(), imageBuffer->imageDisp->byteCount() ); //!!debug
#endif
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
  if ( imageBuffer->useGray || (imageBuffer->iAverage != 0 && imageBuffer->iAverage != 1) ) {
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

/*
 * For a color image, we handle averaging using the RGB total to convert to greyscale.
 */
#define GRAY(rgb) ((rgb)[0] + (rgb)[1] + (rgb)[2])
#define RGB(rgb)  (ALPHA_VALUE | ((rgb)[0] << 16) | ((rgb)[1] << 8) | (rgb)[2])
static void _pyColorImagePvCallback(void* cadata, long count, size_t size, void* usr)
{
    ImageBuffer*  imageBuffer = reinterpret_cast<ImageBuffer*>(usr);
    QImage*       image       = imageBuffer->imageDisp;
    const int     width       = image->width();
    const int     height      = image->height();

    uint8_t* cadata8 = static_cast<uint8_t*>(cadata); /* R, G, B! */

    if ( imageBuffer->iAverage == 0 || imageBuffer->iAverage == 1 ) {
        const uint8_t*  pui8new  = cadata8;

        for (int iPixel = 0; iPixel < width*height; ++iPixel, pui8new += 3)
            imageBuffer->imageData[iPixel] = GRAY(pui8new);
    } else if ( imageBuffer->iAverage == -1 ) {
        float*          pfcur    = imageBuffer->imageDataF;      
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint8_t*  pui8new  = cadata8;
        const int       iNewAverage = imageBuffer->iNumAveraged + 1;
      
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, pui8new += 3) {
            *pfcur    += (GRAY(pui8new) - *pfcur) / iNewAverage;
            *pui32cur  = (unsigned int) *pfcur;
        }
      
        imageBuffer->iNumAveraged = iNewAverage;
    } else {           
        uint32_t* pui32update = imageBuffer->circBuffer + width * height * imageBuffer->iFrameIndex;
        //printf("avg %d/%d org f %f i %d  new %d old %d ", imageBuffer->iNumAveraged, imageBuffer->iAverage,
        //  *imageBuffer->imageDataF, *imageBuffer->imageData, *cadata8, *pui32update );
        
        if ( imageBuffer->iNumAveraged == 0 ) {
            const uint8_t*  pui8new  = cadata8;
            float*          pfcur    = imageBuffer->imageDataF;

            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, pui8new += 3) {
                imageBuffer->imageData[iPixel] = GRAY(pui8new);
                *pfcur = GRAY(pui8new);
            }
             
            pui8new = cadata8;
        
            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, pui8new += 3)
        
            imageBuffer->iNumAveraged = 1;
        } else if ( imageBuffer->iNumAveraged < imageBuffer->iAverage ) {
            float*          pfcur    = imageBuffer->imageDataF;
            uint32_t*       pui32cur = imageBuffer->imageData;      
            const uint8_t*  pui8new = cadata8;
            const int       iNewAverage = imageBuffer->iNumAveraged + 1;
        
            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, pui8new += 3) {
                *pfcur    += (GRAY(pui8new) - *pfcur) / iNewAverage;
                *pui32cur  = (unsigned int) *pfcur;
            }
        
            imageBuffer->iNumAveraged = iNewAverage;
        } else {
            float*          pfcur    = imageBuffer->imageDataF;
            uint32_t*       pui32cur = imageBuffer->imageData;
            const uint8_t*  pui8new  = cadata8;
            const uint32_t* pui32old = pui32update;
            const int       iAverage = imageBuffer->iAverage;
                      
            for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, pui8new += 3, ++pui32old) {
                *pfcur    += (GRAY(pui8new) - (float) *pui32old) / iAverage;
                *pui32cur  = (unsigned int) *pfcur;
            }
        }
  
        //printf(" updated f %f i %d\n", *imageBuffer->imageDataF, *imageBuffer->imageData);
        {
            const uint8_t*  pui8new  = cadata8;
        
            for (int iPixel = 0; iPixel < width*height; ++iPixel, pui8new += 3) 
                pui32update[iPixel] = GRAY(pui8new);
        }
        imageBuffer->iFrameIndex = ( imageBuffer->iFrameIndex + 1 ) % imageBuffer->iAverage;      
    }

    if ( !imageBuffer->useGray && (imageBuffer->iAverage == 0 || imageBuffer->iAverage == 1) ) {
        const uint8_t*  pui8new  = cadata8;
        uint32_t*       data       = reinterpret_cast<uint32_t*>(image->bits());
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++data, pui8new += 3)
            *data = RGB(pui8new);
    } else {
        const uint32_t* pui32Pixel = (const uint32_t*) imageBuffer->imageData;
        uint32_t*       data       = reinterpret_cast<uint32_t*>(image->bits());
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++data, ++pui32Pixel)
            *data = (*pui32Pixel < MAX_INDEX_PLUS1) ? gColorMap[*pui32Pixel] : 0;
    }
}

static void _pyImagePvCallback(void* cadata, long count, size_t size, void* usr)
{
  ImageBuffer*  imageBuffer = reinterpret_cast<ImageBuffer*>(usr);
  QImage*       image       = imageBuffer->imageDisp;
  const int     width       = image->width();
  const int     height      = image->height();

  //printf( "_pyImagePvCallback(): imageBuffer obj %p : imageDisp %p  data %p  width %d height %d byte %d\n"
  //  "    cirBuf %p avg %d num_avged %d frmIdx %d\n",
  //  imageBuffer, imageBuffer->imageDisp, imageBuffer->imageData, 
  //  imageBuffer->imageDisp->width(), imageBuffer->imageDisp->height(), imageBuffer->imageDisp->byteCount(),
  //  imageBuffer->circBuffer, imageBuffer->iAverage, imageBuffer->iNumAveraged, imageBuffer->iFrameIndex); //!!debug
  if (size != 1 && size != 2 && size != 4) {
    printf("Image pixel size is %d bytes?\n", (int) size);
    return;
  }
  switch (size) {
    case 4: {
    uint32_t* cadata32 = static_cast<uint32_t*>(cadata);
    
    //!!debug: use any other pv (other than pulnix camera), and generate random values
    if (giSyntheticData)
    {
      uint32_t* pui32Pixel = (uint32_t*) cadata32;
      for (int iY = 0; iY < height; ++iY)
      {
        for (int iX = 0; iX < width; ++iX, ++pui32Pixel)
        {
          //int32_t iValue = (uint32_t) (MAX_INDEX_PLUS1 * (rand() / (RAND_MAX + 1.0)));         
          //int32_t iValue = (uint32_t) (iX + iY);
          int32_t iValue = (int32_t) (MAX_INDEX_PLUS1 * exp(- 3*((iX-320)*(iX-320) / 102400.0 + (iY-240)*(iY-240)/57600.0)) +
            MAX_INDEX_PLUS1 * 0.05 * (rand() / (RAND_MAX + 1.0)) - MAX_INDEX_PLUS1 * 0.025);
          
          if ( iValue < 0 )
            *pui32Pixel = 0;
          else if (iValue >= (int) MAX_INDEX_PLUS1)
            *pui32Pixel = MAX_INDEX_PLUS1-1;
          else
            *pui32Pixel = iValue;
        }   
      }
    }    
    
    const int iNumFrameBytes = width * height * sizeof(uint32_t);
    
    if ( imageBuffer->iAverage == 0 || imageBuffer->iAverage == 1 )
      memcpy( imageBuffer->imageData, cadata32, iNumFrameBytes );
    else if ( imageBuffer->iAverage == -1 )
    {
      float*          pfcur    = imageBuffer->imageDataF;      
      uint32_t*       pui32cur = imageBuffer->imageData;      
      const uint32_t* pui32new = cadata32;
      const int       iNewAverage = imageBuffer->iNumAveraged + 1;
      
      for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui32new)
      {
        *pfcur    += (*pui32new - *pfcur) / iNewAverage;
        *pui32cur  = (unsigned int) *pfcur;
      }
      
      imageBuffer->iNumAveraged = iNewAverage;
    }
    else
    {           
      uint32_t* pui32update = imageBuffer->circBuffer + width * height * imageBuffer->iFrameIndex;
      //printf("avg %d/%d org f %f i %d  new %d old %d ", imageBuffer->iNumAveraged, imageBuffer->iAverage,
      //  *imageBuffer->imageDataF, *imageBuffer->imageData, *cadata32, *pui32update );
        
      if ( imageBuffer->iNumAveraged == 0 )
      {
        memcpy( imageBuffer->imageData, cadata32, iNumFrameBytes );
        
        float*          pfcur    = imageBuffer->imageDataF;
        const uint32_t* pui32new = cadata32;
        
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32new)
          *pfcur = *pui32new;
        
        imageBuffer->iNumAveraged = 1;
      }
      else if ( imageBuffer->iNumAveraged < imageBuffer->iAverage )
      {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint32_t* pui32new = cadata32;
        const int       iNewAverage = imageBuffer->iNumAveraged + 1;
        
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui32new)
        {
          *pfcur    += (*pui32new - *pfcur) / iNewAverage;
          *pui32cur  = (unsigned int) *pfcur;
        }
        
        imageBuffer->iNumAveraged = iNewAverage;
      }
      else
      {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;
        const uint32_t* pui32new = cadata32;
        const uint32_t* pui32old = pui32update;
        const int       iAverage = imageBuffer->iAverage;
                      
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui32new, ++pui32old)
        {
          *pfcur    += (*pui32new - (float) *pui32old) / iAverage;
          *pui32cur  = (unsigned int) *pfcur;
        }
      }
  
      //printf(" updated f %f i %d\n", *imageBuffer->imageDataF, *imageBuffer->imageData);
        
      memcpy( pui32update, cadata32, iNumFrameBytes );        
      imageBuffer->iFrameIndex = ( imageBuffer->iFrameIndex + 1 ) % imageBuffer->iAverage;      
    }
    
    //const uint32_t* pui32Pixel = (uint32_t*) cadata32;
    //for (int iY = 0; iY < height; ++iY)
    //{
    //  for (int iX = 0; iX < width; ++iX, ++pui32Pixel)
    //  {      
    //    if (*pui32Pixel < imageBuffer->iFrameMin)
    //      imageBuffer->iFrameMin = *pui32Pixel;
    //    if (*pui32Pixel < imageBuffer->iFrameMax)
    //      imageBuffer->iFrameMax = *pui32Pixel;        
    //  }       
    //}  
    
    const uint32_t* pui32Pixel = (const uint32_t*) imageBuffer->imageData;
    uint32_t*       data       = reinterpret_cast<uint32_t*>(image->bits());    
    
    for (int iPixel = 0; iPixel < width*height; ++iPixel, ++data, ++pui32Pixel)
      *data = (*pui32Pixel < MAX_INDEX_PLUS1) ? gColorMap[*pui32Pixel] : 0;
    break;
    }
    case 2: {
    uint16_t* cadata16 = static_cast<uint16_t*>(cadata);
    
    //!!debug: use any other pv (other than pulnix camera), and generate random values
    if (giSyntheticData)
    {
      uint16_t* pui16Pixel = (uint16_t*) cadata16;
      for (int iY = 0; iY < height; ++iY)
      {
        for (int iX = 0; iX < width; ++iX, ++pui16Pixel)
        {
          //int32_t iValue = (uint32_t) (MAX_INDEX_PLUS1 * (rand() / (RAND_MAX + 1.0)));         
          //int32_t iValue = (uint32_t) (iX + iY);
          int32_t iValue = (int32_t) (MAX_INDEX_PLUS1 * exp(- 3*((iX-320)*(iX-320) / 102400.0 + (iY-240)*(iY-240)/57600.0)) +
            MAX_INDEX_PLUS1 * 0.05 * (rand() / (RAND_MAX + 1.0)) - MAX_INDEX_PLUS1 * 0.025);
          
          if ( iValue < 0 )
            *pui16Pixel = 0;
          else if (iValue >= (int) MAX_INDEX_PLUS1)
            *pui16Pixel = MAX_INDEX_PLUS1-1;
          else
            *pui16Pixel = iValue;
        }   
      }
    }    
    
    if ( imageBuffer->iAverage == 0 || imageBuffer->iAverage == 1 ) {
      for (int iPixel = 0; iPixel < width*height; ++iPixel) 
        imageBuffer->imageData[iPixel] = cadata16[iPixel]; 
    } else if ( imageBuffer->iAverage == -1 )
    {
      float*          pfcur    = imageBuffer->imageDataF;      
      uint32_t*       pui32cur = imageBuffer->imageData;      
      const uint16_t* pui16new = cadata16;
      const int       iNewAverage = imageBuffer->iNumAveraged + 1;
      
      for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui16new)
      {
        *pfcur    += (*pui16new - *pfcur) / iNewAverage;
        *pui32cur  = (unsigned int) *pfcur;
      }
      
      imageBuffer->iNumAveraged = iNewAverage;
    }
    else
    {           
      uint32_t* pui32update = imageBuffer->circBuffer + width * height * imageBuffer->iFrameIndex;
      //printf("avg %d/%d org f %f i %d  new %d old %d ", imageBuffer->iNumAveraged, imageBuffer->iAverage,
      //  *imageBuffer->imageDataF, *imageBuffer->imageData, *cadata16, *pui32update );
        
      if ( imageBuffer->iNumAveraged == 0 )
      {
        for (int iPixel = 0; iPixel < width*height; ++iPixel) 
          imageBuffer->imageData[iPixel] = cadata16[iPixel];
             
        float*          pfcur    = imageBuffer->imageDataF;
        const uint16_t* pui16new = cadata16;
        
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui16new)
          *pfcur = *pui16new;
        
        imageBuffer->iNumAveraged = 1;
      }
      else if ( imageBuffer->iNumAveraged < imageBuffer->iAverage )
      {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint16_t* pui16new = cadata16;
        const int       iNewAverage = imageBuffer->iNumAveraged + 1;
        
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui16new)
        {
          *pfcur    += (*pui16new - *pfcur) / iNewAverage;
          *pui32cur  = (unsigned int) *pfcur;
        }
        
        imageBuffer->iNumAveraged = iNewAverage;
      }
      else
      {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;
        const uint16_t* pui16new = cadata16;
        const uint32_t* pui32old = pui32update;
        const int       iAverage = imageBuffer->iAverage;
                      
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui16new, ++pui32old)
        {
          *pfcur    += (*pui16new - (float) *pui32old) / iAverage;
          *pui32cur  = (unsigned int) *pfcur;
        }
      }
  
      //printf(" updated f %f i %d\n", *imageBuffer->imageDataF, *imageBuffer->imageData);
        
      for (int iPixel = 0; iPixel < width*height; ++iPixel) 
        pui32update[iPixel] = cadata16[iPixel];
      imageBuffer->iFrameIndex = ( imageBuffer->iFrameIndex + 1 ) % imageBuffer->iAverage;      
    }
    
    //const uint16_t* pui16Pixel = (uint16_t*) cadata16;
    //for (int iY = 0; iY < height; ++iY)
    //{
    //  for (int iX = 0; iX < width; ++iX, ++pui32Pixel)
    //  {      
    //    if (*pui32Pixel < imageBuffer->iFrameMin)
    //      imageBuffer->iFrameMin = *pui32Pixel;
    //    if (*pui32Pixel < imageBuffer->iFrameMax)
    //      imageBuffer->iFrameMax = *pui32Pixel;        
    //  }       
    //}  
    
    const uint32_t* pui32Pixel = (const uint32_t*) imageBuffer->imageData;
    uint32_t*       data       = reinterpret_cast<uint32_t*>(image->bits());    
    
    for (int iPixel = 0; iPixel < width*height; ++iPixel, ++data, ++pui32Pixel)
      *data = (*pui32Pixel < MAX_INDEX_PLUS1) ? gColorMap[*pui32Pixel] : 0;      
    break;
    }
    case 1: {
    uint8_t* cadata8 = static_cast<uint8_t*>(cadata);
    
    //!!debug: use any other pv (other than pulnix camera), and generate random values
    if (giSyntheticData)
    {
      uint8_t* pui8Pixel = (uint8_t*) cadata8;
      for (int iY = 0; iY < height; ++iY)
      {
        for (int iX = 0; iX < width; ++iX, ++pui8Pixel)
        {
          //int32_t iValue = (uint32_t) (MAX_INDEX_PLUS1 * (rand() / (RAND_MAX + 1.0)));         
          //int32_t iValue = (uint32_t) (iX + iY);
          int32_t iValue = (int32_t) (MAX_INDEX_PLUS1 * exp(- 3*((iX-320)*(iX-320) / 102400.0 + (iY-240)*(iY-240)/57600.0)) +
            MAX_INDEX_PLUS1 * 0.05 * (rand() / (RAND_MAX + 1.0)) - MAX_INDEX_PLUS1 * 0.025);
          
          if ( iValue < 0 )
            *pui8Pixel = 0;
          else if (iValue >= (int) MAX_INDEX_PLUS1)
            *pui8Pixel = 255; /* ??? MAX_INDEX_PLUS1-1; */
          else
            *pui8Pixel = iValue;
        }   
      }
    }    
    
    if ( imageBuffer->iAverage == 0 || imageBuffer->iAverage == 1 ) {
      for (int iPixel = 0; iPixel < width*height; ++iPixel) 
        imageBuffer->imageData[iPixel] = cadata8[iPixel]; 
    } else if ( imageBuffer->iAverage == -1 )
    {
      float*          pfcur    = imageBuffer->imageDataF;      
      uint32_t*       pui32cur = imageBuffer->imageData;      
      const uint8_t*  pui8new  = cadata8;
      const int       iNewAverage = imageBuffer->iNumAveraged + 1;
      
      for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui8new)
      {
        *pfcur    += (*pui8new - *pfcur) / iNewAverage;
        *pui32cur  = (unsigned int) *pfcur;
      }
      
      imageBuffer->iNumAveraged = iNewAverage;
    }
    else
    {           
      uint32_t* pui32update = imageBuffer->circBuffer + width * height * imageBuffer->iFrameIndex;
      //printf("avg %d/%d org f %f i %d  new %d old %d ", imageBuffer->iNumAveraged, imageBuffer->iAverage,
      //  *imageBuffer->imageDataF, *imageBuffer->imageData, *cadata8, *pui32update );
        
      if ( imageBuffer->iNumAveraged == 0 )
      {
        for (int iPixel = 0; iPixel < width*height; ++iPixel) 
          imageBuffer->imageData[iPixel] = cadata8[iPixel];
             
        float*          pfcur    = imageBuffer->imageDataF;
        const uint8_t*  pui8new = cadata8;
        
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui8new)
          *pfcur = *pui8new;
        
        imageBuffer->iNumAveraged = 1;
      }
      else if ( imageBuffer->iNumAveraged < imageBuffer->iAverage )
      {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;      
        const uint8_t*  pui8new = cadata8;
        const int       iNewAverage = imageBuffer->iNumAveraged + 1;
        
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui8new)
        {
          *pfcur    += (*pui8new - *pfcur) / iNewAverage;
          *pui32cur  = (unsigned int) *pfcur;
        }
        
        imageBuffer->iNumAveraged = iNewAverage;
      }
      else
      {
        float*          pfcur    = imageBuffer->imageDataF;
        uint32_t*       pui32cur = imageBuffer->imageData;
        const uint8_t*  pui8new  = cadata8;
        const uint32_t* pui32old = pui32update;
        const int       iAverage = imageBuffer->iAverage;
                      
        for (int iPixel = 0; iPixel < width*height; ++iPixel, ++pfcur, ++pui32cur, ++pui8new, ++pui32old)
        {
          *pfcur    += (*pui8new - (float) *pui32old) / iAverage;
          *pui32cur  = (unsigned int) *pfcur;
        }
      }
  
      //printf(" updated f %f i %d\n", *imageBuffer->imageDataF, *imageBuffer->imageData);
        
      for (int iPixel = 0; iPixel < width*height; ++iPixel) 
        pui32update[iPixel] = cadata8[iPixel];
      imageBuffer->iFrameIndex = ( imageBuffer->iFrameIndex + 1 ) % imageBuffer->iAverage;      
    }
    
    //const uint8_t* pui8Pixel = (uint16_t*) cadata8;
    //for (int iY = 0; iY < height; ++iY)
    //{
    //  for (int iX = 0; iX < width; ++iX, ++pui32Pixel)
    //  {      
    //    if (*pui32Pixel < imageBuffer->iFrameMin)
    //      imageBuffer->iFrameMin = *pui32Pixel;
    //    if (*pui32Pixel < imageBuffer->iFrameMax)
    //      imageBuffer->iFrameMax = *pui32Pixel;        
    //  }       
    //}  
    
    const uint32_t* pui32Pixel = (const uint32_t*) imageBuffer->imageData;
    uint32_t*       data       = reinterpret_cast<uint32_t*>(image->bits());    
    
    for (int iPixel = 0; iPixel < width*height; ++iPixel, ++data, ++pui32Pixel)
      *data = (*pui32Pixel < MAX_INDEX_PLUS1) ? gColorMap[*pui32Pixel] : 0;   
    }
    break;
  }
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

void findMinMax(ImageBuffer* imageBuffer, const bool lbProjLine[4], bool bProjRoi, const QPointF* lptMarker[4], int xmin, int xmax, int ymin, int ymax)
{
  QImage*         imageDisp       = imageBuffer->imageDisp;       
  uint32_t* const pImgValue       = imageBuffer->imageData;     
  const int       iLinePixelsOrg  = imageDisp->width();
  
  imageBuffer->iProjXmin = 1<<15;
  imageBuffer->iProjXmax = -1;
  imageBuffer->iProjYmin = 1<<15;
  imageBuffer->iProjYmax = -1;
 
  for (int iProj = 0; iProj < 4; ++iProj)
  {
    if ( lbProjLine[iProj] )
    {    
      const int iProjX = (int) (lptMarker[iProj]->x());
      const int iProjY = (int) (lptMarker[iProj]->y());  
      
      if ( iProjY >= 0 && iProjY < imageDisp->height() )
      {
        for (int iX=xmin; iX < xmax; ++iX)
        {
          int iValue   = *(pImgValue + ( iLinePixelsOrg * iProjY + iX ));        
          
          if (iValue < imageBuffer->iProjXmin)
            imageBuffer->iProjXmin = iValue;
          if (iValue > imageBuffer->iProjXmax)
            imageBuffer->iProjXmax = iValue;
        }
      }
      
      if ( iProjX >= 0 && iProjX < imageDisp->width() )
      {
        for (int iY=ymin; iY < ymax; ++iY)
        {
          int iValue = *(pImgValue + ( iLinePixelsOrg * iY + iProjX ));
                
          if (iValue < imageBuffer->iProjYmin)
            imageBuffer->iProjYmin = iValue;
          if (iValue > imageBuffer->iProjYmax)
            imageBuffer->iProjYmax = iValue;
        }
      }    
    } // if ( bProjLine )
  } // for (int iProj = 0; iProj < 4; ++iProj)  
  
  
  if ( bProjRoi )
  {                  
    for (int iX=xmin; iX < xmax; ++iX)
    {
      if ( imageBuffer->projSumX[iX] == 0xFFFFFFFF )
        continue;
        
      int iValue = (int) (imageBuffer->projSumX[iX] / imageBuffer->iRoiH);      
      if (iValue < imageBuffer->iProjXmin)
        imageBuffer->iProjXmin = iValue;
      if (iValue > imageBuffer->iProjXmax)
        imageBuffer->iProjXmax = iValue;      
    }
        
    for (int iY=ymin; iY < ymax; ++iY)
    {
      if ( imageBuffer->projSumY[iY] == 0xFFFFFFFF )
        continue;
        
      int iValue = (int) (imageBuffer->projSumY[iY] / imageBuffer->iRoiW);      
      if (iValue < imageBuffer->iProjYmin)
        imageBuffer->iProjYmin = iValue;
      if (iValue > imageBuffer->iProjYmax)
        imageBuffer->iProjYmax = iValue;
    }        
  }
  
  if ( imageBuffer->iProjXmax == -1 )
  {
    imageBuffer->iProjXmin = 0;
    imageBuffer->iProjXmax = 1;
  }
  else
  {
    if ( imageBuffer->iProjXmin > 0 )
      --imageBuffer->iProjXmin;
    ++imageBuffer->iProjXmax;
  }

  if ( imageBuffer->iProjYmax == -1 )
  {
    imageBuffer->iProjYmin = 0;
    imageBuffer->iProjYmax = 1;
  }  
  else
  {
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
  memset(projSumX, 0xFF, imageDisp->width () * sizeof(uint32_t));
  memset(projSumY, 0xFF, imageDisp->height() * sizeof(uint32_t));
  
  
  int x1  = (int) rectRoi->x();
  int x2  = x1 + (int) rectRoi->width() - 1;
  if ( x1 > x2 ) {int xtmp = x1; x1 = x2; x2 = xtmp;}
  if ( x1 < 0 ) x1 = 0;
  else if ( x1 >= imageDisp->width() ) x1 = imageDisp->width()-1;
  if ( x2 < 0 ) x2 = 0;
  else if ( x2 >= imageDisp->width() ) x2 = imageDisp->width()-1;    

  int y1  = (int) rectRoi->y();
  int y2  = y1 + (int) rectRoi->height() - 1;
  if ( y1 > y2 ) {int ytmp = y1; y1 = y2; y2 = ytmp;}
  if ( y1 < 0 ) y1 = 0;
  else if ( y1 >= imageDisp->height() ) y1 = imageDisp->height()-1;
  if ( y2 < 0 ) y2 = 0;
  else if ( y2 >= imageDisp->height() ) y2 = imageDisp->height()-1;
  
  uint32_t* const pImgValue       = imageBuffer->imageData;
  const int       iLinePixelsOrg  = imageDisp->width();
  uint64_t  u64PixelSum           = 0;
  uint64_t  u64PixelSqSum         = 0;
  uint32_t* pPixelLineStart       = pImgValue + y1 * iLinePixelsOrg + x1;

  for (int iY = y1; iY <= y2; ++iY, pPixelLineStart += iLinePixelsOrg)
  {
    if (iY < 0)
      continue;
    if (iY >= imageDisp->height())
      break;
      
    uint32_t* pPixel = pPixelLineStart;
    for (int iX = x1; iX <= x2; ++iX, ++pPixel)
    {
      if (iX < 0)
        continue;
      if (iX >= imageDisp->width())
        break;
        
      const int iValue = *pPixel;
      if ( iValue >= 0x10000)
      {
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
  if ( fNumRoiPixels > 0 )
  {
    imageBuffer->fRoiPixelMean = u64PixelSum   / fNumRoiPixels;
    imageBuffer->fRoiPixelVar  = u64PixelSqSum / fNumRoiPixels - imageBuffer->fRoiPixelMean * imageBuffer->fRoiPixelMean;
  }
  else
  {
    imageBuffer->fRoiPixelMean  = 0;
    imageBuffer->fRoiPixelVar   = 0;             
  }
}

PyObject* pyUpdateProj( PyObject* pyImageBuffer, int iOrientation, int iScaleIndex, 
  QPointF* marker1, QPointF* marker2, QPointF* marker3, QPointF* marker4, 
  bool bProjLine1, bool bProjLine2, bool bProjLine3, bool bProjLine4, 
  bool bProjRoi, bool bProjAutoRange,
  unsigned int uMin, unsigned int uMax, QRectF* rectRoi, QRectF* rectZoom, 
  QImage* imageProjX, QImage* imageProjY )
{  
  ImageBuffer* imageBuffer = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  //printf( "pyUpdateProj(): imagedata %p marker (%f, %f) Or %d proj line %d roi %d ROI (%f,%f) w %f h %f\n", 
  //  imageBuffer, marker->x(), marker->y(), iOrientation, (int) bProjLine, (int) bProjRoi,
  //  rectRoi->x(), rectRoi->y(), rectRoi->width(), rectRoi->height() ); //!!debug
  
  /*
   * Compute the ROI projection values, and also update the mean/variance
   */
  computeRoiProj( imageBuffer, rectRoi);
  
  const bool      lbProjLine[4] = {bProjLine1, bProjLine2, bProjLine3, bProjLine4};
  const QPointF*  lptMarker [4] = {marker1, marker2, marker3, marker4};
  QImage*         imageDisp     = imageBuffer->imageDisp;             
  
  const int       xmin      = (int) (rectZoom->x() < 0 ? 0 : rectZoom->x());
  const int       xmax      = (int) (rectZoom->x() + rectZoom->width() > imageDisp->width() 
	                             ? imageDisp->width() : rectZoom->x() + rectZoom->width());
  const int       ymin      = (int) (rectZoom->y() < 0 ? 0 : rectZoom->y());
  const int       ymax      = (int) (rectZoom->y() + rectZoom->height() > imageDisp->height()
                                     ? imageDisp->height() : rectZoom->y() + rectZoom->height());
    
  /*
   * Look at the Zoom region to find the min/max values of ProjX/ProjY/ROI
   */
   
  if (bProjAutoRange)
    findMinMax( imageBuffer, lbProjLine, bProjRoi, lptMarker, xmin, xmax, ymin, ymax);
  else
  {
    imageBuffer->iProjXmin = uMin;
    imageBuffer->iProjXmax = uMax;
    imageBuffer->iProjYmin = uMin;
    imageBuffer->iProjYmax = uMax;
  }
  
  const float  fPixelValueRangeX = (float) ( (imageBuffer->iProjXmin != imageBuffer->iProjXmax) ? 
    imageBuffer->iProjXmax-imageBuffer->iProjXmin: 1);  
  const float  fPixelValueRangeY = (float) ( (imageBuffer->iProjYmin != imageBuffer->iProjYmax) ? 
    imageBuffer->iProjYmax-imageBuffer->iProjYmin: 1);  
  
  const int iOffsetX    = ( imageProjX->width()  - imageDisp->width() ) /2;
  const int iOffsetY    = ( imageProjY->height() - imageDisp->height() ) /2;    
  
  uint32_t* const pImgValue       = imageBuffer->imageData;     
  const int       iLinePixelsOrg  = imageDisp->width();
  const int       iLinePixelsPx   = imageProjX->width();
  const int       iLinePixelsPy   = imageProjY->width();
  
  imageProjX->fill( 0xFFFFFFFF );
  imageProjY->fill( 0xFFFFFFFF );   
    
  const uint32_t  lu32ColorD[4] = {0xFF0000FF, 0xFFFF0000, 0xFF00CCCC, 0xFF800080};
  //const uint32_t  lu32ColorL[4] = {0xFF000000, 0xFF000000, 0xFF000000, 0xFF000000};
  const uint32_t  u32ColorProj  = 0xFF00CC00;  

  if ( bProjRoi )
  {                  
    uint32_t* pImgProjX = (uint32_t*) imageProjX->bits();
        
    for (int iX=xmin; iX < xmax; ++iX)
    {
      if ( imageBuffer->projSumX[iX] == 0xFFFFFFFF )
        continue;
        
      float fValue = imageBuffer->projSumX[iX] / imageBuffer->iRoiH;
      
      if (fValue < 0)
      {
        printf("pyUpdateProj(): Invalid ProjSumX[%d] : %lf\n", iX, fValue);
        continue;
      }
      
      int iProjValue;
      if (fValue <= imageBuffer->iProjXmin)
        iProjValue = imageProjX->height() - 1;
      else if (fValue >= imageBuffer->iProjXmax)
        iProjValue = 0;
      else
      {
        float fIndex;
        if ( iScaleIndex == 0 )
          fIndex = (fValue - imageBuffer->iProjXmin) / fPixelValueRangeX;
        else if ( iScaleIndex == 1 )
          fIndex = log2( 1 + (fValue - imageBuffer->iProjXmin) / fPixelValueRangeX);
        else
          fIndex = exp2( (fValue - imageBuffer->iProjXmin) / fPixelValueRangeX) - 1;
        
        iProjValue = (int) ( (imageProjX->height()-1) * (1.0 - fIndex));
      }
      
      for (int i = iProjValue; i < imageProjX->height(); i++)  
	*(pImgProjX + ( iLinePixelsPx * i + iOffsetX + iX )) = u32ColorProj;
    }
      
    uint32_t* pImgProjY = (uint32_t*) imageProjY->bits();
        
    for (int iY=ymin; iY < ymax; ++iY)
    {
      if ( imageBuffer->projSumY[iY] == 0xFFFFFFFF )
        continue;
        
      float fValue = imageBuffer->projSumY[iY] / imageBuffer->iRoiW;

      if (fValue < 0)
      {
        printf("pyUpdateProj(): Invalid ProjSumY[%d] : %lf\n", iY, fValue);
        continue;
      }
      
      int iProjValue;
      if (fValue <= imageBuffer->iProjYmin)
        iProjValue = imageProjY->width() - 1;
      else if (fValue >= imageBuffer->iProjYmax)
        iProjValue = 0;
      else
      {
        float fIndex;
        if ( iScaleIndex == 0 )
          fIndex = (fValue - imageBuffer->iProjYmin) / fPixelValueRangeY;
        else if ( iScaleIndex == 1 )
          fIndex = log2( 1 + (fValue - imageBuffer->iProjYmin) / fPixelValueRangeY);
        else
          fIndex = exp2( (fValue - imageBuffer->iProjYmin) / fPixelValueRangeY) - 1;
        
        iProjValue = (int) ( (imageProjY->width()-1) * (1.0 - fIndex));
      }
        
      for (int i = iProjValue; i < imageProjY->width(); i++)  
	*(pImgProjY + ( iLinePixelsPy * (iOffsetY+iY) + i )) = u32ColorProj;
    }        
  }
  
  for (int iProj = 0; iProj < 4; ++iProj)
  {
    if ( lbProjLine[iProj] )
    {    
      const int iProjX = (int) (lptMarker[iProj]->x());
      const int iProjY = (int) (lptMarker[iProj]->y());  
      
      uint32_t* pImgProjX = (uint32_t*) imageProjX->bits();
      uint32_t* pImgProjY = (uint32_t*) imageProjY->bits();      
              
      //if ( iProjY >= ymin && iProjY < ymax )
      //  for (int iX=0; iX < imageProjY->width(); iX+=2)
      //    *(pImgProjY + ( iLinePixelsPy * (iProjY + iOffsetY) + iX)) = lu32ColorL[iProj];                
            
      if ( iProjY >= 0 && iProjY < imageDisp->height() )
      {
        for (int iX=xmin; iX < xmax; ++iX)
        {
          int iValue   = *(pImgValue + ( iLinePixelsOrg * iProjY + iX ));        
          
          int iProjValue;
          if (iValue <= imageBuffer->iProjXmin)
            iProjValue = imageProjX->height() - 1;
          else if (iValue >= imageBuffer->iProjXmax)
            iProjValue = 0;
          else
          {
            float fIndex;
            if ( iScaleIndex == 0 )
              fIndex = (iValue - imageBuffer->iProjXmin) / fPixelValueRangeX;
            else if ( iScaleIndex == 1 )
              fIndex = log2( 1 + (iValue - imageBuffer->iProjXmin) / fPixelValueRangeX);
            else
              fIndex = exp2( (iValue - imageBuffer->iProjXmin) / fPixelValueRangeX) - 1;
            
            iProjValue = (int) ( (imageProjX->height()-1) * (1.0 - fIndex));
          }
            
          *(pImgProjX + ( iLinePixelsPx * iProjValue + iOffsetX + iX )) = lu32ColorD[iProj];
        }                  
      }
      
      //if ( iProjX >= xmin && iProjX < xmax ) 
      //  for (int iY=0; iY < imageProjX->height(); iY+=2)
      //    *(pImgProjX + ( iLinePixelsPx * iY + iOffsetX + iProjX )) = lu32ColorL[iProj];                        
        
      if ( iProjX >= 0 && iProjX < imageDisp->width() )
      {
        for (int iY=ymin; iY < ymax; ++iY)
        {
          int iValue = *(pImgValue + ( iLinePixelsOrg * iY + iProjX ));
                
          int iProjValue;
          if (iValue <= imageBuffer->iProjYmin)
            iProjValue = imageProjY->width() - 1;
          else if (iValue >= imageBuffer->iProjYmax)
            iProjValue = 0;
          else
          {
            float fIndex;
            if ( iScaleIndex == 0 )
              fIndex = (iValue - imageBuffer->iProjYmin) / fPixelValueRangeY;
            else if ( iScaleIndex == 1 )
              fIndex = log2( 1 + (iValue - imageBuffer->iProjYmin) / fPixelValueRangeY);
            else
              fIndex = exp2( (iValue - imageBuffer->iProjYmin) / fPixelValueRangeY) - 1;
            
            iProjValue = (int) ( (imageProjY->width()-1) * (1.0 - fIndex));
          }
            
          *(pImgProjY + ( iLinePixelsPy * (iOffsetY+iY) + iProjValue )) = lu32ColorD[iProj];
        }
      }    
    } // if ( bProjLine )
  } // for (int iProj = 0; iProj < 4; ++iProj)

  return Py_BuildValue("ffiiii", imageBuffer->fRoiPixelMean, imageBuffer->fRoiPixelVar, 
    imageBuffer->iProjXmin, imageBuffer->iProjXmax, imageBuffer->iProjYmin, imageBuffer->iProjYmax);
}
  
PyObject* pyGetPixelValue( PyObject* pyImageBuffer, QPointF* cursor, QPointF* marker1, QPointF* marker2, 
  QPointF* marker3, QPointF* marker4)
{
  ImageBuffer* imageBuffer = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  uint32_t*    pImgValue   = (uint32_t*) imageBuffer->imageData;     
  QImage*      imageDisp   = imageBuffer->imageDisp;           
  const int    iLinePixels = imageDisp->width();
  
  uint32_t     u32ValueCursor;
  if (cursor->x() < 0 || cursor->x() >= imageDisp->width() || cursor->y() < 0 || cursor->y() >= imageDisp->height())
    u32ValueCursor = -1;
  else
    u32ValueCursor = pImgValue[ (int) cursor->y() * iLinePixels + (int) cursor->x() ];    

  uint32_t     u32Value1;
  if (marker1->x() < 0 || marker1->x() >= imageDisp->width() || marker1->y() < 0 || marker1->y() >= imageDisp->height())
    u32Value1 = -1;
  else
    u32Value1 = pImgValue[ (int) marker1->y() * iLinePixels + (int) marker1->x() ];    

  uint32_t     u32Value2;
  if (marker2->x() < 0 || marker2->x() >= imageDisp->width() || marker2->y() < 0 || marker2->y() >= imageDisp->height())
    u32Value2 = -1;
  else
    u32Value2 = pImgValue[ (int) marker2->y() * iLinePixels + (int) marker2->x() ];    

  uint32_t     u32Value3;
  if (marker3->x() < 0 || marker3->x() >= imageDisp->width() || marker3->y() < 0 || marker3->y() >= imageDisp->height())
    u32Value3 = -1;
  else
    u32Value3 = pImgValue[ (int) marker3->y() * iLinePixels + (int) marker3->x() ];    

  uint32_t     u32Value4;
  if (marker4->x() < 0 || marker4->x() >= imageDisp->width() || marker4->y() < 0 || marker4->y() >= imageDisp->height())
    u32Value4 = -1;
  else
    u32Value4 = pImgValue[ (int) marker4->y() * iLinePixels + (int) marker4->x() ];    
    
  return Py_BuildValue("iiiiii", u32ValueCursor, u32Value1, u32Value2, u32Value3, u32Value4, 
    (imageBuffer->iNumAveraged == 0? 1: imageBuffer->iNumAveraged));
}

PyObject* pySetFrameAverage(int iAverage, PyObject* pyImageBuffer)
{
  if ( iAverage == 0 )
    iAverage = 1;
    
  ImageBuffer* imageBuffer  = (ImageBuffer*) PyCObject_AsVoidPtr( pyImageBuffer );
  
  if ( iAverage != imageBuffer->iAverage )
  {
    free( imageBuffer->circBuffer );
    imageBuffer->iAverage = iAverage;
    
    if ( iAverage <= 1 )
      imageBuffer->circBuffer = NULL;
    else
    {
      imageBuffer->circBuffer = (uint32_t*) malloc( imageBuffer->imageDisp->width () * 
        imageBuffer->imageDisp->height() * sizeof(uint32_t) * iAverage );
      if ( imageBuffer->circBuffer == NULL )
      {
        printf("!! pySetFrameAverage(): malloc() failed for circBuffer\n");
        imageBuffer->iAverage = 1;
      }
    }
  }
  
  imageBuffer->iNumAveraged = 0;
  imageBuffer->iFrameIndex  = 0;
  
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
  
//PyObject* pyTest1(PyObject* pyGUI)
//{  
//  PyObject* pyAutoRange = PyObject_GetAttrString(pyGUI, "autoRange");
//  if (pyAutoRange == Py_False)
//    printf("autoRange: False\n");
//  else if (pyAutoRange == Py_True)
//    printf("autoRange: True\n");
//  else
//    printf("autoRange: Unknown\n");  
//  Py_RETURN_TRUE;
//}

} // extern "C"


%End

void pydspl_setup_color_map(const char* colormap, int iLimitLow, int iLimitHigh, int iScaleIndex);
void pydspl_setup_gray(int iLimitLow, int iLimitHigh, int iScaleIndex);
SIP_PYOBJECT pyCreateImagePvCallbackFunc(SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyCreateColorImagePvCallbackFunc(SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyCreateImageBuffer(QImage* imageDisp, int iSyntheticData);
SIP_PYOBJECT pySetImageBufferGray(SIP_PYOBJECT pyImageBuffer, int gray);
SIP_PYOBJECT pyRecolorImageBuffer(SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyUpdateProj       (SIP_PYOBJECT pyImageBuffer, int iOrientation, int iScaleIndex,
                                  QPointF* marker1, QPointF* marker2, QPointF* marker3, QPointF* marker4, 
                                  bool bProjLine1, bool bProjLine2, bool bProjLine3, bool bProjLine4, 
                                  bool bProjRoi, bool bProjAutoRange,
                                  int uMin, int uMax, QRectF* rectRoi, QRectF* rectZoom, QImage* imageProjX, QImage* imageProjY ); 
SIP_PYOBJECT pyGetPixelValue    (SIP_PYOBJECT pyImageBuffer, QPointF* cursor, 
                                  QPointF* marker1, QPointF* marker2, 
                                  QPointF* marker3, QPointF* marker4);
SIP_PYOBJECT pySetFrameAverage  (int iAverage, SIP_PYOBJECT pyImageBuffer);
SIP_PYOBJECT pyGetImageData     (SIP_PYOBJECT pyImageBuffer, bool bPortrait);
SIP_PYOBJECT pyGetImageData8bit (SIP_PYOBJECT pyImageBuffer, bool bPortrait, int depth);
SIP_PYOBJECT pySaveRawImageData (SIP_PYOBJECT pyImageBuffer, bool bPortrait, const char* sFileName);
