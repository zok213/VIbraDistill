@echo off
chcp 65001 >nul
title VIBRADISTILL-EDGE: LIVE DEMO CONTROLLER - DSAC 2026
color 0B

:MENU
cls
echo ================================================================================
echo        VIBRADISTILL-EDGE : BẢNG ĐIỀU KHIỂN TRÌNH DIỄN DEMO DSAC 2026
echo               Tang Primer 20K (GW2A-18) + Sonix SN32F407 (ARM M0)
echo ================================================================================
echo.
echo   [1]  VECTOR 1  : Vòng bi Lành Lặn 0 HP (RUL 100.0%% - NOMINAL RUN - Đèn Xanh)
echo   [2]  VECTOR 6  : Chớm nứt Vòng Trong 7-mil (RUL 76.2%% - ADVISORY - Đèn Vàng)
echo   [3]  VECTOR 20 : Phá Hủy Nặng 21-mil (SIL-2 EMERGENCY TRIP - CẮT RƠ-LE 0.75ms!)
echo   ----------------------------------------------------------------------------
echo   [4]  VECTOR 11 : Chớm nứt Vòng Ngoài 7-mil 2 HP (BPFO Fault)
echo   [5]  VECTOR 16 : Chớm nứt Viên Bi 7-mil 3 HP (BSF Ball Fault)
echo   [6]  VECTOR 27 : Ngoại Lai (OOD) - Nhiễu Cảm Biến Cực Đại (Vacuity Alert)
echo   ----------------------------------------------------------------------------
echo   [P1] VECTOR P1 : PRONOSTIA Run-to-Failure Đầu Đời (Early Life - RUL 98.5%%)
echo   [P3] VECTOR P3 : PRONOSTIA Run-to-Failure Cuối Đời (Terminal - SIL-2 Trip)
echo   ----------------------------------------------------------------------------
echo   [C]  Tự nhập số vector tùy ý (1 .. 28 hoặc p1 .. p3)
echo   [Q]  Thoát khỏi chương trình
echo.
echo ================================================================================
set /p opt="👉 MỜI THẦY CÔ / BẠN CHỌN KỊCH BẢN THỬ NGHIỆM: "

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
    set /p custom_vec="Nhập mã vector muốn thử (1..28 hoặc p1..p3): "
    python switch_cosim_vector.py %custom_vec%
    goto DONE
)
if /i "%opt%"=="Q" (
    exit /b 0
)

echo.
echo [LỖI] Lựa chọn không hợp lệ, vui lòng chọn lại!
timeout /t 2 >nul
goto MENU

:DONE
echo.
echo ================================================================================
echo 👉 Toàn mở ModelSim gõ: do run.do.txt để chạy kiểm chứng Bit-True Parity!
echo ================================================================================
echo.
pause
goto MENU
