#!/usr/bin/env python3
"""Dump raw::OpDetWaveform from a PDVD pdsraw ART file into a PLAIN-ROOT flat tree
'raw_waveform' -- the PDVD analog of PDHD's _final.root (made by PDSRawWaveformDump).
Readable with uproot/ROOT anywhere; no art dependency to READ it.

Run INSIDE the SL7 container with dunesw set up (needs pyROOT to read the art input):
  python pdvd_dump_rawwf.py <in_pdsraw.root> <out_rawwf.root> [--max-events N] [--chanmap CSV]

Tree branches (one entry per waveform):
  run, subrun, event, opchannel(1010-3240), opdet(0-39), x, y, z (cm), timestamp, nsamp, adc[]
adc is RAW ADC (baseline ~2700 for X-ARAPUCA, ~8600 for PMT; saturates at 16383); no deconvolution.

With --triglight <tag>_triglight.root (the TFileService file of pdvd_pds_raw_trigoff.fcl)
a second tree 'trigger_offset' is written (one entry per event) -- the PDVD analog of
PDHD's trigoff/trigger_offset, but carrying the full charge<->light relation:
  run, subrun, event, tc_type, n_tc, tc_us, charge_tde_us, charge_bde_us,
  fs_t0_us, light_t0_us, fs_nsamp, offset_tde_us, offset_bde_us
All *_us on the DTS clock masked to 40 bits x 0.016 us -- the SAME domain as the
raw_waveform 'timestamp' branch. offset_*_us = charge_window_start - light_fullstream_start
per crate (TDE = top CRPs, ns-stored RDTimeStamps; BDE = bottom, tick-stored); i.e.
light_time + offset_us lands on the charge time base.
"""
import sys, os, csv, argparse
import ROOT

_MAPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maps")
ap = argparse.ArgumentParser()
ap.add_argument("infile"); ap.add_argument("outfile")
ap.add_argument("--max-events", type=int, default=5, help="events to dump (-1 = all)")
ap.add_argument("--chanmap", default=os.path.join(_MAPS, "pdvd_offlinechan_to_opdet.csv"))
ap.add_argument("--positions", default=os.path.join(_MAPS, "pdvd_v5_opdet_positions.csv"))
ap.add_argument("--triglight", default=None,
                help="triglight TFileService file (pdvd_pds_raw_trigoff.fcl) -> add trigger_offset tree")
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
# PDHD-style layout: one TDirectoryFile per "module", so PDHD-side readers
# (rawdump/raw_waveform, trigoff/trigger_offset) work with the same paths.
d_raw = fout.mkdir("rawdump"); d_raw.cd()
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
d_raw.cd(); tr.Write("", ROOT.TObject.kOverwrite)   # kOverwrite: no backup cycles

# opdet_geo: one row per OpDet (0-39), like PDHD's flashopdet/opdet_geo -- makes the
# file self-describing (no need for the maps CSVs downstream).
d_geo = fout.mkdir("flashopdet"); d_geo.cd()
tg = ROOT.TTree("opdet_geo", "PDVD v5 OpDet positions/types")
gi = array.array('i', [0])
gd = {n: array.array('d', [0.0]) for n in ("x", "y", "z")}
gname = ROOT.std.string(); gtype = ROOT.std.string()
tg.Branch("opdet", gi, "opdet/I")
for n in gd: tg.Branch(n, gd[n], f"{n}/D")
tg.Branch("pd_type", gtype); tg.Branch("name", gname)
for row in csv.DictReader(open(a.positions)):
    gi[0] = int(row["opdet"])
    gd["x"][0], gd["y"][0], gd["z"][0] = float(row["x"]), float(row["y"]), float(row["z"])
    gtype.replace(0, ROOT.std.string.npos, row["json_pd_type"])
    gname.replace(0, ROOT.std.string.npos, row["json_name"])
    tg.Fill()
d_geo.cd(); tg.Write("", ROOT.TObject.kOverwrite)

if a.triglight:
    # per-event charge/trigger/light time bases -> 'trigger_offset' tree (PDVD trigoff).
    # rd_ns_min = TDE crate window start (ns since epoch); rd_tk_min = BDE (16-ns DTS
    # ticks); tc_time = CTB TriggerCandidates (DTS ticks). Everything is compared in
    # the 40-bit-masked DTS-us domain of the light timestamps (rollover ~17592 s).
    MASK = (1 << 40) - 1
    PERIOD_US = (1 << 40) * 0.016
    us40 = lambda t: (int(t) & MASK) * 0.016
    wrap = lambda dv: (dv + PERIOD_US / 2) % PERIOD_US - PERIOD_US / 2

    ftl = ROOT.TFile.Open(a.triglight)
    tl = ftl.Get("triglight/triglight")
    if not tl:
        sys.exit(f"no triglight/triglight tree in {a.triglight}")
    d_to = fout.mkdir("trigoff"); d_to.cd()
    to = ROOT.TTree("trigger_offset", "PDVD per-event charge/trigger/light time bases")
    ti = {n: array.array('i', [0]) for n in ("run", "subrun", "event", "tc_type", "n_tc", "fs_nsamp")}
    td = {n: array.array('d', [0.0]) for n in ("tc_us", "charge_tde_us", "charge_bde_us",
                                               "fs_t0_us", "light_t0_us",
                                               "offset_tde_us", "offset_bde_us")}
    for n in ti: to.Branch(n, ti[n], f"{n}/I")
    for n in td: to.Branch(n, td[n], f"{n}/D")
    for e in tl:
        ti["run"][0], ti["subrun"][0], ti["event"][0] = int(e.run), int(e.subrun), int(e.event)
        ti["n_tc"][0] = len(e.tc_time)
        ti["tc_type"][0] = int(e.tc_type[0]) if len(e.tc_type) else -1
        ti["fs_nsamp"][0] = int(e.fs_nsamp_max)
        td["tc_us"][0] = us40(e.tc_time[0]) if len(e.tc_time) else -1.0
        td["charge_tde_us"][0] = us40(int(e.rd_ns_min) // 16)   # TDE stores ns
        td["charge_bde_us"][0] = us40(int(e.rd_tk_min))         # BDE stores ticks
        td["fs_t0_us"][0] = float(e.fs_t0_us)
        td["light_t0_us"][0] = float(e.light_t0_us)
        td["offset_tde_us"][0] = wrap(td["charge_tde_us"][0] - float(e.fs_t0_us))
        td["offset_bde_us"][0] = wrap(td["charge_bde_us"][0] - float(e.fs_t0_us))
        to.Fill()
    d_to.cd(); to.Write("", ROOT.TObject.kOverwrite)
    print(f"wrote trigger_offset tree ({to.GetEntries()} events) from {a.triglight}")

fout.Close()
print(f"wrote {nwf} waveforms from {nev} events -> {a.outfile}")
