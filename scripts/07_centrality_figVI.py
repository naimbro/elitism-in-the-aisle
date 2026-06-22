"""07 — Figure VI: centrality by surname group in the 19th-c. family network.
Data: genealogical adjacency matrix (Bro 2023), fetched from the author's site.
Output: figures/figure_VI1_centrality_298.png + elite/other centrality ratios."""
import pandas as pd, numpy as np, unicodedata, urllib.request, io, os
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import networkx as nx
dac=lambda s: unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
ELITE=set(dac(s) for s in pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname)
COMMON=set(dac(x) for x in "GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS MOLINA RIVERA GUZMAN SANDOVAL ORTIZ".split())
URL="https://raw.githubusercontent.com/naimbro/naimbro.github.io/main/data/naimbro_chilean_political_networks.csv"
raw=urllib.request.urlopen(URL,timeout=60).read()
net=pd.read_csv(io.BytesIO(raw), index_col=0); net.index=net.index.astype(str)
M=(net.fillna(0).values!=0).astype(int); A=np.maximum(M,M.T); np.fill_diagonal(A,0)
nodes=list(net.index); G=nx.from_numpy_array(A)
def grp(n):
    t=dac(n).split("."); pat=t[0] if t else ""; mat=t[1] if len(t)>1 else ""
    return "Elite" if (pat in ELITE or mat in ELITE) else "Common" if (pat in COMMON or mat in COMMON) else "Other"
df=pd.DataFrame({"group":[grp(n) for n in nodes]})
cent={"Degree":nx.degree_centrality(G),"Betweenness":nx.betweenness_centrality(G),
      "Closeness":nx.closeness_centrality(G),"Eigenvector":nx.eigenvector_centrality_numpy(G)}
for k,v in cent.items(): df[k]=[v[i] for i in range(len(nodes))]
print("ratios Elite/Other:", {k:round(df[df.group=="Elite"][k].mean()/max(df[df.group=="Other"][k].mean(),1e-9),1) for k in cent})
fig,axes=plt.subplots(1,4,figsize=(13,4)); order=["Elite","Common","Other"]; col={"Elite":"#1f3a93","Common":"#b03030","Other":"#E7B800"}
plt.rcParams.update({"font.family":"serif"})
for ax,k in zip(axes,cent):
    g=df.groupby("group")[k]; ax.bar(order,g.mean().reindex(order),yerr=1.96*g.sem().reindex(order),color=[col[o] for o in order],capsize=4,alpha=.85)
    ax.set_title(k); ax.set_xticklabels(order,rotation=20,fontsize=9)
    for s in ["top","right"]: ax.spines[s].set_visible(False)
# No in-figure suptitle (INV-12): title lives in the LaTeX \caption. Per-panel labels are sub-panel identifiers and stay.
fig.tight_layout()
fig.savefig("figures/figure_VI1_centrality_298.png",dpi=150)
fig.savefig("figures/figure_VI1_centrality_298.pdf")
