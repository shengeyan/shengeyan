# Deep Space Profile assets

`python3 scripts/generate_profile.py --refresh` reads public GitHub data and renders the SVG assets. Locally it uses `GH_TOKEN`, `GITHUB_TOKEN`, or the signed-in `gh` CLI, in that order. No token is written to disk. Omit `--refresh` to render the committed public snapshot without network access.

The workflow updates assets daily at 09:00 Asia/Shanghai and supports manual runs. It never rewrites either README. Pushes containing only generated assets do not trigger another run.

The atlas distinguishes GitHub-counted commit contributions from total contributions and labels the rolling-year scope. Repository counts and stars cover public, owned, non-fork repositories. Language percentages measure code bytes in SSR-ResourceHub, anyheap-2025 and feishu-codex-local-agent; they are not an assessment of personal language proficiency. Contribution activity is shown only as aggregate counts and daily totals. The generator does not request or publish individual commit messages, hashes, authors or commit links. Both refresh and offline rendering remove legacy commit details from the snapshot and delete the retired recent-activity cards and link file.

The workflow first runs the pinned [lowlighter/metrics isocalendar plugin](https://github.com/lowlighter/metrics/tree/master/source/plugins/isocalendar). Its generated 3D geometry is embedded in the themed atlas when available. A public-data renderer keeps the atlas available if the third-party action cannot run. The optional `METRICS_TOKEN` secret can contain a scopeless personal access token if repository-token access is insufficient. No personal token is copied from a workstation into GitHub Actions.

Every linked project is a separate image wrapped in a native Markdown/HTML link, because links embedded within an SVG displayed as an image are not clickable. Desktop/mobile `<picture>` sources keep artwork readable at different widths. All six project descriptions, stacks and the five chapters remain as native README content. Contacts list the Blog at https://shengeyan.github.io/, the published WeChat ID and email.

The light code-atlas palette lives in `scripts/generate_profile.py`. All contact, technology and repository-statistic tags are generated locally with pastel fills and dark text. Repository, follower and star tags use the daily public snapshot. The Profile views tag links directly to the original live Komarev counter. It avoids embedding the counter through GitHub Camo, which currently returns HTTP 404 for both its pixel and normal SVG styles; no local view count is invented.

The desktop and mobile hero SVGs animate their satellite dots with native SVG motion paths. CSS moves short highlights along the orbital lines, breathes the halo and gently twinkles selected stars. The artwork runs as an image on GitHub without JavaScript or external requests. `prefers-reduced-motion: reduce` hides moving dots, shows stationary dots and disables CSS animation.

The 30-day contribution curve uses the final 30 dates of the same GitHub contribution calendar as the annual atlas. It replaces the English README's unavailable external activity graph and is also included in Chinese. The separate lifetime streak card retains its original service, with a light palette and disabled entrance animations.

Original wave assets are retained for compatibility and Git history preserves the previous layout.

Validation: `python3 -m unittest discover -s tests -v` and XML parsing of generated assets. SVGs contain no external fonts, scripts, or network requests.
