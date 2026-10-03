import json, hashlib, os

def canon(p):
    raw=open(p,encoding="utf-8").read()
    d=json.loads(raw)
    d.pop("project",None); d.pop("synced_at",None)
    return json.dumps(d,sort_keys=True,ensure_ascii=False)

print("== insights-хэш без project/synced_at ==")
for proj in ["Project1","Project2","Project3","Project4"]:
    for cyc in ["001","1351"]:
        p=f"/home/thomas/LivingCode/{proj}/memory/professor_insights_cycle_{cyc}.json"
        print(proj,cyc,hashlib.sha256(canon(p).encode()).hexdigest()[:24])

print("== CHRONICLE.md ==")
for proj in ["Project1","Project2","Project3","Project4"]:
    p=f"/home/thomas/LivingCode/{proj}/CHRONICLE.md"
    b=open(p,'rb').read()
    print(proj,len(b),hashlib.sha256(b).hexdigest()[:24])

print("== образец записи Project3/001 ==")
d=json.loads(open("/home/thomas/LivingCode/Project3/memory/professor_insights_cycle_001.json",encoding="utf-8").read())
print(json.dumps(d["insights"][0],ensure_ascii=False)[:800])
print("---- последняя ----")
print(json.dumps(d["insights"][-1],ensure_ascii=False)[:800])