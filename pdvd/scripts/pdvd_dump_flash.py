#!/usr/bin/env python3
"""Dump recob::OpFlash (+ recob::OpHit) from a PDVD reco ART file into PLAIN-ROOT
flat trees -- the flash-level analog of pdvd_dump_rawwf.py (which dumps the raw
waveforms).  Together they are the PDVD analog of PDHD's _final.root.

REQUIRES the fixed OpFlashFinderVerticalDrift (see studies/pdvd_flash_finder/): the
stock module in dunesw v10_21_00d00 single-PDs every flash.  Produce the input with
pdvd/fcl/pdvd_pds_ophit.fcl run against a dev area that has the patched module
(`source vddev/localProducts*/setup; mrbslp`).

Run INSIDE the SL7 container with dunesw set up (needs pyROOT to read the art input):
  python pdvd_dump_flash.py <in_ophit.root> <out_flash.root> [--max-events N]

Output trees (all keyed by run, subrun, event):
  flash        one entry per recob::OpFlash: flash_id, time, abstime, total_pe,
               n_opdet, ycenter, zcenter, ywidth, zwidth
  flash_opdet  one entry per (flash, OpDet-with-PE>0): flash_id, opdet, pe, x, y, z
  ophit        one entry per recob::OpHit: opdet, opchannel, peaktime, peaktimeabs,
               pe, amplitude, width, area, fasttotal
PE = OpHit area / SPE gain (no deconvolution in VD reco); positions in cm.
"""
import sys, os, csv, argparse, array
import ROOT

_MAPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maps")
ap = argparse.ArgumentParser()
ap.add_argument("infile"); ap.add_argument("outfile")
ap.add_argument("--max-events", type=int, default=-1, help="events to dump (-1 = all)")
ap.add_argument("--positions", default=os.path.join(_MAPS, "pdvd_v5_opdet_positions.csv"))
ap.add_argument("--chanmap", default=os.path.join(_MAPS, "pdvd_offlinechan_to_opdet.csv"))
a = ap.parse_args()

# opdet -> (x, y, z)   and   offline channel -> opdet
pos = {int(d["opdet"]): (float(d["x"]), float(d["y"]), float(d["z"]))
       for d in csv.DictReader(open(a.positions))}
ch2od = {int(d["offline_channel"]): int(d["opdet"]) for d in csv.DictReader(open(a.chanmap))}

fin = ROOT.TFile.Open(a.infile)
tree = fin.Get("Events")
if not tree:
    sys.exit(f"no Events tree in {a.infile}")

def find_branch(tokens):
    """first Events branch whose name contains all tokens and is a product (.obj), not an Assns."""
    for b in tree.GetListOfBranches():
        n = b.GetName()
        if "Assns" in n:
            continue
        if all(t in n for t in tokens):
            return n
    return None

fb = find_branch(["recob::OpFlash", "opflash"]) or find_branch(["OpFlash", "opflash"])
hb = find_branch(["recob::OpHit", "ophit"])     or find_branch(["OpHit", "ophit"])
if not fb:
    sys.exit("no recob::OpFlash branch (label 'opflash') found")
print("flash branch:", fb, "\nophit branch:", hb)

fout = ROOT.TFile(a.outfile, "RECREATE")

# --- flash tree ---
tf = ROOT.TTree("flash", "PDVD recob::OpFlash (fixed finder)")
fi = {n: array.array('i', [0]) for n in ("run", "subrun", "event", "flash_id", "n_opdet")}
fd = {n: array.array('d', [0.0]) for n in ("time", "abstime", "total_pe", "ycenter", "zcenter", "ywidth", "zwidth")}
for n in fi: tf.Branch(n, fi[n], f"{n}/I")
for n in fd: tf.Branch(n, fd[n], f"{n}/D")

# --- flash_opdet tree ---
to = ROOT.TTree("flash_opdet", "PDVD per-flash per-OpDet PE")
oi = {n: array.array('i', [0]) for n in ("run", "subrun", "event", "flash_id", "opdet")}
od = {n: array.array('d', [0.0]) for n in ("pe", "x", "y", "z")}
for n in oi: to.Branch(n, oi[n], f"{n}/I")
for n in od: to.Branch(n, od[n], f"{n}/D")

# --- ophit tree ---
th = ROOT.TTree("ophit", "PDVD recob::OpHit")
hi = {n: array.array('i', [0]) for n in ("run", "subrun", "event", "opdet", "opchannel")}
hd = {n: array.array('d', [0.0]) for n in ("peaktime", "peaktimeabs", "pe", "amplitude", "width", "area", "fasttotal")}
for n in hi: th.Branch(n, hi[n], f"{n}/I")
for n in hd: th.Branch(n, hd[n], f"{n}/D")

nev = tree.GetEntries()
if a.max_events >= 0:
    nev = min(nev, a.max_events)
nfl = noh = 0
for i in range(nev):
    tree.GetEntry(i)
    aux = tree.EventAuxiliary
    run, sub, evt = int(aux.run()), int(aux.subRun()), int(aux.event())
    for d in (fi, oi, hi):
        d["run"][0], d["subrun"][0], d["event"][0] = run, sub, evt

    flashes = getattr(tree, fb).product()
    for fid, fl in enumerate(flashes):
        pes = fl.PEs()
        contribs = [(od_i, pes[od_i]) for od_i in range(pes.size()) if pes[od_i] > 0]
        fi["flash_id"][0] = fid; fi["n_opdet"][0] = len(contribs)
        fd["time"][0] = fl.Time(); fd["abstime"][0] = fl.AbsTime(); fd["total_pe"][0] = fl.TotalPE()
        fd["ycenter"][0] = fl.YCenter(); fd["zcenter"][0] = fl.ZCenter()
        fd["ywidth"][0] = fl.YWidth(); fd["zwidth"][0] = fl.ZWidth()
        tf.Fill(); nfl += 1
        for od_i, pe in contribs:
            oi["flash_id"][0] = fid; oi["opdet"][0] = od_i; od["pe"][0] = pe
            x, y, z = pos.get(od_i, (0.0, 0.0, 0.0))
            od["x"][0], od["y"][0], od["z"][0] = x, y, z
            to.Fill()

    if hb:
        for h in getattr(tree, hb).product():
            ch = int(h.OpChannel())
            hi["opchannel"][0] = ch; hi["opdet"][0] = ch2od.get(ch, -1)
            hd["peaktime"][0] = h.PeakTime(); hd["peaktimeabs"][0] = h.PeakTimeAbs()
            hd["pe"][0] = h.PE(); hd["amplitude"][0] = h.Amplitude(); hd["width"][0] = h.Width()
            hd["area"][0] = h.Area(); hd["fasttotal"][0] = h.FastToTotal()
            th.Fill(); noh += 1
    print(f"  event {i} (run {run} evt {evt}): {flashes.size()} flashes")

fout.cd(); tf.Write(); to.Write(); th.Write(); fout.Close()
print(f"wrote {nfl} flashes, {noh} ophits from {nev} events -> {a.outfile}")
