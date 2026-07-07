void ophit_times(const char* in){
  TFile* f=TFile::Open(in);
  TTree* t=(TTree*)f->Get("opflashana/PerOpHitTree");
  printf("PerOpHitTree entries=%lld\n", t->GetEntries());
  TObjArray* br=t->GetListOfBranches();
  for(int i=0;i<br->GetEntries();i++){
    TBranch* b=(TBranch*)br->At(i); const char* nm=b->GetName();
    printf("  %-16s min=%.6g  max=%.6g\n", nm, t->GetMinimum(nm), t->GetMaximum(nm));
  }
  // how many distinct PeakTimeAbs values within a tight window? proxy for time-coincidence
}
