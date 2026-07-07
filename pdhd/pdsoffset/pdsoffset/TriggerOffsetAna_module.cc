////////////////////////////////////////////////////////////////////////
// Class:       TriggerOffsetAna
// Plugin Type: analyzer
//
// Per-event TPC<->trigger time offset for ProtoDUNE, computed natively
// from products already in the reco file (no HDF5 / h5py needed):
//
//   offset_us = ( TriggerCandidateData.time_candidate - RDTimeStamp[0] ) * DTS_tick
//             = ( trigger time  -  TPC waveform start ) in microseconds
//
// This is the per-event "frame offset" (the precise waveform-start vs
// trigger value, ~250-282 us for PDHD), i.e. what RDTimeStamp actually
// sees -- the refinement over the nominal 250 us DetectorClocks value.
//
// Verified recipe (xn wcp-porting-validation, method 2): RDTimeStamp from
// tpcrawdecoder:daq, time_candidate from triggerrawdecoder:daq, both in
// DTS ticks of 16 ns.
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
#include "detdataformats/trigger/TriggerCandidateData.hpp"

#include "TTree.h"
#include <vector>

class TriggerOffsetAna : public art::EDAnalyzer {
public:
  explicit TriggerOffsetAna(fhicl::ParameterSet const& p);
  void beginJob() override;
  void analyze(art::Event const& e) override;

private:
  art::InputTag fRDTSTag;   // tpcrawdecoder:daq
  art::InputTag fTCTag;     // triggerrawdecoder:daq
  double        fTickUs;    // DTS tick in us (16 ns -> 0.016)

  TTree* fTree{nullptr};
  int                 fRun{}, fSubRun{}, fEvent{}, fTCType{};
  unsigned long long  fRDTS{}, fTCTime{};
  double              fOffsetUs{};
};

TriggerOffsetAna::TriggerOffsetAna(fhicl::ParameterSet const& p)
  : art::EDAnalyzer(p)
  , fRDTSTag(p.get<art::InputTag>("RDTimeStampTag", art::InputTag("tpcrawdecoder", "daq")))
  , fTCTag  (p.get<art::InputTag>("TriggerCandidateTag", art::InputTag("triggerrawdecoder", "daq")))
  , fTickUs (p.get<double>("DTSTickUs", 0.016))
{}

void TriggerOffsetAna::beginJob()
{
  art::ServiceHandle<art::TFileService> tfs;
  fTree = tfs->make<TTree>("trigger_offset", "per-event TPC-trigger time offset");
  fTree->Branch("run",               &fRun,      "run/I");
  fTree->Branch("subrun",            &fSubRun,   "subrun/I");
  fTree->Branch("event",             &fEvent,    "event/I");
  fTree->Branch("tc_type",           &fTCType,   "tc_type/I");
  fTree->Branch("rd_timestamp",      &fRDTS,     "rd_timestamp/l");      // DTS ticks
  fTree->Branch("tc_time_candidate", &fTCTime,   "tc_time_candidate/l"); // DTS ticks
  fTree->Branch("offset_us",         &fOffsetUs, "offset_us/D");         // trigger - waveform start
}

void TriggerOffsetAna::analyze(art::Event const& e)
{
  fRun = e.run(); fSubRun = e.subRun(); fEvent = e.event();
  fRDTS = 0; fTCTime = 0; fTCType = -1; fOffsetUs = -1e9;

  art::Handle<std::vector<raw::RDTimeStamp>> rdtsH;
  art::Handle<std::vector<dunedaq::trgdataformats::TriggerCandidateData>> tcH;
  e.getByLabel(fRDTSTag, rdtsH);
  e.getByLabel(fTCTag,   tcH);

  if (rdtsH.isValid() && !rdtsH->empty() && tcH.isValid() && !tcH->empty()) {
    fRDTS   = rdtsH->at(0).GetTimeStamp();
    fTCTime = tcH->at(0).time_candidate;
    fTCType = static_cast<int>(tcH->at(0).type);
    // trigger - waveform start, in us (positive ~250-282 us for PDHD)
    fOffsetUs = static_cast<double>(static_cast<long long>(fTCTime) -
                                    static_cast<long long>(fRDTS)) * fTickUs;
  }
  fTree->Fill();
}

DEFINE_ART_MODULE(TriggerOffsetAna)
