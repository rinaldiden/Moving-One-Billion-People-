import adsk.core, adsk.fusion, json
P3=adsk.core.Point3D.create
def col(r,g,b,a=255):
    return adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(r,g,b,a))
def run(_ctx):
    app=adsk.core.Application.get()
    doc=[x for x in app.documents if x.name=='Asmile'][0]; doc.activate()
    mod0=doc.isModified
    des=adsk.fusion.Design.cast(app.activeProduct)
    root=des.rootComponent
    for i in range(root.customGraphicsGroups.count-1,-1,-1):
        g=root.customGraphicsGroups.item(i)
        if g.id=='flusso': g.deleteMe()
    grp=root.customGraphicsGroups.add(); grp.id='flusso'
    occ={o.name:o for o in root.allOccurrences}
    def addb(b,c):
        o=b.assemblyContext
        nb=b.nativeObject if o else b
        cg=grp.addBRepBody(nb); cg.color=c
        if o: cg.transform=o.transform2
        return cg
    ss=occ['servosterzo:1']
    for b in ss.bRepBodies:
        if b.name=='Body3': addb(b,col(220,40,40))
        elif b.name=='Body6': addb(b,col(255,150,0))
        elif b.name in ('Body1','Body2'): addb(b,col(255,220,0))
        elif b.name in ('Body10','Body11'): addb(b,col(90,140,255))
    for b in root.bRepBodies:
        if b.name in ('Body107',): addb(b,col(60,110,255))
        if b.name in ('Body134','Body137'): addb(b,col(255,230,60))
    w=occ['stelvio 4all_ruota 20" v1:2']
    for b in w.bRepBodies: addb(b,col(60,190,90))
    w=occ['stelvio 4all_ruota 20" v1(Specchio):1']
    for b in w.bRepBodies: addb(b,col(60,190,90))
    for nm in ('ruota asta sterzo(Specchio):1','ruota asta sterzo:1'):
        for b in occ[nm].bRepBodies: addb(b,col(255,230,60))
    # tie rods + handlebar schematic lines
    def line(pts,c,w=6):
        coords=[]
        for p in pts: coords+=list(p)
        cc=adsk.fusion.CustomGraphicsCoordinates.create(coords)
        l=grp.addLines(cc,list(range(len(pts))),True); l.color=c; l.weight=w; return l
    line([(5.1,12.1,8.05),(40,15.5,0.2)],col(255,230,60),8)
    line([(-5.1,12.1,8.05),(-40,15.5,0.2)],col(255,230,60),8)
    line([(-32.5,5.5,54.5),(32.5,5.5,54.5)],col(190,80,255),10)
    line([(40,0,-26.6),(40,0,20)],col(255,255,255),3)
    line([(-40,0,-26.6),(-40,0,20)],col(255,255,255),3)
    line([(0,5.5,-10),(0,5.5,62)],col(255,255,255),3)
    app.activeViewport.refresh()
    return json.dumps({'mod_before':mod0,'mod_after':doc.isModified})
