#!/usr/bin/env python3
"""Dump raw::OpDetWaveform from a PDVD pdsraw ART file into a PLAIN-ROOT flat tree
'raw_waveform' -- the PDVD analog of PDHD's _final.root (made by PDSRawWaveformDump).
Readable with uproot/ROOT anywhere; no art dependency to READ it.

Run INSIDE the SL7 container with dunesw set up (needs pyROOT to read the art input):
  python pdvd_dump_rawwf.py <in_pdsraw.root> <out_rawwf.root> [--max-events N] [--chanmap CSV]

Tree branches (one entry per waveform):
  run, subrun, event, opchannel(1010-3240), opdet(0-39), x, y, z (cm), timestamp, nsamp, adc[]
adc is RAW ADC (baseline ~2700 for X-ARAPUCA, ~8600 for PMT; saturates at 16383); no deconvolution.
"""
import sys, os, csv, argparse
import ROOT

_MAPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maps")
ap = argparse.ArgumentParser()
ap.add_argument("infile"); ap.add_argument("outfile")
ap.add_argument("--max-events", type=int, default=5, help="events to dump (-1 = all)")
ap.add_argument("--chanmap", default=os.path.join(_MAPS, "pdvd_offlinechan_to_opdet.csv"))
a = ap.parse_args()

# offline channel -> (opdet, x, y, z)
cm = {}
for d in csv.DictReader(open(a.chanmap)):
    cm[int(d["offline_channel"])] = (int(d["opdet"]), float(d["x"]), float(d["y"]), float(d["z"]))

fin = ROOT.TFile.Open(a.infile)
tree = fin.Get("Events")
if not tree:
    sys.exit(f"no Events tree in {a.infile}")
bn = next((b.GetName() for b in tree.GetListOfBranches()
           if "OpDetWaveforms_pdvddaphne" in b.GetName()), None)
if not bn:
    sys.exit("no pdvddaphne OpDetWaveform branch found")
print("reading branch:", bn)

import array
fout = ROOT.TFile(a.outfile, "RECREATE")
tr = ROOT.TTree("raw_waveform", "PDVD raw OpDetWaveforms")
b = {n: array.array('i', [0]) for n in ("run", "subrun", "event", "opchannel", "opdet", "nsamp")}
d = {n: array.array('d', [0.0]) for n in ("x", "y", "z", "timestamp")}
adc = ROOT.std.vector('short')()
for n in b: tr.Branch(n, b[n], f"{n}/I")
for n in d: tr.Branch(n, d[n], f"{n}/D")
tr.Branch("adc", adc)

nev = tree.GetEntries()
if a.max_events >= 0:
    nev = min(nev, a.max_events)
nwf = 0
for i in range(nev):
    tree.GetEntry(i)
    aux = tree.EventAuxiliary
    prod = getattr(tree, bn).product()
    b["run"][0], b["subrun"][0], b["event"][0] = int(aux.run()), int(aux.subRun()), int(aux.event())
    for wf in prod:
        ch = int(wf.ChannelNumber())
        b["opchannel"][0] = ch
        od, x, y, z = cm.get(ch, (-1, 0.0, 0.0, 0.0))
        b["opdet"][0] = od; d["x"][0], d["y"][0], d["z"][0] = x, y, z
        d["timestamp"][0] = float(wf.TimeStamp()); b["nsamp"][0] = int(wf.size())
        adc.clear()
        try:
            adc.assign(wf.begin(), wf.end())
        except Exception:
            for j in range(wf.size()):
                adc.push_back(int(wf[j]))
        tr.Fill(); nwf += 1
    print(f"  event {i} (run {int(aux.run())} evt {int(aux.event())}): {prod.size()} waveforms")
fout.cd(); tr.Write(); fout.Close()
print(f"wrote {nwf} waveforms from {nev} events -> {a.outfile}")
