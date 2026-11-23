"""Pipeline logger02 v2 AUTOMATICA su una sessione nuova (nessun parametro del giro del 23/11):
    cd projects/asmile/logger/depth/calib_rock && python3 -m logger02_v2.run <cartella_giro> [--calib base.json] [--lavoro DIR] [--senza-dy]
<cartella_giro> = A/ e B/ (clip .h264 + _frames.csv + sensors_*.csv). Max 2 processi di decodifica insieme; intermedi piccoli (feature/match) in --lavoro.
 1 focale dal giroscopio (g1_extract -> g6_focal: scale per asse + gravita')      -> focal.json
 2 d0 dai punti lontanissimi sopra l'orizzonte IMU (s6_auto far)                  -> auto_far.json
 3 baseline dalle targhe (rilevatore + catene + inseguitore + regressione)        -> auto_plates.json
 4 JSON candidato <lavoro>/calib_auto.json: se un passo non trova nulla, tiene il valore della calib base e lo marca "non rimisurato"
 5 dy per zona sul JSON risultante (d1_dy_indep, tratto con piu' rotazione) -> dy_*.npy
La scala metrica assoluta resta NON verificata senza un oggetto misurato col metro."""
import os,sys,json,argparse,subprocess,tempfile
HERE=os.path.dirname(os.path.abspath(__file__))
def df(): return subprocess.run(['df','-h','/System/Volumes/Data'],capture_output=True,text=True).stdout.splitlines()[-1]
def sh(mod,args,env):
    print('>>',mod,*args,'|',df(),flush=True);r=subprocess.run([sys.executable,os.path.join(HERE,mod),*map(str,args)],env=env,capture_output=True,text=True)
    print(r.stdout[-1200:])
    if r.returncode: print('ERRORE',mod,r.stderr[-600:])
    return r.returncode==0
def load(p):
    return json.load(open(p)) if os.path.exists(p) else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument('giro');ap.add_argument('--calib');ap.add_argument('--lavoro');ap.add_argument('--senza-dy',action='store_true')
    a=ap.parse_args();W=os.path.abspath(a.lavoro or tempfile.mkdtemp(prefix='l02w_'));os.makedirs(W,exist_ok=True)
    base=os.path.abspath(a.calib) if a.calib else os.path.abspath(os.path.join(HERE,'..','..','calib_logger02.CANDIDATO_20261123.json'))
    env=dict(os.environ,L02W=W,L02_GIRO=os.path.abspath(a.giro),L02_CALIB=base)
    print('lavoro',W,'| base',base,'|',df())
    c=json.load(open(base));ok={}
    ok['focale']=sh('g1_extract.py',[],env) and sh('g6_focal.py',[],env)
    ok['d0']=sh('s6_auto.py',['far'],env);ok['targhe']=sh('s6_auto.py',['plates'],env)
    fo,fa,pl=load(os.path.join(W,'focal.json')),load(os.path.join(W,'auto_far.json')),load(os.path.join(W,'auto_plates.json'))
    nota={}
    f0=c.get('focal_rect_px',1236.26)
    if fo: c['focal_fit_px']=round(f0*fo['q'],1);c['focal_scale_vs_base']=round(fo['q'],3);nota['focale']='rimisurata (giroscopio, +-3%)'+(' [scala giro NON calibrata dalla gravita\']' if fo['giro_non_calibrato'] else '')
    else: nota['focale']='NON RIMISURATA: tenuto il valore della calib base'
    if fa and fa.get('trovato'): c['d0_px']=round(fa['d0'],2);nota['d0']='rimisurato (punti lontani, %d fotogrammi)'%fa['n_fotogrammi']
    else: nota['d0']='NON RIMISURATO: %s - tenuto d0_px=%s della calib base'%((fa or {}).get('motivo','passo fallito'),c.get('d0_px'))
    if pl and pl.get('trovato'): c['baseline_misurata_mm']=round(pl['B_mm'],1);nota['baseline']='rimisurata (targhe: %.1f +-%.1f stat +-%.1f sist, %d viste, %d catene)'%(pl['B_mm'],pl['B_boot_sd'],pl['B_sist_mm'],pl['n_viste'],pl['n_catene_usate'])
    else: nota['baseline']='NON RIMISURATA: %s - tenuto |T| della calib base'%((pl or {}).get('motivo','passo fallito'))
    c['auto_note']=nota;c['stato']='CANDIDATO automatico (logger02_v2.run): scala metrica NON verificata col metro';c['valid_for']='SOLO logger02 con queste 2 camere'
    out=os.path.join(W,'calib_auto.json');json.dump(c,open(out,'w'),indent=1)
    sh('export_versioni.py',[out,os.path.join(W,'calib_auto')],env)   # _720.json e _800.json (la 800 e' derivata: cy+40, da verificare)
    if not a.senza_dy: ok['dy']=sh('d1_dy_indep.py',[out,0,1e9,40],env)
    json.dump(dict(passi=ok,nota=nota,lavoro=W),open(os.path.join(W,'riepilogo_v2.json'),'w'),indent=1)
    print('\n=== ESITO ===');[print(' ',k,':',v) for k,v in nota.items()];print('  passi',ok,'\n  JSON:',out)
if __name__=='__main__': main()
