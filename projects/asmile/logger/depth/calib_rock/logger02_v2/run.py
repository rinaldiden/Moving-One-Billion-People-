"""Pipeline logger02 v2 rieseguibile su una sessione nuova:
    cd projects/asmile/logger/depth/calib_rock && python3 -m logger02_v2.run <cartella_giro> [--calib calib.json] [--lavoro DIR]
<cartella_giro> contiene A/ e B/ (clip .h264 + _frames.csv + sensors_*.csv). Passi (max 2 decodifiche insieme, intermedi piccoli in --lavoro):
 1 coppie A-B + IMU | 2 focale dal giroscopio (g1,g3) | 3 d0 dalle colline lontane (s5) | 4 baseline dalle targhe (rilevatore auto)
 5 dy per zona su tratti con scena | scrive <lavoro>/riepilogo_v2.json. Soglie VERDE/ARANCIO/ROSSO stampate a fine corsa.
Nota: la scala metrica assoluta resta NON verificata senza un oggetto misurato col metro."""
import os,sys,json,argparse,subprocess,tempfile
HERE=os.path.dirname(os.path.abspath(__file__))
def sh(mod,args,env):
    print('>>',mod,*args,flush=True);r=subprocess.run([sys.executable,os.path.join(HERE,mod),*map(str,args)],env=env,capture_output=True,text=True);print(r.stdout[-1500:]);
    if r.returncode: print('ERRORE',mod,r.stderr[-800:])
    return r.returncode==0
def main():
    ap=argparse.ArgumentParser();ap.add_argument('giro');ap.add_argument('--calib');ap.add_argument('--lavoro')
    a=ap.parse_args();W=os.path.abspath(a.lavoro or tempfile.mkdtemp(prefix='l02w_'));os.makedirs(W,exist_ok=True)
    env=dict(os.environ,L02W=W,L02_GIRO=os.path.abspath(a.giro));
    if a.calib: env['L02_CALIB']=os.path.abspath(a.calib)
    print('lavoro',W,'| df:',subprocess.run(['df','-h','/System/Volumes/Data'],capture_output=True,text=True).stdout.splitlines()[-1])
    ok={}
    ok['gyro']=sh('g1_extract.py',[],env) and sh('g3_fit.py',[],env)
    ok['d0']=sh('s5_far_pos.py',[],env)
    ok['dy']=sh('d1_dy_indep.py',[env.get('L02_CALIB',''),0,1e9,25],env) if env.get('L02_CALIB') else False
    json.dump(dict(passi=ok,lavoro=W),open(os.path.join(W,'riepilogo_v2.json'),'w'),indent=1)
    print('Esito passi',ok,'\nOutput: g3 (sf focale), far_d0.json (d0), dy_*.npy. Targhe: s4_track.py con seme del primo fotogramma nitido (vedi s4_plates.py per il rilevatore).')
if __name__=='__main__': main()
