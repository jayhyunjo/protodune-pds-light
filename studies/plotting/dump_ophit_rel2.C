// Dump PerOpHitTree with BOTH PeakTime and PeakTimeAbs, each relative to its per-event
// min (full precision preserved). Lets us test coincidence on the finder's actual variable.
#include <map>
void dump_ophit_rel2(const char* in, const char* out){
  TFile* f=TFile::Open(in);
  TTree* t=(TTree*)f->Get("opflashana/PerOpHitTree");
  if(!t){ printf("!! no PerOpHitTree\n"); f->ls(); return; }
  int EventID=0, OpChannel=0; double PeakTime=0, PeakTimeAbs=0; float PE=0;
  t->SetBranchAddress("EventID",&EventID); t->SetBranchAddress("OpChannel",&OpChannel);
  t->SetBranchAddress("PeakTime",&PeakTime); t->SetBranchAddress("PeakTimeAbs",&PeakTimeAbs);
  t->SetBranchAddress("PE",&PE);
  Long64_t n=t->GetEntries();
  std::map<int,double> mnT, mnTA;
  for(Long64_t i=0;i<n;i++){ t->GetEntry(i);
    if(!mnT.count(EventID)||PeakTime<mnT[EventID]) mnT[EventID]=PeakTime;
    if(!mnTA.count(EventID)||PeakTimeAbs<mnTA[EventID]) mnTA[EventID]=PeakTimeAbs; }
  FILE* o=fopen(out,"w"); fprintf(o,"event,opchannel,ptime_rel,ptimeabs_rel,pe\n");
  for(Long64_t i=0;i<n;i++){ t->GetEntry(i);
    fprintf(o,"%d,%d,%.6f,%.6f,%.5g\n",EventID,OpChannel,PeakTime-mnT[EventID],PeakTimeAbs-mnTA[EventID],PE); }
  fclose(o); printf("wrote %lld -> %s\n",n,out);
}
