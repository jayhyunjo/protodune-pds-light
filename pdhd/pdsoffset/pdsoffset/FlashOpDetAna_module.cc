////////////////////////////////////////////////////////////////////////
// Class:       FlashOpDetAna
// Plugin Type: analyzer
//
// Per-OpDet (physical photon detector) info for charge-light matching / BEE.
//
// IMPORTANT mapping note:
//   recob::OpHit/OpFlash "OpChannel" IS the OpDet index in DUNE (1:1), the same
//   convention used by sim (cf. larana SimPhotonCounter, which loops 0..NOpDet
//   and uses OpDetGeoFromOpDet(ch)). So we map OpChannel -> OpDet *directly* and
//   take the position from geo::Geometry::OpDetGeoFromOpDet().
//   We deliberately do NOT use WireReadout::OpDetFromOpChannel -- that is the
//   hardware-readout-channel map (the generic FD GeoObjectSorterAPA one), which
//   collapses everything onto the +x plane for PDHD and is the wrong abstraction.
//
//   opdet_geo  : one row per optical detector (all NOpDets)  -> opdet, x, y, z
//   flash_opdet: one row per (flash, OpDet)                  -> run, event,
//                flash_id, flash_time, flash_total_pe, opdet, x, y, z, pe
////////////////////////////////////////////////////////////////////////

#include "art/Framework/Core/EDAnalyzer.h"
#include "art/Framework/Core/ModuleMacros.h"
#include "art/Framework/Principal/Event.h"
#include "art/Framework/Principal/Handle.h"
#include "art/Framework/Services/Registry/ServiceHandle.h"
#include "art_root_io/TFileService.h"
#include "canvas/Utilities/InputTag.h"
#include "fhiclcpp/ParameterSet.h"

#include "lardataobj/RecoBase/OpFlash.h"
#include "larcore/Geometry/Geometry.h"
#include "larcore/Geometry/WireReadout.h"
#include "larcorealg/Geometry/OpDetGeo.h"
#include "larcorealg/Geometry/TPCGeo.h"
#include "larcoreobj/SimpleTypesAndConstants/geo_vectors.h"

#include "TTree.h"
#include <vector>

class FlashOpDetAna : public art::EDAnalyzer {
public:
  explicit FlashOpDetAna(fhicl::ParameterSet const& p);
  void beginJob() override;
  void analyze(art::Event const& e) override;

private:
  art::InputTag fFlashTag;

  TTree* fGeo{nullptr};
  TTree* fFlashOD{nullptr};

  int    fRun{}, fSubRun{}, fEvent{}, fFlashID{}, fOpDet{};
  double fX{}, fY{}, fZ{}, fPE{}, fFlashTime{}, fFlashTotalPE{};
};

FlashOpDetAna::FlashOpDetAna(fhicl::ParameterSet const& p)
  : art::EDAnalyzer(p)
  , fFlashTag(p.get<art::InputTag>("OpFlashTag", art::InputTag("opflash")))
{}

void FlashOpDetAna::beginJob()
{
  art::ServiceHandle<art::TFileService> tfs;

  fGeo = tfs->make<TTree>("opdet_geo", "optical detector positions (all OpDets)");
  fGeo->Branch("opdet", &fOpDet, "opdet/I");
  fGeo->Branch("x", &fX, "x/D");
  fGeo->Branch("y", &fY, "y/D");
  fGeo->Branch("z", &fZ, "z/D");

  fFlashOD = tfs->make<TTree>("flash_opdet", "PE per OpDet per flash");
  fFlashOD->Branch("run", &fRun, "run/I");
  fFlashOD->Branch("subrun", &fSubRun, "subrun/I");
  fFlashOD->Branch("event", &fEvent, "event/I");
  fFlashOD->Branch("flash_id", &fFlashID, "flash_id/I");
  fFlashOD->Branch("flash_time", &fFlashTime, "flash_time/D");
  fFlashOD->Branch("flash_total_pe", &fFlashTotalPE, "flash_total_pe/D");
  fFlashOD->Branch("opdet", &fOpDet, "opdet/I");
  fFlashOD->Branch("x", &fX, "x/D");
  fFlashOD->Branch("y", &fY, "y/D");
  fFlashOD->Branch("z", &fZ, "z/D");
  fFlashOD->Branch("pe", &fPE, "pe/D");

  // ---- diagnostic: which of OpChannels 0..159 does the WireReadout consider valid? ----
  {
    auto const& wr = art::ServiceHandle<geo::WireReadout>()->Get();
    std::cout << "[FlashOpDetAna] NOpChannels=" << wr.NOpChannels()
              << "  MaxOpChannel=" << wr.MaxOpChannel() << "\n[FlashOpDetAna] INVALID OpChannels in 0-159: ";
    for (int ch = 0; ch < 160; ++ch)
      if (!wr.IsValidOpChannel(static_cast<unsigned int>(ch))) std::cout << ch << " ";
    std::cout << std::endl;

    // ---- diagnostic: OpChannel -> OpDet map + positions both ways ----
    art::ServiceHandle<geo::Geometry const> g;
    int permuted = 0;
    std::cout << "[MAPCHECK] ch  OpDetFromOpChannel  y_opch z_opch  y_map z_map" << std::endl;
    for (int ch = 0; ch < 160; ++ch) {
      if (!wr.IsValidOpChannel(static_cast<unsigned int>(ch))) continue;
      int od = static_cast<int>(wr.OpDetFromOpChannel(static_cast<unsigned int>(ch)));
      auto p1 = g->OpDetGeoFromOpDet(static_cast<unsigned int>(ch)).GetCenter();
      auto p2 = g->OpDetGeoFromOpDet(static_cast<unsigned int>(od)).GetCenter();
      if (od != ch) ++permuted;
      if (ch < 80)
        std::cout << "[MAPCHECK] " << ch << "  " << od << "   " << p1.Y() << " " << p1.Z()
                  << "   " << p2.Y() << " " << p2.Z() << std::endl;
    }
    std::cout << "[MAPCHECK] permuted (OpDetFromOpChannel != opch) count = " << permuted << std::endl;

    // ---- diagnostic: TPC (APA) layout from the geometry, to correlate OpDet blocks
    //      to the collaboration's APA numbering (PDs sit on these APA frames) ----
    std::cout << "[APACHK] NTPC=" << g->NTPC() << std::endl;
    for (auto const& tpc : g->Iterate<geo::TPCGeo>())
      std::cout << "[APACHK] TPC t" << tpc.ID().TPC
                << "  centerX=" << tpc.GetCenter().X()
                << "  centerZ=" << tpc.GetCenter().Z() << std::endl;
    // one collection-plane TPC channel per PHYSICAL APA (from PD2HDChannelMap col1):
    //   APA1->2000, APA2->7000, APA3->4500, APA4->9500  -> get its wire (x,z)
    for (unsigned int chan : {2000u, 7000u, 4500u, 9500u}) {
      auto const wids = wr.ChannelToWire(chan);
      if (!wids.empty()) {
        auto wc = wr.Wire(wids[0]).GetCenter();
        std::cout << "[CHANCHK] TPCchan " << chan << "  wireX=" << wc.X() << "  wireZ=" << wc.Z() << std::endl;
      }
    }
  }

  // all OpDets, directly from the geometry (both anode planes)
  art::ServiceHandle<geo::Geometry const> geom;
  for (unsigned int iod = 0; iod < geom->NOpDets(); ++iod) {
    auto const c = geom->OpDetGeoFromOpDet(iod).GetCenter();
    fOpDet = static_cast<int>(iod);
    fX = c.X(); fY = c.Y(); fZ = c.Z();
    fGeo->Fill();
  }
}

void FlashOpDetAna::analyze(art::Event const& e)
{
  fRun = e.run(); fSubRun = e.subRun(); fEvent = e.event();

  art::ServiceHandle<geo::Geometry const> geom;
  unsigned int const nopdet = geom->NOpDets();

  art::Handle<std::vector<recob::OpFlash>> fh;
  e.getByLabel(fFlashTag, fh);
  if (!fh.isValid()) return;

  for (size_t i = 0; i < fh->size(); ++i) {
    auto const& fl = fh->at(i);
    fFlashID = static_cast<int>(i);
    fFlashTime = fl.Time();
    fFlashTotalPE = fl.TotalPE();

    auto const& pes = fl.PEs();   // indexed by OpChannel == OpDet (DUNE convention)
    for (size_t ch = 0; ch < pes.size(); ++ch) {
      if (pes[ch] <= 0) continue;
      if (ch >= nopdet) continue;                 // guard out-of-range
      auto const c = geom->OpDetGeoFromOpDet(static_cast<unsigned int>(ch)).GetCenter();
      fOpDet = static_cast<int>(ch);
      fX = c.X(); fY = c.Y(); fZ = c.Z();
      fPE = pes[ch];
      fFlashOD->Fill();
    }
  }
}

DEFINE_ART_MODULE(FlashOpDetAna)
