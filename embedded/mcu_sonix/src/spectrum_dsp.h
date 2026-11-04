#ifndef SPECTRUM_DSP_H
#define SPECTRUM_DSP_H

#include <stdint.h>

#define SPEC_BINS        257U
#define SPEC_FIRST_BIN   2U          /* bins 0/1 = DC of rectified envelope */
#define SPEC_BIN_HZ      6.25f       /* 3200 Hz / 512 points               */
#define SPEC_PRIOR_FMAX  1600.0f

/* ---- MUST match the training pipeline of vibradistill_model.c ----------- */
#ifndef SPEC_QUANT_SHIFT
#define SPEC_QUANT_SHIFT 4U          /* int8 = min(bin >> shift, 127)      */
#endif
#ifndef SPEC_ZERO_DC_FOR_MODEL
#define SPEC_ZERO_DC_FOR_MODEL 1U    /* zero bins 0/1 in the model input   */
#endif

/** arg-max over bins [2..256] (never bin 0/1). Ties -> lowest bin. */
uint16_t Spec_FindPeakBin(const uint8_t *frame);
float    Spec_BinToHz(uint16_t bin);                     /* bin * 6.25f */
void     Spec_Quantize(const uint8_t *frame, int8_t *out_257);
/** priors[] = {BPFO, BPFI, BSF, FTF}, each clamp(floor(f/1600*127),0,127) */
void     Spec_ComputePriors(float fr_hz, uint8_t *priors_4);

#endif
