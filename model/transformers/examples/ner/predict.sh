dffml predict all \
  -model ner_tagger \
  -sources s=csv \
  -source-filename test.csv \
  -model-sid SentenceId:int:1 \
  -model-words Words:str:1 \
  -model-predict Tag:str:1 \
  -model-model_name_or_path bert-base-cased \
  -model-no_cuda \
  -log debug