import json, collections, os
for proj in ["Project1","Project2","Project3","Project4"]:
    for cyc in ["001","1351"]:
        p=f"/home/thomas/LivingCode/{proj}/memory/professor_insights_cycle_{cyc}.json"
        raw=open(p,encoding="utf-8").read()
        print("=====",proj,cyc,"len",len(raw))
        print("  head:",repr(raw[:100]))
        try:
            d=json.loads(raw)
        except Exception as e:
            print("  JSON FAIL:",e); continue
        print("  toplevel type",type(d).__name__)
        if isinstance(d,dict):
            for k,v in d.items():
                print("   ",k,"=",type(v).__name__, len(v) if isinstance(v,(list,dict,str)) else v)
        elif isinstance(d,list):
            print("  len",len(d))
            if d: print("  item0:",json.dumps(d[0],ensure_ascii=False)[:600])