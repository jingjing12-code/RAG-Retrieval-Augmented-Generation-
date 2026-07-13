import re

def parse_srt(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # remove line numbers
    content = re.sub(r'^\d+\s*$', '', content, flags=re.MULTILINE)

    # remove timestamps
    content = re.sub(
        r'\d{2}:\d{2}:\d{2},\d{3}\s-->\s(?:\d{2}:\d{2}:\d{2},\d{3}|NaN:NaN:NaN,NaN)',
        '',
        content
    )

    # remove [Music]
    content = re.sub(r'\[.*?\]', '', content)

    # remove extra blank lines
    content = re.sub(r'\n+', '\n', content)

    return content.strip()