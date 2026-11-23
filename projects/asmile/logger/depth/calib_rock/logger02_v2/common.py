"""Moduli comuni logger02 v2 (23/11). I file intermedi (pairs.pkl, imu.npy, ...) stanno in $L02W (cartella di lavoro, NON su git).
Rigenerazione: idx.py + imu.py + dec.py sono in ../selfcal_senza_encoder.py (sezioni '# ===== file:'); qui sotto una copia compatta."""
import os,glob,csv,pickle,subprocess,functools,numpy as np,cv2
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
@functools.lru_cache(maxsize=2)
def clip(path):
    p=subprocess.run(['ffmpeg','-v','error','-i',path,'-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    return np.frombuffer(p.stdout,np.uint8).reshape(-1,720,1280)
