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
BG, INK, SOFT, DIM, GOLD, VIOLET, LINE = '#0d0d15', '#f4f0eb', '#b3aec1', '#9690a8', '#f4bd8d', '#ad9ae8', '#353040'
FEATURED = ['SSR-ResourceHub', 'anyheap-2025', 'feishu-codex-local-agent']
PROJECTS = [
    ('SSR-ResourceHub', 'WEB × DISCOVERY', 'Vue / Nuxt / Nest', '资源与发现，在同一条轨道相遇。', 'Resources and discovery, in the same orbit.'),
    ('anyheap-2025', 'REAL-TIME × COLLABORATION', 'TypeScript / WebSocket', '让物料拖拽、协同与同步自然发生。', 'Draggable materials. Seamless collaboration.'),
    ('feishubot', 'HUMAN × AI', 'TypeScript / Bot', '从飞书对话，抵达本地开发工作流。', 'From a Feishu conversation to a local workflow.'),
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
<rect width="{width}" height="{height}" rx="8" fill="{BG}"/>{content}</svg>'''
    ET.fromstring(markup)
    (OUT / (name + '.svg')).write_text(markup, encoding='utf-8')


def hero(mobile=False):
    w, h = (440, 660) if mobile else (846, 700)
    cx, cy = w / 2, 310 if mobile else 325
    content = '''<defs><radialGradient id="glow"><stop stop-color="#7c64b0" stop-opacity=".21"/><stop offset="1" stop-color="#0d0d15" stop-opacity="0"/></radialGradient><radialGradient id="planet" cx="38%" cy="58%" r="63%"><stop offset=".73" stop-color="#0a0a11"/><stop offset=".92" stop-color="#251c2c"/><stop offset=".99" stop-color="#ac7867"/><stop offset="1" stop-color="#f4cca0"/></radialGradient></defs>'''
    content += text(27, 37, 'DEEP SPACE OBSERVATORY', 10 if mobile else 12, SOFT, extra='class="mono" letter-spacing="1"')
    content += text(w - 27, 37, 'EST. 2022  ✦', 10 if mobile else 12, GOLD, extra='class="mono" text-anchor="end"')
    content += text(cx, 96, 'A PERSONAL UNIVERSE IN CODE', 11 if mobile else 12, GOLD, extra='class="mono" text-anchor="middle" letter-spacing="2"')
    content += text(cx, 152, 'SHENGEYAN', 47 if mobile else 68, extra='text-anchor="middle" font-weight="600" letter-spacing="-2"')
    content += text(cx, 186, '沈 歌 宴', 16, SOFT, extra='text-anchor="middle" letter-spacing="5"')
    content += text(cx, 216, 'Frontend Developer · CS Student · AI Tools', 11 if mobile else 14, SOFT, extra='class="mono" text-anchor="middle"')
    content += f'<ellipse cx="{cx}" cy="{cy}" rx="{w*.45}" ry="137" fill="url(#glow)"/>'
    for i in range(40):
        x, y = 23 + (i * 113) % (w - 46), 237 + (i * 61) % 205
        content += f'<circle cx="{x}" cy="{y}" r="{.7 if i%4 else 1.3}" fill="{SOFT}" opacity="{.22+(i%4)*.1}"/>'
    for rx, ry, angle in [(w*.39, 69, 15), (w*.24, 101, -52)]:
        content += f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="rotate({angle} {cx} {cy})" fill="none" stroke="#756586" stroke-opacity=".58"/>'
    content += f'<circle cx="{cx}" cy="{cy}" r="{72 if mobile else 86}" fill="url(#planet)" transform="rotate(-30 {cx} {cy})"/>'
    content += f'<ellipse cx="{cx}" cy="{cy}" rx="{w*.35}" ry="53" transform="rotate(-22 {cx} {cy})" fill="none" stroke="#95819b" stroke-opacity=".65"/>'
    for x, y, c in [(cx-w*.27, cy-37, GOLD),(cx+w*.28,cy+49,VIOLET),(cx+w*.13,cy-109,GOLD)]:
        content += f'<circle cx="{x}" cy="{y}" r="2.7" fill="{c}"/>'
    content += text(26, cy+92, 'WEB EXPERIENCES', 9 if mobile else 12, SOFT, extra='class="mono"')
    content += text(w-26, cy-66, 'AI WORKFLOWS', 9 if mobile else 12, SOFT, extra='class="mono" text-anchor="end"')
    content += text(cx, 485 if mobile else 511, 'Good ideas deserve', 29 if mobile else 38, extra='text-anchor="middle" letter-spacing="-1"')
    content += text(cx, 525 if mobile else 558, 'their own orbit.', 39 if mobile else 49, GOLD, extra='class="serif" text-anchor="middle" font-style="italic" letter-spacing="-1"')
    content += text(cx, 572 if mobile else 606, '像风一样流动，像浪一样推进', 14 if mobile else 17, SOFT, extra='text-anchor="middle" letter-spacing="2"')
    content += line(h-42, w, 27)
    content += text(27, h-19, 'CHONGQING, CN / BUILDING WITH CURIOSITY', 9 if mobile else 11, DIM, extra='class="mono"')
    svg('hero-mobile' if mobile else 'hero', w, h, 'ShenGeYan / 深空星图', content)


def flow(lang):
    en = lang == 'en'
    content = text(30, 43, 'flow.profile', 19, VIOLET, extra='class="mono"')
    copy = ['Build clear, gentle, maintainable Web experiences', 'with Vue 3, React and TypeScript.'] if en else ['用 Vue 3、React、TypeScript 构建清晰、柔和、', '可持续维护的 Web 体验。']
    for i, value in enumerate(copy):
        content += text(30, 84+i*28, value, 19 if en else 18)
    focus = ['Frontend architecture / AI-assisted workflows', 'SSR & SEO / Collaboration tools'] if en else ['关注方向：前端架构 / AI 辅助工作流', 'SSR 与 SEO / 协同工具']
    for i, value in enumerate(focus):
        content += text(30, 153+i*24, value, 14, SOFT)
    content += line(200, 600, 30)
    content += text(30, 229, 'clear interface  ✦  soft motion  ✦  steady build', 12, GOLD, extra='class="mono"')
    svg('flow-'+lang, 600, 254, 'flow.profile', content)


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
            palette = {'#ebedf0':'#302938','#161b22':'#302938','#9be9a8':'#79607f','#0e4429':'#79607f','#40c463':'#957398','#006d32':'#957398','#30a14e':VIOLET,'#26a641':VIOLET,'#216e39':GOLD,'#39d353':GOLD}
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
    content = text(28, 35, '02 / ACTIVITY ATLAS', 11, GOLD, extra='class="mono" letter-spacing="1.5"')
    content += text(28, 76, 'Every commit, a coordinate.', 26 if mobile else 32, extra='class="serif" font-style="italic"')
    content += text(28, 105, days[0]['date']+' — '+days[-1]['date'], 12, SOFT, extra='class="mono"')
    for i, (number, label) in enumerate([(len(repositories),'PUBLIC ORIGINAL REPOS'),(user['followers']['totalCount'],'FOLLOWERS'),(sum(r['stargazerCount'] for r in repositories),'REPOSITORY STARS'),(user['createdAt'][:4],'SINCE')]):
        x = 28 + (i % (2 if mobile else 4)) * ((w-56)/(2 if mobile else 4))
        y = 150 + (i//2)*76 if mobile else 150
        content += text(x, y, number, 31, extra='class="serif"')
        content += text(x, y+23, label, 9 if mobile else 10, SOFT, extra='class="mono"')
    top = 283 if mobile else 220
    content += line(top-17,w,28)
    content += text(28, top+30, cal['totalContributions'], 50, GOLD, extra='class="serif"')
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
                color=GOLD if c>=8 else VIOLET if c>=4 else '#957398' if c else '#302938'
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
    svg('atlas-mobile' if mobile else 'atlas',w,h,'GitHub 潮汐 / 过去一年贡献与提交',content, f"{cal['totalContributions']} contributions; {cc['totalCommitContributions']} commits; {stats['active']} active days. Commit counts use GitHub's contribution rules, not all-branch lifetime totals.")


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
    colors=[GOLD,VIOLET,'#8abfce','#575062']
    content=text(28,36,'03 / LANGUAGE SPECTRUM',11,GOLD,extra='class="mono" letter-spacing="1"')
    content+=text(28,76,'Tools change. Curiosity stays.',26 if mobile else 31,extra='class="serif" font-style="italic"')
    content+=text(28,107,'精选项目 · 按代码体积' if lang=='cn' else 'Selected repositories · by code size',13,SOFT)
    cx,cy=(112,208) if mobile else (470,173)
    radius=68
    content+=f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#302938" stroke-width="12"/>'
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
        content+=text(x,y,'Written in',24)
        content+=text(x,y+35,'many wavelengths.',29,VIOLET,extra='class="serif" font-style="italic"')
    else:
        content+=text(x,y,'Written in many wavelengths.',24,VIOLET,extra='class="serif" font-style="italic"')
    content+=text(28,h-43,'SSR-ResourceHub / anyheap-2025 /',10,DIM,extra='class="mono"')
    content+=text(28,h-24,'feishu-codex-local-agent',10,DIM,extra='class="mono"')
    svg('languages-'+lang+('-mobile' if mobile else ''),w,h,'精选项目语言分布 / Selected project languages',content)


def activity(data, lang, mobile=False):
    commits=data.get('commits', [])
    w=440 if mobile else 846
    h=115+len(commits)*102
    content=text(28,36,'RECENT PUBLIC SIGNALS',11,GOLD,extra='class="mono" letter-spacing="1"')
    content+=text(28,77,'最近的开发信号' if lang=='cn' else 'Small steps. Real progress.',25,extra='class="serif"')
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
        content=f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="8" fill="none" stroke="{LINE}"/>'
        content+=text(26,35,chr(65+i)+' / '+category,10,GOLD,extra='class="mono" letter-spacing=".7"')
        content+=text(w-25,38,'↗',25,GOLD,extra='text-anchor="end"')
        content+=text(26,88,name,30 if mobile else 36,extra='letter-spacing="-1"')
        content+=text(26,127,cn if lang=='cn' else en,14 if mobile else 17,SOFT)
        if not mobile:
            for angle,color in [(-30,VIOLET),(35,GOLD)]:
                content+=f'<ellipse cx="725" cy="96" rx="62" ry="30" transform="rotate({angle} 725 96)" fill="none" stroke="{color}" stroke-opacity=".48"/>'
            content+=text(725,101,['SSR','SYNC','AI'][i],12,GOLD,extra='class="mono" text-anchor="middle"')
        content+=line(h-52,w,26)
        content+=text(26,h-23,stack,12,DIM,extra='class="mono"')
        svg('project-'+str(i+1)+'-'+lang+('-mobile' if mobile else ''),w,h,name,content)


def footer(mobile=False):
    w,h=(440,215) if mobile else (846,224)
    cx=w/2
    content=text(cx,58,"Let's build",30,extra='text-anchor="middle"')
    content+=text(cx,104,'something interesting.',33 if mobile else 43,GOLD,extra='class="serif" font-style="italic" text-anchor="middle"')
    content+=line(142,w,28)
    content+=text(28,180,'✦  FLOW.ONLINE',13,SOFT,extra='class="mono"')
    content+=text(w-28,180,'一起创造有趣的东西吧！',12,SOFT,extra='text-anchor="end"')
    svg('footer-mobile' if mobile else 'footer',w,h,'FLOW.ONLINE / 一起创造有趣的东西吧！',content)


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
            languages(data,lang,mobile)
            activity(data,lang,mobile)
            projects(lang,mobile)
    for lang in ('cn','en'):
        flow(lang)
    print(f"Rendered {len(list(OUT.glob('*.svg')))} SVGs from public data dated {data['updated']}")


if __name__=='__main__':
    main()
