import csv, re, sys, datetime

def clean(s):
    s = str(s)
    s = s.replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
    return s.strip()

def parse_amount(plan):
    plan_prices = {
        'starter weekly': 9.99, 'starter quarterly': 19.99,
        'expert weekly': 19.99, 'expert quarterly': 59.99,
        'elite v1 weekly': 29.99, 'premium weekly': 14.99,
        'premium quarterly': 39.99, 'standard annual': 99.99,
        'premium lifetime': 199.99,
    }
    pl = plan.lower()
    for k, v in plan_prices.items():
        if k in pl:
            return v
    return 0

def parse_dollar(s):
    try:
        return round(float(re.sub(r'[^\d.]', '', s)), 2)
    except Exception:
        return 0

def parse_iso(date_str):
    try:
        date_str = str(date_str).strip()
        date_str = re.sub(r'/+', '/', date_str)
        parts = date_str.split('/')
        if len(parts) == 3:
            m, d, y = parts
            if len(y) > 4:
                y = y[:4]
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        elif len(parts) == 2:
            m = parts[0]
            rest = parts[1]
            if len(rest) == 6:
                d = rest[:2]
                y = rest[2:]
                return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        for fmt in ('%b %d, %Y', '%B %d, %Y'):
            try:
                return datetime.datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except Exception:
                pass
    except Exception:
        pass
    return date_str

def read_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.reader(f))

def parse_all(rows):
    records = []
    i = 0
    n = len(rows)
    while i < n:
        row = [c.strip() for c in rows[i]]
        if len(row) >= 3 and row[0] == 'Date' and row[1] == 'Created' and row[2] == 'LOB':
            has_status = 'Status' in row
            has_amount = 'Amount' in row
            i += 1
            while i < n:
                r = [c.strip() for c in rows[i]]
                if not any(r):
                    i += 1
                    continue
                if len(r) >= 2 and r[0] == 'Date' and r[1] == 'Created':
                    break
                if len(r) < 8:
                    i += 1
                    continue
                if has_status:
                    rec = {
                        'date': r[0], 'created': r[1], 'lob': r[2], 'email': r[3], 'plan': r[4],
                        'status': r[5] if len(r) > 5 else '',
                        'reason': r[6] if len(r) > 6 else '',
                        'payment': r[7] if len(r) > 7 else '',
                        'notes': r[8] if len(r) > 8 else '',
                        'reso': r[9] if len(r) > 9 else '',
                        'rep': r[10] if len(r) > 10 else '',
                        'month': r[11] if len(r) > 11 else '',
                        'amount_str': '',
                    }
                elif has_amount:
                    rec = {
                        'date': r[0], 'created': r[1], 'lob': r[2], 'email': r[3], 'plan': r[4],
                        'status': 'Refunded',
                        'reason': r[5] if len(r) > 5 else '',
                        'payment': r[7] if len(r) > 7 else '',
                        'amount_str': r[8] if len(r) > 8 else '',
                        'notes': r[9] if len(r) > 9 else '',
                        'reso': r[10] if len(r) > 10 else '',
                        'rep': r[11] if len(r) > 11 else '',
                        'month': r[12] if len(r) > 12 else '',
                    }
                else:
                    i += 1
                    continue
                if rec['date'] and rec['date'] != 'Date':
                    records.append(rec)
                i += 1
        else:
            i += 1
    return records

def build_js_data(records):
    js_rows = []
    for r in records:
        date = clean(r['date'])
        created = clean(r['created'])
        lob = clean(r['lob'])
        email = clean(r['email'])
        plan = clean(r['plan'])
        status = clean(r['status'])
        reason = clean(r['reason'])
        payment = clean(r['payment'])
        notes = clean(r['notes'])
        reso = clean(r['reso'])
        rep = clean(r['rep'])
        month = clean(r['month'])
        amount_str = r.get('amount_str', '')
        if amount_str and amount_str not in ('', 'Amount'):
            amount = parse_dollar(amount_str)
        else:
            amount = parse_amount(plan)
        iso = parse_iso(date)
        js_rows.append(
            '  {date:"' + iso + '",rawDate:"' + date + '",created:"' + created +
            '",lob:"' + lob + '",email:"' + email + '",plan:"' + plan +
            '",status:"' + status + '",reason:"' + reason + '",payment:"' + payment +
            '",notes:"' + notes + '",reso:"' + reso + '",rep:"' + rep +
            '",month:"' + month + '",amount:' + str(amount) + '}'
        )
    return 'const DATA = [\n' + ',\n'.join(js_rows) + '\n];'

def inject_data(html, js_data):
    return re.sub(r'const DATA = \[[\s\S]*?\];', js_data, html, count=1)

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: build_dashboard_ci.py <tracker_new.csv> <refund_tracker.csv> <out_index.html>")
        sys.exit(1)
    tracker_new_path, refund_tracker_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    all_records = []
    for path in (tracker_new_path, refund_tracker_path):
        try:
            rows = read_rows(path)
            all_records.extend(parse_all(rows))
        except FileNotFoundError:
            print(f"warning: {path} not found, skipping")

    js_data = build_js_data(all_records)

    with open(out_path, encoding='utf-8') as f:
        existing = f.read()
    if 'const DATA = [' in existing:
        result = inject_data(existing, js_data)
    else:
        result = existing.replace('</body>', f'<script>{js_data}</script>\n</body>')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"Built dashboard with {len(all_records)} records -> {out_path}")
