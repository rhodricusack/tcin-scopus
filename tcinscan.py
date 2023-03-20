"""An example program that uses the elsapy module"""

from elsapy.elsclient import ElsClient
from elsapy.elsprofile import ElsAuthor, ElsAffil
from elsapy.elsdoc import FullDoc, AbsDoc
from elsapy.elssearch import ElsSearch
import json
import pickle

## Load configuration
con_file = open("config.json")
config = json.load(con_file)
con_file.close()

# TCIN authors
with open('scopus_ids.json') as f:
    scopus_ids=json.load(f)

## Initialize client
client = ElsClient(config['apikey'])

allpubs={}

## Initialize author search object and execute search
for authorname, scopus_id in scopus_ids:
    auth_srch = ElsSearch(f'AU-ID({scopus_id})','scopus')
    auth_srch.execute(client, get_all=True)
    # for item in auth_srch.results:
    #     print(f"{item['citedby-count']}  {item['dc:title']}")
    allpubs[scopus_id] = auth_srch.results
    print (f"{authorname} has {len(auth_srch.results)} results.")

with open('allpubs.pickle','wb') as of:
    pickle.dump( allpubs, of)