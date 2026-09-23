"""Photoshop-free RLAYER4 finishing. No Photoshop process or automation calls.
Only accepts the converter's standard scene-linear sRGB 32-bit flat PSD/PSB.
"""
from pathlib import Path
import copy,re,tempfile,os
import numpy as np
from PIL import Image,ImageCms
from psd_tools import PSDImage
from psd_tools.composite import composite
from psd_tools.api.layers import Group,PixelLayer
from psd_tools.constants import BlendMode,Resource,Compression,ColorMode,Tag
from .psd import linear_profile
from .converter import Cancelled

def pass_name(name):
    if re.search(r'(?:^|[./])Crypto(?:Object|Material|Asset)(?:[./]|$)',name,re.I):return None
    m=re.search(r'(?:^|[./])(AO|GlossDIR|Gloss|Image|Diff|DecalMask)(?:\.RGBA?)?$',name)
    return m[1] if m else None

def srgb8(rgb):
    rgb=np.clip(np.nan_to_num(rgb,nan=0.,posinf=1.,neginf=0.),0,1)
    return np.rint(np.where(rgb<=.0031308,12.92*rgb,1.055*np.power(rgb,1/2.4)-.055)*255).astype(np.uint8)

def alpha8(alpha):return np.rint(np.clip(np.nan_to_num(alpha),0,1)*255).astype(np.uint8)

def finish(source,destination,log=print,cancel=None):
    def check():
        if cancel is not None and cancel.is_set():raise Cancelled('Cancelled')
    check()
    source,destination=Path(source),Path(destination)
    if destination.exists():raise FileExistsError(destination)
    raw=PSDImage.open(source)
    check()
    if raw.depth!=32 or raw.color_mode!=ColorMode.RGB:raise ValueError('Requires converter 32-bit RGB input')
    if raw.image_resources.get_data(Resource.ICC_PROFILE)!=linear_profile():raise ValueError('Photoshop-free finishing only supports the standard scene-linear sRGB converter profile')
    passes={};layers=list(raw)
    for layer in layers:
        if layer.is_group() or layer.has_mask():raise ValueError('Requires fresh flat converter output, with no existing groups or masks')
        key=pass_name(layer.name)
        if key:
            if key in passes:raise ValueError('Ambiguous pass: '+key)
            passes[key]=layer
    if not all(k in passes for k in ['Diff','Image']):raise ValueError('Requires unique Diff and Image passes')
    for name in ['AO','Gloss','GlossDIR','DecalMask']:
        if name not in passes:log('RLAYER4_WARNING: Optional pass missing: '+name)
    log('Creating 8-bit sRGB layer groups and masks...')
    out=PSDImage.new('RGBA',raw.size,depth=8)
    out.background_color=None
    out._record.header.version=2 if destination.suffix.lower()=='.psb' else raw._record.header.version
    for key in [Resource.XMP_METADATA,Resource.RESOLUTION_INFO,Resource.PIXEL_ASPECT_RATIO]:
        if key in raw.image_resources:out.image_resources[key]=copy.deepcopy(raw.image_resources[key])
    out.image_resources[Resource.ICC_PROFILE]=copy.deepcopy(raw.image_resources[Resource.ICC_PROFILE])
    out.image_resources[Resource.ICC_PROFILE].data=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    utility=Group.new(out,'RLAYERS');utility.blend_mode=BlendMode.PASS_THROUGH;utility.visible=False
    comp=Group.new(out,'COMP');comp._bounding_channels=copy.deepcopy(comp._bounding_channels);comp.blend_mode=BlendMode.PASS_THROUGH
    converted={};mask=np.zeros((raw.height,raw.width),np.uint8)
    for layer in layers:
        check()
        log('Finishing '+layer.name)
        rgb=layer.numpy('color') if layer.width and layer.height else None;shape=layer.numpy('shape') if layer.width and layer.height else None
        if rgb is None or rgb.size==0:
            rgba=np.zeros((1,1,4),np.uint8)
        else:
            a=np.ones(rgb.shape[:2]+(1,),np.float32) if shape is None else shape
            rgba=np.concatenate([srgb8(rgb[...,:3]),alpha8(a)],axis=2)
        new=PixelLayer.frompil(Image.fromarray(rgba),utility,name=layer.name,top=layer.top,left=layer.left,compression=Compression.ZIP)
        new._record.tagged_blocks.set_data(Tag.UNICODE_LAYER_NAME,layer.name);new._record.name=layer.name.encode('ascii','replace').decode('ascii');new.visible=layer.visible;converted[layer.name]=new
        if layer is passes['Image']:
            x,y=layer.left,layer.top;h,w=rgba.shape[:2]
            x0,y0,x1,y1=max(x,0),max(y,0),min(x+w,raw.width),min(y+h,raw.height)
            if x1>x0 and y1>y0:mask[y0:y1,x0:x1]=rgba[y0-y:y1-y,x0-x:x1-x,3]
    for key in ['GlossDIR','Diff','Image','Gloss','AO']:
        if key not in passes:continue
        layer=converted[passes[key].name];layer.move_to_group(comp)
        layer.visible=key!='GlossDIR'
        if key in ['AO','Gloss','Image']:
            layer.opacity=128
            layer.blend_mode={'AO':BlendMode.MULTIPLY,'Gloss':BlendMode.SCREEN,'Image':BlendMode.SOFT_LIGHT}[key]
        if key=='Gloss':layer.create_mask(Image.new('L',layer.size,255),top=layer.top,left=layer.left)
    if 'DecalMask' in passes:converted[passes['DecalMask'].name].visible=False
    comp.create_mask(Image.fromarray(mask),top=0,left=0)
    out._record.layer_and_mask_information.layer_info.layer_count=-abs(out._record.layer_and_mask_information.layer_info.layer_count)
    fd,temp=tempfile.mkstemp(prefix=destination.name+'.',suffix='.partial',dir=destination.parent)
    os.close(fd)
    try:
        # Photoshop's merged RGB is white-matted when the layer count marks
        # merged alpha as transparency. Store that representation explicitly.
        log('Compositing finished document...')
        check()
        color,_,alpha=composite(out,force=True)
        check()
        merged=alpha8(np.concatenate([color*alpha+(1-alpha),alpha],axis=2))
        out._record.image_data.set_data([merged[...,i].tobytes() for i in range(4)],out._record.header)
        with open(temp,'wb') as stream:
            out._record.write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        PSDImage.open(temp)  # Validate serialization before publication.
        check()
        if os.name=='nt':os.rename(temp,destination)
        else:
            os.link(temp,destination)
            os.unlink(temp)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    log('RLAYER4_HEADLESS_OK: '+str(destination))
    return destination

