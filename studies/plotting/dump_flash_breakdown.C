void dump_flash_breakdown(const char* in, const char* out){
  TFile* f=TFile::Open(in);
  TTree* t=(TTree*)f->Get("opflashana/FlashBreakdownTree");
  int EventID, FlashID, OpChannel; float NPe, TotalPE; double FlashTime;
  t->SetBranchAddress("EventID",&EventID); t->SetBranchAddress("FlashID",&FlashID);
  t->SetBranchAddress("OpChannel",&OpChannel); t->SetBranchAddress("NPe",&NPe);
  t->SetBranchAddress("FlashTime",&FlashTime); t->SetBranchAddress("TotalPE",&TotalPE);
  FILE* o=fopen(out,"w"); fprintf(o,"event,flash_id,opchannel,npe,flashtime,totalpe\n");
  Long64_t n=t->GetEntries(), kept=0;
  for(Long64_t i=0;i<n;i++){ t->GetEntry(i);
    if(!(NPe<1e30) || NPe<=0) continue;   // drop inf/zero
    if(OpChannel<0 || OpChannel>=40) continue; // physical OpDets only
    fprintf(o,"%d,%d,%d,%.5g,%.6g,%.5g\n",EventID,FlashID,OpChannel,NPe,FlashTime,TotalPE); kept++;
  }
  fclose(o); printf("wrote %lld / %lld rows -> %s\n", kept, n, out);
}
