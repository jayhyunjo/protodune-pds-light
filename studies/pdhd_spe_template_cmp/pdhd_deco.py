"""Exact numpy port of the LArSoft opdet::Deconvolution module (duneopdet
v10_20_09d00) as configured by `protodunehd_deconvolution` (Wiener filter,
AutoScale, 1.5 MHz Gauss post-filter, post-BL correction), for re-deconvolving
the PDHD raw self-trigger waveforms stored in the flat `rawdump/raw_waveform`
tree with any SPE template set (v0 / v1 / NP04 vendor-average).

Configuration constants are the resolved values of `protodunehd_deconvolution`
(duneopdet/fcl/Deconvolution.fcl + dune_opdet_channels.fcl); template/noise
files are read from the cvmfs osgstorage stash exactly like FW_SEARCH_PATH
would resolve them.
"""

import os
import numpy as np

# --- resolved protodunehd_deconvolution configuration -----------------------
SAMPLES = 1024          # fcl Samples
PRETRIGGER = 50         # fcl PreTrigger [ticks]
PEDESTAL_BUFFER = 30    # fcl PedestalBuffer [ticks]
PED_N = PRETRIGGER - PEDESTAL_BUFFER   # pedestal window = first 20 samples
INPUT_POLARITY = -1     # fcl InputPolarity
SAMPLE_FREQ_MHZ = 62.5  # protodunehd_detectorclocks.ClockSpeedOptical
POSTFILTER_CUTOFF_MHZ = 1.5  # fcl WfmPostfilter.Cutoff (Gauss)
NFREQ = SAMPLES // 2 + 1

STASH = "/cvmfs/dune.osgstorage.org/pnfs/fnal.gov/usr/dune/persistent/stash"
OPDETRESP = os.path.join(STASH, "ProtoDUNE/HD/opdetresponse")
FCLDIR = ("/cvmfs/dune.opensciencegrid.org/products/dune/duneopdet/"
          "v10_20_09d00/fcl")

IGNORE_CHANNELS = frozenset(
    [3, 86, 87, 97, 107, 116, 117] + list(range(120, 160)))

# FBK/HPK vendor channels (dune_opdet_channels.fcl, all 160 channels)
FBK_CHANNELS = [4,14,24,34,40,42,45,46,47,49,50,52,55,56,57,59,60,62,65,66,67,
                69,70,72,75,76,77,79,84,85,86,87,94,95,96,97,104,105,106,107,
                114,115,116,117,120,121,124,125,127,129,130,131,134,135,137,
                139,140,141,144,145,147,149,150,151,154,155,157,159]
HPK_CHANNELS = [0,1,2,3,5,6,7,8,9,10,11,12,13,15,16,17,18,19,20,21,22,23,25,
                26,27,28,29,30,31,32,33,35,36,37,38,39,41,43,44,48,51,53,54,
                58,61,63,64,68,71,73,74,78,80,81,82,83,88,89,90,91,92,93,98,
                99,100,101,102,103,108,109,110,111,112,113,118,119,122,123,
                126,128,132,133,136,138,142,143,146,148,152,153,156,158]
VENDOR = {c: "FBK" for c in FBK_CHANNELS}
VENDOR.update({c: "HPK" for c in HPK_CHANNELS})

NOISE_FILES = {
    "FBK": os.path.join(OPDETRESP, "v0",
        "FFT_Noise_Template_run27950_PDHD_VGain2318_sample513_fbk_Dec2024.txt"),
    "HPK": os.path.join(OPDETRESP, "v0",
        "FFT_Noise_Template_run27950_PDHD_VGain2318_sample513_hpk_Dec2024.txt"),
}


def _read_column_file(path, column=0):
    """Read one whitespace-separated column, like the module's file reader
    (SPETemplateFileDataColumn=0 for all PDHD configs)."""
    vals = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if parts:
                vals.append(float(parts[column]))
    return np.asarray(vals, dtype=np.float64)


def _spe_files_from_fcl(fcl_path):
    """Extract the SPETemplateFiles list (quoted file names) from a
    protodunehd template-list fcl."""
    import re
    names = []
    in_block = False
    with open(fcl_path) as f:
        for line in f:
            if "SPETemplateFiles:" in line:
                in_block = True
            if in_block:
                names += re.findall(r'"([^"]+)"', line)
                if "]" in line:
                    break
    return names


def spe_template_map(version):
    """Return {channel: template_path} for 'v0', 'v1', or 'np04'."""
    if version in ("v0", "v1"):
        fcl = {"v0": "protodunehd_first_template_list.fcl",
               "v1": "protodunehd_template_list_v1.fcl"}[version]
        files = _spe_files_from_fcl(os.path.join(FCLDIR, fcl))
        assert len(files) == 113, (version, len(files))
        # SPETemplateMapChannels = the 113 non-ignored channels 0..119 in
        # ascending order; MapTemplates = 0..112 (strict 1:1, see fcl)
        channels = [c for c in range(120) if c not in IGNORE_CHANNELS]
        assert len(channels) == 113
        return {c: os.path.join(OPDETRESP, version, fn)
                for c, fn in zip(channels, files)}
    if version == "np04":
        return {c: os.path.join(
                    OPDETRESP, f"SPE_NP04_{VENDOR[c]}_2024_without_pretrigger.dat")
                for c in range(120) if c not in IGNORE_CHANNELS}
    raise ValueError(version)


class DecoEngine:
    """Per-template-set deconvolution engine (one SPE kernel per channel)."""

    def __init__(self, version):
        self.version = version
        self.channel_files = spe_template_map(version)
        # unique templates -> fft, |fft|^2, amplitude
        self._tmpl = {}
        for path in set(self.channel_files.values()):
            h = _read_column_file(path)
            assert len(h) <= SAMPLES, path
            h = np.pad(h, (0, SAMPLES - len(h)))          # resize(fSamples, 0)
            hfft = np.fft.rfft(h)
            amp = max(1.0, h.max())                       # fSinglePEAmplitudes
            self._tmpl[path] = (hfft, np.abs(hfft) ** 2, amp, h)
        # per-vendor noise power spectra, resize(fSamples/2+1, 0)
        self._noise = {}
        for vendor, path in NOISE_FILES.items():
            n = _read_column_file(path)
            assert len(n) <= NFREQ, path
            self._noise[vendor] = np.pad(n, (0, NFREQ - len(n)))
        # Gauss post-filter fxG1 (BuildExtraFilter)
        df = SAMPLE_FREQ_MHZ / SAMPLES
        cutoff = POSTFILTER_CUTOFF_MHZ / df               # in bins
        sigma = SAMPLES * np.sqrt(np.log(2)) / (2 * np.pi * cutoff)
        mu = int(0.5 * SAMPLES)
        i = np.arange(SAMPLES)
        xf = np.exp(-0.5 * ((i - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
        k = np.arange(NFREQ)
        self._g1 = np.fft.rfft(xf) * np.exp(-2j * np.pi * k * mu / SAMPLES)

    def kernel(self, channel):
        """(time-domain kernel, amplitude) for a channel."""
        hfft, h2, amp, h = self._tmpl[self.channel_files[channel]]
        return h, amp

    def deconvolve(self, channel, wfs):
        """Deconvolve raw waveforms of one channel.

        wfs: (N, 1024) integer ADC array. Returns (N, 1024) float32,
        bit-comparable to the stored decodump trees (float64 pipeline,
        float32 cast at the end, like the module).
        """
        if channel in IGNORE_CHANNELS:
            raise ValueError(f"channel {channel} is in IgnoreChannels")
        hfft, h2, amp, _ = self._tmpl[self.channel_files[channel]]
        xN = self._noise[VENDOR[channel]]

        wfs = np.asarray(wfs, dtype=np.float64)
        assert wfs.shape[1] == SAMPLES, "only 1024-sample records supported"

        pedestal = wfs[:, :PED_N].mean(axis=1, keepdims=True)
        xv = INPUT_POLARITY * (wfs - pedestal)

        # expected input = delta of amplitude max(xv)/SPE_amp at bin 512
        # -> |xS[k]|^2 == SPE_Max^2 exactly, for every frequency bin
        s2 = (xv.max(axis=1) / amp) ** 2                    # (N,)
        xV = np.fft.rfft(xv, axis=1)                        # (N, 513)

        # Wiener filter G = conj(H) * S2 / (|H|^2 S2 + N2), per record
        denom = h2[None, :] * s2[:, None] + xN[None, :]
        G = np.conj(hfft)[None, :] * s2[:, None] / denom

        # xvdec = unnormalized c2r of G*V (ROOT c2r = N * numpy irfft)
        xvdec = np.fft.irfft(G * xV, n=SAMPLES, axis=1) * SAMPLES

        # AutoScale: norm of the filtered SPE response (ComputeAutoNormalization)
        k = np.arange(NFREQ)
        phase = np.exp(2j * np.pi * k * (SAMPLES // 2) / SAMPLES)
        xgh = np.fft.irfft(G * hfft[None, :] * phase[None, :],
                           n=SAMPLES, axis=1) * SAMPLES
        norm = self._auto_norm(xgh)
        scale = (1.0 / norm) / SAMPLES                      # (N,)

        # post-deco pedestal, computed before the post-filter
        dec_ped = xvdec[:, :PED_N].mean(axis=1)

        # Gauss post-filter (rfft -> *G1 -> irfft includes the 1/N g1_scale)
        xvdec = np.fft.irfft(np.fft.rfft(xvdec, axis=1) * self._g1[None, :],
                             n=SAMPLES, axis=1)

        out = (xvdec - dec_ped[:, None]) * scale[:, None]
        return out.astype(np.float32)

    @staticmethod
    def _auto_norm(x):
        """Vector port of ComputeAutoNormalization (thrs=0): integrate the
        filtered SPE around its peak between the surrounding zero-crossings;
        clip to (0, 1], return the clipped norm (caller uses 1/norm)."""
        n = np.empty(len(x))
        for j, xx in enumerate(x):
            imax = int(np.argmax(xx))
            ileft = imax
            while xx[ileft] > 0 and ileft > 0:
                ileft -= 1
            iright = imax
            while iright < SAMPLES and xx[iright] > 0:
                iright += 1
            iright = min(iright, SAMPLES - 1)   # C++ reads x[fSamples] OOB; clamp
            s = xx[ileft:iright + 1].sum() / SAMPLES
            n[j] = s if 0.0 < s <= 1.0 else 1.0
        return n
