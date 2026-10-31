"""Bounded local OCR/QR/quality adapters. Never follow QR URLs or infer survey facts."""
from functools import lru_cache
from io import BytesIO
import math
from datetime import datetime
from pathlib import Path
from PIL import Image,ImageFilter,ImageStat

TOOL_VERSION='local-tools-v1'


def _ocr_model_paths():
    """Resolve only the already-installed RapidOCR 1.4.4 model bundle.

    Metadata lookup does not import ONNX or construct an engine. Check every
    file before importing the OCR package so a missing bundle cannot invoke a
    constructor's fallback or download behavior, now or after an upgrade.
    """
    from importlib import metadata
    try:
        package=metadata.distribution('rapidocr-onnxruntime')
        root=Path(package.locate_file('rapidocr_onnxruntime/models'))
        names={'det_model_path':'ch_PP-OCRv4_det_infer.onnx',
               'cls_model_path':'ch_ppocr_mobile_v2.0_cls_infer.onnx',
               'rec_model_path':'ch_PP-OCRv4_rec_infer.onnx'}
        paths={}
        for key,name in names.items():
            path=(root/name).resolve(strict=True)
            if not path.is_file() or path.stat().st_size<=0:raise OSError()
            with path.open('rb') as model:
                if not model.read(1):raise OSError()
            paths[key]=str(path)
        return paths
    except (metadata.PackageNotFoundError,OSError,ValueError,TypeError):
        raise ImportError('The approved offline OCR model bundle is unavailable.') from None


@lru_cache(maxsize=1)
def _ocr_engine():
    paths=_ocr_model_paths()
    from rapidocr_onnxruntime import RapidOCR
    # Leave CPU capacity for the web app, embeddings and GPU input preparation.
    # Unbounded ONNX thread pools can contend heavily on this eight-core PC.
    return RapidOCR(**paths,intra_op_num_threads=2, inter_op_num_threads=1)

def capture_facts(source_metadata):
    source=source_metadata if isinstance(source_metadata,dict) else {}
    facts={}
    value=source.get('captured_at')
    if isinstance(value,str) and len(value)<=100:
        for parser in [lambda text:datetime.strptime(text,'%Y:%m:%d %H:%M:%S'),datetime.fromisoformat]:
            try:parser(value);facts['captured_at']=value;break
            except (ValueError,TypeError):pass
    gps=source.get('gps')
    if isinstance(gps,dict):
        try:
            if any(type(gps[key]) is bool for key in ['latitude','longitude']):raise ValueError()
            lat,lon=float(gps['latitude']),float(gps['longitude'])
            if math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180 and (lat!=0 or lon!=0):facts['gps']={'latitude':lat,'longitude':lon}
        except (KeyError,TypeError,ValueError,OverflowError):pass
    return facts

def _lines(raw):
    # RapidOCR returns (rows, elapsed); test/local adapters may return rows directly.
    rows=raw[0] if isinstance(raw,tuple) else raw
    if rows is None:return []
    if not isinstance(rows,list) or len(rows)>10000:raise ValueError('Invalid OCR output.')
    result=[]
    for row in rows[:64]:
        if isinstance(row,dict):text,confidence,box=row.get('text'),row.get('confidence'),row.get('box',[])
        elif isinstance(row,(list,tuple)) and len(row)==3:box,text,confidence=row
        else:continue
        if not isinstance(text,str) or not text.strip() or type(confidence) not in {float,int} or not math.isfinite(confidence) or not 0<=confidence<=1:continue
        points=[]
        if hasattr(box,'tolist'):box=box.tolist()
        if isinstance(box,(list,tuple)) and len(box)<=4:
            for point in box:
                if isinstance(point,(list,tuple)) and len(point)==2 and all(type(value) in {float,int} and math.isfinite(value) for value in point):points.append([round(float(value),3) for value in point])
        result.append({'text':text.strip()[:200],'confidence':round(float(confidence),6),'box':points})
    return result

def extract_local_tools(image_source,ocr_backend=None,qr_backend=None,source_metadata=None):
    if isinstance(image_source,Image.Image):image=image_source.copy()
    elif isinstance(image_source,(bytes,bytearray)):image=Image.open(BytesIO(image_source))
    else:image=Image.open(image_source)
    if image.width*image.height>24000000:raise ValueError('Image exceeds local evidence dimensions.')
    image=image.convert('RGB')
    image.thumbnail((1600,1600))
    result={'version':TOOL_VERSION,'ocr_lines':[],'qr_values':[],'capture_facts':capture_facts(source_metadata),'quality':{'width':image.width,'height':image.height,'low_resolution':min(image.size)<400},'errors':[]}
    sample=image.copy();sample.thumbnail((512,512))
    edges=sample.convert('L').filter(ImageFilter.FIND_EDGES)
    if min(edges.size)>2:edges=edges.crop((1,1,edges.width-1,edges.height-1))
    blur=float(ImageStat.Stat(edges).var[0])
    result['quality'].update({'blur_score':round(blur,3),'possible_blur':blur<60,'method':'pillow-edge-variance-v1'})
    try:
        if ocr_backend is None:
            import numpy as np
            raw=_ocr_engine()(np.asarray(image))
        else:raw=ocr_backend(image)
        result['ocr_lines']=_lines(raw)
    except ImportError:result['errors'].append({'tool':'ocr','code':'unavailable'})
    except Exception:result['errors'].append({'tool':'ocr','code':'processing_failed'})
    try:
        if qr_backend is None:
            import cv2
            import numpy as np
            detector=cv2.QRCodeDetector();pixels=np.asarray(image)[:,:,::-1]
            success,decoded,_,_=detector.detectAndDecodeMulti(pixels)
            if success:values=list(decoded)
            else:
                text,_,_=detector.detectAndDecode(pixels);values=[text] if text else []
        else:values=qr_backend(image)
        if not isinstance(values,(list,tuple)):raise ValueError('Invalid QR output.')
        result['qr_values']=sorted({value.strip()[:512] for value in values[:8] if isinstance(value,str) and value.strip()})
    except ImportError:result['errors'].append({'tool':'qr','code':'unavailable'})
    except Exception:result['errors'].append({'tool':'qr','code':'processing_failed'})
    return result

def _vector(value):
    if not isinstance(value,list) or not 1<=len(value)<=4096 or any(type(number) not in {int,float} or not math.isfinite(number) for number in value):raise ValueError('Invalid local embedding vector.')
    return value


def local_ocr(image_source,ocr_backend=None):
    """Local text/confidence/boxes only; QR contents never trigger lookups.

    A controlled backend can be supplied by ordinary tests. Actual native OCR
    is verified separately against synthetic evidence and installed weights.
    OCR text is source evidence, not a verified engineering answer.
    """
    result=extract_local_tools(image_source,ocr_backend=ocr_backend,qr_backend=lambda image:[])
    errors=[entry['code'] for entry in result['errors'] if entry.get('tool')=='ocr']
    result['status']='unavailable' if 'unavailable' in errors else 'failed' if errors else 'complete'
    from importlib import metadata
    try:version=metadata.version('rapidocr-onnxruntime') if ocr_backend is None else None
    except metadata.PackageNotFoundError:version=None
    result['provenance']={'engine':'rapidocr-onnxruntime' if ocr_backend is None else 'provided_adapter',
                          'version':version,'verification_status':'unverified_source_text'}
    return result

def semantic_similarities(metadata,fields,embed_callback):
    if not isinstance(fields,list) or len(fields)>500:raise ValueError('Bound the field catalog before embedding.')
    subject=' '.join([metadata.get('caption',''),*metadata.get('objects',[])])[:1600]
    texts=[subject]+[(str(field.get('label',''))+' '+str(field.get('description','')))[:800] for field in fields]
    vectors=[]
    for start in range(0,len(texts),32):
        batch=texts[start:start+32];values=embed_callback(batch)
        if not isinstance(values,list) or len(values)!=len(batch):raise ValueError('Local embeddings do not match the requested batch.')
        vectors.extend(_vector(value) for value in values)
    if not vectors:return {}
    query=vectors[0];norm=math.sqrt(math.fsum(number*number for number in query))
    result={}
    for field,vector in zip(fields,vectors[1:]):
        if len(vector)!=len(query):raise ValueError('Local embedding dimensions changed.')
        other_norm=math.sqrt(math.fsum(number*number for number in vector))
        value=math.fsum(a*b for a,b in zip(query,vector))/(norm*other_norm) if norm and other_norm else 0.0
        result[field['id']]=round(max(-1.0,min(1.0,value)),6)
    return result
