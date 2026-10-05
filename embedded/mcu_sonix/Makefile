# ============================================================================
# Makefile for VibraDistill-Micro Embedded Firmware
# Dual-Target Architecture with Automatic Fallback:
#   - TARGET=SN32F407 : ARM Cortex-M0 @ 60 MHz (Default, Pure ANSI C99)
#   - TARGET=SN34F788 : ARM Cortex-M4F @ 192 MHz (__SMLAD SIMD Hardware MAC)
#   - HOST=1          : Native Host Binary for PC/CI Unit Testing
# ============================================================================

TARGET ?= SN32F407
CROSS_COMPILE ?= arm-none-eabi-

CC      = $(CROSS_COMPILE)gcc
OBJCOPY = $(CROSS_COMPILE)objcopy
SIZE    = $(CROSS_COMPILE)size

APP_DIR = app
BUILD_DIR = build

SRCS = $(APP_DIR)/main.c \
       $(APP_DIR)/vibradistill_model.c \
       $(APP_DIR)/adaptive_conformal.c

INCLUDES = -I$(APP_DIR)

# Common Compiler Optimization Flags
CFLAGS = -O3 -Wall -Wextra -std=c99 -ffunction-sections -fdata-sections $(INCLUDES)

# Architecture Configuration
ifeq ($(HOST), 1)
  # Host Native Compilation (Unit Test)
  CC = gcc
  CFLAGS += -DVIBRA_HOST_TEST
  BIN = $(BUILD_DIR)/vibradistill_host.exe
else ifeq ($(TARGET), SN34F788)
  # Cortex-M4F with Hardware FPU & DSP SIMD (__SMLAD)
  CFLAGS += -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb \
            -DARM_MATH_CM4 -D__ARM_FEATURE_DSP=1 -DTARGET_SN34F788
  LDFLAGS = -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard -mthumb \
            -Wl,--gc-sections -Wl,-Map=$(BUILD_DIR)/firmware.map
  BIN = $(BUILD_DIR)/vibradistill_sn34f788.elf
else
  # Default Fallback: Cortex-M0 Pure Integer / Zero Heap
  CFLAGS += -mcpu=cortex-m0 -mthumb -DARM_MATH_CM0 -DTARGET_SN32F407
  LDFLAGS = -mcpu=cortex-m0 -mthumb -Wl,--gc-sections \
            -Wl,-Map=$(BUILD_DIR)/firmware.map
  BIN = $(BUILD_DIR)/vibradistill_sn32f407.elf
endif

OBJS = $(patsubst $(APP_DIR)/%.c, $(BUILD_DIR)/%.o, $(SRCS))

all: $(BIN) size

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/%.o: $(APP_DIR)/%.c | $(BUILD_DIR)
	@echo "[CC] Compiling $< (Target: $(TARGET))..."
	$(CC) $(CFLAGS) -c $< -o $@

$(BIN): $(OBJS)
	@echo "[LD] Linking $@..."
	$(CC) $(OBJS) $(LDFLAGS) -o $@
ifneq ($(HOST), 1)
	$(OBJCOPY) -O binary $@ $(BUILD_DIR)/firmware.bin
endif

size: $(BIN)
ifneq ($(HOST), 1)
	@echo "\n--- Memory Footprint Breakdown ---"
	$(SIZE) -B $(BIN)
endif

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all size clean
