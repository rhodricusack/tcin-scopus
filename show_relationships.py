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
    short_name = auth.split(',')[0]+','+auth.split(',')[1].strip().replace('Dr ','')[0]
    if short_name == 'P Doherty,C':
        short_name = 'Doherty,C'
    return short_name

suffix='-2023'
logcoauth = False

with open('scopus_ids.json', 'r') as f:
    scopus_ids = json.load(f)


with open(f'allpubs{suffix}.pickle', 'rb') as f:
    p = pickle.load(f)


    from collections import Counter
    
    doc_author_pairs = [[doc['prism:url'], k] for k, v in p.items() for doc in v if not 'error' in doc]


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

    df_dept = df_dept.sort_values(by='medic') # separate medical disciplines from others for later chord diagram

    df_dept['medic_cross'] = ''
    df_dept['medic_cross'][df_dept['medic']=='yes']='+' 
    df_dept['medic_dept'] = df_dept['medic_cross'] + df_dept['school/dept']
    nauth = len(auth_short_names_unique)
    coauthcount = np.zeros((nauth,nauth))

    depts = list(set(df_dept['medic_dept']))
    depts.sort()
    
    
    for k, v in result.items():
        for a1 in v:
            for a2 in v:
                if a1==a2:
                    coauthcount[auth_short_names_unique.index(auth_short_names[auth_list.index(a1)]), auth_short_names_unique.index(auth_short_names[auth_list.index(a2)])] +=0.5
                else:
                    coauthcount[auth_short_names_unique.index(auth_short_names[auth_list.index(a1)]), auth_short_names_unique.index(auth_short_names[auth_list.index(a2)])] +=1
    
    mask = np.diag(coauthcount) >0

    # Take out people with no publications
    coauthcount = coauthcount[mask,:][:,mask]
    auth_short_names_unique = [auth_short_names_unique[i] for i in range(nauth) if mask[i]]

    rdm = 1/(coauthcount +1)

    fig, ax = plt.subplots(nrows = 1, figsize=(12,12), dpi=300)
    #ax.imshow(rdm)
    Z = hierarchy.linkage(rdm, 'single')
    r = hierarchy.dendrogram(Z, no_plot=True) 
    iv1 = r['leaves']
#    im = ax.imshow(np.power(coauthcount[iv1,:][:,iv1],0.5))
    if logcoauth:
        im = ax.imshow(np.log10(coauthcount[iv1,:][:,iv1]))
    else:
        im = ax.imshow(coauthcount[iv1,:][:,iv1])

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
        if row['medic']=='yes':
            ax.annotate(name, (E[authind,0], E[authind,1]), ha='center', va='center', color='red')
        else:
            ax.annotate(name, (E[authind,0], E[authind,1]), ha='center', va='center', color='black')
#        ax.annotate(name, (E[authind,0], E[authind,1]), ha='center', color=list(mcolors.XKCD_COLORS.keys())[depts.index(row['medic_dept'])])
        # if row['medic']=='yes':
        #    ax.annotate('+', (E[authind,0], E[authind,1]), ha='center', va='center',color='r', weight = 'bold', alpha=0.3, fontsize=20)

    # printing result

    ax.set_xlim(-1,1)
    ax.set_ylim(-1,1)
    ax.axis('off')
    plt.tight_layout()

    plt.savefig('coauth_mds{suffix}.png')

    edges = pd.DataFrame()

    for a0,n0 in enumerate(auth_short_names_unique):
        for a1 in range(a0,len(auth_short_names_unique)):
            n1 =auth_short_names_unique[a1]
            dept0 = depts.index(df_dept[df_dept['name_x']==n0].iloc[0]['medic_dept'])
            dept1 = depts.index(df_dept[df_dept['name_x']==n1].iloc[0]['medic_dept'])
#            ax.annotate(name, (E[authind,0], E[authind,1]), ha='center', color=list(mcolors.XKCD_COLORS.keys())[depts.index(row['medic_dept'])])
            ax.annotate(name, (E[authind,0], E[authind,1]), ha='center', color='black')
            if coauthcount[a0,a1]:
                edges = pd.concat((edges, pd.DataFrame.from_dict({'source':[dept0], 'target':[dept1], 'value': [coauthcount[a0,a1]] })), ignore_index=True)
    
    df_depts_unique = pd.DataFrame.from_dict({'depts': depts})
    df_depts_unique.to_csv('chord_dept_unique.csv')

    hv.extension('matplotlib')
    hv.output(size=300, dpi=300)
    edges = pd.read_csv('chord_edges.csv')
    edges['source'] = pd.to_numeric(edges['source'])
    edges['target'] = pd.to_numeric(edges['target'])
    edges['value'] = pd.to_numeric(edges['value'])
    edges = edges.drop(columns='Unnamed: 0')
    edges_grouped = edges.groupby(by=['source', 'target'],  as_index=False).sum()
    # get rid of within dept links
    edges_grouped = edges_grouped[edges_grouped['source'] != edges_grouped['target']]

    edges_grouped.to_csv('chord_edges_grouped.csv')
    print(edges)
    print(edges_grouped)

    df_dept = pd.read_csv('chord_dept_unique.csv')

    nodes=hv.Dataset(df_dept, 'index')
    chord = hv.Chord((edges_grouped, nodes)).select(value=(2, None))

    #chord.sort(by='source')

    chord.opts(
        opts.Chord(cmap='Category20', edge_cmap='Category20', edge_color=dim('source').str(), 
                labels='depts', node_color=dim('depts').str()))
        
    hv.save(chord, 'chorddiag{suffix}.png')


    print("duplicate values", str(result))

    
