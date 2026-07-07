////////////////////////////////////////////////////////////////////////
// Class:       PDSRawWaveformDump
// Plugin Type: analyzer
//
// Dumps EVERY raw optical waveform (raw::OpDetWaveform) regardless of whether
// the channel was deconvolved. This preserves the raw light for channels the
// deconvolution ignores (e.g. APA1 full-stream channels 120-159, which have no
// SPE templates) and therefore appear nowhere in the flat output (DecoAnalysis
// only stores deconvolved channels, 0-119).
//
// Two output modes (either or both, via fhicl):
//   MakeTree (default true): flat TTree "raw_waveform", one row per record:
//     run, subrun, event, opch, timestamp, nsamples, adc[nsamples]
//   MakeHistograms (default false): per-record TH1S histograms laid out like
//     DecoAnalysis -> run_<run>_evt_<evt>/ch<N>/waveform_<K>, x-axis in us
//     (DTSTickUs/bin), y-axis ADC. Browsable in a TBrowser.
//
// Channels: empty (default) = all channels; otherwise only the listed OpCh.
////////////////////////////////////////////////////////////////////////

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art/Framework/Principal/Handle.h"
#include "art/Framework/Services/Registry/ServiceHandle.h"
#include "art_root_io/TFileService.h"
#include "art_root_io/TFileDirectory.h"
#include "canvas/Utilities/InputTag.h"
#include "fhiclcpp/ParameterSet.h"

#include "lardataobj/RawData/OpDetWaveform.h"

#include "TTree.h"
#include "TH1S.h"
#include "TString.h"
#include <map>
#include <set>
#include <vector>

class PDSRawWaveformDump : public art::EDAnalyzer {
public:
  explicit PDSRawWaveformDump(fhicl::ParameterSet const& p);
  void beginJob() override;
  void analyze(art::Event const& e) override;

private:
  art::InputTag fTag;
  std::set<int> fChannels;        // empty => all channels
  bool          fMakeTree;
  bool          fMakeHistograms;
  double        fTickUs;          // sample period in us (DAPHNE: 16 ns)

  TTree* fTree{nullptr};
  int    fRun{}, fSubRun{}, fEvent{}, fOpCh{}, fNSamples{};
  double fTimeStamp{};
  std::vector<short> fAdc;
};

PDSRawWaveformDump::PDSRawWaveformDump(fhicl::ParameterSet const& p)
  : art::EDAnalyzer(p)
  , fTag(p.get<art::InputTag>("OpDetWaveformTag", art::InputTag("pdhddaphne", "daq")))
  , fMakeTree(p.get<bool>("MakeTree", true))
  , fMakeHistograms(p.get<bool>("MakeHistograms", false))
  , fTickUs(p.get<double>("DTSTickUs", 0.016))
{
  for (int c : p.get<std::vector<int>>("Channels", std::vector<int>())) fChannels.insert(c);
}

void PDSRawWaveformDump::beginJob()
{
  if (!fMakeTree) return;
  art::ServiceHandle<art::TFileService> tfs;
  fTree = tfs->make<TTree>("raw_waveform", "all raw OpDetWaveforms (one row per record)");
  fTree->Branch("run", &fRun, "run/I");
  fTree->Branch("subrun", &fSubRun, "subrun/I");
  fTree->Branch("event", &fEvent, "event/I");
  fTree->Branch("opch", &fOpCh, "opch/I");
  fTree->Branch("timestamp", &fTimeStamp, "timestamp/D");
  fTree->Branch("nsamples", &fNSamples, "nsamples/I");
  fTree->Branch("adc", &fAdc);
}

void PDSRawWaveformDump::analyze(art::Event const& e)
{
  art::Handle<std::vector<raw::OpDetWaveform>> h;
  e.getByLabel(fTag, h);
  if (!h.isValid()) return;

  fRun = e.run(); fSubRun = e.subRun(); fEvent = e.event();

  if (fMakeTree) {
    for (auto const& wf : *h) {
      int const ch = static_cast<int>(wf.ChannelNumber());
      if (!fChannels.empty() && !fChannels.count(ch)) continue;
      fOpCh = ch;
      fTimeStamp = wf.TimeStamp();
      fNSamples = static_cast<int>(wf.size());
      fAdc.assign(wf.begin(), wf.end());
      fTree->Fill();
    }
  }

  if (fMakeHistograms) {
    art::ServiceHandle<art::TFileService> tfs;
    art::TFileDirectory evtdir = tfs->mkdir(Form("run_%d_evt_%d", fRun, fEvent));
    std::map<int, art::TFileDirectory> chdir;   // one ch<N> subdir per channel
    std::map<int, int> kcount;                  // record index within the channel
    for (auto const& wf : *h) {
      int const ch = static_cast<int>(wf.ChannelNumber());
      if (!fChannels.empty() && !fChannels.count(ch)) continue;
      if (!chdir.count(ch)) chdir.emplace(ch, evtdir.mkdir(Form("ch%d", ch)));
      int const k = kcount[ch]++;
      int const n = static_cast<int>(wf.size());
      TH1S* hh = chdir.at(ch).make<TH1S>(
        Form("waveform_%d", k),
        Form("OpCh %d  run %d evt %d  t0=%.0f;t - t0 (#mus);ADC", ch, fRun, fEvent, wf.TimeStamp()),
        n, 0.0, n * fTickUs);
      for (int i = 0; i < n; ++i) hh->SetBinContent(i + 1, wf[i]);
    }
  }
}

DEFINE_ART_MODULE(PDSRawWaveformDump)
