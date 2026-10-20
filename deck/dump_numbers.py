import json, numpy as np
from flightline import engine
ctx=engine.context(); out={}
def scen(**kw):
    st=engine.run(engine.normalise(**kw)); j=st.state_json(); b,p=j['baseline'],j['plan']
    return st,j,{'ao_b':b['ao'],'ao_p':p['ao'],'ceil_b':b['ceiling'],'gap_b':b['gap'],'attr_b':b['attribution'],'attr_days_b':b['attribution_days'],'attr_p':p['attribution'],
      'lost_b':b['sortie_days_lost'],'lost_p':p['sortie_days_lost'],'tasked':p['sortie_days_tasked'],'d_ac':j['delta']['aircraft_days'],'d_sd':j['delta']['sortie_days'],'d_ao':j['delta']['ao_points'],
      'queue_b':j['depot']['mean_queue_days']['baseline'],'queue_p':j['depot']['mean_queue_days']['plan'],'counts':j['prognosis']['counts'],'ms':j['timings_ms']['total'],
      'top':[(a['title'],a['aircraft_days_gained']) for a in st.actions[:4]],
      'cann':[(c['donor'],c['recipient'],c['part'],c['net_aircraft_days'],c['inputs']['donor_free_days']) for c in st.cann_candidates]}
st,j,out['default']=scen()
out['twin']=j['twin']; out['metrics']=j['metrics']; out['evaluation']=j['prognosis']['evaluation']
_,_,out['ground']=scen(ground_tails=['TAIL-01','TAIL-03'])
_,_,out['delay']=scen(spares_delay_days=10)
_,_,out['surge']=scen(sortie_surge=40)
engine.run(engine.normalise())
m=ctx.model; X,y,_=m.eval_rows(ctx.deg.split('test'),13); p,lo,hi=m.predict_rows(X); s=y<=20
out['cov_last20']=float(np.mean((y[s]>=lo[s])&(y[s]<=hi[s]))); out['n_last20']=int(s.sum()); out['n_test_units']=len(ctx.deg.split('test'))
json.dump(out, open('numbers.json','w'), indent=1, default=float)
d=out['default']; print('ao', d['ao_b'], d['ao_p'], 'ms', d['ms'])
