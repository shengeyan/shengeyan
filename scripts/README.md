# Deep Space Profile assets

`python3 scripts/generate_profile.py --refresh` reads public GitHub data and renders the SVG assets. Locally it uses `GH_TOKEN`, `GITHUB_TOKEN`, or the signed-in `gh` CLI, in that order. No token is written to disk. Omit `--refresh` to render the committed public snapshot without network access.

The workflow updates assets daily at 09:00 Asia/Shanghai and supports manual runs. It never rewrites either README. Pushes containing only generated assets do not trigger another run.

The atlas distinguishes GitHub-counted commit contributions from total contributions and labels the rolling-year scope. Repository counts and stars cover public, owned, non-fork repositories. Language percentages measure code bytes in SSR-ResourceHub, anyheap-2025 and feishu-codex-local-agent; they are not an assessment of personal language proficiency. Recent signals are actual user-authored commits from public repositories' default branches. The full messages and links are retained in `assets/deep-space/recent-commits.md` and the public data snapshot.

The workflow first runs the pinned [lowlighter/metrics isocalendar plugin](https://github.com/lowlighter/metrics/tree/master/source/plugins/isocalendar). Its generated 3D geometry is embedded in the themed atlas when available. A public-data renderer keeps the atlas available if the third-party action cannot run. The optional `METRICS_TOKEN` secret can contain a scopeless personal access token if repository-token access is insufficient. No personal token is copied from a workstation into GitHub Actions.

Every linked project is a separate image wrapped in a native Markdown/HTML link, because links embedded within an SVG displayed as an image are not clickable. Desktop/mobile `<picture>` sources keep artwork readable at different widths. All six original descriptions, stacks, contacts and the five chapters remain as native README content.

Original wave assets are retained for compatibility and Git history preserves the previous layout.

Validation: `python3 -m unittest discover -s tests -v` and XML parsing of generated assets. SVGs contain no external fonts, scripts, or network requests.
