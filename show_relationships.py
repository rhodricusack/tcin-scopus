import pickle
import numpy as np
from matplotlib import pyplot as plt
import seaborn as sns
import json
from sklearn import manifold
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster import hierarchy
import pandas as pd
import holoviews as hv
import matplotlib.colors as mcolors 
from holoviews import opts, dim

def short_name(auth):
    return auth.split(',')[0]+','+auth.split(',')[1].strip().replace('Dr ','')[0]


with open('scopus_ids.json', 'r') as f:
    scopus_ids = json.load(f)


with open('allpubs.pickle', 'rb') as f:
    p = pickle.load(f)


    from collections import Counter
    
    doc_author_pairs = [[doc['prism:url'], k] for k, v in p.items() for doc in v]


    rev_dict = {}
    
    for doc, author in doc_author_pairs:
        rev_dict.setdefault(doc, list()).append(author)
        
    result = {key:values for key, values in rev_dict.items()
                                if len(values) > 1}
    auth_list = [x[1] for x in scopus_ids]
    # auth_list = list(set([v for x in rev_dict.values() for v in x]))
    auth_names = [x[0] for id in auth_list for x in scopus_ids if id==x[1] ]

    # Find duplicate scopus IDs for the same person
    auth_list = [x[1] for x in scopus_ids]
    auth_short_names = [short_name(x[0]) for x in scopus_ids]

    # Get departments 
    auth_short_names_unique = list(set(auth_short_names))
    df_asnu = pd.DataFrame.from_dict({'name': auth_short_names_unique, 'id': [auth_list[auth_short_names.index(x)] for x in auth_short_names_unique]})
    df_asnu.to_csv('auth_short_names_unique.csv')
    df_asnu['id']=df_asnu['id'].astype(int)

    df_dept = pd.read_csv('departments.csv')
    df_dept['id']=df_dept['id'].astype(int)
    df_dept = df_asnu.merge(df_dept, on='id', how='left')

    nauth = len(auth_short_names_unique)
    coauthcount = np.zeros((nauth,nauth))

    depts = list(set(df_dept['school/dept']))
    
    
    for k, v in result.items():
        for a1 in v:
            for a2 in v:
                if a1==a2:
                    coauthcount[auth_short_names_unique.index(auth_short_names[auth_list.index(a1)]), auth_short_names_unique.index(auth_short_names[auth_list.index(a2)])] +=0.5
                else:
                    coauthcount[auth_short_names_unique.index(auth_short_names[auth_list.index(a1)]), auth_short_names_unique.index(auth_short_names[auth_list.index(a2)])] +=1
    coauthcount
    rdm = 1/(coauthcount +1)
    fig, ax = plt.subplots(nrows = 1, figsize=(12,12), dpi=300)
    #ax.imshow(rdm)
    Z = hierarchy.linkage(rdm, 'single')
    r = hierarchy.dendrogram(Z, no_plot=True) 
    iv1 = r['leaves']
#    im = ax.imshow(np.power(coauthcount[iv1,:][:,iv1],0.5))
    im = ax.imshow(np.log10(coauthcount[iv1,:][:,iv1]))
    ax.set_xticks(range(nauth))
    ax.set_xticklabels([auth_short_names_unique[i] for i in iv1], rotation=90)
    ax.set_yticks(range(nauth))
    ax.set_yticklabels([auth_short_names_unique[i] for i in iv1])
    fig.colorbar(im)

    plt.tight_layout()

    plt.savefig('coauth_matrix.png')

    embedding = manifold.MDS(n_components = 2, n_init=10, max_iter = 5000, eps=1e-4, dissimilarity = 'precomputed', metric = True)
    E = embedding.fit_transform(rdm)

    fig, ax = plt.subplots(nrows = 1, figsize=(12,12), dpi=300)

    for a0 in range(nauth):
        for a1 in range(nauth):
            if coauthcount[a0,a1]:
                ax.plot((E[a0,0],E[a1,0]), (E[a0,1],E[a1,1]), 'c', linewidth=5*np.log(1+coauthcount[a0,a1]), alpha=0.2 )

    for authind, name in enumerate(auth_short_names_unique):
        row = df_dept[df_dept['name_x']==name].iloc[0]
        ax.annotate(name, (E[authind,0], E[authind,1]), ha='center', color=list(mcolors.XKCD_COLORS.keys())[depts.index(row['school/dept'])])
        if row['medic']=='yes':
           ax.annotate('+', (E[authind,0], E[authind,1]), ha='center', color='r', weight = 'bold', alpha=0.5, fontsize=20)
    # printing result

    ax.set_xlim(-1,1)
    ax.set_ylim(-1,1)
    plt.tight_layout()

    plt.savefig('coauth_mds.png')

    edges = pd.DataFrame()

    for a0,n0 in enumerate(auth_short_names_unique):
        for a1,n1 in enumerate(auth_short_names_unique):
            dept0 = depts.index(df_dept[df_dept['name_x']==n0].iloc[0]['school/dept'])
            dept1 = depts.index(df_dept[df_dept['name_x']==n1].iloc[0]['school/dept'])
            ax.annotate(name, (E[authind,0], E[authind,1]), ha='center', color=list(mcolors.XKCD_COLORS.keys())[depts.index(row['school/dept'])])
            if coauthcount[a0,a1]:
                edges = pd.concat((edges, pd.DataFrame.from_dict({'source':[dept0], 'target':[dept1], 'value': [1+np.log10(coauthcount[a0,a1])] })), ignore_index=True)
    
    hv.extension('matplotlib')
    hv.output(size=200)
    edges.to_csv('chord_edges.csv', columns=['source', 'target', 'value'])
    df_dept.to_csv('chord_dept.csv')
    
    nodes=hv.Dataset(df_dept, 'index')
    chord = hv.Chord((edges, nodes))
    chord.sort(by='source')

    chord.opts(
        opts.Chord(cmap='Category20', edge_cmap='Category20', edge_color=dim('source').str(), 
                labels='school/dept', node_color=dim('index').str()))
        
    hv.save(chord, 'chorddiag.png')


    print("duplicate values", str(result))

    
