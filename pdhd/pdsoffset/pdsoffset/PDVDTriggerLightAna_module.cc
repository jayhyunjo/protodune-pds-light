////////////////////////////////////////////////////////////////////////
// Class:       PDVDTriggerLightAna
// Plugin Type: analyzer
//
// Per-event ProtoDUNE-VD charge / trigger / light time-base dump, for the
// Q-L matching trigger-T0 question:
//
//   - rd_timestamp    : charge readout-window start (raw::RDTimeStamp from
//                       tpcrawdecoder:daq), 64-bit DTS ticks (16 ns)
//   - tc_*            : all TriggerCandidates (trgdataformats2, from
//                       triggerrawdecoder:daq) -- type, time_candidate,
//                       time_start, DTS ticks
//   - light_*         : raw::OpDetWaveform (pdvddaphne:daq) summary. NB the
//                       DAPHNE decoder stores TimeStamp() in microseconds
//                       computed from the DTS tick masked to its 40 LSBs
//                       (see DAPHNEInterface3_tool.cc), so to compare against
//                       rd/tc values apply the same mask: (ts & 0xffffffffff)*0.016.
//
// offset_us(event) = charge_window_start - light_t0 is then
//   ((rd_timestamp & 0xffffffffff)*0.016) - fs_t0_us   (or light_t0_us)
// computed offline (mind the 40-bit rollover, period ~17592 s).
////////////////////////////////////////////////////////////////////////

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art/Framework/Principal/Handle.h"
#include "art/Framework/Services/Registry/ServiceHandle.h"
#include "art_root_io/TFileService.h"
#include "canvas/Utilities/InputTag.h"
#include "fhiclcpp/ParameterSet.h"

#include "lardataobj/RawData/RDTimeStamp.h"
#include "lardataobj/RawData/RawDigit.h"
#include "lardataobj/RawData/OpDetWaveform.h"
#include "detdataformats/trigger/TriggerCandidateData2.hpp"

#include "TTree.h"
#include <vector>
#include <algorithm>

class PDVDTriggerLightAna : public art::EDAnalyzer {
public:
  explicit PDVDTriggerLightAna(fhicl::ParameterSet const& p);
  void beginJob() override;
  void analyze(art::Event const& e) override;

private:
  art::InputTag fRDTSTag;      // tpcrawdecoder:daq
  art::InputTag fTCTag;        // triggerrawdecoder:daq
  art::InputTag fWfTag;        // pdvddaphne:daq
  unsigned      fFullStreamMinSamples;

  TTree* fTree{nullptr};
  int fRun{}, fSubRun{}, fEvent{};
  int fNRDTS{};
  unsigned long long fRDTS{}, fRDTSMin{}, fRDTSMax{};
  // PDVD decoder quirk: TDE (top) channels carry ns-since-epoch (exactly 32-us
  // frame aligned), BDE (WIBEth, bottom) channels carry 16-ns DTS ticks. Split
  // the per-channel stamps into the two families (threshold 2^58) so each
  // electronics' window start can be checked separately.
  int fNRdNs{}, fNRdTk{};
  unsigned long long fRdNsMin{}, fRdNsMax{}, fRdTkMin{}, fRdTkMax{};
  std::vector<int>                fTCType;
  std::vector<unsigned long long> fTCTime, fTCTimeStart;
  long long fDigitNsampMin{}, fDigitNsampMax{};
  int    fNWf{}, fNFullStream{};
  double fLightT0Us{}, fLightT1Us{};   // min / max OpDetWaveform TimeStamp (us)
  double fFsT0Us{}, fFsT1Us{};         // same, full-stream records only
  long long fFsNsampMin{}, fFsNsampMax{};
};

PDVDTriggerLightAna::PDVDTriggerLightAna(fhicl::ParameterSet const& p)
  : art::EDAnalyzer(p)
  , fRDTSTag(p.get<art::InputTag>("RDTimeStampTag", art::InputTag("tpcrawdecoder", "daq")))
  , fTCTag  (p.get<art::InputTag>("TriggerCandidateTag", art::InputTag("triggerrawdecoder", "daq")))
  , fWfTag  (p.get<art::InputTag>("OpDetWaveformTag", art::InputTag("pdvddaphne", "daq")))
  , fFullStreamMinSamples(p.get<unsigned>("FullStreamMinSamples", 100000))
{}

void PDVDTriggerLightAna::beginJob()
{
  art::ServiceHandle<art::TFileService> tfs;
  fTree = tfs->make<TTree>("triglight", "per-event PDVD charge/trigger/light time bases");
  fTree->Branch("run",    &fRun,    "run/I");
  fTree->Branch("subrun", &fSubRun, "subrun/I");
  fTree->Branch("event",  &fEvent,  "event/I");
  fTree->Branch("n_rdts",       &fNRDTS,   "n_rdts/I");
  fTree->Branch("rd_timestamp", &fRDTS,    "rd_timestamp/l");
  fTree->Branch("rd_ts_min",    &fRDTSMin, "rd_ts_min/l");
  fTree->Branch("rd_ts_max",    &fRDTSMax, "rd_ts_max/l");
  fTree->Branch("n_rd_ns",   &fNRdNs,   "n_rd_ns/I");
  fTree->Branch("rd_ns_min", &fRdNsMin, "rd_ns_min/l");
  fTree->Branch("rd_ns_max", &fRdNsMax, "rd_ns_max/l");
  fTree->Branch("n_rd_tk",   &fNRdTk,   "n_rd_tk/I");
  fTree->Branch("rd_tk_min", &fRdTkMin, "rd_tk_min/l");
  fTree->Branch("rd_tk_max", &fRdTkMax, "rd_tk_max/l");
  fTree->Branch("tc_type",       &fTCType);
  fTree->Branch("tc_time",       &fTCTime);
  fTree->Branch("tc_time_start", &fTCTimeStart);
  fTree->Branch("digit_nsamp_min", &fDigitNsampMin, "digit_nsamp_min/L");
  fTree->Branch("digit_nsamp_max", &fDigitNsampMax, "digit_nsamp_max/L");
  fTree->Branch("n_wf",          &fNWf,         "n_wf/I");
  fTree->Branch("n_fullstream",  &fNFullStream, "n_fullstream/I");
  fTree->Branch("light_t0_us",   &fLightT0Us,   "light_t0_us/D");
  fTree->Branch("light_t1_us",   &fLightT1Us,   "light_t1_us/D");
  fTree->Branch("fs_t0_us",      &fFsT0Us,      "fs_t0_us/D");
  fTree->Branch("fs_t1_us",      &fFsT1Us,      "fs_t1_us/D");
  fTree->Branch("fs_nsamp_min",  &fFsNsampMin,  "fs_nsamp_min/L");
  fTree->Branch("fs_nsamp_max",  &fFsNsampMax,  "fs_nsamp_max/L");
}

void PDVDTriggerLightAna::analyze(art::Event const& e)
{
  fRun = e.run(); fSubRun = e.subRun(); fEvent = e.event();
  fNRDTS = 0; fRDTS = fRDTSMin = fRDTSMax = 0;
  fNRdNs = fNRdTk = 0;
  fRdNsMin = fRdNsMax = fRdTkMin = fRdTkMax = 0;
  fTCType.clear(); fTCTime.clear(); fTCTimeStart.clear();
  fDigitNsampMin = fDigitNsampMax = 0;
  fNWf = fNFullStream = 0;
  fLightT0Us = fLightT1Us = fFsT0Us = fFsT1Us = -1.0;
  fFsNsampMin = fFsNsampMax = 0;

  art::Handle<std::vector<raw::RDTimeStamp>> rdtsH;
  if (e.getByLabel(fRDTSTag, rdtsH) && !rdtsH->empty()) {
    fNRDTS = rdtsH->size();
    fRDTS = rdtsH->front().GetTimeStamp();
    auto mm = std::minmax_element(rdtsH->begin(), rdtsH->end(),
      [](auto const& a, auto const& b){ return a.GetTimeStamp() < b.GetTimeStamp(); });
    fRDTSMin = mm.first->GetTimeStamp();
    fRDTSMax = mm.second->GetTimeStamp();
    constexpr unsigned long long kNsFamily = 1ULL << 58;
    for (auto const& r : *rdtsH) {
      unsigned long long ts = r.GetTimeStamp();
      if (ts >= kNsFamily) {
        if (!fNRdNs || ts < fRdNsMin) fRdNsMin = ts;
        if (!fNRdNs || ts > fRdNsMax) fRdNsMax = ts;
        ++fNRdNs;
      } else {
        if (!fNRdTk || ts < fRdTkMin) fRdTkMin = ts;
        if (!fNRdTk || ts > fRdTkMax) fRdTkMax = ts;
        ++fNRdTk;
      }
    }
  }

  art::Handle<std::vector<raw::RawDigit>> digH;
  if (e.getByLabel(fRDTSTag, digH) && !digH->empty()) {
    for (auto const& d : *digH) {
      long long n = static_cast<long long>(d.Samples());
      if (fDigitNsampMin == 0 || n < fDigitNsampMin) fDigitNsampMin = n;
      if (n > fDigitNsampMax) fDigitNsampMax = n;
    }
  }

  art::Handle<std::vector<dunedaq::trgdataformats2::TriggerCandidateData>> tcH;
  if (e.getByLabel(fTCTag, tcH)) {
    for (auto const& tc : *tcH) {
      fTCType.push_back(static_cast<int>(tc.type));
      fTCTime.push_back(tc.time_candidate);
      fTCTimeStart.push_back(tc.time_start);
    }
  }

  art::Handle<std::vector<raw::OpDetWaveform>> wfH;
  if (e.getByLabel(fWfTag, wfH) && !wfH->empty()) {
    fNWf = wfH->size();
    for (auto const& wf : *wfH) {
      double ts = wf.TimeStamp();
      if (fLightT0Us < 0 || ts < fLightT0Us) fLightT0Us = ts;
      if (ts > fLightT1Us) fLightT1Us = ts;
      if (wf.size() >= fFullStreamMinSamples) {
        ++fNFullStream;
        long long n = static_cast<long long>(wf.size());
        if (fFsT0Us < 0 || ts < fFsT0Us) fFsT0Us = ts;
        if (ts > fFsT1Us) fFsT1Us = ts;
        if (fFsNsampMin == 0 || n < fFsNsampMin) fFsNsampMin = n;
        if (n > fFsNsampMax) fFsNsampMax = n;
      }
    }
  }

  fTree->Fill();
}

DEFINE_ART_MODULE(PDVDTriggerLightAna)
