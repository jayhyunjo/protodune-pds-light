////////////////////////////////////////////////////////////////////////
// Class:       PDSDecoWaveformDump
// Plugin Type: analyzer
//
// Dumps EVERY deconvolved optical waveform (recob::OpWaveform, from `opdec`) to a
// flat TTree, with NO per-event cap. DecoAnalysis ('decoana') saves only ~400
// waveforms/event, so in busy events most lit channels have flash PE but no stored
// deconvolved waveform; this module stores them all so the viewer can show a
// deconvolved trace for any channel.
//
// One row per OpWaveform record:
//   run, subrun, event, opch, timestamp (= associated raw OpDetWaveform time),
//   nsamples, adc[nsamples]  (deconvolved signal, float)
////////////////////////////////////////////////////////////////////////

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art/Framework/Principal/Handle.h"
#include "art/Framework/Services/Registry/ServiceHandle.h"
#include "art_root_io/TFileService.h"
#include "canvas/Utilities/InputTag.h"
#include "fhiclcpp/ParameterSet.h"

#include "lardataobj/RecoBase/OpWaveform.h"

#include "TTree.h"
#include <vector>

class PDSDecoWaveformDump : public art::EDAnalyzer {
public:
  explicit PDSDecoWaveformDump(fhicl::ParameterSet const& p);
  void beginJob() override;
  void analyze(art::Event const& e) override;

private:
  art::InputTag fTag;

  TTree* fTree{nullptr};
  int    fRun{}, fSubRun{}, fEvent{}, fOpCh{}, fNSamples{};
  double fTimeStamp{};
  std::vector<float> fAdc;
};

PDSDecoWaveformDump::PDSDecoWaveformDump(fhicl::ParameterSet const& p)
  : art::EDAnalyzer(p)
  , fTag(p.get<art::InputTag>("OpWaveformTag", art::InputTag("opdec")))
{}

void PDSDecoWaveformDump::beginJob()
{
  art::ServiceHandle<art::TFileService> tfs;
  fTree = tfs->make<TTree>("deco_waveform", "all deconvolved recob::OpWaveforms (one row per record)");
  fTree->Branch("run", &fRun, "run/I");
  fTree->Branch("subrun", &fSubRun, "subrun/I");
  fTree->Branch("event", &fEvent, "event/I");
  fTree->Branch("opch", &fOpCh, "opch/I");
  fTree->Branch("timestamp", &fTimeStamp, "timestamp/D");
  fTree->Branch("nsamples", &fNSamples, "nsamples/I");
  fTree->Branch("adc", &fAdc);
}

void PDSDecoWaveformDump::analyze(art::Event const& e)
{
  art::Handle<std::vector<recob::OpWaveform>> h;
  e.getByLabel(fTag, h);
  if (!h.isValid()) return;

  fRun = e.run(); fSubRun = e.subRun(); fEvent = e.event();
  for (auto const& wf : *h) {
    fOpCh = static_cast<int>(wf.Channel());
    fTimeStamp = wf.TimeStamp();
    auto const sig = wf.Signal();
    fNSamples = static_cast<int>(sig.size());
    fAdc.assign(sig.begin(), sig.end());
    fTree->Fill();
  }
}

DEFINE_ART_MODULE(PDSDecoWaveformDump)
