#!/bin/sh
# Host unit tests (no hardware). Run from the firmware root.
set -e
gcc -std=c99 -Wall -Wextra -Isrc -Itest -fsanitize=address,undefined -o /tmp/host_test \
  test/host_test.c src/spi_slave_dma.c src/spectrum_dsp.c src/tachometer.c src/safety_trip.c src/oled_ssd1306.c
/tmp/host_test
# Cross-compile check for Cortex-M0 (needs arm-none-eabi-gcc); hal_sn32f407.c excluded (needs DFP header)
for f in spi_slave_dma spectrum_dsp tachometer safety_trip oled_ssd1306 main; do
  arm-none-eabi-gcc -mcpu=cortex-m0 -mthumb -Os -std=c99 -Wall -Wextra -Wconversion -Isrc -Itest -c src/$f.c -o /tmp/$f.o
done
echo "Cortex-M0 build OK"
