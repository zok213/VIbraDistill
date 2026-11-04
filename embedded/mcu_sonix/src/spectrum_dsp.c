#include "spectrum_dsp.h"
#include "spi_slave_dma.h"

/* SKF 6205 ratios (Nb=9, d=7.94, D=39.04, alpha=0) as given in the spec. */
static const float k_ratio[4] = { 3.58f, 5.42f, 2.32f, 0.40f };

uint16_t Spec_FindPeakBin(const uint8_t *frame)
{
    uint16_t best_bin = (uint16_t)SPEC_FIRST_BIN;
    uint16_t best_val = Spi_Frame_GetBin(frame, (uint16_t)SPEC_FIRST_BIN);
    uint16_t i;

    for (i = (uint16_t)(SPEC_FIRST_BIN + 1U); i < (uint16_t)SPEC_BINS; i++) {
        uint16_t v = Spi_Frame_GetBin(frame, i);
        if (v > best_val) {
            best_val = v;
            best_bin = i;
        }
    }
    return best_bin;
}

float Spec_BinToHz(uint16_t bin)
{
    return (float)bin * SPEC_BIN_HZ;       /* never integer division */
}

void Spec_Quantize(const uint8_t *frame, int8_t *out_257)
{
    uint16_t i;
    for (i = 0U; i < (uint16_t)SPEC_BINS; i++) {
        uint16_t v = (uint16_t)(Spi_Frame_GetBin(frame, i) >> SPEC_QUANT_SHIFT);
        if (v > 127U) { v = 127U; }
        out_257[i] = (int8_t)v;
    }
#if (SPEC_ZERO_DC_FOR_MODEL != 0U)
    out_257[0] = 0;
    out_257[1] = 0;
#endif
}

void Spec_ComputePriors(float fr_hz, uint8_t *priors_4)
{
    uint8_t j;
    for (j = 0U; j < 4U; j++) {
        float p = ((k_ratio[j] * fr_hz) / SPEC_PRIOR_FMAX) * 127.0f;
        if (!(p > 0.0f)) {                 /* also catches NaN */
            priors_4[j] = 0U;
        } else if (p >= 127.0f) {
            priors_4[j] = 127U;
        } else {
            priors_4[j] = (uint8_t)p;      /* truncation == floor for p > 0 */
        }
    }
}
