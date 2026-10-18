import warnings, json
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score, roc_curve
warnings.filterwarnings("ignore")
import sys
from reproduce_lgbm import load_combined
RNG=42
# 사용법: python onset_detection.py [LO HI] [--raw]  (기본 0.8 1.2, 결함 제외본)
_args=[a for a in sys.argv[1:] if a!='--raw']
LO,HI=(float(_args[0]),float(_args[1])) if len(_args)==2 else (0.8,1.2)
print(f'대역 {LO}~{HI}, 데이터 {"원본" if "--raw" in sys.argv else "결함 제외"}')
BASE=['temp','humidity','co2','VPD']
FLAT=BASE+[f'{c}_lag1' for c in BASE]+[f'{c}_lag2' for c in BASE]
GH24={'gh24_1온실','gh24_2온실','gh24_3온실','gh24_4온실'}
raw=load_combined(clean='--raw' not in sys.argv).sort_values(['source','date']).reset_index(drop=True)
for lag in (1,2):
    for c in BASE: raw[f'{c}_lag{lag}']=raw.groupby('source')[c].shift(lag)
raw['dt_back']=raw.groupby('source')['date'].diff().dt.total_seconds()/3600
raw['hour']=raw.date.dt.hour
KEY=raw.set_index(['source','date'])['VPD']
def build(h):
    df=raw.copy()
    idx=pd.MultiIndex.from_arrays([df['source'],df['date']+pd.Timedelta(hours=h)])
    df['target']=KEY.reindex(idx).values
    m=(df.dt_back==1)&df[[f'{c}_lag2' for c in BASE]].notna().all(axis=1)&df.target.notna()
    d=df[m].reset_index(drop=True); d['trend']=d.VPD+h*(d.VPD-d.VPD_lag1); return d
def fit(Xtr,ytr,Xte):
    m=lgb.LGBMRegressor(n_estimators=300,learning_rate=0.05,num_leaves=31,random_state=RNG,verbose=-1); m.fit(Xtr,ytr); return m.predict(Xte)
def score(p): return np.maximum(p-HI,LO-p)
def stats(ev,s):
    if ev.sum()==0 or (1-ev).sum()==0: return np.nan,np.nan
    f,t,_=roc_curve(ev,s); return roc_auc_score(ev,s), t[f<=0.10].max()
def evaluate(t,p,mask,label,boot=False):
    """t: test df, p: model preds, mask: eval population mask (hour window)"""
    cur=t.VPD.values; y=t.target.values
    inb=(cur>=LO)&(cur<=HI)&mask
    ev=((y<LO)|(y>HI))[inb].astype(int)
    out={'n_pop':int(inb.sum()),'n_ev':int(ev.sum())}
    S={'model':score(p)[inb],'trend':score(t.trend.values)[inb],'edge':np.maximum(cur-HI,LO-cur)[inb]}
    # 경계거리 규칙: 대역 안에서 가장 가까운 경계까지 남은 거리가 작을수록 위험 -> score=-min(HI-cur,cur-LO)
    S['edge']=-np.minimum(HI-cur[inb],cur[inb]-LO)
    res={}
    for k,s in S.items():
        auc,r10=stats(ev,s); res[k]={'auc':auc,'rec10':r10}
    out['res']=res
    if boot:
        days=(t.source.astype(str)+t.date.dt.date.astype(str)).values[inb]
        ud=np.unique(days); rng=np.random.default_rng(0); idx_by={d:np.where(days==d)[0] for d in ud}
        bs={k:[] for k in S}
        for _ in range(300):
            pick=rng.choice(ud,len(ud)); ii=np.concatenate([idx_by[d] for d in pick])
            for k,s in S.items():
                a,r=stats(ev[ii],s[ii]); bs[k].append(r)
        out['ci']={k:(np.nanpercentile(v,5),np.nanpercentile(v,95)) for k,v in bs.items()}
    return out
rows=[]
for h in (1,3,6):
    d=build(h); d['hourf']=d.hour
    F2=FLAT+['hourf']
    poolA=[];poolB=[]
    for s in sorted(d.source.unique()):
        tr=d.source.values!=s; te=~tr
        if te.sum()<30: continue
        p=fit(d.loc[tr,FLAT].values,d.loc[tr,'target'].values,d.loc[te,FLAT].values)
        p2=fit(d.loc[tr,F2].values,d.loc[tr,'target'].values,d.loc[te,F2].values)
        t=d[te].copy(); t['p']=p; t['p2']=p2
        (poolB if s in GH24 else poolA).append(t)
    for g,pool in (('A',poolA),('B',poolB)):
        t=pd.concat(pool).reset_index(drop=True)
        for win,mask in (('전체',np.ones(len(t),bool)),('주간09-17',t.hour.between(9,17).values),('주간10-16',t.hour.between(10,16).values)):
            for name,pcol in (('LGBM(논문동일)','p'),('LGBM+시각','p2')):
                if win=='전체' and name=='LGBM+시각': continue
                r=evaluate(t,t[pcol].values,mask,name,boot=(win=='주간09-17' and name=='LGBM(논문동일)' and h<=3))
                rows.append((h,g,win,name,r))
                rs=r['res']; ci=r.get('ci')
                line=f"h={h} 그룹{g} {win:<9} {name:<13} 모집단={r['n_pop']:>5} 이탈={r['n_ev']:>4} ({r['n_ev']/max(r['n_pop'],1)*100:4.1f}%) | rec@FPR10 모델={rs['model']['rec10']:.3f} 추세={rs['trend']['rec10']:.3f} 경계={rs['edge']['rec10']:.3f} | AUC 모델={rs['model']['auc']:.3f} 추세={rs['trend']['auc']:.3f} 경계={rs['edge']['auc']:.3f}"
                if ci: line+=f" | 90%CI rec10 모델[{ci['model'][0]:.2f},{ci['model'][1]:.2f}] 경계[{ci['edge'][0]:.2f},{ci['edge'][1]:.2f}]"
                print(line)
    print()
