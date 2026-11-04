/* TEST STUB ONLY - the real header comes from the model package. */
#ifndef VIBRADISTILL_MODEL_H
#define VIBRADISTILL_MODEL_H
#include <stdint.h>
typedef struct { uint8_t predicted_class; uint8_t rul_percent; float vacuity; } vibra_inference_result_t;
void vibradistill_model_init(void);
void vibradistill_predict(const int8_t *spectrum_257, const uint8_t *priors_4, vibra_inference_result_t *result);
#endif
