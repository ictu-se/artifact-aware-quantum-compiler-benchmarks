"""Export compact native LaTeX tables and legible vector figures."""
from pathlib import Path
import json,math
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from packaging.version import Version
R=Path(__file__).resolve().parents[1];T=R/'tables';O=R/'manuscript_assets';O.mkdir(exist_ok=True)
plt.rcParams.update({'axes.labelsize':'medium','xtick.labelsize':'medium','ytick.labelsize':'medium','legend.fontsize':'medium','pdf.fonttype':42,'figure.dpi':160})
BLUE='#2166ac';ORANGE='#d97706';GREEN='#21855b'
def read(n):return pd.read_csv(T/(n+'.csv'))
def esc(s):return str(s).replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')
def f(x,dec=2):return f'{(0.0 if abs(float(x)) < 0.5*10**(-dec) else float(x)):,.{dec}f}'
def table(name,caption,headers,rows,spec=None):
 spec=spec or 'l'+'r'*(len(headers)-1)
 text='\\par\\begin{center}\\begin{minipage}{\\linewidth}\\def\\@captype{table}\n\\centering\n\\caption{'+caption+'}\n\\label{tab:'+name+'}\n\\begin{tabular}{'+spec+'}\n\\toprule\n'+' & '.join(headers)+r' \\'+'\n\\midrule\n'
 text+='\n'.join(' & '.join(map(str,r))+r' \\' for r in rows)+'\n\\bottomrule\n\\end{tabular}\n\\end{minipage}\\end{center}\\par\n'
 (O/('table_'+name+'.tex')).write_text(text)
def save(fig,name):fig.savefig(O/(name+'.pdf'),bbox_inches='tight',pad_inches=.06,metadata={'CreationDate':None,'ModDate':None});plt.close(fig)
b=read('benchpress_sdk_version_distribution');b=b.sort_values(['sdk'],kind='stable');b=b.iloc[sorted(range(len(b)),key=lambda i:(b.iloc[i].sdk,Version(b.iloc[i].sdk_version)))].reset_index(drop=True)
rows=[]
for _,r in b.iterrows():rows.append([esc(r.sdk+' '+r.sdk_version),f'{int(r.n):,}',f(r.runtime_mean_s_mean,3),f(r.runtime_mean_s_median,3),f(r.runtime_mean_s_p95,3)])
table('runtime','Runtime distribution across successful Benchpress records. Values are seconds; p95 uses the nearest-rank estimator.',['SDK and version','$N$','Mean','Median','p95'],rows)
fig,ax=plt.subplots(figsize=(4.65,3.7),layout='constrained');yy=np.arange(len(b))
for key,lab,m,col in [('runtime_mean_s_median','Median','o',BLUE),('runtime_mean_s_mean','Mean','s',ORANGE),('runtime_mean_s_p95','95th percentile','^',GREEN)]:ax.scatter(b[key],yy,label=lab,marker=m,color=col,s=24)
ax.set_yticks(yy,[x.sdk+' '+x.sdk_version for _,x in b.iterrows()]);ax.invert_yaxis();ax.set_xscale('log');ax.set_xlabel('Compilation runtime (seconds, log scale)');ax.grid(axis='x',alpha=.18);ax.legend(loc='lower right');save(fig,'runtime')
u=pd.read_csv(R/'results/unified_compiler_artifacts.csv');bp=u[(u.source=='benchpress_public')&(u.status=='passed')];top=bp.nlargest(40,'runtime_mean_s');show=top.head(6).iloc[::-1]
fig,ax=plt.subplots(figsize=(4.65,3.0),layout='constrained');labels=[]
for _,r in show.iterrows():
 family=r.benchmark_family.replace('.qasm','').replace('_',' ').replace('abstract qasmbench','QASM').replace('condensedmatter','condensed matter')
 labels.append(f'{family}\n{r.topology}, {int(r.input_num_qubits)} qubits')
ax.barh(range(6),show.runtime_mean_s,color=BLUE);ax.set_yticks(range(6),labels);ax.set_xlabel('Mean compilation runtime (seconds)');ax.grid(axis='x',alpha=.15);save(fig,'largest_runtimes')
q=read('qiskit_first_last_paired_summary');rows=[]
for (_,r),lab in zip(q.iterrows(),['Runtime','2q depth','2q gates']):rows.append([lab,f'{int(r.n):,}',f(r['mean']),f(r['median']),f'{f(r.bootstrap_median_ci_low)}--{f(r.bootstrap_median_ci_high)}'])
table('qiskit','Qiskit 1.3.3 to 2.5.0rc1 paired reductions (percent). Positive reductions denote improvements; confidence intervals concern the median.',['Metric','$N$','Mean','Median','95\\% interval'],rows)
m=read('metriq_seed_paired_summary');d=read('metriq_seed_level_first_last_deltas');rows=[]
for (_,r),lab,a,z in zip(m.iterrows(),['Depth','Gates'],['depth_0180','gate_count_0180'],['depth_0452','gate_count_0452']):rows.append([lab,f(r['mean']),f(r['median']),f'{f(r.bootstrap_median_ci_low)}--{f(r.bootstrap_median_ci_high)}',f(100*(d[a].mean()-d[z].mean())/d[a].mean())])
table('metriq','Historical endpoint reductions (percent) across 200 backend--seed pairs. The last column measures reduction of pooled means; the preceding columns summarize paired reductions.',['Metric','Mean','Median','95\\% interval','Pooled'],rows)
v=read('metriq_version_backend_optlevel_distribution');versions=sorted(v.sdk_version.unique(),key=Version);fig,axs=plt.subplots(2,1,figsize=(4.65,4.1),layout='constrained',sharex=True)
for backend,col,label in [('ibm_rochester',BLUE,'IBM Rochester'),('rigetti_16q_aspen',ORANGE,'Rigetti Aspen')]:
 vv=v[v.backend_or_device==backend].set_index('sdk_version').loc[versions]
 for ax,metric,ylabel in zip(axs,['output_depth_mean','output_gate_count_mean'],['Total circuit depth','Total gate count']):ax.plot(range(len(versions)),vv[metric],'-o',color=col,label=label,markersize=3);ax.set_ylabel(ylabel);ax.grid(alpha=.15)
axs[0].legend();ticks=[0,1,4,7,10,14];axs[1].set_xticks(ticks,[versions[i] for i in ticks],rotation=45,ha='right');axs[1].set_xlabel('Qiskit version (ordered releases)');save(fig,'metriq_trajectory')
p=read('benchpress_topology_penalty_by_family');fams=['abstract_qasmbench_100q','abstract_qasmbench_32q','binaryoptimization','discreteoptimization','qft','qec9xz','bwt','adder'];fig,ax=plt.subplots(figsize=(4.65,3.6),layout='constrained')
for j,(topo,col) in enumerate([('heavy-hex',BLUE),('linear',ORANGE),('square',GREEN)]):
 vals=[float(p[(p.benchmark_family==fam)&(p.topology==topo)].depth_2q_ratio_median.iloc[0]) for fam in fams]
 ax.scatter(vals,np.arange(len(fams))+(j-1)*.16,color=col,label=topo,s=25)
ax.set_yticks(range(len(fams)),['QASMBench 100q','QASMBench 32q','Binary optimization','Discrete optimization','QFT','QEC9XZ','BWT','Adder']);ax.invert_yaxis();ax.axvline(1,color='#666',ls='--',lw=1);ax.set_xscale('log');ax.set_xlabel('Median two-qubit depth ratio (log scale)');ax.set_xlim(.8,120);ax.legend(loc='lower right');ax.grid(axis='x',alpha=.15);save(fig,'topology')
z=read('topology_penalty_inference_summary');rows=[]
for topo in ['heavy-hex','linear','square']:
 x=z[(z.topology==topo)&(z.metric=='two-qubit depth ratio')].iloc[0]
 rows.append([topo,f'{int(x.n):,}',f(x.median_ratio),f'{f(x.q25_ratio)}--{f(x.q75_ratio)}',f'{int(x.above_one_n):,}'])
table('topology','Matched two-qubit depth ratios relative to all-to-all. Support excludes zero baselines; the final column counts ratios above one.',['Topology','$N$','Median','Interquartile range','$>1$'],rows)
c=read('cross_sdk_descriptive_summary');fig,axs=plt.subplots(2,1,figsize=(4.65,3.0),layout='constrained');c=c[c.sdk_version.str.startswith(('qpanda','tket'))].reset_index(drop=True)
for ax,metric,title in zip(axs,['runtime','depth'],['Runtime ratio','Two-qubit depth ratio']):
 vals=c[f'{metric}_ratio_median_vs_qiskit'];lo=c[f'{metric}_ratio_q25'];hi=c[f'{metric}_ratio_q75'];ax.errorbar(vals,range(2),xerr=np.array([vals-lo,hi-vals]),fmt='o',color=BLUE,capsize=4);ax.set_yticks(range(2),['QPanda 0.3.2','TKET 2.6.0']);ax.invert_yaxis();ax.axvline(1,color='#666',ls='--');ax.set_xlabel(title+' relative to Qiskit 2.5.0rc1');ax.grid(axis='x',alpha=.15)
axs[0].set_xscale('log');save(fig,'cross_sdk')
meta={'top40_rows':len(top),'top40_groups':int(top.groupby(['sdk','sdk_version','benchmark_family','topology']).ngroups),'top6_all_tket':bool((show.sdk=='tket').all()),'qiskit_clusters':read('benchpress_qiskit_first_last_deltas').circuit_base.nunique(),'bootstrap_iterations':2000,'bootstrap_seed':20260716,'figure_font_size':plt.rcParams['font.size'],'plot_nominal_width_inches':4.65}
(R/'verification/presentation_metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(meta)
