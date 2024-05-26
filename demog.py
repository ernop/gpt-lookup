#!/usr/bin/env python3

import os
import time
import sys
import json
import re
import argparse
import requests
import openai
from datetime import datetime

CONFIG_FILE = 'config.json'
API_KEY_FILE = 'apikey.txt'
USER_AGENT = 'DemographicsLookupBot/1.0 (https://example.org/demographicslookupbot/; contact@example.org)'
LANG_CODES = ['en', 'es', 'de', 'jp', 'fr', 'ar', 'iu','sv','ko','mn']
#~ LANG_CODES = ['en', 'de']
MAX_CHARS=120000
#~ LANG_CODES = ['en', 'es']

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_message(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

def strip_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def extract_json_from_response(response_content):
    json_pattern = re.compile(r'json\s*(\{.*\})', re.DOTALL)
    response_content=response_content.replace('```plaintext','').replace('```','')

    #lets line-wise split out and remove comments?
    parts=response_content.split('\n')
    response_content2='\n'.join([p.split('//')[0] for p in parts])
    if response_content!= response_content2:
        print("diff.")
        response_content=response_content2

    match = json_pattern.search(response_content)
    if match:
        return match.group(1)  # Return the JSON object excluding the "json" prefix
    else:
        json_pattern = re.compile(r'(\{.*\})', re.DOTALL)
        match = json_pattern.search(response_content)
        if match:
            return match.group(1)
        else:
            raise ValueError("No JSON content found in the response")

def setup_argparse():
    parser = argparse.ArgumentParser(description='Personal Demographics Lookup Tool')
    parser.add_argument('command', choices=['lookup', 'force_lookup'], help='Command to execute')
    parser.add_argument('name', nargs='+', help='Name of the person to look up, optionally followed by a comma and a hint')
    return parser

def get_cached_file(name):
    cache_file = f"cache/{name}.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None

def save_to_cache(name, data):
    cache_file = f"cache/{name}.json"
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(data, f, indent=4)

def load_apikey():
    with open(API_KEY_FILE, 'r') as f:
        return f.read().strip()

def load_prompt():
    with open('prompt.txt', 'r') as file:
        return file.read()


def get_filling(space_avail, items):
    answer = 0

    #the dumb way. many ways to do this faster but whatever
    while True:
        if sum([len(el[:answer]) for el in items]) >= space_avail:
            break

        answer=answer+1
        #break from loop if we're longer than all.
        doBreak = True
        if (any([answer<=len(el) for el in items])):
            continue

        #if we already include all, well, no problem.
        break
    return answer

def format_for_prompt(atl):
    return f'Language source: {atl[2]}, Regarding: "{atl[1]}": {atl[0]}'

def summarize_info_and_produce_blurb(article_text_title_lang):
    openai.api_key = load_apikey()
    prompt_template = load_prompt()
    english_content = format_for_prompt([at for at in article_text_title_lang if at[2] == 'en'][0])[:35000]
    #we also truncate hard english.

    other_languages_content = [format_for_prompt(at) for at in article_text_title_lang if at[2] != 'en']

    remaining = MAX_CHARS - len(english_content)

    #how much is left to take from each of them?
    n = get_filling(remaining, other_languages_content)

    joined=f"{english_content} - \r\n\r\n{','.join([aa[:n] for aa in other_languages_content] )}"

    start_time=time.time()
    prompt=prompt_template.format(article_text=joined)[:MAX_CHARS]
    arts=','.join([f'Taking {n>len(el) and "all" or n} of {el[:40]}' for el in other_languages_content])
    print(f"Taking first N{n} characters of other lang articles: {arts} Prompt length: {len(prompt)}\tQuery start time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4000
    )

    fn='%Y%m%d_%H%M%S_response.txt'
    print(fn)
    end_time=time.time()
    filename = time.strftime(fn, time.localtime(end_time))

    # Save response details to a file
    with open(filename, 'w') as file:
        json.dump(response.choices[0].message['content'], file, indent=4)

    # Extract and load the JSON content from the response
    response_content = response.choices[0].message['content'].strip()

    print(f"Response length: {len(response_content)}, query time: {end_time - start_time:.2f} seconds")

    try:
        json_content = extract_json_from_response(response_content)
    except Exception as ex1:
        print(json_content)
        #this is when openai doesn't actually return json.
        print(ex1)
        sys.exit(3)
    try:
        person_data = json.loads(json_content)
    except Exception as ex2:
        print(json_content)
        #this is when openai doesn't actually return json.
        print(ex2)
        sys.exit(4)

    return person_data

def download_wikipedia_article(title=None, pageid=None, lang='en'):
    if pageid:
        url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext&pageids={pageid}&format=json"
    else:
        url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext&titles={title}&format=json"

    headers = {'User-Agent': USER_AGENT}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pages = response.json().get('query', {}).get('pages', {})
    page = next(iter(pages.values()))
    if 'extract' in page:
        return page['extract'], page['title']
    else:
        raise ValueError("Page does not exist")

def search_wikipedia(title, hint=None, lang='en'):
    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={title}&format=json"
    headers = {'User-Agent': USER_AGENT}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    search_results = response.json().get('query', {}).get('search', [])
    if search_results:
        for el in search_results:
            el['snippet'] = strip_html_tags(el['snippet'])
        pageid = pick_right_page(search_results, title, hint)
        wikipedia_content, actual_title = download_wikipedia_article(pageid=pageid, lang=lang)
        return wikipedia_content, actual_title
    else:
        raise ValueError("No search results found")

def pick_right_page(search_results, title, hint=None):
    options = [json.dumps(result) for result in search_results]
    if hint:
        # Use GPT to determine the correct article based on the hint
        openai.api_key = load_apikey()
        prompt = f"""Given the hint '{hint}', which of the following options is most likely to be the correct Wikipedia article?
        Please return JUST the pageid field as a simple text and no other information.

        Here are your choices:
        {options}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3500
        )

        chosen_title = response.choices[0].message.content.strip()
        return chosen_title
    else:
        # Present options to the user
        print("Multiple pages detected. Please select the correct option by entering the corresponding number:")

        mm={}
        title_width = 40
        snippet_width = 80
        print("\r\n")
        while True:
            for idx, option in enumerate(search_results, 1):
                title = option['title'].ljust(title_width)
                print(f"\t{idx}\t{title}\t{option['snippet']}")
                mm[idx] = option['pageid']

            try:
                choice = int(input("Enter the number of the correct option: "))
                break
            except:
                continue

        pageid=mm[choice]
        return pageid

def main():
    parser = setup_argparse()

    if len(sys.argv) < 3:
        parser.print_help()
        sys.exit(1)

    try:
        args = parser.parse_args()
        name_parts = ' '.join(args.name)

        if ',' in name_parts:
            search_name, hint = map(str.strip, name_parts.rsplit(',', 1))
        else:
            search_name = name_parts
            hint = None

        tt=[]
        for lang_code in LANG_CODES:
            try:
                con, name = search_wikipedia(search_name, hint, lang=lang_code)
                time.sleep(0.2)
                tt.append((con, name, lang_code))
            except ValueError:
                wikipedia_content_en, actual_name_en = None, None
            except requests.exceptions.ConnectionError as e2:
                log_message(f"Connectino error: {e2} {lang_code}")
                continue
            except Exception as e3:
                log_message(f"Bad lang: {e3} {lang_code}")
                continue

        summarize_info_and_produce_blurb(tt)

    except Exception as e:
        log_message(f"Unexpected error: {e}")
        sys.exit(7)

if __name__ == "__main__":
    main()
