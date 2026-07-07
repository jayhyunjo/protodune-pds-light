// Dump PerOpHitTree (event, opchannel, peaktime, peaktimeabs, pe) from an OpFlashAna file.
void dump_ophit(const char* in, const char* out){
  TFile* f=TFile::Open(in);
  TTree* t=(TTree*)f->Get("opflashana/PerOpHitTree");
  if(!t){ printf("!! no opflashana/PerOpHitTree in %s\n",in); f->ls(); return; }
  int EventID=0, OpChannel=0; double PeakTime=0, PeakTimeAbs=0; float PE=0;
  t->SetBranchAddress("EventID",&EventID); t->SetBranchAddress("OpChannel",&OpChannel);
  t->SetBranchAddress("PeakTime",&PeakTime); t->SetBranchAddress("PeakTimeAbs",&PeakTimeAbs);
  t->SetBranchAddress("PE",&PE);
  FILE* o=fopen(out,"w"); fprintf(o,"event,opchannel,peaktime,peaktimeabs,pe\n");
  Long64_t n=t->GetEntries();
  for(Long64_t i=0;i<n;i++){ t->GetEntry(i);
    fprintf(o,"%d,%d,%.8g,%.8g,%.5g\n",EventID,OpChannel,PeakTime,PeakTimeAbs,PE); }
  fclose(o); printf("wrote %lld -> %s\n",n,out);
}
