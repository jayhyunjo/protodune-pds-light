// Dump PerOpHitTree with time RELATIVE to each event's min (preserves fine precision
// that %.8g on the raw ~1e9-1e17 absolute times destroys).
#include <map>
void dump_ophit_rel(const char* in, const char* out){
  TFile* f=TFile::Open(in);
  TTree* t=(TTree*)f->Get("opflashana/PerOpHitTree");
  if(!t){ printf("!! no opflashana/PerOpHitTree\n"); f->ls(); return; }
  int EventID=0, OpChannel=0; double PeakTimeAbs=0; float PE=0;
  t->SetBranchAddress("EventID",&EventID); t->SetBranchAddress("OpChannel",&OpChannel);
  t->SetBranchAddress("PeakTimeAbs",&PeakTimeAbs); t->SetBranchAddress("PE",&PE);
  Long64_t n=t->GetEntries();
  std::map<int,double> mn;
  for(Long64_t i=0;i<n;i++){ t->GetEntry(i); if(!mn.count(EventID)||PeakTimeAbs<mn[EventID]) mn[EventID]=PeakTimeAbs; }
  FILE* o=fopen(out,"w"); fprintf(o,"event,opchannel,trel,pe\n");
  for(Long64_t i=0;i<n;i++){ t->GetEntry(i); fprintf(o,"%d,%d,%.6f,%.5g\n",EventID,OpChannel,PeakTimeAbs-mn[EventID],PE); }
  fclose(o); printf("wrote %lld -> %s (min offset per event subtracted)\n",n,out);
}
