from scopus_ids_utils import write_scopus_ids

pos=0
scopus_ids=[]
with open('edie_scopus_ids.txt') as f:
    txt=f.read()
    while True:
        pos=txt.find('AU-ID', pos+1)
        if pos==-1:
            break
        open_bracket=txt.find('(',pos)
        close_bracket=txt.find(')',open_bracket)
        open_quotes=txt.find('"', open_bracket)
        close_quotes=txt.find('"', open_quotes+1)

        fld=txt[open_quotes+1:close_quotes]
        id=txt[close_quotes+1:close_bracket]
        scopus_ids.append((fld,id))
    
    write_scopus_ids(scopus_ids)
    print(scopus_ids)