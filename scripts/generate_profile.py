#!/usr/bin/env python3
"""Refresh public GitHub data and render self-contained Profile SVG assets.

Only assets/deep-space is written. README content is never rewritten here.
Uses Python's standard library; GH_TOKEN is optional locally when gh is signed in.
"""
import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import math
import os
from pathlib import Path
import subprocess
import urllib.request
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'deep-space'
BG, INK, SOFT, DIM, GOLD, VIOLET, LINE = '#f8faff', '#263653', '#536681', '#64748b', '#a15336', '#6d58a4', '#dce4f1'
BLUE, MINT, CLOUD, LAVENDER = '#46679f', '#397b72', '#e7eef9', '#b9a9df'
FEATURED = ['SSR-ResourceHub', 'anyheap-2025', 'feishu-codex-local-agent']
PROJECTS = [
    ('SSR-ResourceHub', 'SSR × SEO', 'Vue / Nuxt / Nest', '用 Nuxt 与 Nest，探索资源平台的 SSR 与 SEO。', 'A resource platform built with Nuxt and Nest.'),
    ('anyheap-2025', 'REAL-TIME × COLLABORATION', 'TypeScript / WebSocket', '重做物料拖拽与实时协同，让操作保持同步。', 'Draggable materials. Shared work. Synced updates.'),
    ('feishubot', 'FEISHU × CODEX', 'TypeScript / Bot', '在飞书发起 Codex 任务，连接本地开发流程。', 'Start Codex tasks from Feishu conversations.'),
    ('DRSP-client', 'HEALTH × INSIGHT', 'JavaScript / Mini Program', '读懂配料表，让过敏源清晰可见。', 'Make ingredient labels and allergens clear.'),
    ('Mlysl-UI', 'COMPONENTS × CRAFT', 'TypeScript / Vue', '将界面细节，沉淀为可复用的组件。', 'Thoughtful interfaces, reusable components.'),
    ('FrontMidPlatform', 'PRODUCT × ENGINEERING', 'Vue', '用前端工程，连接产品与复杂系统。', 'Connecting products and complex systems.'),
]


def streaks(days):
    """Count consecutive calendar dates; an unfinished today may remain empty."""
    days = sorted(days, key=lambda d: d['date'])
    longest = run = active = 0
    previous = None
    for item in days:
        current = date.fromisoformat(item['date'])
        if item['contributionCount']:
            active += 1
            run = run + 1 if previous and current - previous == timedelta(days=1) else 1
            longest = max(longest, run)
            previous = current
        else:
            run = 0
            previous = None
    end = len(days) - 1
    if end >= 0 and not days[end]['contributionCount']:
        end -= 1
    current = 0
    while end >= 0 and days[end]['contributionCount']:
        if current and date.fromisoformat(days[end + 1]['date']) - date.fromisoformat(days[end]['date']) != timedelta(days=1):
            break
        current += 1
        end -= 1
    return {'current': current, 'longest': longest, 'active': active}


def refresh():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        token = subprocess.check_output(['gh', 'auth', 'token'], text=True).strip()
    identity_request = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query': '{ user(login:"shengeyan") { id } }'}).encode(),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'shengeyan-profile'})
    with urllib.request.urlopen(identity_request) as response:
        identity = json.load(response)
    if identity.get('errors'):
        raise RuntimeError('; '.join(error['message'] for error in identity['errors']))
    author = identity['data']['user']['id']
    query = '''query($after:String,$author:ID!) { user(login:"shengeyan") {
      createdAt followers { totalCount }
      contributionsCollection { totalCommitContributions totalIssueContributions
        totalPullRequestContributions totalPullRequestReviewContributions
        contributionCalendar { totalContributions weeks { contributionDays {
          date contributionCount contributionLevel } } } }
      repositories(first:100,after:$after,ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false,orderBy:{field:UPDATED_AT,direction:DESC}) {
        totalCount pageInfo { hasNextPage endCursor } nodes {
          name url stargazerCount languages(first:100) { edges { size node { name } } }
          defaultBranchRef { target { ... on Commit { history(first:5,author:{id:$author}) { nodes {
            oid messageHeadline committedDate url author { user { login } }
          } } } } }
        }
      }
    } }'''
    after = None
    repos = []
    while True:
        request = urllib.request.Request('https://api.github.com/graphql',
            data=json.dumps({'query': query, 'variables': {'after': after, 'author': author}}).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'shengeyan-profile'})
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        if result.get('errors'):
            raise RuntimeError('; '.join(error['message'] for error in result['errors']))
        user = result['data']['user']
        if not user:
            raise RuntimeError('GitHub did not return the public user')
        page = user['repositories']
        repos.extend(page['nodes'])
        if not page['pageInfo']['hasNextPage']:
            break
        after = page['pageInfo']['endCursor']
    user['repositories']['nodes'] = repos
    commits = {}
    for repo in repos:
        branch = repo.get('defaultBranchRef')
        for commit in branch['target']['history']['nodes'] if branch else []:
            if (commit['author'].get('user') or {}).get('login', '').lower() == 'shengeyan':
                commits[commit['oid']] = {**{k: commit[k] for k in ['oid', 'messageHeadline', 'committedDate', 'url']}, 'repo': repo['name']}
    return {'updated': datetime.now(timezone.utc).date().isoformat(), 'user': user,
            'commits': sorted(commits.values(), key=lambda c: c['committedDate'], reverse=True)[:4]}


def text(x, y, value, size=16, color=INK, family='sans-serif', extra=''):
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-family="{family}" {extra}>{escape(str(value))}</text>'


def line(y, width=846, x=34):
    return f'<path d="M{x} {y}H{width-x}" stroke="{LINE}" fill="none"/>'


def svg(name, width, height, title, content, desc=''):
    markup = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xhtml="http://www.w3.org/1999/xhtml" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc or title)}</desc>
<style>text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans CJK SC','Microsoft YaHei',sans-serif}}.mono{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}.serif{{font-family:Georgia,'Times New Roman',serif}}</style>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="16" fill="{BG}" stroke="{LINE}"/>{content}</svg>'''
    ET.fromstring(markup)
    (OUT / (name + '.svg')).write_text(markup, encoding='utf-8')


def hero(mobile=False):
    w, h = (440, 638) if mobile else (846, 510)
    cx, cy = (220, 413) if mobile else (648, 258)
    content = '''<defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#ccd9ed"/></pattern><radialGradient id="glow"><stop stop-color="#e2dcf5" stop-opacity=".9"/><stop offset="1" stop-color="#f8faff" stop-opacity="0"/></radialGradient><radialGradient id="planet" cx="28%" cy="25%" r="85%"><stop stop-color="#ffffff"/><stop offset=".38" stop-color="#e2eafa"/><stop offset=".74" stop-color="#c6c5e8"/><stop offset="1" stop-color="#9daed7"/></radialGradient></defs>'''
    content += '''<style>
@keyframes hero-orbit-flow { to { stroke-dashoffset: -360; } }
@keyframes hero-glow-breathe { 0%,100% { opacity: .65; } 50% { opacity: 1; } }
@keyframes hero-star-twinkle { 0%,100% { opacity: .25; } 50% { opacity: .6; } }
.hero-orbit-flow { animation: hero-orbit-flow 24s linear infinite; }
.hero-glow { animation: hero-glow-breathe 8s ease-in-out infinite; }
.hero-star { animation: hero-star-twinkle 7s ease-in-out infinite; }
.hero-resting-dot { display: none; }
@media (prefers-reduced-motion: reduce) {
  .hero-orbit-flow, .hero-glow, .hero-star { animation: none; }
  .hero-moving-dot { display: none; }
  .hero-resting-dot { display: inline; }
}
</style>'''
    content += f'<rect x="16" y="66" width="{w-32}" height="{h-121}" fill="url(#grid)" opacity=".48"/>'
    content += text(28, 36, 'SHENGEYAN / CODE ATLAS', 10 if mobile else 11, BLUE, extra='class="mono" letter-spacing="1"')
    content += text(w-28, 36, 'EST. 2022  ✦', 10 if mobile else 11, VIOLET, extra='class="mono" text-anchor="end"')
    content += line(56, w, 28)
    content += f'<circle class="hero-glow" cx="{cx}" cy="{cy}" r="{165 if mobile else 185}" fill="url(#glow)"/>'
    for i in range(22):
        x, y = cx-145+(i*73)%290, cy-132+(i*53)%264
        twinkle = f'class="hero-star" style="animation-delay: -{i%7}s"' if i%4 == 0 else ''
        content += f'<circle {twinkle} cx="{x}" cy="{y}" r="{1 if i%4 else 1.8}" fill="{BLUE if i%2 else VIOLET}" opacity=".35"/>'
    for rx, ry, angle, duration in [(166, 53, -23, 24), (112, 134, 35, 36), (164, 83, 25, 30)]:
        dash = '3 5' if angle == 35 else 'none'
        content += f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="rotate({angle} {cx} {cy})" fill="none" stroke="{LAVENDER if angle>0 else BLUE}" stroke-opacity=".5" stroke-dasharray="{dash}"/>'
        content += f'<ellipse class="hero-orbit-flow" style="animation-duration: {duration}s" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="rotate({angle} {cx} {cy})" pathLength="360" fill="none" stroke="{VIOLET if angle>0 else BLUE}" stroke-width="1.5" stroke-opacity=".65" stroke-dasharray="32 328"/>'
    content += f'<path d="M{cx-13} {cy}h26 M{cx} {cy-13}v26" stroke="{BLUE}" opacity=".3"/>'
    content += f'<circle cx="{cx}" cy="{cy}" r="70" fill="url(#planet)" stroke="#bdcbe6"/>'
    content += f'<ellipse cx="{cx}" cy="{cy}" rx="159" ry="43" transform="rotate(-23 {cx} {cy})" fill="none" stroke="#899bd1"/>'
    for rx,ry,angle,color,duration,begin in [(159,43,-23,BLUE,18,-5),(164,83,25,VIOLET,26,-13),(112,134,35,GOLD,32,-21)]:
        orbit = f'M {rx} 0 A {rx} {ry} 0 1 1 {-rx} 0 A {rx} {ry} 0 1 1 {rx} 0'
        content += f'<g transform="translate({cx} {cy}) rotate({angle})">'
        content += f'<g class="hero-moving-dot"><circle r="8" fill="{color}" opacity=".1"/><circle r="4" fill="{color}" stroke="{BG}" stroke-width="2"/>'
        content += f'<animateMotion path="{orbit}" dur="{duration}s" begin="{begin}s" repeatCount="indefinite"/></g>'
        content += f'<circle class="hero-resting-dot" cx="{rx}" cy="0" r="4" fill="{color}" stroke="{BG}" stroke-width="2"/></g>'
    content += text(cx+81, cy-88, 'AI / TOOLS', 9, VIOLET, extra='class="mono"')
    content += text(cx-155, cy+116, 'WEB / CRAFT', 9, BLUE, extra='class="mono"')
    content += text(32, 104, 'FRONTEND DEVELOPER · CS STUDENT', 10 if mobile else 11, VIOLET, extra='class="mono" letter-spacing=".5"')
    content += text(30, 158, 'ShenGeYan', 49 if mobile else 55, extra='font-weight="650" letter-spacing="-2"')
    content += text(32, 190, '沈歌宴 / 重庆理工大学', 14, SOFT)
    content += text(32, 239 if mobile else 270, 'Ideas, built into', 29 if mobile else 36, extra='letter-spacing="-1"')
    content += text(32, 278 if mobile else 315, 'useful things.', 37 if mobile else 44, BLUE, extra='class="serif" font-style="italic" letter-spacing="-1"')
    if not mobile:
        content += text(32, 356, '用代码把想法做成作品，把细节做到好用。', 15, SOFT)
        content += text(32, 394, 'VUE / REACT / TYPESCRIPT', 11, VIOLET, extra='class="mono" letter-spacing="1"')
    else:
        content += text(220, 571, '用代码把想法做成作品，把细节做到好用。', 14, SOFT, extra='text-anchor="middle"')
    content += line(h-45, w, 28)
    content += text(28, h-20, 'CHONGQING, CN / FRONTEND × AI', 9 if mobile else 10, DIM, extra='class="mono"')
    content += text(w-28, h-20, 'COMMIT → BUILD', 9 if mobile else 10, BLUE, extra='class="mono" text-anchor="end"')
    svg('hero-mobile' if mobile else 'hero', w, h, 'ShenGeYan / 浅色动态代码星图', content,
        'Light code atlas with orbiting satellites, flowing orbital highlights and a gently breathing halo. Reduced-motion preferences display a still illustration.')


def flow(lang, mobile=False):
    en = lang == 'en'
    w = 440 if mobile else 846
    content = text(30, 43, '01 / CURRENT FOCUS', 13, VIOLET, extra='class="mono" letter-spacing="1"')
    copy = ['Building Web apps with Vue 3, React', 'and TypeScript. Learning by shipping.'] if en else ['用 Vue 3、React 和 TypeScript 做 Web 应用，', '在真实项目里打磨交互与工程细节。']
    for i, value in enumerate(copy):
        content += text(30, 84+i*28, value, 19 if en else 18)
    focus = ['Exploring SSR / SEO and real-time collaboration', 'Connecting AI tools with development workflows'] if en else ['正在探索：SSR / SEO 与实时协同', '让 AI 工具接入日常开发流程']
    for i, value in enumerate(focus):
        content += text(30, 153+i*24, value, 14, SOFT)
    if not mobile:
        content += f'<path d="M610 126H766" stroke="{LINE}"/>'
        for i, label in enumerate(['UI', 'CODE', 'SHIP']):
            x = 610+i*76
            content += f'<circle cx="{x}" cy="126" r="25" fill="{CLOUD}" stroke="{LINE}"/>'
            content += text(x, 130, label, 10, BLUE, extra='class="mono" text-anchor="middle"')
    content += line(200, w, 30)
    content += text(30, 229, 'BUILD / REFINE / REPEAT', 12, BLUE, extra='class="mono" letter-spacing="1"')
    svg('flow-'+lang+('-mobile' if mobile else ''), w, 254, '正在探索 / Current focus', content)


def native_calendar(width, y):
    source = OUT / 'metrics-source.svg'
    if not source.exists():
        return None
    tree = ET.parse(source).getroot()
    for child in tree.iter():
        if child.tag.endswith('}svg') and child is not tree and child.get('viewBox', '').startswith('0,0 480,'):
            child.set('x', '22')
            child.set('y', str(y-35))
            child.set('width', str(width-44))
            child.set('height', '150')
            child.set('preserveAspectRatio', 'none')
            child.attrib.pop('style', None)
            palette = {'#ebedf0':CLOUD,'#161b22':CLOUD,'#9be9a8':'#c6d5ef','#0e4429':'#c6d5ef','#40c463':'#a9bde5','#006d32':'#a9bde5','#30a14e':'#a797cf','#26a641':'#a797cf','#216e39':BLUE,'#39d353':BLUE}
            for node in child.iter():
                if node.get('fill', '').lower() in palette:
                    node.set('fill', palette[node.get('fill').lower()])
                if node.get('id'):
                    node.set('id', 'metrics-'+node.get('id'))
                if 'url(#' in node.get('filter', ''):
                    node.set('filter', node.get('filter').replace('url(#','url(#metrics-'))
            return ET.tostring(child, encoding='unicode')
    raise ValueError('Metrics output has no isocalendar SVG; refusing a malformed render')


def atlas(data, mobile=False):
    w, h = (440, 670) if mobile else (846, 570)
    user = data['user']
    cc = user['contributionsCollection']
    cal = cc['contributionCalendar']
    days = [d for week in cal['weeks'] for d in week['contributionDays']]
    stats = streaks(days)
    repositories = user['repositories']['nodes']
    content = text(28, 35, '02 / CONTRIBUTION ATLAS', 11, BLUE, extra='class="mono" letter-spacing="1.5"')
    content += text(28, 76, 'A year of building.', 29 if mobile else 34, extra='class="serif" font-style="italic"')
    content += text(28, 105, days[0]['date']+' — '+days[-1]['date'], 12, SOFT, extra='class="mono"')
    for i, (number, label) in enumerate([(len(repositories),'PUBLIC ORIGINAL REPOS'),(user['followers']['totalCount'],'FOLLOWERS'),(sum(r['stargazerCount'] for r in repositories),'REPOSITORY STARS'),(user['createdAt'][:4],'SINCE')]):
        x = 28 + (i % (2 if mobile else 4)) * ((w-56)/(2 if mobile else 4))
        y = 150 + (i//2)*76 if mobile else 150
        content += text(x, y, number, 31, extra='class="serif"')
        content += text(x, y+23, label, 9 if mobile else 10, SOFT, extra='class="mono"')
    top = 283 if mobile else 220
    content += line(top-17,w,28)
    content += text(28, top+30, cal['totalContributions'], 50, BLUE, extra='class="serif"')
    content += text(113, top+7, 'CONTRIBUTIONS', 12, extra='class="mono"')
    content += text(113, top+30, 'PAST YEAR / 过去一年', 11, SOFT, extra='class="mono"')
    native = native_calendar(w, top+80)
    if native:
        content += native
    else:
        unit = (w-64)/56.5
        for wi, week in enumerate(cal['weeks']):
            for di, d in enumerate(week['contributionDays']):
                c = d['contributionCount']
                x, y = 24+wi*unit+di*unit*.48, top+118-wi*unit*.085+di*unit*.57
                a,b,k=unit*.83,unit*.4,unit*.47
                z=0 if not c else 7+math.sqrt(c)*8
                color=BLUE if c>=8 else '#a797cf' if c>=4 else '#a9bde5' if c else CLOUD
                faces=[([(x,y-z),(x+a,y-z-unit*.085),(x+a,y-unit*.085),(x,y)],.45), ([(x+a,y-z-unit*.085),(x+a+b,y-z+k-unit*.085),(x+a+b,y+k-unit*.085),(x+a,y-unit*.085)],.65)] if c else []
                faces.append(([(x,y-z),(x+a,y-z-unit*.085),(x+a+b,y-z+k-unit*.085),(x+b,y-z+k)],1))
                for points, opacity in faces:
                    coords=' '.join(f'{px:.2f},{py:.2f}' for px,py in points)
                    content += f'<polygon points="{coords}" fill="{color}" opacity="{opacity}"/>'
    row = top+210
    content += line(row-27,w,28)
    values=[(cc['totalCommitContributions'],'COMMITS'),(cc['totalPullRequestContributions'],'PULL REQUESTS'),(cc['totalIssueContributions'],'ISSUES'),(stats['active'],'ACTIVE DAYS')]
    for i,(number,label) in enumerate(values):
        x=28+i*(w-56)/4
        content += text(x,row+10,number,27,extra='class="serif"')
        content += text(x,row+34,label,9,SOFT,extra='class="mono"')
    content += text(28,row+66,f"CURRENT STREAK  {stats['current']}d    BEST THIS YEAR  {stats['longest']}d",11,SOFT,extra='class="mono"')
    content += text(28,h-25,'GitHub contribution calendar · updated '+data['updated'],10,DIM,extra='class="mono"')
    svg('atlas-mobile' if mobile else 'atlas',w,h,'贡献星图 / 过去一年贡献与提交',content, f"{cal['totalContributions']} contributions; {cc['totalCommitContributions']} commits; {stats['active']} active days. Commit counts use GitHub's contribution rules, not all-branch lifetime totals.")


def languages(data, lang, mobile=False):
    w,h=(440,410) if mobile else (846,302)
    totals=defaultdict(int)
    for repo in data['user']['repositories']['nodes']:
        if repo['name'] in FEATURED:
            for edge in repo['languages']['edges']:
                totals[edge['node']['name']]+=edge['size']
    total=sum(totals.values())
    categories=[(name,totals.get(name,0)) for name in ['TypeScript','Vue','JavaScript']]
    categories.append(('Other',total-sum(v for _,v in categories)))
    colors=[BLUE,'#a797cf','#83bcb1','#d2dcec']
    content=text(28,36,'03 / LANGUAGE SPECTRUM',11,BLUE,extra='class="mono" letter-spacing="1"')
    content+=text(28,76,'The code behind the projects.',23 if mobile else 31,extra='class="serif" font-style="italic"')
    content+=text(28,107,'精选项目 · 按代码体积' if lang=='cn' else 'Selected repositories · by code size',13,SOFT)
    cx,cy=(112,208) if mobile else (470,173)
    radius=68
    content+=f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{CLOUD}" stroke-width="12"/>'
    offset=0
    for (_,value),color in zip(categories,colors):
        fraction=value/total if total else 0
        circumference=2*math.pi*radius
        content+=f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{color}" stroke-width="12" stroke-dasharray="{fraction*circumference:.3f} {circumference:.3f}" stroke-dashoffset="{-offset*circumference:.3f}" transform="rotate(-130 {cx} {cy})"/>'
        offset+=fraction
    content+=text(cx,cy-7,'TypeScript',11,SOFT,extra='class="mono" text-anchor="middle"')
    content+=text(cx,cy+28,f'{100*totals.get("TypeScript",0)/total:.1f}%' if total else '—',32,extra='class="serif" text-anchor="middle"')
    lx,ly=(222,166) if mobile else (586,128)
    for i,((name,value),color) in enumerate(zip(categories,colors)):
        y=ly+i*29
        content+=f'<circle cx="{lx}" cy="{y-4}" r="3" fill="{color}"/>'
        content+=text(lx+11,y,name,12,SOFT,extra='class="mono"')
        content+=text(w-28,y,f'{value/total*100:.1f}%' if total else '—',12,extra='class="mono" text-anchor="end"')
    y=320 if mobile else 158
    x=28
    if not mobile:
        content+=text(x,y,'Different tools.',24)
        content+=text(x,y+35,'One working product.',26,VIOLET,extra='class="serif" font-style="italic"')
    else:
        content+=text(x,y,'Different tools. One working product.',21,VIOLET,extra='class="serif" font-style="italic"')
    content+=text(28,h-43,'SSR-ResourceHub / anyheap-2025 /',10,DIM,extra='class="mono"')
    content+=text(28,h-24,'feishu-codex-local-agent',10,DIM,extra='class="mono"')
    svg('languages-'+lang+('-mobile' if mobile else ''),w,h,'精选项目语言分布 / Selected project languages',content)


def contribution_trend(data, lang, mobile=False):
    w, h = (440, 255) if mobile else (846, 265)
    days = [d for week in data['user']['contributionsCollection']['contributionCalendar']['weeks']
            for d in week['contributionDays']][-30:]
    ceiling = max(1, max(d['contributionCount'] for d in days))
    content = text(28, 34, 'LAST 30 DAYS / DAILY CONTRIBUTIONS', 10, BLUE, extra='class="mono"')
    content += text(28, 71, '最近 30 天的贡献' if lang == 'cn' else 'Recent contribution activity', 23)
    left, right, top, bottom = 44, w-28, 106, h-49
    for tick in (0, ceiling):
        y = bottom-tick/ceiling*(bottom-top)
        content += f'<path d="M{left} {y}H{right}" stroke="{LINE}" stroke-dasharray="3 5"/>'
        content += text(28, y+4, tick, 10, DIM, extra='class="mono" text-anchor="end"')
    points = [(left+i*(right-left)/(len(days)-1), bottom-d['contributionCount']/ceiling*(bottom-top))
              for i, d in enumerate(days)]
    coords = ' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
    content += f'<polygon points="{left},{bottom} {coords} {right},{bottom}" fill="{CLOUD}" opacity=".7"/>'
    content += f'<polyline points="{coords}" fill="none" stroke="{BLUE}" stroke-width="2" stroke-linejoin="round"/>'
    for (x,y),d in zip(points,days):
        if d['contributionCount']:
            content += f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{VIOLET}" stroke="{BG}"/>'
    for i, anchor in [(0,'start'), (len(days)-1,'end')]:
        content += text(points[i][0], h-23, days[i]['date'], 10, DIM, extra=f'class="mono" text-anchor="{anchor}"')
    title = '最近 30 天每日贡献 / Last 30 days of GitHub contributions'
    svg('trend-'+lang+('-mobile' if mobile else ''), w, h, title, content,
        f'{sum(d["contributionCount"] for d in days)} contributions across {days[0]["date"]} to {days[-1]["date"]}; GitHub contribution-calendar counts.')


def activity(data, lang, mobile=False):
    commits=data.get('commits', [])
    w=440 if mobile else 846
    h=115+len(commits)*102
    content=text(28,36,'RECENT PUBLIC COMMITS',11,BLUE,extra='class="mono" letter-spacing="1"')
    content+=text(28,77,'最近在写什么' if lang=='cn' else 'What I have been working on.',25,extra='class="serif"')
    if not commits:
        content+=text(28,113,'No recent public authored commits.',14,SOFT)
        h+=40
    for i,c in enumerate(commits):
        y=112+i*102
        message=c['messageHeadline']
        budget = w - 91
        shortened = ''
        for char in message:
            cost = (16 if mobile else 18) * (1 if unicodedata.east_asian_width(char) in 'WF' else .6)
            if budget < cost + 18:
                shortened += '…'
                break
            shortened += char
            budget -= cost
        message = shortened
        moment=datetime.fromisoformat(c['committedDate'].replace('Z','+00:00')).astimezone(timezone(timedelta(hours=8)))
        content+=f'<circle cx="31" cy="{y}" r="3.5" fill="{VIOLET}"/>'
        if i<len(commits)-1:
            content+=f'<path d="M31 {y+10}v82" stroke="{LINE}"/>'
        content+=text(49,y+4,'shengeyan / '+c['repo'],11,DIM,extra='class="mono"')
        content+=text(49,y+34,message,16 if mobile else 18)
        content+=text(49,y+60,c['oid'][:7]+' · '+moment.strftime('%Y.%m.%d / %H:%M')+' UTC+8',10,SOFT,extra='class="mono"')
    svg('activity-'+lang+('-mobile' if mobile else ''),w,h,'最近的公开提交 / Recent public commits',content)
    links='\n'.join(f"- [{escape(c['messageHeadline'])} · `{c['oid'][:7]}`]({c['url']}) — {c['repo']}" for c in commits)
    (OUT/'recent-commits.md').write_text(links+'\n',encoding='utf-8')


def projects(lang, mobile=False):
    w,h=(440,215) if mobile else (846,205)
    for i,(name,category,stack,cn,en) in enumerate(PROJECTS[:3]):
        accent=[BLUE,VIOLET,MINT][i]
        content=f'<rect x="1" y="19" width="4" height="{h-38}" rx="2" fill="{accent}" opacity=".65"/>'
        content+=text(26,35,chr(65+i)+' / '+category,10,accent,extra='class="mono" letter-spacing=".7"')
        content+=text(w-25,38,'↗',25,accent,extra='text-anchor="end"')
        content+=text(26,88,name,30 if mobile else 36,extra='letter-spacing="-1"')
        content+=text(26,127,cn if lang=='cn' else en,14 if mobile else 17,SOFT)
        if not mobile:
            for angle,color in [(-30,VIOLET),(35,BLUE)]:
                content+=f'<ellipse cx="725" cy="96" rx="62" ry="30" transform="rotate({angle} 725 96)" fill="none" stroke="{color}" stroke-opacity=".48"/>'
            content+=text(725,101,['SSR','SYNC','AI'][i],12,accent,extra='class="mono" text-anchor="middle"')
        content+=line(h-52,w,26)
        content+=text(26,h-23,stack,12,DIM,extra='class="mono"')
        svg('project-'+str(i+1)+'-'+lang+('-mobile' if mobile else ''),w,h,name,content)


def footer(mobile=False):
    w,h=(440,215) if mobile else (846,224)
    cx=w/2
    content=text(cx,58,"Let's build",30,extra='text-anchor="middle"')
    content+=text(cx,104,'something interesting.',33 if mobile else 43,BLUE,extra='class="serif" font-style="italic" text-anchor="middle"')
    content+=line(142,w,28)
    content+=text(28,180,'✦  SAY HELLO',13,BLUE,extra='class="mono"')
    content+=text(w-28,180,'一起创造有趣的东西吧！',12,SOFT,extra='text-anchor="end"')
    svg('footer-mobile' if mobile else 'footer',w,h,'一起创造有趣的东西吧！ / Say hello',content)


def badges(data):
    """Local pastel tags keep text legible and avoid external badge dependencies."""
    tags = [
        ('typescript', 'TypeScript', 116, '#eaf1fd', BLUE),
        ('javascript', 'JavaScript', 116, '#fbf3de', '#876726'),
        ('vue', 'Vue.js', 86, '#e7f4ed', '#39785e'),
        ('react', 'React', 80, '#e7f3f9', '#346f8d'),
        ('nuxt', 'Nuxt', 76, '#e7f4ed', '#39785e'),
        ('nestjs', 'NestJS', 88, '#faeaf0', '#a04e69'),
        ('vite', 'Vite', 72, '#f0ebfb', VIOLET),
        ('tailwind', 'Tailwind CSS', 126, '#e7f3f6', '#34737e'),
        ('node', 'Node.js', 94, '#edf4e8', '#4b743b'),
        ('git', 'Git', 62, '#fbede7', GOLD),
        ('website', 'Website · shengeyan.github.io', 258, '#eaf1fd', BLUE),
        ('blog', 'Blog · shengeyan.tuanwo.cn', 242, '#f0ebfb', VIOLET),
        ('email', 'Email · itshengeyan@qq.com', 244, '#e7f4f0', '#39785e'),
        ('more-projects', 'Explore more projects ↗', 218, '#eaf1fd', BLUE),
        ('views', 'Profile views · live ↗', 184, '#f0ebfb', VIOLET),
        ('since', 'Since · 2022', 118, '#e7f4f0', '#39785e'),
    ]
    user = data['user']
    repos = user['repositories']['nodes']
    tags += [
        ('repos', f'Public repos · {len(repos)}', 154, '#eaf1fd', BLUE),
        ('followers', f"Followers · {user['followers']['totalCount']}", 142, '#f0ebfb', VIOLET),
        ('stars', f"Repo stars · {sum(r['stargazerCount'] for r in repos)}", 140, '#fbf3de', '#876726'),
    ]
    for name, label, width, fill, ink in tags:
        content = f'<rect x=".5" y=".5" width="{width-1}" height="31" rx="9" fill="{fill}" stroke="{ink}" stroke-opacity=".12"/>'
        content += f'<circle cx="14" cy="16" r="3" fill="{ink}" opacity=".65"/>'
        content += text(26, 20, label, 12, ink, extra='font-weight="500"')
        svg('tag-'+name, width, 32, label, content)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    snapshot=OUT/'data.json'
    data=refresh() if args.refresh else json.loads(snapshot.read_text())
    if args.refresh:
        snapshot.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for mobile in (False,True):
        hero(mobile)
        atlas(data,mobile)
        footer(mobile)
        for lang in ('cn','en'):
            flow(lang,mobile)
            languages(data,lang,mobile)
            contribution_trend(data,lang,mobile)
            activity(data,lang,mobile)
            projects(lang,mobile)
    badges(data)
    print(f"Rendered {len(list(OUT.glob('*.svg')))} SVGs from public data dated {data['updated']}")


if __name__=='__main__':
    main()
