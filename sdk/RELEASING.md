# Releasing the SDKs

Three packages, three registries, one tag each. Versions live in `sdk/python/pyproject.toml`, `sdk/mcp/pyproject.toml` and `sdk/typescript/package.json`; the workflow refuses a tag that does not match.

## One-time setup

| Registry | Step |
|---|---|
| PyPI | Sign in as the HeliusOne account → [Publishing](https://pypi.org/manage/account/publishing/) → add a *pending publisher* for `h1news` and again for `h1news-mcp`: owner `HeliusOne`, repository `h1news`, workflow `publish.yml`, environment `pypi`. Then in GitHub → Settings → Environments create `pypi`. No API token is stored anywhere. |
| npm | Create the free org `heliusone` at npmjs.com/org/create (public packages are free). Mint a granular access token with *Read and write* on packages, scoped to `@heliusone`, and save it as the `NPM_TOKEN` repository secret. |

## Every release

```bash
# bump the version in the package's manifest, commit, then:
git tag python-v0.1.0 && git push origin python-v0.1.0     # h1news → PyPI
git tag mcp-v0.1.0    && git push origin mcp-v0.1.0        # h1news-mcp → PyPI (after h1news, it depends on it)
git tag ts-v0.1.0     && git push origin ts-v0.1.0         # @heliusone/h1news → npm
```

## By hand, without the workflow

```bash
pip install build twine
python -m build sdk/python  && twine upload sdk/python/dist/*      # asks for a PyPI API token as the password, username __token__
python -m build sdk/mcp     && twine upload sdk/mcp/dist/*
cd sdk/typescript && npm login && npm publish --access public      # prepublishOnly runs typecheck, tests and the build
```

Publish `h1news` before `h1news-mcp`; the MCP server depends on it. After the first publish, remove the `git+…#subdirectory=` fallbacks from the three READMEs and the guides.
