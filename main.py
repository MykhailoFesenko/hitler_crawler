import sys
import asyncio
import importlib
from urllib.parse import urljoin
from collections import deque as _dq
import subprocess

def ensure(pkg: str):
    try:
        importlib.import_module(pkg)
    except ImportError:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--disable-pip-version-check",
            "-q",
            pkg
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for _pkg in ("aiohttp", "nest_asyncio", "beautifulsoup4"):
    ensure(_pkg)

import aiohttp
import nest_asyncio
from bs4 import BeautifulSoup

HITLER_URL = "https://en.wikipedia.org/wiki/Adolf_Hitler"
WIKI_PREFIX = "https://en.wikipedia.org"
MAX_DEPTH = 6
MAX_CONCURRENCY = 20
KEYWORDS = { "history", "politics", "war", "nazi", "germany", "hitler", "fascism", "sport", "olympics"}

def extract_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [
        urljoin(WIKI_PREFIX, a["href"])
        for a in soup.select("a[href^='/wiki/']")
        if ":" not in a["href"] and not a["href"].endswith("Main_Page")
    ]

def has_keywords(html: str) -> bool:
    txt = html.lower()
    return any(k in txt for k in KEYWORDS)

async def fetch(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        resp = await session.get(url, timeout=5)
        if resp.status == 200:
            return await resp.text()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    return None

async def find_path(start: str) -> list[str] | None:
    visited = {start}
    queue = _dq([(start, [start])])

    async with aiohttp.ClientSession() as session:
        first = await fetch(session, HITLER_URL) or ""
        neighbors = set(extract_links(first))

        while queue:
            batch = []
            while queue and len(batch) < MAX_CONCURRENCY:
                u, p = queue.popleft()
                if len(p) <= MAX_DEPTH:
                    batch.append((u, p))

            pages = await asyncio.gather(*(fetch(session, u) for u, _ in batch))
            for (u, path), html in zip(batch, pages):
                if not html:
                    continue
                print(f"[{len(path)-1}] {u}")

                if u == HITLER_URL or HITLER_URL in extract_links(html):
                    return path + [HITLER_URL]

                links = extract_links(html)
                if has_keywords(html):
                    links = links[:40]

                for lnk in links[:20]:
                    if lnk not in visited:
                        visited.add(lnk)
                        queue.append((lnk, path + [lnk]))

                if u in neighbors and HITLER_URL not in path:
                    if 'href="/wiki/Adolf_Hitler"' in html:
                        return path + [HITLER_URL]
    return None

def normalize(url: str) -> str:
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/wiki/"):
        url = WIKI_PREFIX + url
    if not url.startswith("http"):
        print("Invalid URL")
        sys.exit(1)
    return url

def main():
    nest_asyncio.apply()
    start = normalize(input("Enter Wikipedia URL: "))
    print("Searching path to Adolf Hitler...\n")
    path = asyncio.run(find_path(start))

    if path:
        print("\nPath found:")
        for p in path:
            print(" ->", p)
    else:
        print("\nNot found within", MAX_DEPTH, "steps.")

if __name__ == "__main__":
    main()
