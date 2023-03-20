import json

with open('scopus_ids.json', 'r') as f:
    scopus_ids = json.load(f)
    
auth_list = [x[1] for x in scopus_ids]
auth_short_names = [x[0].split(',')[0]+','+x[0].split(',')[1].strip().replace('Dr ','')[0] for x in scopus_ids]

auth_dict = {}
for ind, auth in enumerate(auth_short_names):
    auth_dict.setdefault(auth, list()).append(auth_list[ind])

    
print(auth_dict)
