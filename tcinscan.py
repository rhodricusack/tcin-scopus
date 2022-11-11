"""An example program that uses the elsapy module"""

from elsapy.elsclient import ElsClient
from elsapy.elsprofile import ElsAuthor, ElsAffil
from elsapy.elsdoc import FullDoc, AbsDoc
from elsapy.elssearch import ElsSearch
import json

## Load configuration
con_file = open("config.json")
config = json.load(con_file)
con_file.close()

## Initialize client
client = ElsClient(config['apikey'])

## Initialize author search object and execute search
#auth_srch = ElsSearch('orcid(0000-0002-5234-7415)','author')
auth_srch = ElsSearch('orcid(0000-0002-5234-7415)','scopus')
auth_srch.execute(client, get_all=True)
for item in auth_srch.results:
    print(f"{item['citedby-count']}  {item['dc:title']}")

print ("auth_srch has", len(auth_srch.results), "results.")