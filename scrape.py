#!/usr/bin/env python3

import os
import requests
import bs4

os.system("mkdir -p infodump/thumbs")
url = "https://moneroinfodump.neocities.org/"
contents = requests.get(url, timeout=15).content
soup = bs4.BeautifulSoup(contents, "html.parser")
images = soup.find_all("img")
links = soup.find_all("a")

for image in images:
    img = image.get("src")
    if img.startswith("http"):
        os.system(f"wget -q --no-clobber -O infodump/{os.path.basename(img)} {img}")
        image["src"] = os.path.basename(img)
    elif img.startswith("data:image/png"):
        pass
    else:
        os.system(f"wget -q --no-clobber -O infodump/{img} {img}")
        image["src"] = img

for link in links:
    href = link.get("href")
    if href and href.startswith("https://i.imgur.com"):
        link["href"] = os.path.basename(href)

with open("infodump/index.html", "w") as f:
    f.write(str(soup))
