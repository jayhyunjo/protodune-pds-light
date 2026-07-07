// Dump a FlashBreakdownTree (event,flash_id,opchannel,npe) with NPe>0, any channel range.
void dump_flash_generic(const char* in, const char* tree, const char* out){
  TFile* f=TFile::Open(in);
  TTree* t=(TTree*)f->Get(tree);
  if(!t){ printf("!! no tree '%s' in %s. keys:\n",tree,in); f->ls(); return; }
  printf("tree '%s' entries=%lld ; branches:", tree, t->GetEntries());
  TObjArray* br=t->GetListOfBranches();
  for(int i=0;i<br->GetEntries();i++) printf(" %s",br->At(i)->GetName());
  printf("\n");
  int EventID=0, FlashID=0, OpChannel=0; float NPe=0;
  t->SetBranchAddress("EventID",&EventID); t->SetBranchAddress("FlashID",&FlashID);
  t->SetBranchAddress("OpChannel",&OpChannel); t->SetBranchAddress("NPe",&NPe);
  FILE* o=fopen(out,"w"); fprintf(o,"event,flash_id,opchannel,npe\n");
  Long64_t n=t->GetEntries(), kept=0;
  for(Long64_t i=0;i<n;i++){ t->GetEntry(i);
    if(!(NPe<1e30) || NPe<=0) continue;
    fprintf(o,"%d,%d,%d,%.5g\n",EventID,FlashID,OpChannel,NPe); kept++;
  }
  fclose(o); printf("wrote %lld/%lld -> %s\n",kept,n,out);
}
