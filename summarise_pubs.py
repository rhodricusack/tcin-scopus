import json
import pickle
import pandas as pd
import numpy as np
def short_name(auth):
    short_name = auth.split(',')[0]+','+auth.split(',')[1].strip().replace('Dr ','')[0]
    if short_name == 'P Doherty,C':
        short_name = 'Doherty,C'
    return short_name

suffix='-eeg-2025'
logcoauth = False

with open('scopus_ids.json', 'r') as f:
    scopus_ids = json.load(f)

prism=[]
with open(f'allpubs{suffix}.pickle', 'rb') as f:
    allpubs = pickle.load(f)
    for k,v in allpubs.items():
        for paper in v:
            if 'prism:url' in paper:
                author = [auth[0] for auth in scopus_ids if auth[1] == k][0] 
                prism.append((paper['prism:url'], paper['citedby-count'],k, author, paper['dc:title'], paper['prism:coverDate']))

prism = list(set(prism))

citations = np.array([int(x[1]) for x in prism])
ind = np.argsort(citations)
print(prism)
print(citations[ind])
print(len(prism))
print([prism[x] for x in ind[-10:]])

