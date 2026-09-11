"""Owner-supplied draft sources. No approval, file execution, OCR or network."""
import base64
import hashlib
import re

def validate(items, text_validator):
    if not isinstance(items,list) or len(items)>4:
        raise ValueError('Attach up to four files.')
    result=[];total=0
    for item in items:
        if not isinstance(item,dict) or set(item)-{'name','text','image'}:
            raise ValueError('Invalid attachment fields.')
        name=item.get('name','')
        if not isinstance(name,str) or not re.fullmatch(r'[\w .()-]{1,100}',name) or name in {'.','..'}:
            raise ValueError('Use a simple attachment filename without folders.')
        text=text_validator(item.get('text',''),'Attachment text',12000,required=True)
        total+=len(text.encode('utf-8'))
        if total>24000:raise ValueError('Attachment text exceeds 24 KB in total. Use a shorter source excerpt.')
        value={'name':name,'text':text,'authority':'OWNER_SUPPLIED_UNVERIFIED_SOURCE','approved':False}
        image=item.get('image')
        if image is not None:
            if not isinstance(image,str) or len(image)>45000:raise ValueError('Image reference is too large.')
            raw=base64.b64decode(image,validate=True)
            if not raw.startswith(b'\xff\xd8\xff') or not raw.endswith(b'\xff\xd9'):
                raise ValueError('Image reference must be a JPEG preview.')
            value.update(image=image,image_sha256=hashlib.sha256(raw).hexdigest(),interpretation='OWNER_DESCRIPTION_ONLY_NO_OCR')
        elif not name.lower().endswith(('.txt','.md','.csv','.json','.yaml','.yml')):
            raise ValueError('Use TXT, MD, CSV, JSON, YAML or an image with your description.')
        value['source_sha256']=hashlib.sha256((name+'\n'+text).encode()).hexdigest()
        result.append(value)
    return result

def context(items):
    return [{k:v for k,v in item.items() if k!='image'} for item in items]

def passages(items, timestamp):
    result={}
    for i,item in enumerate(items,1):
        # Bounded verbatim chunks, never synthesized or silently truncated.
        chunks=re.findall(r'.{1,1400}(?:\s|$)|.{1,1400}',item['text'],re.S)
        for j,chunk in enumerate(chunks,1):
            if chunk.strip():
                result[f'A{i}:P{j}']={'text':chunk.strip(),'url':'','retrieved_at':timestamp,
                    'source_name':item['name'],'source_sha256':item['source_sha256'],
                    'authority':item['authority'],'interpretation':item.get('interpretation','OWNER_DOCUMENT_TEXT')}
    return result
