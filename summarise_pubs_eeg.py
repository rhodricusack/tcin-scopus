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

df= pd.DataFrame()


prism=[]
with open(f'allpubs{suffix}.pickle', 'rb') as f:
    allpubs = pickle.load(f)
    for k,v in allpubs.items():
        for paper in v:
            if 'prism:url' in paper:
                author = [auth[0] for auth in scopus_ids if auth[1] == k][0] 
                df_row = pd.DataFrame(
                    {'tcin-author':author, 'url':paper['prism:url'], 'citations': paper['citedby-count'], 'author-scopus-id': k, 'title':paper['dc:title'], 'pubDate':paper['prism:coverDate']}, index=[0])
                df = pd.concat((df, df_row), ignore_index=True)

df = df.drop_duplicates(subset=['url'])

print(df)
df.to_csv(f'tcin-eeg-pubs.csv', index=False)
