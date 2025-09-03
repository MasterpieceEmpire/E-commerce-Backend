# Temporary patch for Python 3.13 (since cgi was removed)
# Only implements what Django needs
import urllib.parse as urlparse

def parse_header(line):
    parts = line.split(';')
    key = parts[0].strip().lower()
    pdict = {}
    for p in parts[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            pdict[k.strip()] = v.strip().strip('"')
    return key, pdict
