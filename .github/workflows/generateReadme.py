import requests

def fetch_repos(username):
    url = f'https://api.github.com/users/{username}/repos'
    response = requests.get(url)
    repos = response.json()
    return repos

def update_readme(repos):
    with open('README.md', 'r') as file:
        readme_content = file.readlines()

    # 找到项目部分的位置
    start_line = 0
    for i, line in enumerate(readme_content):
        if line.strip() == '### 💡 Projects':
            start_line = i + 1
            break
    
    # 插入新的项目列表
    new_content = readme_content[:start_line]
    for repo in repos:
        new_content.append(f"- [{repo['name']}]({repo['html_url']}): {repo['description']}\n")

    with open('README.md', 'w') as file:
        file.writelines(new_content)

if __name__ == '__main__':
    username = 'shengeyan'
    repos = fetch_repos(username)
    update_readme(repos)
