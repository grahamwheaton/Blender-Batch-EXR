import numpy as np
import pytest
from psd_tools import PSDImage
from blender_batch_exr.converter import Layer,composite_layers
from blender_batch_exr.psd import write_psd
from blender_batch_exr.headless_rlayer4 import finish

def source(path,names,version=1,empty=False):
    color=np.full((8,12),.4,np.float32);alpha=np.ones_like(color);alpha[:,:2]=0;alpha[:,2]=.5
    if empty:alpha[:]=0
    layers=[Layer(n,(color,)*3,alpha,0,0,alpha.shape,visible=True) for n in names]
    with path.open('wb') as f:write_psd(f,12,8,layers,composite_layers(layers,12,8,lambda:None),version=version)
    return path

@pytest.mark.parametrize('version',[1,2])
@pytest.mark.parametrize('empty',[False,True])
def test_finishing_structure_colour_masks(tmp_path,version,empty):
    names=['Image.RGBA','GlossDIR.RGBA','Diff.RGBA','Gloss.RGBA','AO.RGBA','DecalMask.RGBA','CryptoObject.\u5154\u5b50']
    suffix='.psb' if version==2 else '.psd'
    original=source(tmp_path/('input'+suffix),names,version,empty);out=tmp_path/('output'+suffix)
    finish(original,out,log=lambda m:None)
    psd=PSDImage.open(out);assert psd.depth==8 and psd.size==(12,8)
    groups={l.name:l for l in psd};assert set(groups)=={'COMP','RLAYERS'}
    comp=groups['COMP'];assert comp.visible and not groups['RLAYERS'].visible
    assert [l.name for l in comp]==['GlossDIR.RGBA','Diff.RGBA','Image.RGBA','Gloss.RGBA','AO.RGBA']
    assert {l.name for l in psd.descendants() if not l.is_group()}==set(names)
    assert psd.topil().mode=='RGBA'
    mask=np.asarray(comp.mask.topil());assert np.all(mask[:,:2]==0)
    if empty:assert not mask.any()
    else:assert np.all(mask[:,2]==128) and np.all(mask[:,3:]==255)
    layers={l.name:l for l in comp}
    for name,mode in [('AO.RGBA',b'mul '),('Gloss.RGBA',b'scrn'),('Image.RGBA',b'sLit')]:
        assert layers[name].blend_mode.value==mode and layers[name].opacity==128
    assert not layers['GlossDIR.RGBA'].visible and layers['Gloss.RGBA'].has_mask()
    assert np.all(np.rint(layers['Diff.RGBA'].numpy('color')*255)==170)
    with pytest.raises(FileExistsError):finish(original,out)

def test_pass_validation_and_warnings(tmp_path):
    for names in [['Diff.RGBA'],['Diff.RGBA','Image.RGBA','Other.Image.RGBA']]:
        with pytest.raises(ValueError):finish(source(tmp_path/'bad.psd',names),tmp_path/'no.psd')
        assert not (tmp_path/'no.psd').exists()
    messages=[];finish(source(tmp_path/'good.psd',['Diff.RGBA','Image.RGBA']),tmp_path/'done.psd',log=messages.append)
    assert len([m for m in messages if m.startswith('RLAYER4_WARNING:')])==4
