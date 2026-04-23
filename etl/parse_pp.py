import pdfplumber 
import re 
from pathlib import Path
from dotenv import load_dotenv 

load_dotenv()

TRACK_CODES = {
    'Keeneland': 'KEE'
    , 'Churchill Downs': 'CD'
    ,
}

# BrisNet uses superscript-style chars for fractions 
# These appear in fractional times like :22@ = :22.2

FRACTION_MAP = {
    '©': '.2', 'ª': '.1', '«': '.3', '¬': '.4',
    '­': '.5', '®': '.6', '¯': '.7', '°': '.8',
    '±': '.9', '²': '.0',
}

RUNNING_STYLES = ['E', 'E/P', 'P', 'S', 'NA'] 

# ------------------------------------------
# Utility Functions
# ------------------------------------------

def clean_fraction_chars(text: str) -> str:
    """
    Replace BrisNet fraction characters with decimal equivalents.
    """
    for char, replacement in FRACTION_MAP.items():
        text = text.replace(char, replacement)
    return text

def parse_date(date_str: str) -> str:
    """
    Convert BrisNet data format to ISO format
    e.g. '24Jan26' -> '2026-01-24'
    """
    months = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jly': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    try:
        day = date_str[:2]
        month = date_str[2:5]
        year = '20' + date_str[5:7]
        return f"{year}--{months.get(month, '01')}--{day.zfill(2)}"
    except Exception:
        return None 
    
def parse_race_header(line: str) -> dict:
    """
    Parse the race header line.
    Example: 'Keeneland "Clm 16000 6 Furlongs 4&up, F & M Thursday, April 16, 2026 Race 1'
    """
    result = {}

    # Track Name 
    for track_name, code in TRACK_CODES.items():
        if track_name in line:
            result['track_code'] = code 
            result['track_name'] = track_name 
            break
    
    # Race Number 
    race_num = re.search(r'Race\s+(\d+)', line)
    if race_num:
        result['race_number'] = int(race_num.group(1))

    # Race Date
    date_match = re.search(
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
        r'(\w+ \d+, \d{4})', line
    )
    if date_match:
        from datetime import datetime
        try:
            dt = datetime.strptime(date_match.group(2), '%B %d, %Y')
            result['race_date'] = dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    
    # Distance — handles all BrisNet formats:
    # '6 Furlongs', '4½ Furlongs', '5½ Furlongs'
    # '1ˆ Mile' (1 1/16), '1½ Mile' (1 1/2)
    DIST_CHAR_MAP = {
        '½': ' 1/2',
        'ˆ': ' 1/16',
        '¼': ' 1/4',
        '¾': ' 3/4',
        '‰': ' 1/8',
        'Š': ' 3/8',
    }
    dist_match = re.search(
        r'[\dˆ½¼¾‰Š]+\s*(?:Mile|Furlongs?)', line
    )
    if dist_match:
        raw_dist = dist_match.group(0).strip()
        # Replace special chars with readable fractions
        clean_dist = raw_dist
        for char, replacement in DIST_CHAR_MAP.items():
            clean_dist = clean_dist.replace(char, replacement)
        result['distance'] = clean_dist.strip()

    # Surface - check for Turf indicator
    if '(T)' in line or 'Turf' in line:
        result['surface'] = 'Turf'
    else:
        result['surface'] = 'Dirt'

    # Race type and claiming price
    race_type_match = re.search(
        r'™?(Clm|Mdn|Alw|Stk|Hcp|OC|MC)\s*(\d+)?', line
    )
    if race_type_match:
        result['race_type'] = race_type_match.group(1)
        if race_type_match.group(2):
            result['claiming_price'] = int(race_type_match.group(2))

    return result


def parse_pars(text: str) -> dict:
    """
    Extract pace pars from text.
    Example: 'PARS: 92 94/ 82 82'
    Returns empty dict if pars are 0 0/ 0 0 (no pars available)
    """
    par_match = re.search(
        r'PARS:\s*(\d+)\s+(\d+)/\s*(\d+)\s+(\d+)', text
    )
    if par_match:
        e1   = float(par_match.group(1))
        e2   = float(par_match.group(2))
        late = float(par_match.group(3))
        spd  = float(par_match.group(4))
        # BrisNet uses 0 0/ 0 0 when no pars available
        if e1 == 0 and e2 == 0:
            return {}
        return {
            'pace_par_e1':   e1,
            'pace_par_e2':   e2,
            'pace_par_late': late,
            'speed_par':     spd,
        }
    return {}


def parse_entry_header(line: str) -> dict:
    """
    Parse a horse entry header line - all on one line in BrisNet format.
    Example: '1 Emirates Affair (E 8) $16,000 Dkbbr.m.8 Prime Power: 119.0 (1st) Life:...'
    """
    result = {}

    # Post position, horse name, running style
    entry_match = re.match(
        r'^(\d+)\s+(.+?)\s+\(([A-Z/]+)\s+\d+\)', line
    )
    if entry_match:
        result['post_position'] = int(entry_match.group(1))
        result['horse_name']    = entry_match.group(2).strip()
        result['running_style'] = entry_match.group(3).strip()

    # Claiming price — only present for claiming races
    claiming_match = re.search(r'\$(\d{1,2},?\d{3})\s+\w', line)
    if claiming_match:
        price = claiming_match.group(1).replace(',', '')
        result['claiming_price'] = int(price)

    # Sex and age - pattern like 'Dkbbr.m.8' or 'B.g.5'
    sex_map = {'m': 'Mare', 'f': 'Filly', 'g': 'Gelding',
               'c': 'Colt', 'h': 'Horse', 'r': 'Ridgling'}
    sex_match = re.search(r'\b[A-Za-z]+\.([mfgchr])\.\s*(\d+)', line)
    if sex_match:
        result['sex'] = sex_map.get(sex_match.group(1).lower(), 'Unknown')
        result['age'] = int(sex_match.group(2))

    # Prime Power
    pp_match = re.search(r'Prime Power:\s*([\d.]+)', line)
    if pp_match:
        result['prime_power'] = float(pp_match.group(1))

    # Life stats - best Beyer
    # Pattern: 'Life: 56 12 -14 - 7 $407,880 91'
    life_match = re.search(
        r'Life:\s*\d+\s+\d+\s*-\s*\d+\s*-\s*\d+\s*\$[\d,]+\s+(\d+)', line
    )
    if life_match:
        result['best_beyer_career'] = int(life_match.group(1))

    # Morning line odds - appears before the entry on its own line
    # Will be captured separately when we see a standalone odds pattern
    odds_match = re.search(r'^(\d+/\d+|\d+)\s*$', line)
    if odds_match:
        result['morning_line_raw'] = odds_match.group(1)

    return result


def parse_prime_power(line: str) -> dict:
    """
    Extract Prime Power rating.
    Example: 'Prime Power: 119.0 (1st)'
    """
    pp_match = re.search(r'Prime Power:\s*([\d.]+)', line)
    if pp_match:
        return {'prime_power': float(pp_match.group(1))}
    return {}


def parse_past_performance_line(line: str) -> dict:
    """
    Parse a single past performance line.
    Example: '24Jan26SA­ 6½ft :22© :45©1:10« 1:17©¡¨¨ª™OC25k-N ¨¨ª90 91/ 75 -3 -5 76...'
    """
    result = {}
    line = clean_fraction_chars(line)

    # Date and track - first 9-10 chars typically
    date_track = re.match(r'(\d{2}\w{3}\d{2})(\w+)', line)
    if date_track:
        result['race_date'] = parse_date(date_track.group(1))
        result['track']     = date_track.group(2)[:3].upper()

    # E1, E2, Late pace figures: pattern like '90 91/ 75'
    pace_match = re.search(r'(\d{2,3})\s+(\d{2,3})/\s*(\d{2,3})', line)
    if pace_match:
        result['e1_pace']   = float(pace_match.group(1))
        result['e2_pace']   = float(pace_match.group(2))
        result['late_pace'] = float(pace_match.group(3))

    # Beyer speed figure — appears after pace figures
    # Pattern: pace nums then two +/- numbers then the Beyer
    beyer_match = re.search(
        r'\d{2,3}/\s*\d{2,3}\s+[+-]\d+\s+[+-]\d+\s+(\d{2,3})', line
    )
    if beyer_match:
        result['beyer_figure'] = int(beyer_match.group(1))

    # Finish position — look for FIN column area
    # Simplified: grab last standalone 1-2 digit number before jockey
    fin_match = re.search(r'\s(\d{1,2})[ªº«¬]?\s+\w+\w+\s+L', line)
    if fin_match:
        result['finish_pos'] = int(fin_match.group(1))

    # Comment — everything after the odds number at end
    comment_match = re.search(r'\d+\.\d+\s+\w.*?\s{2,}(.+)$', line)
    if comment_match:
        result['comment'] = comment_match.group(1).strip()

    return result


def parse_trainer_jockey_stats(line: str) -> dict:
    """
    Extract trainer and jockey win percentages.
    Example: 'ORTIZ, JR. IRAD (33 5-5-7 15%)'
    """
    result = {}
    # Pattern: Name (starts nn-nn-nn WW%)
    stat_match = re.search(r'\((\d+)\s+\d+-\d+-\d+\s+(\d+)%\)', line)
    if stat_match:
        result['starts']  = int(stat_match.group(1))
        result['win_pct'] = float(stat_match.group(2))
    return result


# ─────────────────────────────────────────
# Main page parser
# ─────────────────────────────────────────

def parse_page(page_text: str) -> dict:
    """
    Parse a single page of a BrisNet PP PDF.
    Returns structured data for that page.
    """
    lines = page_text.split('\n')
    lines = [l.strip() for l in lines if l.strip()]

    page_data = {
        'race_header': {},
        'pars':        {},
        'entries':     [],
    }

    current_entry = None

    for i, line in enumerate(lines):
    # ── Race header — MUST BE FIRST ──────────────────
        if re.search(r'\bRace\s+\d+\b', line) and any(t in line for t in TRACK_CODES):
            page_data['race_header'] = parse_race_header(line)
            continue

    # ── Pace pars ────────────────────────────────
        if 'PARS:' in line:
            page_data['pars'] = parse_pars(line)
            continue

        # ── Entry header (post + horse + style) ──────
        # Handles both:
        # '1 Emirates Affair (E 8) $16,000 Dkbbr...'  (claiming)
        # '1 Maycocks Bay (E/P 8) Ch.g.5...'          (allowance)
        entry_match = re.match(
            r'^(\d{1,2})\s+([A-Z][A-Za-z\s\'\(\)]+?)\s+\(([A-Z/]+)\s+\d+\)',
            line
        )
        if entry_match:
            # Make sure it's not a past performance line
            # PP lines start with date like '24Jan26'
            if not re.match(r'^\d{2}[A-Z][a-z]{2}\d{2}', line):
                if current_entry:
                    page_data['entries'].append(current_entry)
                current_entry = parse_entry_header(line)
                current_entry['past_performances'] = []
                continue

        # ── Prime Power ───────────────────────────────
        if current_entry and 'Prime Power:' in line:
            current_entry.update(parse_prime_power(line))
            continue

        # ── Past performance lines ────────────────────
        if current_entry and re.match(r'\d{2}\w{3}\d{2}', line):
            pp = parse_past_performance_line(line)
            if pp:
                current_entry['past_performances'].append(pp)
            continue

    # Don't forget the last entry
    if current_entry:
        page_data['entries'].append(current_entry)

    return page_data


# ─────────────────────────────────────────
# Full PDF processor
# ─────────────────────────────────────────

def process_pp_pdf(pdf_path: str) -> list:
    pdf_path = Path(pdf_path)
    raw_pages = []
    last_race_num = None

    with pdfplumber.open(pdf_path) as pdf:
        print(f"Processing {len(pdf.pages)} pages...")

        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue

            page_data = parse_page(text)
            race_num = page_data['race_header'].get('race_number')

            if race_num:
                last_race_num = race_num
            elif page_data['entries'] and last_race_num:
                # Page has entries but header was truncated — inherit last race
                page_data['race_header']['race_number'] = last_race_num

            if page_data['race_header'].get('race_number'):
                page_data['page_num'] = page_num
                raw_pages.append(page_data)

    # ── Consolidate pages by race number ─────────────
    races = {}

    for page in raw_pages:
        race_num = page['race_header']['race_number']

        if race_num not in races:
            # First page of this race — initialize it
            races[race_num] = {
                'race_header': page['race_header'],
                'pars':        page['pars'],
                'entries':     page['entries'],
            }
        else:
            # Subsequent page — merge entries in
            existing = races[race_num]

            # Fill in pars if we got them on this page
            if page['pars'] and not existing['pars']:
                existing['pars'] = page['pars']

            # Fill in distance/surface if missing
            if not existing['race_header'].get('distance'):
                existing['race_header']['distance'] = \
                    page['race_header'].get('distance')
            if not existing['race_header'].get('surface'):
                existing['race_header']['surface'] = \
                    page['race_header'].get('surface')

            # Add entries from this page
            existing['entries'].extend(page['entries'])

    # Convert to sorted list
    consolidated = [races[k] for k in sorted(races.keys())]

    print(f"\nConsolidated into {len(consolidated)} races")
    for race in consolidated:
        header = race['race_header']
        print(
            f"  Race {header.get('race_number')}: "
            f"{len(race['entries'])} entries — "
            f"{header.get('distance')} {header.get('surface')} "
            f"{header.get('race_type')}"
        )

    return consolidated


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

def main():
    pp_path = "data/pps/pp_kee_260416.pdf"

    if not Path(pp_path).exists():
        print(f"PDF not found at {pp_path}")
        return

    print(f"\nProcessing: {pp_path}")
    print("=" * 50)

    races = process_pp_pdf(pp_path)

    print(f"\n{'='*50}")
    print(f"EXTRACTION SUMMARY")
    print(f"{'='*50}")
    print(f"Total race pages found: {len(races)}")

    for race in races:
        header = race['race_header']
        pars   = race['pars']
        print(f"\nRace {header.get('race_number')} — "
              f"{header.get('distance')} {header.get('surface')} "
              f"{header.get('race_type')}")
        print(f"  Date:    {header.get('race_date')}")
        print(f"  Purse:   {header.get('purse')}")
        print(f"  Pars:    E1={pars.get('pace_par_e1')} "
              f"E2={pars.get('pace_par_e2')} "
              f"Late={pars.get('pace_par_late')}")
        print(f"  Entries: {len(race['entries'])}")
        for entry in race['entries']:
            print(f"    {entry.get('post_position')} "
                  f"{entry.get('horse_name')} "
                  f"({entry.get('running_style')}) "
                  f"PP={entry.get('prime_power')} "
                  f"PPs={len(entry.get('past_performances', []))}")

        for entry in race['entries']:
            print(f"    {entry.get('post_position')} "
                  f"{entry.get('horse_name')} "
                  f"({entry.get('running_style')}) "
                  f"PP={entry.get('prime_power')} "
                  f"PPs={len(entry.get('past_performances', []))}")


if __name__ == "__main__":
    main()