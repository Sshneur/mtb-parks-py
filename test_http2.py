import urllib.request, json
# Make multiple requests to ensure we go past cache
for i in range(2):
    try:
        r = urllib.request.urlopen('http://localhost:8000/api/park/fili/soil-forecast', timeout=30)
        d = json.loads(r.read())
        all_good = all(len(x.get('periods',[])) > 0 for x in d['forecast'])
        print(f"Req {i}: {len(d['forecast'])} days, all have periods: {all_good}")
        for x in d['forecast']:
            print(f"  {x['date']}: {len(x.get('periods',[]))} periods")
    except Exception as e:
        print(f"Req {i} error: {e}")
