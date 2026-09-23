#!/home/thomas/bin/python3
import json
import re
import sys
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Configuration
VAULT_PATH = "/home/thomas/Documents/ObsidianVault"
TEXTBOOK_PATH = VAULT_PATH + "/Учебник.md"
JOURNAL_PATH = "/home/thomas/LivingCode/agents/journal.md"
REPORTS_PATH = "/home/thomas/LivingCode/reports"

# Current time
now = datetime.now()
current_datetime_str = now.strftime('%Y-%m-%d %H:%M')
current_date_str = now.strftime('%Y-%m-%d')

def fetch_url(url, headers=None):
    """Fetch a URL and return the content as string."""
    if headers is None:
        headers = {}
    # Set a default user agent to avoid 403
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None

def parse_github_trending_api(json_content):
    """Parse GitHub trending API response."""
    try:
        data = json.loads(json_content)
        results = []
        for repo in data:
            # repo is a dict with keys: name, description, url, language, etc.
            name = repo.get('name', '')
            url = repo.get('url', '')
            if not name or not url:
                continue
            # The name is in the format "owner/repo"
            title = name
            results.append((title, url))
        return results
    except Exception as e:
        print(f"Error parsing GitHub trending API: {e}", file=sys.stderr)
        return []

def parse_sysadmins(html):
    """Parse SysAdmins.ru for news titles and URLs."""
    # Look for h2 or h3 with a link
    pattern = r'<h[23]><a href="([^"]+)">([^<]+)</a></h[23]>'
    matches = re.findall(pattern, html, re.DOTALL)
    results = []
    for match in matches:
        url = match[0]
        title = match[1]
        title = re.sub(r'\s+', ' ', title)
        if not title:
            continue
        if not url.startswith('http'):
            url = f"https://sysadmins.ru{url}"
        results.append((title, url))
    return results

def parse_ixbt(html):
    """Parse iXBT news for titles and URLs."""
    pattern = r'<h[23]><a href="([^"]+)">([^<]+)</a></h[23]>'
    matches = re.findall(pattern, html, re.DOTALL)
    results = []
    for match in matches:
        url = match[0]
        title = match[1]
        title = re.sub(r'\s+', ' ', title)
        if not title:
            continue
        if not url.startswith('http'):
            url = f"https://www.ixbt.com{url}"
        results.append((title, url))
    return results

def parse_reddit_json(json_content):
    """Parse Reddit JSON for posts."""
    try:
        data = json.loads(json_content)
        posts = data['data']['children']
        results = []
        for post in posts:
            post_data = post['data']
            title = post_data['title']
            url = post_data['url']
            # If the URL is a reddit link, we want the permalink to the post
            if url.startswith('/r/'):
                url = f"https://www.reddit.com{url}"
            results.append((title, url))
        return results
    except Exception as e:
        print(f"Error parsing Reddit JSON: {e}", file=sys.stderr)
        return []

def filter_topics(topics, source_name):
    """Filter topics by keywords."""
    keywords = [
        'ai агент', 'llm', 'локальная модель', 'inference', 'amd', 'linux', 'android',
        'sovereign', 'приватность', 'dev-tools', 'polymarket', 'trading', 'agent', 'coding',
        'model', 'llamacpp', 'vulkan', 'rungpt', 'lmstudio', 'ollama', 'text-generation-webui',
        'autogpt', 'babyagi', 'metagpt', 'agentverse', 'superguard', 'godmode', 'paranoidx',
        'pxnode', 'polymarket', 'kalshi', 'freebuff', 'codebuff', 'hermes', 'opencode',
        'agency-agents', 'openclaw'
    ]
    # Extended keywords without spaces
    keywords_extended = keywords + [k.replace(' ', '') for k in keywords]
    filtered = []
    seen_titles = set()
    for title, url in topics:
        title_lower = title.lower()
        match = False
        for kw in keywords_extended:
            if kw in title_lower:
                match = True
                break
        if match and title not in seen_titles:
            seen_titles.add(title)
            filtered.append((title, url, source_name))
        # Skip very short titles
        if len(title) < 10:
            if title in seen_titles:
                seen_titles.remove(title)
    return filtered

def find_best_section(title, section_keywords):
    """Find the best section for a title based on keyword matches."""
    title_lower = title.lower()
    scores = {}
    for section_name, kws in section_keywords.items():
        score = 0
        for kw in kws:
            if kw in title_lower:
                score += 1
        if score > 0:
            scores[section_name] = score
    if scores:
        return max(scores, key=scores.get)
    else:
        return "Hermes Agent Internals"

def main():
    # Define section keywords (simplified mapping)
    section_keywords = {
        "Graph Engineering & Evolution": ['graph', 'эволюция', 'агент', 'модель'],
        "Obsidian Advanced": ['obsidian', 'заметки', 'zk'],
        "MCP & Agent Integration": ['mcp', 'агент', 'интеграция', 'agent'],
        "AI/ML on AMD Radeon 780M": ['ai', 'ml', 'amd', 'radeon', '780m', 'vulkan'],
        "Video Surveillance & YOLO": ['video', 'surveillance', 'yolo', 'object detection'],
        "Network Stability & DHCP": ['network', 'dhcp', 'стабильность'],
        "ParanoidX / Sovereign Systems": ['paranoidx', 'sovereign', 'безопасность', 'приватность'],
        "Windows/MSYS Mastery": ['windows', 'msys'],
        "Classic CS Literature": ['classic', 'cs', 'литература'],
        "Hermes Agent Internals": ['hermes', 'агент'],
        "GitHub Awesome Collections": ['github', 'awesome'],
        "Design-Code Integration": ['design', 'code'],
        "Obsidian Second Brain": ['obsidian', 'second brain'],
        "vLLM Optimization": ['vllm', 'optimization'],
        "Autonomous AI Agents": ['autonomous', 'ai agent'],
        "Quantization & Model Compression": ['quantization', 'compression', 'model'],
        "RAG Pipeline & Retrieval": ['rag', 'pipeline', 'retrieval'],
        "Fine-tuning & LoRA": ['fine-tuning', 'lora'],
        "Spec-Driven Development": ['spec', 'driven', 'development'],
        "AI Engineering Stacks": ['ai', 'engineering', 'stack'],
        "Marketing Automation": ['marketing', 'automation'],
        "AI Engineering Mastery": ['ai', 'engineering', 'mastery'],
        "Advanced Spec-Driven": ['advanced', 'spec', 'driven'],
        "Marketing Deep Dive": ['marketing', 'deep dive'],
        "Neo Kim's 21 Concepts": ['neo kim', '21 concepts'],
        "GodModeMarketing Skill": ['godmode', 'marketing'],
        "Mindset & Psychology": ['mindset', 'psychology']
    }

    # Fetch and parse sources
    sources = [
        ("https://ghapi.huchen.dev/repositories?since=daily", "GitHub Trending (API)", parse_github_trending_api),
        ("https://sysadmins.ru/", "SysAdmins.ru", parse_sysadmins),
        ("https://www.ixbt.com/news/", "iXBT News", parse_ixbt),
        ("https://www.reddit.com/r/LocalLLaMA/hot.json?limit=20", "Reddit r/LocalLLaMA", parse_reddit_json),
        ("https://www.reddit.com/r/MachineLearning/hot.json?limit=20", "Reddit r/MachineLearning", parse_reddit_json),
        ("https://www.reddit.com/r/programming/hot.json?limit=20", "Reddit r/Programming", parse_reddit_json)
    ]

    all_filtered = []
    for url, source_name, parser in sources:
        print(f"Fetching {source_name}...", file=sys.stderr)
        # For Reddit, we need to set a User-Agent to avoid 403, but our fetch_url already sets a default one.
        content = fetch_url(url)
        if content is None:
            print(f"Failed to fetch {source_name}", file=sys.stderr)
            continue
        if source_name.startswith("Reddit"):
            topics = parser(content)
        else:
            topics = parser(content)
        filtered = filter_topics(topics, source_name)
        all_filtered.extend(filtered)
        print(f"Found {len(filtered)} relevant topics from {source_name}", file=sys.stderr)

    # Deduplicate by title
    seen = set()
    unique_topics = []
    for title, url, source in all_filtered:
        if title not in seen:
            seen.add(title)
            unique_topics.append((title, url, source))

    print(f"Total unique relevant topics: {len(unique_topics)}", file=sys.stderr)

    # Assign sections
    section_entries = {}
    for title, url, source in unique_topics:
        section_name = find_best_section(title, section_keywords)
        if section_name not in section_entries:
            section_entries[section_name] = []
        section_entries[section_name].append((title, url, source))

    # Prepare textbook entry files and index updates
    textbook_entries_to_write = []  # (file_path, content)
    index_insertions = []  # (section_name, line_to_insert)

    for title, url, source in unique_topics:
        # Create safe filename
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        if not safe_title:
            safe_title = "topic"
        file_path = f"{VAULT_PATH}/{safe_title}.md"

        # Source tag
        source_tag = f"#source:{source.lower().replace(' ', '_').replace('.', '')}"
        tags = [f"#Искатель", f"#researcher:{current_date_str}", source_tag]

        frontmatter = f"""---
type: textbook-entry
topic: "{title}"
status: "🔴 Не изучено"
learned: "{current_datetime_str}"
source: "{url}"
tags: {json.dumps(tags, ensure_ascii=False)}
---

# {title}

## Key Insights
- Точные insights будут добавлены профессором при изучении.

## Code Patterns
- Будет добавлено при изучении.

## Applied To
- Project/Skill: {source}
- File changed: Учебник.md

## Next Steps
- [ ] Изучить топик
- [ ] Добавить примеры кода
"""
        textbook_entries_to_write.append((file_path, frontmatter))

        # Prepare index line
        # We need the file name only (relative to vault)
        file_name = f"{safe_title}.md"
        line_to_insert = f"- [ ] [{title}]({file_name}) — 🔴 #researcher:{current_date_str}"
        # We'll store the section name and the line, we'll insert later
        index_insertions.append((section_name, line_to_insert))

    # Read the textbook index
    with open(TEXTBOOK_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # We'll process insertions per section in reverse order to avoid index shifting
    # Group insertions by section
    insertions_by_section = {}
    for section_name, line in index_insertions:
        if section_name not in insertions_by_section:
            insertions_by_section[section_name] = []
        insertions_by_section[section_name].append(line)

    # For each section, insert the lines after the section header, in reverse order of the list
    # so that the first topic in the list appears at the top.
    # We'll process sections in reverse order of appearance in the file to avoid shifting issues.
    # First, find the line numbers of each section header.
    section_header_lines = {}
    for i, line in enumerate(lines):
        if line.startswith('### '):
            # Extract section name: remove '### ' and then split by ' (priority:'
            header = line.strip()
            # Remove the leading '### '
            header_name = header[4:]
            # Remove the priority part if present
            if ' (priority:' in header_name:
                header_name = header_name.split(' (priority:', 1)[0].strip()
            section_header_lines[header_name] = i

    # Now, for each section that has insertions, insert the lines after the header.
    # We'll process sections in reverse order of their header line number to avoid shifting.
    sections_sorted = sorted(section_header_lines.items(), key=lambda x: x[1], reverse=True)
    for section_name, header_idx in sections_sorted:
        if section_name not in insertions_by_section:
            continue
        # Get the lines to insert for this section
        to_insert = insertions_by_section[section_name]
        # We want to insert them in reverse order so that the first in the list ends up at the top.
        for line in reversed(to_insert):
            # Insert at header_idx + 1
            lines.insert(header_idx + 1, line + '\n')
            # Update header_idx for subsequent insertions in the same section? Actually, we are inserting multiple lines,
            # and each insertion shifts the positions. Since we are inserting in reverse order of the list,
            # and we are inserting at the same position (header_idx+1) each time, the next insertion will be after the previous one.
            # This is correct: we want the lines to appear in the order of the list (first at the top).
            # Example: list = [A, B, C]; we insert in reverse order: C, B, A.
            # Insert C at header_idx+1 -> [header, C, ...]
            # Insert B at header_idx+1 -> [header, B, C, ...]
            # Insert A at header_idx+1 -> [header, A, B, C, ...]
            # So the final order is A, B, C as desired.

    # Write the updated textbook index
    with open(TEXTBOOK_PATH, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    # Write the textbook entry files
    for file_path, content in textbook_entries_to_write:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    # Write the report file
    import os
    os.makedirs(REPORTS_PATH, exist_ok=True)
    report_path = f"{REPORTS_PATH}/searcher-{now.strftime('%Y%m%d-%H%M')}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"""# Отчет поисковика-агента за {current_datetime_str}

## Найдено тем: {len(unique_topics)}

## Источники:
""")
        # Count by source
        source_counts = {}
        for _, _, source in unique_topics:
            source_counts[source] = source_counts.get(source, 0) + 1
        for source, count in source_counts.items():
            f.write(f"- {source}: {count}\n")
        f.write("\n## Топ-3 темы по релевантности (по порядку нахождения):\n")
        for i, (title, url, source) in enumerate(unique_topics[:3]):
            f.write(f"{i+1}. **{title}**\n   - Источник: {source}\n   - URL: {url}\n\n")
        f.write(f"""## Действия выполнены:
- Создано {len(textbook_entries_to_write)} записей в учебнике.
- Обновлен указатель учебника (Учебник.md) с новыми темами.
- Записан журнал агентов.

## Ссылка на отчет:
{report_path}
""")

    # Update the journal
    with open(JOURNAL_PATH, 'a', encoding='utf-8') as f:
        f.write(f"\n[TRIGGER_PROFESSOR] — найдено {len(unique_topics)} новых топиков, файлы в vault, список ниже\n")

    print(f"Job completed. Found {len(unique_topics)} topics.", file=sys.stderr)

if __name__ == "__main__":
    main()