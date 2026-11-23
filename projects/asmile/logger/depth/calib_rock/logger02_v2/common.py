"""Moduli comuni logger02 v2 (23/11). I file intermedi (pairs.pkl, imu.npy, ...) stanno in $L02W (cartella di lavoro, NON su git).
Rigenerazione: idx.py + imu.py + dec.py sono in ../selfcal_senza_encoder.py (sezioni '# ===== file:'); qui sotto una copia compatta."""
import os,glob,csv,json,pickle,subprocess,functools,numpy as np,cv2
W=os.environ.get('L02W','.')
D=os.path.abspath(os.path.expanduser(os.environ.get('L02_GIRO','~/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02_giro_20261123')))
CALIB=os.environ.get('L02_CALIB') or os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_logger02.CANDIDATO_20261123.json')
IMUJ=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/imu_montaggio_case_v5.json')
def make_pairs():
    def load(side,col):
        rows=[]
        for f in sorted(glob.glob(f'{D}/{side}/clip_*_{side}_*_frames.csv')):
            clip=f.replace('_frames.csv','.h264')
            for i,r in enumerate(csv.DictReader(open(f))): rows.append((int(r[col]),clip,i,int(r['frame'])))
        return rows
    A=load('A','t_us');B=load('B','t_a_us');ta=np.array([r[0] for r in A]);tb=np.array([r[0] for r in B])
    j=np.clip(np.searchsorted(tb,ta),1,len(tb)-1);jj=np.where(abs(tb[j]-ta)<abs(tb[j-1]-ta),j,j-1);dt=tb[jj]-ta;ok=abs(dt)<10000
    return [(A[i],B[jj[i]],dt[i]) for i in range(len(A)) if ok[i]]
def pairs():
    p=os.path.join(W,'pairs.pkl')
    if not os.path.exists(p): pickle.dump(make_pairs(),open(p,'wb'))
    return pickle.load(open(p,'rb'))
def imu():
    p=os.path.join(W,'imu.npy')
    if not os.path.exists(p):
        rows=[]
        for f in sorted(glob.glob(D+'/A/sensors_*.csv')):
            for r in csv.DictReader(open(f)):
                try: rows.append([int(r['t_us']),*(float(r[c]) for c in ('imu_ax_g','imu_ay_g','imu_az_g','imu_gx_dps','imu_gy_dps','imu_gz_dps'))])
                except Exception: pass
        X=np.array(rows);np.save(p,X[np.argsort(X[:,0])])
    return np.load(p)
def _probe(path):
    r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','csv=p=0',path],capture_output=True,text=True).stdout.strip().split(',')
    return int(r[0]),int(r[1])
_SIZE=None
def size():
    """(larghezza, altezza) letti dal primo clip A della sessione (ffprobe): 1280x720 (giri 23/11) o 1280x800 (firmware dal 23/11 sera)."""
    global _SIZE
    if _SIZE is None:
        c=sorted(glob.glob(D+'/A/clip_*.h264'))[0];_SIZE=_probe(c)
    return _SIZE
def load_calib(path=None):
    """JSON di calibrazione adattato alla risoluzione della sessione: 720->800 = finestra verticale piena, riga 0 del 720 = riga 40 dell'800 => cy +40 (f,cx invariati)."""
    c=json.load(open(path or CALIB));Wc,Hc=c['size'];Ws,Hs=size()
    if (Wc,Hc)!=(Ws,Hs):
        assert Wc==Ws,'larghezza diversa: calibrazione non adattabile'
        dy=(Hs-Hc)/2.0
        for k in('K_left','K_right'): c[k][1][2]+=dy
        c['size']=[Ws,Hs];c['adattata_da']=[Wc,Hc]
    return c
@functools.lru_cache(maxsize=2)
def clip(path):
    p=subprocess.run(['ffmpeg','-v','error','-i',path,'-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    return np.frombuffer(p.stdout,np.uint8).reshape(-1,size()[1],size()[0])
