"""
Physics-Informed Bearing Kinematics & Fault Frequency Engine.
Calculates exact characteristic fault frequencies for SKF 6205-2RS JEM bearings
and extracts normalized 4-dimensional kinematic energy prior vectors:
[p_BPFO, p_BPFI, p_BSF, p_FTF] from the 257-bin envelope spectrum.
"""

from dataclasses import dataclass
import numpy as np

@dataclass
class BearingGeometry:
    """Bearing physical geometry parameters."""
    n_balls: int           # Number of rolling elements (balls/rollers)
    ball_diameter_mm: float  # Ball diameter (d)
    pitch_diameter_mm: float # Pitch circle diameter (Dp)
    contact_angle_deg: float # Contact angle (theta)

# Standard SKF 6205-2RS JEM Bearing Geometry (Drive End Bearing on CWRU Rig)
SKF6205Geometry = BearingGeometry(
    n_balls=9,
    ball_diameter_mm=7.94,      # 0.3126 in
    pitch_diameter_mm=39.04,    # 1.537 in
    contact_angle_deg=0.0
)
SKF_6205_GEOMETRY = SKF6205Geometry

class BearingKinematics:
    """
    Computes theoretical kinematic fault frequency multipliers relative to shaft speed fr:
    - BPFO: Ball Pass Frequency Outer Race
    - BPFI: Ball Pass Frequency Inner Race
    - BSF:  Ball Spin Frequency
    - FTF:  Fundamental Train Frequency (Cage)
    """
    def __init__(self, geometry: BearingGeometry = SKF6205Geometry):
        self.geom = geometry
        d = geometry.ball_diameter_mm
        dp = geometry.pitch_diameter_mm
        theta_rad = np.radians(geometry.contact_angle_deg)
        nb = geometry.n_balls
        
        cos_theta = np.cos(theta_rad)
        d_dp = d / dp
        
        # Characteristic multipliers (f / fr)
        self.c_bpfo = (nb / 2.0) * (1.0 - d_dp * cos_theta)
        self.c_bpfi = (nb / 2.0) * (1.0 + d_dp * cos_theta)
        self.c_bsf  = (dp / (2.0 * d)) * (1.0 - (d_dp * cos_theta)**2)
        self.c_ftf  = 0.5 * (1.0 - d_dp * cos_theta)
        
    def get_multipliers(self):
        """Returns dict of frequency multipliers relative to shaft speed."""
        return {
            'BPFO': float(self.c_bpfo),
            'BPFI': float(self.c_bpfi),
            'BSF':  float(self.c_bsf),
            'FTF':  float(self.c_ftf)
        }
        
    def get_frequencies(self, rpm: float):
        """
        Computes physical characteristic fault frequencies (Hz) for a given motor RPM.
        """
        fr = float(rpm) / 60.0
        return {
            'fr':   fr,
            'BPFO': float(self.c_bpfo * fr),
            'BPFI': float(self.c_bpfi * fr),
            'BSF':  float(self.c_bsf * fr),
            'FTF':  float(self.c_ftf * fr)
        }

def compute_kinematic_frequencies(rpm: float, geometry: BearingGeometry = SKF6205Geometry):
    """Convenience helper to compute fault frequencies for an RPM."""
    kin = BearingKinematics(geometry)
    return kin.get_frequencies(rpm)

def estimate_shaft_speed_tacholess(signal_or_spectrum: np.ndarray, fs: float = 12000.0,
                                   min_rpm: float = 600.0, max_rpm: float = 3600.0,
                                   is_raw_signal: bool = False) -> float:
    """
    Tacholess Instantaneous Angular Speed (IAS) / Shaft Rotational Speed Estimator.
    Extracts fundamental shaft rotational frequency fr directly from vibration data
    using Parabolic-Interpolated Spectral Peak Picking and Harmonic Energy Verification.
    
    Eliminates dependency on physical optical/magnetic tachometers on un-instrumented assets.
    
    Args:
        signal_or_spectrum (np.ndarray): 1D raw vibration array OR magnitude spectrum.
        fs (float): Sampling frequency in Hz (default: 12000.0)
        min_rpm (float): Minimum plausible motor RPM (default: 600 RPM = 10 Hz)
        max_rpm (float): Maximum plausible motor RPM (default: 3600 RPM = 60 Hz)
        is_raw_signal (bool): If True, computes high-resolution FFT on raw time-series.
        
    Returns:
        float: Estimated shaft speed in RPM.
    """
    min_fr = float(min_rpm) / 60.0
    max_fr = float(max_rpm) / 60.0
    
    if is_raw_signal:
        x = np.asarray(signal_or_spectrum, dtype=np.float32).flatten()
        n = len(x)
        # Detrend and window
        x_dt = x - np.mean(x)
        n_fft = max(4096, 1 << int(np.ceil(np.log2(n))))
        spec = np.abs(np.fft.rfft(x_dt * np.hanning(n), n=n_fft))
        delta_f = (fs / 2.0) / (len(spec) - 1)
    else:
        spec = np.asarray(signal_or_spectrum, dtype=np.float32).flatten()
        delta_f = (fs / 2.0) / (len(spec) - 1)
        
    k_min = max(2, int(np.floor(min_fr / delta_f)))
    k_max = min(len(spec) - 2, int(np.ceil((max_fr * 2.2) / delta_f)))
    
    # Extract local spectral peaks
    peaks = []
    max_spec = float(np.max(spec[k_min:k_max])) if k_max > k_min else 1.0
    threshold = 0.05 * max_spec
    
    for k in range(k_min, k_max):
        if spec[k] > spec[k - 1] and spec[k] > spec[k + 1] and spec[k] >= threshold:
            # Parabolic interpolation for sub-bin precision
            denom = 2.0 * spec[k] - spec[k - 1] - spec[k + 1]
            delta = 0.5 * (spec[k + 1] - spec[k - 1]) / (denom + 1e-12)
            f_est = float((k + delta) * delta_f)
            peaks.append((f_est, float(spec[k])))
            
    if not peaks:
        return float((min_rpm + max_rpm) / 2.0)
        
    # Score candidate fundamental frequencies based on amplitude and harmonic support
    best_fr = peaks[0][0]
    best_score = -1.0
    
    for f_cand, amp_cand in peaks:
        if not (min_fr * 0.9 <= f_cand <= max_fr * 1.05):
            continue
        cand_score = amp_cand
        # Check for 2x and 3x harmonics among detected peaks
        for h in [2, 3]:
            h_target = h * f_cand
            for f_other, amp_other in peaks:
                if abs(f_other - h_target) < 0.05 * h_target:
                    cand_score += amp_other * 0.8
        if cand_score > best_score:
            best_score = cand_score
            best_fr = f_cand
            
    return float(np.clip(best_fr * 60.0, min_rpm, max_rpm))

def extract_kinematic_energy_prior(spectrum: np.ndarray, rpm: float, fs: float = 12000.0, 
                                   n_fft: int = 512, harmonics: int = 3, 
                                   tolerance_pct: float = 0.03,
                                   geometry: BearingGeometry = SKF6205Geometry,
                                   prior_dim: int = 4):
    """
    Extracts the normalized kinematic energy prior vector from a 257-bin envelope spectrum.
    
    Modes:
      - prior_dim=4: [p_BPFO, p_BPFI, p_BSF, p_FTF] (Aggregated 1x-3x harmonic contrast)
      - prior_dim=8: [BPFO_1x, BPFO_2x, BPFI_1x, BPFI_2x, BSF_1x, BSF_2x, FTF_1x, NoiseFloor]
                     (Separates fundamental impact vs non-linear spall ringing harmonics)
    
    Args:
        spectrum (np.ndarray): 1D array of 257 magnitude bins [0 .. fs/2]
        rpm (float): Motor rotational speed (RPM)
        fs (float): Sampling frequency in Hz (default: 12000.0)
        n_fft (int): FFT size (default: 512 -> 257 positive bins)
        harmonics (int): Number of fault harmonics to aggregate (default: 3)
        tolerance_pct (float): Search bandwidth relative to center frequency (default: 0.03)
        geometry (BearingGeometry): Bearing physical geometry
        prior_dim (int): 4 or 8 dimensional prior vector (default: 4)
        
    Returns:
        np.ndarray: Length-4 or Length-8 float32 vector.
    """
    spectrum = np.asarray(spectrum, dtype=np.float32).flatten()
    n_bins = len(spectrum)
    delta_f = (fs / 2.0) / (n_bins - 1)
    
    freqs = compute_kinematic_frequencies(rpm, geometry)
    fault_keys = ['BPFO', 'BPFI', 'BSF', 'FTF']
    
    if prior_dim == 8:
        # 8-dimensional harmonic prior
        scores_8d = np.zeros(8, dtype=np.float32)
        # 0: BPFO_1x, 1: BPFO_2x, 2: BPFI_1x, 3: BPFI_2x, 4: BSF_1x, 5: BSF_2x, 6: FTF_1x, 7: NoiseFloor
        mapping = [
            ('BPFO', 1, 0), ('BPFO', 2, 1),
            ('BPFI', 1, 2), ('BPFI', 2, 3),
            ('BSF',  1, 4), ('BSF',  2, 5),
            ('FTF',  1, 6)
        ]
        total_noise = 0.0
        n_noise_samples = 0
        
        for key, h, out_idx in mapping:
            f_target = h * freqs[key]
            if f_target < 20.0 or f_target >= (fs / 2.0) - 2 * delta_f:
                scores_8d[out_idx] = 0.0
                continue
            c_bin = int(round(f_target / delta_f))
            if c_bin < 2 or c_bin >= n_bins - 4:
                continue
            p_val = float(np.max(spectrum[c_bin - 1:c_bin + 2]))
            l_noise = spectrum[max(1, c_bin - 6):c_bin - 1]
            r_noise = spectrum[c_bin + 2:min(n_bins, c_bin + 7)]
            noise_pool = np.concatenate([l_noise, r_noise]) if len(l_noise) > 0 and len(r_noise) > 0 else spectrum[1:10]
            n_val = float(np.median(noise_pool))
            total_noise += n_val
            n_noise_samples += 1
            scores_8d[out_idx] = max(0.0, float((p_val / (n_val + 1e-6)) - 1.0))
            
        # Noise floor feature
        avg_noise = total_noise / max(1, n_noise_samples)
        scores_8d[7] = float(np.clip(avg_noise / (np.max(spectrum) + 1e-6), 0.0, 1.0))
        
        s_sum = float(np.sum(scores_8d[:7]))
        if s_sum > 1e-4:
            scores_8d[:7] = scores_8d[:7] / s_sum
        else:
            scores_8d[:7] = 1.0 / 7.0
        return scores_8d.astype(np.float32)

    # 4-dimensional standard prior
    scores = np.zeros(4, dtype=np.float32)
    for idx, key in enumerate(fault_keys):
        f_fault = freqs[key]
        if f_fault < 25.0:
            scores[idx] = 0.05
            continue
            
        peak_sum = 0.0
        noise_sum = 0.0
        valid_harmonics = 0
        
        for h in range(1, harmonics + 1):
            f_target = h * f_fault
            if f_target >= (fs / 2.0) - 2 * delta_f:
                continue
            c_bin = int(round(f_target / delta_f))
            if c_bin < 2 or c_bin >= n_bins - 4:
                continue
            p_val = float(np.max(spectrum[c_bin - 1:c_bin + 2]))
            l_noise = spectrum[max(1, c_bin - 6):c_bin - 1]
            r_noise = spectrum[c_bin + 2:min(n_bins, c_bin + 7)]
            noise_pool = np.concatenate([l_noise, r_noise]) if len(l_noise) > 0 and len(r_noise) > 0 else spectrum[1:10]
            n_val = float(np.median(noise_pool))
            peak_sum += p_val
            noise_sum += (n_val + 1e-6)
            valid_harmonics += 1
            
        if valid_harmonics > 0:
            pnr = peak_sum / (noise_sum + 1e-6)
            scores[idx] = max(0.0, float(pnr - 1.0))
        else:
            scores[idx] = 0.0
            
    s_sum = float(np.sum(scores))
    if s_sum > 1e-4:
        prior_vector = scores / s_sum
    else:
        prior_vector = np.ones(4, dtype=np.float32) * 0.25
        
    return prior_vector.astype(np.float32)
