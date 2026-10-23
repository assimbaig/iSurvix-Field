"""Download public semantic weights into this project; no evidence is uploaded."""
import os
from pathlib import Path

# Public model installation does not authorize native analytics traffic.
os.environ['ORT_DISABLE_TELEMETRY'] = '1'

root=Path(__file__).resolve().parents[1]
cache=root/'.local/models/embeddings'
cache.mkdir(parents=True,exist_ok=True)
os.environ['HF_HOME']=str(cache/'huggingface')
os.environ['HF_HUB_CACHE']=str(cache/'huggingface/hub')
os.environ['FASTEMBED_CACHE_PATH']=str(cache)
from fastembed import TextEmbedding

model=TextEmbedding(model_name='BAAI/bge-small-en-v1.5',cache_dir=str(cache),
                    threads=2,providers=['CPUExecutionProvider'])
vector=list(model.embed(['Local evidence matching setup verification.']))[0]
print(f'Local semantic model ready: {len(vector)} dimensions. Cache: {cache}')
