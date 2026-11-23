"""Focale dal giroscopio, automatica: scale per asse visione/giro (g4) e scala giro dalla gravita' (g5, asse IMU y = beccheggio camera).
q = f_vera/f_base = media( s_beccheggio / s_giro_y , s_imbardata ) [s_giro_x non osservabile: assunto 1, incertezza +-3% MPU6050].
Se la gravita' non e' utilizzabile (<6 transizioni o sd>0.08) s_giro_y=1 e il campo 'giro_non_calibrato' e' vero."""
import os,sys,json,subprocess
sys.path.insert(0,os.path.dirname(__file__))
from g4_axes import *
if __name__=='__main__':
    x,c=fit(M,[1,1,1],[0,1,2]);print('s_x,s_y,s_z',x.round(3),'cost %.3f'%c)
    subprocess.run([sys.executable,os.path.join(os.path.dirname(__file__),'g5_gravity.py')],env=os.environ,check=False)
    g=json.load(open(os.path.join(W,'gravity.json')));sy=g['s_y'] if g['usabile'] else 1.0
    q=0.5*(x[0]/sy+x[1])
    out=dict(q=float(q),s_beccheggio=float(x[0]),s_imbardata=float(x[1]),s_rollio=float(x[2]),s_giro_y=float(sy),giro_non_calibrato=not g['usabile'],n_coppie=len(M),incertezza=0.03)
    json.dump(out,open(os.path.join(W,'focal.json'),'w'),indent=1);print(out)
