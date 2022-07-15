import json
import os
import platform
import subprocess

from xml.dom import minidom 
from datetime import datetime

PANDOC_CMD = 'pandoc'
FFPROBE_CMD = 'ffprobe'
# download pandoc.exe and ffprobe.exe to ./.tools if you are using windows
if platform.system() == 'Windows':
    PANDOC_CMD = "./.tools/pandoc.exe"
    FFPROBE_CMD = "./.tools/ffprobe.exe"

def meta_to_markdown(meta, content):
    out = str()
    out = out + "---\n"
    for entry in meta:
        out = out + entry + ": " + str(meta[entry]) + "\n"
    out = out + "---\n\n"
    out = out + content + "\n"
    return out

def pandoc_meta_to_str(meta):
    ret = str()
    for elem in meta:
        if elem['t'] == 'Str':
            ret = ret + elem['c']
        elif elem['t'] == 'Space':
            ret = ret + ' '
    return ret

def parse_src(filename):
    stdout_ret = subprocess.check_output([PANDOC_CMD, filename, "-t", "json"])
    metadata_j = json.loads(stdout_ret.decode("utf-8"))
    metadata = dict()
    for entry in metadata_j["meta"]:
        metadata[entry] = pandoc_meta_to_str(metadata_j["meta"][entry]["c"])
    md_str = subprocess.check_output([PANDOC_CMD, filename, "-t", "markdown"]).decode("utf-8")
    html_str= subprocess.check_output([PANDOC_CMD, filename, "-t", "html"]).decode("utf-8")
    return metadata, md_str, html_str

def get_audio_info(filename):
    # -v quiet -print_format json -show_format
    audio_info_json_s = subprocess.check_output([FFPROBE_CMD, "-v", "quiet", '-print_format', 'json', '-show_format', filename])
    info = json.loads(audio_info_json_s.decode('utf-8'))['format']
    return int(info['size']), int(float(info['duration']))

def format_pub_date(date, time):
    iso_str = date + " " + time
    return datetime.fromisoformat(iso_str).strftime("%a, %d %b %Y %H:%M:%S %z")

def get_episode(sitemeta, num):
    basepath = "episodes/" + str(num) + "/"
    epimeta, _, html_s = parse_src(basepath + "index.md")
    epimeta["url"] = sitemeta['baseurl'] + '/' + basepath
    epimeta["full_title"] = str(num) + ". " + epimeta['title']
    epimeta["description"] = html_s
    epimeta["number"] = str(num)
    epimeta["pubDate"] = format_pub_date(epimeta['date'], "12:00")
    length, duration = get_audio_info(basepath + epimeta["audio"])
    epimeta["audio_length"] = str(length)
    epimeta["audio_duration"] = str(duration)
    return epimeta

def get_episodes_list():
    episodes = list()
    for entry in os.scandir('./episodes/'):
        try:
            if entry.is_dir() and str(int(entry.name)) == entry.name:
                episodes.append(int(entry.name))
        except:
            continue
    episodes.sort()
    episodes.reverse()
    return episodes


def build_feed_xml(rss_info):
    sitemeta = rss_info["meta"]
    root = minidom.Document()

    def node(name, attr):
        elem = root.createElement(name)
        for key in attr:
            elem.setAttribute(key, attr[key])
        return elem        

    def text_node(name, attr, text):
        elem = node(name, attr)
        elem.appendChild(root.createTextNode(text))
        return elem
    
    rss = node('rss', {
        "version": "2.0",
        "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        'xmlns:atom': 'http://www.w3.org/2005/Atom'
    })
    root.appendChild(rss)

    channel = node("channel", {})
    rss.appendChild(channel)
    channel.appendChild(text_node("title", {}, sitemeta["title"]))
    channel.appendChild(text_node("link", {}, sitemeta["baseurl"]))
    feed_url = sitemeta['baseurl'] + "/feed.xml"
    channel.appendChild(node("atom:link", {
        'href': feed_url,
        'rel': "self",
        'type': "application/rss+xml"
    }))
    channel.appendChild(text_node("itunes:new-feed-url", {}, feed_url))
    channel.appendChild(text_node("description", {}, sitemeta["description"]))

    channel.appendChild(text_node("language", {}, sitemeta["language"]))
    channel.appendChild(node("itunes:category", {'text': sitemeta["category"]}))
    image_url = sitemeta["baseurl"] + "/" + sitemeta["image"]
    channel.appendChild(node("itunes:image", {"href": image_url}))
    channel.appendChild(text_node("itunes:keywords", {}, sitemeta["keywords"]))
    channel.appendChild(text_node("itunes:explicit", {}, 'false'))
    channel.appendChild(text_node("itunes:author", {}, sitemeta["author"]))
    
    owner = node("itunes:owner", {})
    channel.appendChild(owner)
    owner.appendChild(text_node("itunes:name", {}, sitemeta["title"]))
    owner.appendChild(text_node("itunes:email", {}, sitemeta["email"]))

    channel.appendChild(text_node("itunes:type", {}, "episodic"))

    for epi in rss_info['episodes']:
        item = node("item", {})
        item.appendChild(text_node("title", {}, epi["full_title"]))
        item.appendChild(text_node("itunes:episode", {}, epi["number"]))
        item.appendChild(text_node("itunes:title", {}, epi["title"]))
        item.appendChild(text_node("description", {}, epi["description"]))
        item.appendChild(text_node("link", {}, epi["url"]))
        item.appendChild(text_node("guid", {}, epi["url"]))
        item.appendChild(text_node("author", {}, epi["author"]))
        item.appendChild(text_node("pubDate", {}, epi["pubDate"]))
        item.appendChild(node("enclosure", {
            'type': "audio/mpeg",
            'length': epi["audio_length"],
            'url': epi["url"] + epi['audio']
        }))
        item.appendChild(text_node("duration", {}, epi["audio_duration"]))

        channel.appendChild(item)

    xml_str = root.toprettyxml(indent ="\t") 
    return xml_str

def get_site_info():
    rss_info = dict()
    sitemeta, _, _ = parse_src("index.md")
    rss_info["meta"] = sitemeta
    episodes_list = get_episodes_list()
    rss_info['episodes'] = list()
    for epi_num in episodes_list:
        rss_info['episodes'].append(get_episode(sitemeta, epi_num))
    return rss_info

def markdown_to_html(filename, target):
    subprocess.run([PANDOC_CMD, '--template', 'template.html', filename, '-o', target])

def build_index_page(rss_info):
    metadata, md_s, _ = parse_src('./index.md')
    metadata['pagetitle'] = metadata['title']
    metadata['sitetitle'] = metadata['title']
    metadata['ogtitle'] = metadata['title']
    metadata.pop('title', None)
    metadata['icon'] = metadata['baseurl'] + "/" + metadata['image']
    metadata['path'] = metadata['baseurl'] + "/"
    metadata['feedurl'] = metadata['baseurl'] + '/feed.xml'
    metadata['homeurl'] = metadata['baseurl']
    md_s = md_s + '\n'
    for epi in rss_info['episodes']:
        md_s = md_s + '- [' + epi['full_title'] + '](./episodes/' + epi['number'] + ')\n'
    with open('./index.tmp.md', 'w') as fp:
        fp.write(meta_to_markdown(metadata, md_s))
    markdown_to_html('./index.tmp.md', './index.html')
    os.remove('./index.tmp.md')

def build_episode_page(site, episode):
    dir_name = './episodes/' + episode['number'] + '/'
    md_in_filename = dir_name + 'index.md'
    target = dir_name + 'index.html'
    md_out_filename = dir_name + 'index.tmp.md'

    metadata, md_s, _ = parse_src(md_in_filename)
    metadata['pagetitle'] = metadata['title'] + ' - ' + site['title']
    metadata['sitetitle'] = site['title']
    metadata['ogtitle'] = metadata['title'] + ' - ' + site['title']
    metadata['title'] = episode['full_title']
    metadata['icon'] = site['baseurl'] + "/" + site['image']
    metadata['path'] = site['baseurl'] + "/"
    metadata['feedurl'] = site['baseurl'] + '/feed.xml'
    metadata['homeurl'] = site['baseurl']
    metadata['email'] = site['email']

    with open(md_out_filename, "w") as fp:
        fp.write(meta_to_markdown(metadata, md_s))
    markdown_to_html(md_out_filename, target)
    os.remove(md_out_filename)

def build_site(rss_info):
    build_index_page(rss_info)
    for epi in rss_info['episodes']:
        build_episode_page(rss_info['meta'], epi)

site_info = get_site_info()
feed_str = build_feed_xml(site_info)
feed_str = feed_str.replace('?xml version="1.0" ?', '?xml version="1.0" encoding="UTF-8"?')
with open('./feed.xml', "w") as fp:
    fp.write(feed_str)
build_site(site_info)
