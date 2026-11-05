@echo off
setlocal EnableDelayedExpansion
title VIBRADISTILL-EDGE: LIVE DEMO CONTROLLER - DSAC 2026
color 0B
cd /d "%~dp0"

:MENU
cls
echo ================================================================================
echo        VIBRADISTILL-EDGE : BANG DIEU KHIEN TRINH DIEN DEMO DSAC 2026
echo               Tang Primer 20K (GW2A-18) + Sonix SN32F407 (ARM M0)
echo ================================================================================
echo.
echo   [1]  VECTOR 1  : Vong bi Lanh Lan 0 HP  (RUL 100.0%% - NOMINAL RUN - Den Xanh)
echo   [2]  VECTOR 6  : Chom nut Vong Trong 7-mil (RUL 76.2%% - ADVISORY - Den Vang)
echo   [3]  VECTOR 20 : Pha Huy Nang 21-mil (SIL-2 EMERGENCY TRIP - CAT RO-LE 0.75ms!)
echo   ----------------------------------------------------------------------------
echo   [4]  VECTOR 11 : Chom nut Vong Ngoai 7-mil 2 HP (BPFO Fault)
echo   [5]  VECTOR 16 : Chom nut Vien Bi 7-mil 3 HP (BSF Ball Fault)
echo   [6]  VECTOR 27 : Ngoai Lai (OOD) - Nhieu Cam Bien Cuc Dai (Vacuity Alert)
echo   ----------------------------------------------------------------------------
echo   [P1] VECTOR P1 : PRONOSTIA Run-to-Failure Dau Doi (Early Life - RUL 98.5%%)
echo   [P3] VECTOR P3 : PRONOSTIA Run-to-Failure Cuoi Doi (Terminal - SIL-2 Trip)
echo   ----------------------------------------------------------------------------
echo   [C]  Tu nhap so vector tuy y (1 .. 28 hoac p1 .. p3)
echo   [Q]  Thoat khoi chuong trinh
echo.
echo ================================================================================
set "opt="
set /p opt="MOI THAY CO / BAN CHON KICH BAN (1, 2, 3, 4, 5, 6, P1, P3, C, Q): "

if "%opt%"=="" goto MENU
if /i "%opt%"=="1" (
    python switch_cosim_vector.py 1
    goto DONE
)
if /i "%opt%"=="2" (
    python switch_cosim_vector.py 6
    goto DONE
)
if /i "%opt%"=="3" (
    python switch_cosim_vector.py 20
    goto DONE
)
if /i "%opt%"=="4" (
    python switch_cosim_vector.py 11
    goto DONE
)
if /i "%opt%"=="5" (
    python switch_cosim_vector.py 16
    goto DONE
)
if /i "%opt%"=="6" (
    python switch_cosim_vector.py 27
    goto DONE
)
if /i "%opt%"=="P1" (
    python switch_cosim_vector.py p1
    goto DONE
)
if /i "%opt%"=="P3" (
    python switch_cosim_vector.py p3
    goto DONE
)
if /i "%opt%"=="C" (
    set "custom_vec="
    set /p custom_vec="Nhap ma vector muon thu (1..28 hoac p1..p3): "
    if not "!custom_vec!"=="" python switch_cosim_vector.py !custom_vec!
    goto DONE
)
if /i "%opt%"=="Q" (
    exit /b 0
)

echo.
echo [LOI] Lua chon khong hop le, vui long chon lai!
timeout /t 2 >nul
goto MENU

:DONE
echo.
echo ================================================================================
echo Toan mo ModelSim go: do run.do.txt de chay kiem chung Bit-True Parity!
echo ================================================================================
echo.
pause
goto MENU
