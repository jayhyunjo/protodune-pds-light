#!/usr/bin/env python3
"""Build the 10-slide PPTX for the PDVD flash-finder bug report.
Run with the validation venv (python-pptx + PIL via matplotlib deps)."""
import json, os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(f"{HERE}/stats.json"))

INK = RGBColor(0x0B, 0x0B, 0x0B)
INK2 = RGBColor(0x52, 0x51, 0x4E)
MUTED = RGBColor(0x89, 0x87, 0x81)
RED = RGBColor(0xE3, 0x49, 0x48)
YEL = RGBColor(0xC9, 0x85, 0x00)
BLUE = RGBColor(0x2A, 0x78, 0xD6)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

def add_text(slide, x, y, w, h, runs, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT,
             font="Calibri", line_spacing=1.0):
    """runs: str, or list of paragraphs, each str or list of (text, dict) runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    if isinstance(runs, str):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        if isinstance(para, str):
            para = [(para, {})]
        for text, kw in para:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(kw.get("size", size))
            r.font.bold = kw.get("bold", bold)
            r.font.color.rgb = kw.get("color", color)
            r.font.name = kw.get("font", font)
            if kw.get("italic"):
                r.font.italic = True
    return tb

def add_title(slide, text, sub=None, color=INK):
    add_text(slide, 0.45, 0.22, 12.5, 0.75, text, size=27, bold=True, color=color)
    if sub:
        add_text(slide, 0.45, 0.88, 12.5, 0.4, sub, size=14, color=INK2)

def add_image(slide, path, top=1.35, bottom=7.25, left=0.35, right=13.0):
    iw, ih = Image.open(path).size
    box_w, box_h = right - left, bottom - top
    scale = min(box_w / iw, box_h / ih)
    w, h = iw * scale, ih * scale
    x = left + (box_w - w) / 2
    y = top + (box_h - h) / 2
    slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))

def code_box(slide, x, y, w, h, lines, size=13):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xF4, 0xF3, 0xEF)
    box.line.color.rgb = RGBColor(0xE1, 0xE0, 0xD9)
    tf = box.text_frame
    tf.word_wrap = False
    tf.margin_left = Emu(91440 // 2); tf.margin_top = Emu(45720)
    for i, (txt, col) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run(); r.text = txt
        r.font.name = "Consolas"; r.font.size = Pt(size); r.font.color.rgb = col
    return box

P = f"{HERE}/plots"

# ---------- 1. title ----------
sl = prs.slides.add_slide(BLANK)
add_text(sl, 0.7, 2.0, 12.0, 1.8, [
    [("OpFlashFinderVerticalDrift produces only", {})],
    [("single-PD flashes on ProtoDUNE-VD", {})],
], size=34, bold=True)
add_text(sl, 0.7, 3.6, 12.0, 0.6, "diagnosis, fix, and validation", size=22, color=INK2)
add_text(sl, 0.7, 5.6, 12.0, 1.4, [
    "J. Jo  —  2026-07-09",
    "duneopdet v10_21_00d00 (dunesw v10_21_00d00, e26:prof), config protodunevd_opflash",
    "PDVD (NP02) cosmics, run 39349 (raw HDF5, 28 events), protodunevd_v5 — 40 OpDets",
], size=14, color=INK2, line_spacing=1.25)

# ---------- 2. symptom ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "Symptom: every flash contains ~one OpDet",
          f"stock finder: {S['stock']['n_flashes']:,} flashes from {S['n_ophits']:,} OpHits "
          f"— one flash per hit; flash-based charge–light matching is impossible")
add_image(sl, f"{P}/01_multiplicity_stock_vs_fixed.png", top=1.35)

# ---------- 3. same burst ----------
sl = prs.slides.add_slide(BLANK)
d = S["display_flash"]; ds = S["display_stock"]
add_title(sl, "The same light burst, two answers",
          f"fixed: ONE flash, {d['n_opdet']} OpDets, {d['total_pe']:,.0f} PE   —   "
          f"stock: {ds['n_flashes_in_window']} single-PD flashes in the same 2-tick window")
add_image(sl, f"{P}/02_flash_display_stock_vs_fixed.png", top=1.3)

# ---------- 4. coincidence ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "The light IS coincident — the finder drops the association",
          "OpHit times across all 40 OpDets around the burst: a vertical coincidence band, "
          "not scattered singles")
add_image(sl, f"{P}/03_ophit_raster.png", top=1.35)

# ---------- 5. bug 1 ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "Bug 1 — far-detector thresholds never match PDVD", color=RED)
add_text(sl, 0.55, 1.5, 12.2, 1.5, [
    [("getNeighbors() sorts hit pairs into detector “planes” with ", {}),
     ("hard-coded FD-VD-scale coordinates", {"bold": True}),
     (" — but ProtoDUNE-VD is an order of magnitude smaller:", {})],
], size=17, line_spacing=1.15)
code_box(sl, 0.55, 2.35, 7.6, 1.7, [
    ("if (xyz_h.X() < fCx && ...)      // fCx  = -320", RED),
    ("if (xyz_h.Y() > fRMy && ...)     // fRMy = +700", RED),
    ("if (xyz_h.Y() < fLMy && ...)     // fLMy = -700", RED),
    ("   ... 7 plane branches, all unreachable ...", INK2),
])
add_text(sl, 8.5, 2.35, 4.4, 1.7, [
    [("protodunevd_v5 reality:", {"bold": True})],
    "cathode X-ARAPUCAs:  X ≈ 0",
    "membrane X-ARAPUCAs: |Y| ≈ 418",
    "PMTs: periphery",
], size=15, color=INK2, line_spacing=1.2)
add_text(sl, 0.55, 4.5, 12.2, 2.4, [
    [("→ no plane branch ever fires: ", {"bold": True}),
     ("no pair of hits is EVER declared neighbours.", {"bold": True, "color": RED})],
    [("The thresholds live in the module defaults (config protodunevd_opflash inherits them); "
      "nothing in the VD-specific fcl overrides them to the actual geometry.", {"size": 15, "color": INK2})],
], size=17, line_spacing=1.2)

# ---------- 6. bug 2 ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "Bug 2 — float32 cluster-seed time at PDVD timestamps", color=RED)
add_text(sl, 0.55, 1.28, 12.4, 0.5,
         f"PeakTime ≈ 1.6×10¹⁰ ticks → float32 ULP = {S['ulp_at_t0']:.0f} ticks = "
         f"{S['ulp_at_t0']/2:.0f}× MaximumTimeWindow(=2): the <2 cut tests a window centred "
         "up to ±512 ticks away from the seed", size=14, color=INK2)
add_image(sl, f"{P}/04_float_precision.png", top=1.8)

# ---------- 7. bug 3 ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "Bug 3 (decisive) — sorted position used as original index", color=RED)
add_text(sl, 0.55, 1.45, 12.3, 1.0, [
    [("getNeighbors() returns positions in the ", {}),
     ("time-sorted", {"bold": True}),
     (" array; ConstructFlash() and the art::Ptr flash↔hit associations index the ", {}),
     ("original", {"bold": True}),
     (" HitVector with those values.", {})],
], size=17, line_spacing=1.15)
code_box(sl, 0.55, 2.5, 12.2, 2.15, [
    ("clustering:    neighbors.push_back(h);              // h = SORTED position", RED),
    ("construction:  HitVector.at(HitID)                  // HitID read as ORIGINAL index", RED),
    ("associations:  art::Ptr<recob::OpHit>(handle, HitID) // wrong hit attached to flash", RED),
    ("seed only:     flash.push_back(sorted[h]);          // the one correct entry", INK2),
])
add_text(sl, 0.55, 5.0, 12.3, 2.0, [
    [("→ every flash is built from the WRONG hits: ", {"bold": True}),
     ("membership, PE sums, positions and associations are all corrupted.", {})],
    [("Detector-independent: it breaks wherever sorted and original hit orders differ — i.e. always. "
      "Bugs 1+2 hide it on VD (nothing groups at all); fix them and this one still wrecks the contents.",
      {"size": 15, "color": INK2})],
], size=17, line_spacing=1.2)

# ---------- 8. isolation ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "Isolating the bugs — fixing 1+2 is not enough",
          "after fixing thresholds+float the flash count looks right but the contents stay wrong")
add_image(sl, f"{P}/05_bug_isolation.png", top=1.4)

# ---------- 9. fix + validation ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "The fix, validated flash-by-flash", color=BLUE)
add_text(sl, 0.55, 1.3, 12.4, 1.15, [
    [("Replace getNeighbors+BFS with a ", {}),
     ("greedy [t₀, t₀+MaximumTimeWindow] grouping in double precision, "
      "returning original hit indices", {"bold": True}),
     ("; no spatial cut (every PD seeing coincident light belongs to the flash). "
      "Downstream ConstructFlash was already correct.", {})],
], size=16, line_spacing=1.15)
add_image(sl, f"{P}/06_validation_identity.png", top=2.35, bottom=6.9)
add_text(sl, 0.55, 6.95, 12.4, 0.5,
         f"vs independent python grouping of the same OpHits: {S['identity']['n_pairs']:,} flashes — "
         f"Δn_opdet = 0 for all, max |ΔPE/PE| = {S['identity']['max_abs_dpe_rel']:.1e}   "
         "(patch: protodune-pds-light/studies/pdvd_flash_finder/patch/)",
         size=13.5, color=INK2)

# ---------- 10. knob + takeaways ----------
sl = prs.slides.add_slide(BLANK)
add_title(sl, "One knob left, three lessons upstream")
add_image(sl, f"{P}/07_dt_scan.png", top=1.35, left=0.3, right=7.4)
add_text(sl, 7.7, 1.6, 5.3, 5.6, [
    [("MaximumTimeWindow (=2)", {"bold": True}),
     (" is the only remaining tuning parameter — smooth behaviour, no cliff.", {})],
    [("", {})],
    [("For upstream:", {"bold": True})],
    [("•  bug 3 corrupts flash↔OpHit associations on ", {}),
     ("any", {"italic": True}), (" detector — audit other finders for the same pattern", {})],
    [("•  float → double for any absolute DAQ timestamp (VD already 3 orders of "
      "magnitude past float32 resolution)", {})],
    [("•  a spatial cut may return, but only with real geometry + a consistent index space", {})],
    [("", {})],
    [("Fixed finder validated identical to the independent reference on "
      f"{S['identity']['n_pairs']:,} flashes (28 events, run 39349).", {"color": INK2, "size": 14})],
], size=15.5, line_spacing=1.18)

prs.save(f"{HERE}/slides.pptx")
print("slides.pptx written,", len(prs.slides.__iter__.__self__._sldIdLst), "slides")
