import adsk.core, adsk.fusion, json
P3=adsk.core.Point3D.create
PTS={'motore':(1.85,-0.95,10.5),'conica':(0.4,5.0,10.1),'piantone_basso':(0,5.5,4),'piantone_alto':(0,5.5,54.5),
 'manopola_dx':(32.5,5.5,54.5),'manopola_sx':(-32.5,5.5,54.5),'impronta_dx':(46.3,0,-26.6),'impronta_sx':(-45.7,0,-26.6),
 'perno_dx':(40,0,0),'perno_sx':(-40,0,0),'braccio_dx':(40,15.5,0.2),'pitman_dx':(5.1,12.1,8.05),'ruota_dx':(46.3,0,0),'ruota_post':(0,-115,0),'terra_perno_dx':(40,0,-26.6)}
def run(_ctx):
    app=adsk.core.Application.get()
    doc=[x for x in app.documents if x.name=='Asmile'][0]; doc.activate()
    vp=app.activeViewport
    cam=vp.camera
    cam.isSmoothTransition=False
    cam.cameraType=adsk.core.CameraTypes.OrthographicCameraType
    cam.eye=P3(*EYE); cam.target=P3(*TGT)
    cam.upVector=adsk.core.Vector3D.create(0,0,1)
    cam.isFitView=False
    vp.camera=cam
    cam=vp.camera; cam.viewExtents=EXT; vp.camera=cam
    vp.refresh()
    return 'ok'
