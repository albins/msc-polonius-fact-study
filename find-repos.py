#!/usr/bin/env python3
import itertools
import shutil
import time
import itertools

from github import Github
import requests

from benchmark import ALGORITHMS, clone_repo, run_experiment

with open("blacklist.txt") as fp:
    BLACKLIST = set([l.strip() for l in fp.readlines()])

with open("repositories.txt") as fp:
    WHITELIST = set([l.strip() for l in fp.readlines()])

EMA = None
ALPHA = 0.5
CRATES_URL = "https://crates.io/api/v1/crates"


def get_crates():
    for i in itertools.count(start=1):
        params = {"page": i, "per_page": 20, "sort": "recent_downloads"}
        response = requests.get(CRATES_URL, params=params)
        response.raise_for_status()
        if response.json()['meta']['total'] == 0:
            break
        for crate in response.json()['crates']:
            yield crate


def get_crates_io_repos():
    return (c['repository'] for c in get_crates() if verify_repo(c['repository']))


def get_github_repos():
    repo_iterator = Github().search_repositories(
        sort="stars", order="desc", query="language:rust")
    return (r.clone_url for r in repo_iterator if verify_repo(r.clone_url))


def verify_repo(url):
    print(f"verifying {url}")
    if url in BLACKLIST:
        print(f"skipping blacklisted url {url}...")
        return False
    elif url in WHITELIST:
        print(f"skipping verification of whitelisted url {url}...")
        return True

    global EMA

    try:
        path = clone_repo(url)
        results = run_experiment(ALGORITHMS[1], path)
        EMA = results if EMA is None else ALPHA * results + (1 - ALPHA) * EMA

    except Exception as e:
        print(f"repo {url} died, skipping and blacklisting...")
        BLACKLIST.add(url)
        with open("blacklist.txt", "a") as fp:
            fp.write(f"{url}\n")
        return False
    finally:
        shutil.rmtree(path)
    print(f"repo {url} compiled with results {results}, EMA: {EMA}")
    return True


def interleave_iterators(iter_a, iter_b):
    for a, b in itertools.zip_longest(iter_a, iter_b):
        if a is not None:
            yield a
        if b is not None:
            yield b

if __name__ == '__main__':
    count = 0
    with open("repositories.txt", "w") as fp:
        for repo_url in interleave_iterators(get_github_repos(), get_crates_io_repos()):
            fp.write(f"{repo_url}\n")
            fp.flush()
            if count % 10 == 0:
                print("Sleeping...")
                time.sleep(5)
            count += 1
