import urllib.request, json, re
UA={"User-Agent":"CurioBot/0.1 (https://github.com/curio-ac/curio-ac.github.io)"}
def get(u):
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30);b=r.read();return r.status,r.headers.get("content-type"),b
    except Exception as e: return "ERR",str(e)[:80],b""
for u in ["https://science.nasa.gov/wp-json/wp/v2/posts?per_page=2&_fields=id,link,title",
          "https://science.nasa.gov/wp-json/wp/v2/pages?per_page=2&search=black%20hole&_fields=id,link,title",
          "https://www.nasa.gov/wp-json/wp/v2/posts?per_page=2&_fields=id,link,title",
          "https://images-api.nasa.gov/search?q=saturn&media_type=image&page_size=2",
          "https://www.usgs.gov/science/faqs",
          "https://www.usgs.gov/faqs/what-a-volcano",
          "https://www.noaa.gov/education/resource-collections",
          "https://oceanservice.noaa.gov/facts/"]:
    s,ct,b=get(u);t=b[:4000].decode("utf8","ignore")
    print("\n==",u,s,ct,len(b));print(re.sub(r"\s+"," ",t)[:700])
    if "usgs.gov/science/faqs" in u: print("FAQ LINKS:", re.findall(r'href="(/faqs/[^"]+)"', b.decode("utf8","ignore"))[:15])
    if "oceanservice" in u: print("FACT LINKS:", re.findall(r'href="([a-z0-9-]+\.html)"', b.decode("utf8","ignore"))[:15])
