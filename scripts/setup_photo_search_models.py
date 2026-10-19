"""Install pinned local image/text encoders. Never uploads project evidence."""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'.local/models/photo-search'
MODELS={
 'vision':{'repo':'Qdrant/clip-ViT-B-32-vision','revision':'e0c24ed0fa57fa3e4f97f30de74c51d944036ace',
           'sha256':'c68d3d9a200ddd2a8c8a5510b576d4c94d1ae383bf8b36dd8c084f94e1fb4d63',
           'files':['config.json','preprocessor_config.json','model.onnx']},
 'text':{'repo':'Qdrant/clip-ViT-B-32-text','revision':'48ca1db27cb4063eb311ec2aa7f087a808112876',
         'sha256':'4dbe762b11e36488304471e439cde89da053ad7acaddbf9e096745d142ec8d8b',
         'files':['config.json','merges.txt','special_tokens_map.json','tokenizer.json','tokenizer_config.json','vocab.json','model.onnx']}}

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    os.environ['HF_HOME']=str(DEST/'hub')
    os.environ['HF_HUB_CACHE']=str(DEST/'hub/cache')
    os.environ['HF_HUB_DISABLE_XET']='1'
    from huggingface_hub import hf_hub_download
    def install(pair):
        kind,spec=pair
        for name in spec['files']:
            hf_hub_download(spec['repo'],name,revision=spec['revision'],local_dir=DEST/kind)
        actual=hashlib.file_digest((DEST/kind/'model.onnx').open('rb'),'sha256').hexdigest()
        if actual!=spec['sha256']:raise ValueError('Pinned model checksum mismatch: '+kind)
        if json.loads((DEST/kind/'config.json').read_text())['model_type']!='clip':
            # These ONNX ports may expose the component architecture explicitly.
            config=json.loads((DEST/kind/'config.json').read_text())
            if config['model_type'] not in {'clip_vision_model','clip_text_model'}:raise ValueError('Unexpected encoder architecture.')
        print('Verified local '+kind+' encoder: '+actual,flush=True)
        return kind,{**spec,'model_sha256':actual,'dimension':512,'license':'MIT'}
    with ThreadPoolExecutor(max_workers=2) as pool:manifest=dict(pool.map(install,MODELS.items()))
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Photo-search models ready under '+str(DEST),flush=True)

if __name__=='__main__':main()
