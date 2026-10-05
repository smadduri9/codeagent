# GitHub repository setup (one-time)

These steps polish how the repo appears on GitHub and enable the project site. Run from a machine with `gh` authenticated as the repository owner.

## Repository About box

```bash
gh repo edit smadduri9/codeagent \
  --description "Local CLI autonomous coding agent: native tool-calling loop, deterministic permission engine, git worktree isolation, verification gate, and a 40-task eval harness. Python 3.12, Groq."

gh repo edit smadduri9/codeagent \
  --homepage "https://smadduri9.github.io/codeagent/"

gh repo edit smadduri9/codeagent \
  --add-topic ai-agent,coding-agent,llm,python,cli,developer-tools,groq,autonomous-agents
```

On github.com, open **Settings** for the repo and confirm the **About** section shows the description, website link, and topics. Pin useful items if desired (README is the default landing).

## GitHub Pages (Actions)

1. **Settings** -> **Pages** -> **Build and deployment** -> **Source**: **GitHub Actions**.
2. Push to `main` with `.github/workflows/pages.yml` and the `site/` directory. The workflow deploys on changes under `site/`.
3. After the first successful run, the site is at https://smadduri9.github.io/codeagent/

If the Actions job stays queued or you see a 404, publish from the **repository root** (GitHub allows `/` or `/docs` for branch-based Pages). Root [index.html](../index.html) plus [.nojekyll](../.nojekyll) serves the landing page and links static assets under `docs/demo/`:

```bash
gh api --method PUT repos/smadduri9/codeagent/pages \
  -f 'source[branch]=main' \
  -f 'source[path]=/'
gh api --method POST repos/smadduri9/codeagent/pages/builds
```

[docs/index.html](index.html) mirrors the same content for browsing under `/docs/` when that path is used. Keep [site/](../site/) in sync when you change the landing page, or rely on Actions once it deploys successfully.

## Branch protection (optional, owner)

Per BUILD_PLAN section 2, require the CI workflow checks on pull requests to `main`. This is configured in GitHub Settings, not in this repository's code.

## Demo assets

Terminal demo files live in [docs/demo/](demo/). To replace the recording:

1. Save a new capture as `docs/demo/terminal.mp4`.
2. Regenerate the README GIF: `ffmpeg -y -i docs/demo/terminal.mp4 -vf "fps=12,scale=900:-1:flags=lanczos" -loop 0 docs/demo/terminal.gif`
3. Copy updated files to `site/assets/` for the Pages site.

See [scripts/record_demo.sh](../scripts/record_demo.sh) for a short reminder of example commands.
