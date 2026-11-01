# KHO 100 TỆP SÓNG RUNG KIỂM THỬ ĐỘC LẬP TRÊN FPGA
## (100 INDUSTRIAL STIMULUS VECTORS SUITE FOR FPGA VERIFICATION)

> **Thư mục:** `embedded/fpga_gowin/roms/stimulus_suite_100/`  
> **Quy cách:** 100 tệp `.hex`, mỗi tệp gồm 512 mẫu sóng rung thời gian 16-bit signed trích từ 15 file `.mat` CWRU.  
> **Cơ cấu mẫu:** 25 Normal + 25 Inner Race (BPFI) + 25 Outer Race (BPFO) + 25 Ball Fault (BSF).

| ID | Tên Tệp `.hex` | Lớp Thật | File `.mat` Gốc | Điều Kiện Tải / Mức Nứt | Rơ-le An Toàn SIL-2 Dự Kiến |
| :-: | :--- | :---: | :---: | :--- | :---: |
| 001 | `stimulus_001_normal_vec01.hex` | **Normal** | `97.mat` | 0 HP / 1797 RPM | BÌNH THƯỜNG (NC Đóng) |
| 002 | `stimulus_002_normal_vec02.hex` | **Normal** | `98.mat` | 1 HP / 1772 RPM | BÌNH THƯỜNG (NC Đóng) |
| 003 | `stimulus_003_normal_vec03.hex` | **Normal** | `99.mat` | 2 HP / 1750 RPM | BÌNH THƯỜNG (NC Đóng) |
| 004 | `stimulus_004_normal_vec04.hex` | **Normal** | `100.mat` | 3 HP / 1730 RPM | BÌNH THƯỜNG (NC Đóng) |
| 005 | `stimulus_005_normal_vec05.hex` | **Normal** | `97.mat` | 0 HP / 1797 RPM | BÌNH THƯỜNG (NC Đóng) |
| 006 | `stimulus_006_normal_vec06.hex` | **Normal** | `98.mat` | 1 HP / 1772 RPM | BÌNH THƯỜNG (NC Đóng) |
| 007 | `stimulus_007_normal_vec07.hex` | **Normal** | `99.mat` | 2 HP / 1750 RPM | BÌNH THƯỜNG (NC Đóng) |
| 008 | `stimulus_008_normal_vec08.hex` | **Normal** | `100.mat` | 3 HP / 1730 RPM | BÌNH THƯỜNG (NC Đóng) |
| 009 | `stimulus_009_normal_vec09.hex` | **Normal** | `97.mat` | 0 HP / 1797 RPM | BÌNH THƯỜNG (NC Đóng) |
| 010 | `stimulus_010_normal_vec10.hex` | **Normal** | `98.mat` | 1 HP / 1772 RPM | BÌNH THƯỜNG (NC Đóng) |
| 011 | `stimulus_011_normal_vec11.hex` | **Normal** | `99.mat` | 2 HP / 1750 RPM | BÌNH THƯỜNG (NC Đóng) |
| 012 | `stimulus_012_normal_vec12.hex` | **Normal** | `100.mat` | 3 HP / 1730 RPM | BÌNH THƯỜNG (NC Đóng) |
| 013 | `stimulus_013_normal_vec13.hex` | **Normal** | `97.mat` | 0 HP / 1797 RPM | BÌNH THƯỜNG (NC Đóng) |
| 014 | `stimulus_014_normal_vec14.hex` | **Normal** | `98.mat` | 1 HP / 1772 RPM | BÌNH THƯỜNG (NC Đóng) |
| 015 | `stimulus_015_normal_vec15.hex` | **Normal** | `99.mat` | 2 HP / 1750 RPM | BÌNH THƯỜNG (NC Đóng) |
| 016 | `stimulus_016_normal_vec16.hex` | **Normal** | `100.mat` | 3 HP / 1730 RPM | BÌNH THƯỜNG (NC Đóng) |
| 017 | `stimulus_017_normal_vec17.hex` | **Normal** | `97.mat` | 0 HP / 1797 RPM | BÌNH THƯỜNG (NC Đóng) |
| 018 | `stimulus_018_normal_vec18.hex` | **Normal** | `98.mat` | 1 HP / 1772 RPM | BÌNH THƯỜNG (NC Đóng) |
| 019 | `stimulus_019_normal_vec19.hex` | **Normal** | `99.mat` | 2 HP / 1750 RPM | BÌNH THƯỜNG (NC Đóng) |
| 020 | `stimulus_020_normal_vec20.hex` | **Normal** | `100.mat` | 3 HP / 1730 RPM | BÌNH THƯỜNG (NC Đóng) |
| 021 | `stimulus_021_normal_vec21.hex` | **Normal** | `97.mat` | 0 HP / 1797 RPM | BÌNH THƯỜNG (NC Đóng) |
| 022 | `stimulus_022_normal_vec22.hex` | **Normal** | `98.mat` | 1 HP / 1772 RPM | BÌNH THƯỜNG (NC Đóng) |
| 023 | `stimulus_023_normal_vec23.hex` | **Normal** | `99.mat` | 2 HP / 1750 RPM | BÌNH THƯỜNG (NC Đóng) |
| 024 | `stimulus_024_normal_vec24.hex` | **Normal** | `100.mat` | 3 HP / 1730 RPM | BÌNH THƯỜNG (NC Đóng) |
| 025 | `stimulus_025_normal_vec25.hex` | **Normal** | `97.mat` | 0 HP / 1797 RPM | BÌNH THƯỜNG (NC Đóng) |
| 026 | `stimulus_026_inner_vec01.hex` | **Inner** | `105.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 027 | `stimulus_027_inner_vec02.hex` | **Inner** | `106.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 028 | `stimulus_028_inner_vec03.hex` | **Inner** | `107.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 029 | `stimulus_029_inner_vec04.hex` | **Inner** | `108.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 030 | `stimulus_030_inner_vec05.hex` | **Inner** | `170.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 031 | `stimulus_031_inner_vec06.hex` | **Inner** | `210.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 032 | `stimulus_032_inner_vec07.hex` | **Inner** | `105.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 033 | `stimulus_033_inner_vec08.hex` | **Inner** | `106.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 034 | `stimulus_034_inner_vec09.hex` | **Inner** | `107.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 035 | `stimulus_035_inner_vec10.hex` | **Inner** | `108.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 036 | `stimulus_036_inner_vec11.hex` | **Inner** | `170.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 037 | `stimulus_037_inner_vec12.hex` | **Inner** | `210.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 038 | `stimulus_038_inner_vec13.hex` | **Inner** | `105.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 039 | `stimulus_039_inner_vec14.hex` | **Inner** | `106.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 040 | `stimulus_040_inner_vec15.hex` | **Inner** | `107.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 041 | `stimulus_041_inner_vec16.hex` | **Inner** | `108.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 042 | `stimulus_042_inner_vec17.hex` | **Inner** | `170.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 043 | `stimulus_043_inner_vec18.hex` | **Inner** | `210.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 044 | `stimulus_044_inner_vec19.hex` | **Inner** | `105.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 045 | `stimulus_045_inner_vec20.hex` | **Inner** | `106.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 046 | `stimulus_046_inner_vec21.hex` | **Inner** | `107.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 047 | `stimulus_047_inner_vec22.hex` | **Inner** | `108.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 048 | `stimulus_048_inner_vec23.hex` | **Inner** | `170.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 049 | `stimulus_049_inner_vec24.hex` | **Inner** | `210.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 050 | `stimulus_050_inner_vec25.hex` | **Inner** | `105.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 051 | `stimulus_051_outer_vec01.hex` | **Outer** | `130.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 052 | `stimulus_052_outer_vec02.hex` | **Outer** | `131.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 053 | `stimulus_053_outer_vec03.hex` | **Outer** | `132.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 054 | `stimulus_054_outer_vec04.hex` | **Outer** | `133.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 055 | `stimulus_055_outer_vec05.hex` | **Outer** | `198.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 056 | `stimulus_056_outer_vec06.hex` | **Outer** | `235.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 057 | `stimulus_057_outer_vec07.hex` | **Outer** | `130.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 058 | `stimulus_058_outer_vec08.hex` | **Outer** | `131.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 059 | `stimulus_059_outer_vec09.hex` | **Outer** | `132.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 060 | `stimulus_060_outer_vec10.hex` | **Outer** | `133.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 061 | `stimulus_061_outer_vec11.hex` | **Outer** | `198.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 062 | `stimulus_062_outer_vec12.hex` | **Outer** | `235.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 063 | `stimulus_063_outer_vec13.hex` | **Outer** | `130.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 064 | `stimulus_064_outer_vec14.hex` | **Outer** | `131.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 065 | `stimulus_065_outer_vec15.hex` | **Outer** | `132.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 066 | `stimulus_066_outer_vec16.hex` | **Outer** | `133.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 067 | `stimulus_067_outer_vec17.hex` | **Outer** | `198.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 068 | `stimulus_068_outer_vec18.hex` | **Outer** | `235.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 069 | `stimulus_069_outer_vec19.hex` | **Outer** | `130.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 070 | `stimulus_070_outer_vec20.hex` | **Outer** | `131.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 071 | `stimulus_071_outer_vec21.hex` | **Outer** | `132.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 072 | `stimulus_072_outer_vec22.hex` | **Outer** | `133.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 073 | `stimulus_073_outer_vec23.hex` | **Outer** | `198.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 074 | `stimulus_074_outer_vec24.hex` | **Outer** | `235.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 075 | `stimulus_075_outer_vec25.hex` | **Outer** | `130.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 076 | `stimulus_076_ball_vec01.hex` | **Ball** | `118.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 077 | `stimulus_077_ball_vec02.hex` | **Ball** | `119.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 078 | `stimulus_078_ball_vec03.hex` | **Ball** | `120.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 079 | `stimulus_079_ball_vec04.hex` | **Ball** | `121.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 080 | `stimulus_080_ball_vec05.hex` | **Ball** | `186.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 081 | `stimulus_081_ball_vec06.hex` | **Ball** | `223.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 082 | `stimulus_082_ball_vec07.hex` | **Ball** | `118.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 083 | `stimulus_083_ball_vec08.hex` | **Ball** | `119.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 084 | `stimulus_084_ball_vec09.hex` | **Ball** | `120.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 085 | `stimulus_085_ball_vec10.hex` | **Ball** | `121.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 086 | `stimulus_086_ball_vec11.hex` | **Ball** | `186.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 087 | `stimulus_087_ball_vec12.hex` | **Ball** | `223.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 088 | `stimulus_088_ball_vec13.hex` | **Ball** | `118.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 089 | `stimulus_089_ball_vec14.hex` | **Ball** | `119.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 090 | `stimulus_090_ball_vec15.hex` | **Ball** | `120.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 091 | `stimulus_091_ball_vec16.hex` | **Ball** | `121.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 092 | `stimulus_092_ball_vec17.hex` | **Ball** | `186.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 093 | `stimulus_093_ball_vec18.hex` | **Ball** | `223.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 094 | `stimulus_094_ball_vec19.hex` | **Ball** | `118.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 095 | `stimulus_095_ball_vec20.hex` | **Ball** | `119.mat` | 7mil / 1 HP (1772 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 096 | `stimulus_096_ball_vec21.hex` | **Ball** | `120.mat` | 7mil / 2 HP (1750 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 097 | `stimulus_097_ball_vec22.hex` | **Ball** | `121.mat` | 7mil / 3 HP (1730 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
| 098 | `stimulus_098_ball_vec23.hex` | **Ball** | `186.mat` | 14mil / 1 HP (Unseen) | TRIP CẮT NGUỒN (<1.0ms) |
| 099 | `stimulus_099_ball_vec24.hex` | **Ball** | `223.mat` | 21mil / 1 HP (Severe) | TRIP CẮT NGUỒN (<1.0ms) |
| 100 | `stimulus_100_ball_vec25.hex` | **Ball** | `118.mat` | 7mil / 0 HP (1797 RPM) | TRIP CẮT NGUỒN (<1.0ms) |
