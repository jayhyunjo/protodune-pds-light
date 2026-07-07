# dunedetdataformats exports an empty INTERFACE target (no include dirs),
# so add its header path explicitly (ups sets DUNEDETDATAFORMATS_INC).
include_directories($ENV{DUNEDETDATAFORMATS_INC})

cet_build_plugin(TriggerOffsetAna art::EDAnalyzer
  LIBRARIES PRIVATE
    lardataobj::RawData
    dunedetdataformats
    art_root_io::TFileService_service
    art::Framework_Principal
    art::Framework_Core
    art::Framework_Services_Registry
    canvas::canvas
    fhiclcpp::fhiclcpp
    messagefacility::MF_MessageLogger
    ROOT::Tree
)

cet_build_plugin(PDSRawWaveformDump art::EDAnalyzer
  LIBRARIES PRIVATE
    lardataobj::RawData
    art_root_io::TFileService_service
    art::Framework_Principal
    art::Framework_Core
    art::Framework_Services_Registry
    canvas::canvas
    fhiclcpp::fhiclcpp
    ROOT::Tree
)

cet_build_plugin(PDSDecoWaveformDump art::EDAnalyzer
  LIBRARIES PRIVATE
    lardataobj::RecoBase
    art_root_io::TFileService_service
    art::Framework_Principal
    art::Framework_Core
    art::Framework_Services_Registry
    canvas::canvas
    fhiclcpp::fhiclcpp
    ROOT::Tree
)

cet_build_plugin(FlashOpDetAna art::EDAnalyzer
  LIBRARIES PRIVATE
    lardataobj::RecoBase
    larcore::WireReadout
    larcore::Geometry_Geometry_service
    larcorealg::Geometry
    larcoreobj::geo_vectors
    art_root_io::TFileService_service
    art::Framework_Principal
    art::Framework_Services_Registry
    canvas::canvas
    fhiclcpp::fhiclcpp
    ROOT::Tree
)

install_fhicl()
install_source()
