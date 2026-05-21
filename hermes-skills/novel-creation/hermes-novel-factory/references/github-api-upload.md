# GitHub API Upload (Alternative to git push)

When `git push` times out (common on slow network environments), use GitHub Content API
to upload files individually.

## Prerequisites

- Token from `~/.git-credentials` (NOT hardcoded — goes stale):
  ```python
  with open('/root/.git-credentials') as f:
      for line in f:
          if 'github.com' in line:
              token = line.strip().split('@')[0].split(':')[-1]
  ```
- Repo: `1989zj/zj-matrix`
- Branch: `main`

## URL Encoding for Chinese Filenames

**CRITICAL**: File paths containing Chinese characters or spaces MUST be URL-encoded.
The GitHub API will reject unencoded Chinese paths with `"URL can't contain control characters"`.

Use `urllib.parse.quote()` with `safe='/:@'` to keep URL structure intact:

```python
url = "https://api.github.com" + urllib.parse.quote(full_path, safe='/:@')
```

## Python Script (using curl, no requests dependency)

```python
import os, sys, json, base64, subprocess, urllib.parse

owner = "1989zj"
repo = "zj-matrix"

# Read token from git-credentials
with open('/root/.git-credentials') as f:
    for line in f:
        if 'github.com' in line:
            token = line.strip().split('@')[0].split(':')[-1]
            break

def gh_curl(method, url_path, data=None):
    """Call GitHub API with URL-encoded Chinese path"""
    full_path = f"/repos/{owner}/{repo}/{url_path}"
    url = "https://api.github.com" + urllib.parse.quote(full_path, safe='/:@')
    cmd = ["curl", "-s", "-X", method, "-H", f"Authorization: token {token}"]
    if data:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not r.stdout.strip():
        return {}
    return json.loads(r.stdout.strip())

def upload_file(local_path, remote_path, message):
    """Upload a file, handling both create and update"""
    check = gh_curl("GET", f"contents/{remote_path}")
    sha = check.get("sha", "")

    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "message": message,
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    result = gh_curl("PUT", f"contents/{remote_path}", payload)
    return "content" in result

# Usage:
base_path = "/root/.hermes/projects/异能爽文"
path_prefix = "novel/书名/"

for fname in sorted(os.listdir(base_path)):
    if not fname.endswith(".md"):
        continue
    local = os.path.join(base_path, fname)
    remote = f"{path_prefix}{fname}"
    if upload_file(local, remote, f"upload {fname}"):
        print(f"OK: {fname}")
    else:
        print(f"FAIL: {fname}")
```

## Path Convention

`novel/<书名>/<filename>.md`

Example: `novel/末世污染等级评审/ch060_第六十章 不需要埋.md`

## Auth Header Format

Use `Authorization: token <PAT>` — NOT `Bearer <PAT>`. The `Bearer` format is for OAuth tokens;
GitHub personal access tokens use the `token` scheme.

## Why

- Avoids git CLI timeout issues
- Individual file uploads are more resilient
- No rebase/merge conflicts when working solo
- API rate limit is 5000/hr — sufficient for 20-50 files
- No `requests` library required (uses `curl` via `subprocess`)

## Pitfalls

- **Hardcoded token goes stale**: Always read from `~/.git-credentials` at runtime
- **Chinese paths must be URL-encoded**: `urllib.parse.quote(full_path, safe='/:@')` is mandatory
- **Auth header uses `token` not `Bearer`**: Incorrect auth gives 401 Bad credentials
- **curl with `-s` suppresses progress but also errors**: Capture stderr with `2>&1` if debugging
- **Uploading to an existing file without SHA**: Returns `"sha wasn't supplied"` — always GET SHA first
- **~/.git-credentials has Unicode chars**: The file is plain UTF-8, `split(':')` works but beware the format is `https://user:token@host.com`
