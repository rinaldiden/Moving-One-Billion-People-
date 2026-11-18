import adsk.core, adsk.fusion
def run(_ctx):
    app=adsk.core.Application.get()
    doc=[x for x in app.documents if x.name=='Asmile'][0]; doc.activate()
    root=adsk.fusion.Design.cast(app.activeProduct).rootComponent
    n=0
    for i in range(root.customGraphicsGroups.count-1,-1,-1):
        g=root.customGraphicsGroups.item(i)
        if g.id=='flusso': g.deleteMe(); n+=1
    app.activeViewport.refresh()
    m=doc.isModified
    [x for x in app.documents if x.name=='case logger HW3 (2x ESP32-P4)'][0].activate()
    return 'removed %d, asmile modified flag=%s'%(n,m)
