# Profile PRF04: Gearbox & Drivetrain Out-of-Distribution (OOD) Monitor

> **Hardware Target:** Gowin Tang Primer 20K + Sonix SN32F407 (SIL-2 Safety Relay)  
> **Source Testbeds:** Southeast University (SEU) Planetary Gearbox + PHM2009 Industrial Gearbox  
> **Safety Role:** Mechanical OOD Epistemic Vacuity Rejection ($u \ge 0.85 \implies \text{Emergency Trip}$)

---

## 1. Drivetrain Mechanical Physics & Why Gearboxes Differ from Bearings
* **Planetary Gearbox Components:** Sun gear (20 teeth), 3 Planet gears (40 teeth), Ring gear (100 teeth).
* **Gear Meshing Frequency:** $f_\text{mesh} = Z \times f_r$ (typically $400 - 2,500\text{ Hz}$).
* **Why Bearing Models Hallucinate on Gearboxes:**
  Traditional Softmax classifiers force any vibration waveform into one of the 4 bearing fault classes, causing dangerous false alarms in industrial gearboxes.
* **The VibraDistill-Edge Solution:**
  Uses Dirichlet Evidential Deep Learning (EDL) in Q1.15 fixed-point:
  $$u = \frac{4}{\sum_{c=0}^3 e_c + 4}$$
  Because gearbox meshing harmonics do not match bearing kinematic bands, evidence $e_c \approx 0$, driving vacuity to **$u \ge 0.85$**, triggering the SIL-2 P1.0 trip alarm!
