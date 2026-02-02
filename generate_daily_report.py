"""
==========================================================================
ZOOM BREAKOUT ROOM DAILY TRACKER
==========================================================================

WORKFLOW:
1. BEFORE meeting:  python zoom_webhook_listener.py (+ ngrok http 5000)
2. Meeting happens  (webhook captures room data automatically)
3. AFTER meeting:   Ctrl+C to stop webhook
4. Generate report: python generate_daily_report.py --date 2026-02-02

DATA SOURCES:
- Webhook (zoom_raw_payloads.json): Room join/leave events
- Zoom API: Camera/QOS data

USAGE:
    python generate_daily_report.py --date 2026-02-02  # Specific date
    python generate_daily_report.py                    # Yesterday
    python generate_daily_report.py --list             # List meetings
    python generate_daily_report.py --setup            # Name rooms interactively
"""

import requests
import json
import csv
import os
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict

# =============================================================================
# CONFIGURATION - UPDATE THESE WITH YOUR ZOOM CREDENTIALS
# =============================================================================

ACCOUNT_ID = 'xhKbAsmnSM6pNYYYurmqIA'
CLIENT_ID = '2ysNg6WLS0Sm8bKVVDeXcQ'
CLIENT_SECRET = 'iWgD4lZrbkxOWiGEjTgwAc3ZHSC6K5xZ'
MEETING_ID = '9034027764'

WEBHOOK_LOG = 'zoom_raw_payloads.json'
ROOM_MAPPING_FILE = 'room_name_mapping.json'
OUTPUT_DIR = 'reports'

# =============================================================================
# API FUNCTIONS
# =============================================================================

def get_access_token():
    url = "https://zoom.us/oauth/token"
    params = {"grant_type": "account_credentials", "account_id": ACCOUNT_ID}
    response = requests.post(url, params=params, auth=(CLIENT_ID, CLIENT_SECRET))
    return response.json().get('access_token') if response.status_code == 200 else None


def fetch_meeting_instances(token):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.zoom.us/v2/past_meetings/{MEETING_ID}/instances"
    response = requests.get(url, headers=headers)
    return response.json().get('meetings', []) if response.status_code == 200 else []


def find_meeting_for_date(meetings, date_str):
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    for m in meetings:
        start_time = m.get('start_time', '')
        if start_time:
            meeting_date = datetime.fromisoformat(start_time.replace('Z', '+00:00')).date()
            if meeting_date == target_date:
                return m
    return None


def fetch_qos_data(token, meeting_uuid):
    """Fetch camera/video data from QOS API"""
    headers = {"Authorization": f"Bearer {token}"}
    encoded_uuid = urllib.parse.quote(meeting_uuid, safe='')
    url = f"https://api.zoom.us/v2/metrics/meetings/{encoded_uuid}/participants/qos"

    all_participants = []
    next_token = None

    while True:
        params = {"type": "past", "page_size": 100}
        if next_token:
            params["next_page_token"] = next_token

        response = requests.get(url, headers=headers, params=params, timeout=60)
        if response.status_code != 200:
            break

        data = response.json()
        all_participants.extend(data.get('participants', []))
        next_token = data.get('next_page_token')
        if not next_token:
            break

    # Process QOS data
    video_stats = {}
    for p in all_participants:
        name = p.get('user_name', 'Unknown')
        qos_list = p.get('user_qos', []) or p.get('qos', [])

        video_on = 0
        video_off = 0

        for qos in qos_list:
            video_input = qos.get('video_input', {})
            bitrate_str = video_input.get('bitrate', '0') or '0'

            try:
                bitrate = int(bitrate_str.split()[0]) if bitrate_str else 0
            except (ValueError, IndexError):
                bitrate = 0

            if bitrate > 50:
                video_on += 1
            else:
                video_off += 1

        total = video_on + video_off
        video_stats[name] = {
            'camera_on_mins': video_on,
            'camera_off_mins': video_off,
            'total_mins': total,
            'camera_pct': round(video_on / total * 100, 1) if total > 0 else 0
        }

    return video_stats


# =============================================================================
# WEBHOOK DATA PROCESSING
# =============================================================================

def load_webhook_data():
    """Load webhook events from JSON file"""
    try:
        if os.path.exists(WEBHOOK_LOG):
            filepath = WEBHOOK_LOG
        elif os.path.exists(f'old_webhook_files/{WEBHOOK_LOG}'):
            filepath = f'old_webhook_files/{WEBHOOK_LOG}'
        else:
            print(f"       Webhook file not found: {WEBHOOK_LOG}")
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content.startswith('['):
                return json.loads(content)
            else:
                return json.loads('[' + content.rstrip(',\n') + ']')
    except Exception as e:
        print(f"       Error loading webhook data: {e}")
        return []


def process_webhook_data(payloads, date_filter=None):
    """Process webhook data to extract room visits."""
    if date_filter:
        target = datetime.strptime(date_filter, '%Y-%m-%d').date()
        filtered = []
        for p in payloads:
            ts = p.get('event_ts', 0)
            if ts:
                event_date = datetime.fromtimestamp(ts / 1000).date()
                if event_date == target:
                    filtered.append(p)
        payloads = filtered

    rooms = defaultdict(lambda: {'participants': set(), 'joins': 0})
    journeys = defaultdict(list)

    for p in payloads:
        event = p.get('event', '')
        obj = p.get('payload', {}).get('object', {})
        participant = obj.get('participant', {})

        room_uuid = obj.get('breakout_room_uuid', '')
        name = participant.get('user_name', '')
        email = participant.get('email', '')
        ts = p.get('event_ts', 0)

        if not room_uuid or not name:
            continue

        action = 'JOIN' if 'joined' in event else 'LEAVE'

        rooms[room_uuid]['participants'].add(name)
        if action == 'JOIN':
            rooms[room_uuid]['joins'] += 1

        journeys[name].append({
            'ts': ts,
            'room': room_uuid,
            'action': action,
            'email': email
        })

    for uuid in rooms:
        rooms[uuid]['participants'] = list(rooms[uuid]['participants'])

    return dict(rooms), dict(journeys)


# =============================================================================
# ROOM NAME MAPPING
# =============================================================================

def load_room_mapping():
    try:
        with open(ROOM_MAPPING_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_room_mapping(mapping):
    with open(ROOM_MAPPING_FILE, 'w') as f:
        json.dump(mapping, f, indent=2)


def setup_room_names(rooms):
    """Interactive setup to name rooms based on participants"""
    print("\n" + "=" * 70)
    print("ROOM NAME SETUP")
    print("=" * 70)
    print(f"Found {len(rooms)} rooms. Name them based on participants.\n")

    mapping = load_room_mapping()
    updated = False

    for idx, (uuid, data) in enumerate(sorted(rooms.items(), key=lambda x: len(x[1]['participants']), reverse=True), 1):
        participants = data['participants']
        current_name = mapping.get(uuid, '')

        print(f"\nRoom {idx}/{len(rooms)}")
        print(f"  UUID: {uuid[:30]}...")
        print(f"  Participants ({len(participants)}): {', '.join(sorted(participants)[:5])}")
        if len(participants) > 5:
            print(f"                    ... and {len(participants) - 5} more")

        if current_name:
            print(f"  Current name: {current_name}")
            change = input("  New name (Enter to keep): ").strip()
            if change:
                mapping[uuid] = change
                updated = True
        else:
            name = input("  Enter room name: ").strip()
            if name:
                mapping[uuid] = name
                updated = True

    if updated:
        save_room_mapping(mapping)
        print("\nRoom names saved!")

    return mapping


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_report(date_str, rooms, journeys, room_mapping, video_stats):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # MAIN REPORT: One row per participant per room visit
    report_file = os.path.join(OUTPUT_DIR, f'DAILY_REPORT_{date_str}.csv')

    with open(report_file, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'Participant Name',
            'Email ID',
            'Meeting Join Time',
            'Meeting Left Time',
            'Meeting Total Duration (mins)',
            'Room Number/Name',
            'Room Join Time',
            'Room Left Time',
            'Room Duration (mins)',
            'Camera ON Time (mins)',
            'Camera OFF Time (mins)',
            'Camera ON %',
            'Next Room'
        ])

        for name, events in sorted(journeys.items()):
            events.sort(key=lambda x: x['ts'])

            # Get video stats for participant
            vstats = video_stats.get(name, {})
            total_cam_on = vstats.get('camera_on_mins', 0)
            total_cam_off = vstats.get('camera_off_mins', 0)
            total_cam_pct = vstats.get('camera_pct', 0)

            # Find meeting join/leave times
            email = ''
            meeting_join_ts = None
            meeting_leave_ts = None

            for e in events:
                if e.get('email'):
                    email = e['email']
                if meeting_join_ts is None or e['ts'] < meeting_join_ts:
                    meeting_join_ts = e['ts']
                if meeting_leave_ts is None or e['ts'] > meeting_leave_ts:
                    meeting_leave_ts = e['ts']

            meeting_join_str = datetime.fromtimestamp(meeting_join_ts/1000).strftime('%H:%M:%S') if meeting_join_ts else ''
            meeting_leave_str = datetime.fromtimestamp(meeting_leave_ts/1000).strftime('%H:%M:%S') if meeting_leave_ts else ''
            meeting_duration = round((meeting_leave_ts - meeting_join_ts) / 60000, 1) if meeting_join_ts and meeting_leave_ts else 0

            # Build room visits
            visits = []
            for i, e in enumerate(events):
                if e['action'] != 'JOIN':
                    continue

                room_uuid = e['room']
                join_ts = e['ts']

                # Find matching LEAVE
                leave_ts = None
                for j in range(i + 1, len(events)):
                    if events[j]['room'] == room_uuid and events[j]['action'] == 'LEAVE':
                        leave_ts = events[j]['ts']
                        break

                visits.append({
                    'room_uuid': room_uuid,
                    'join_ts': join_ts,
                    'leave_ts': leave_ts
                })

            # Calculate total time in rooms for camera distribution
            total_room_time = sum(
                (v['leave_ts'] - v['join_ts']) / 60000
                for v in visits if v['leave_ts']
            ) or 1

            # Write one row per room visit
            for idx, visit in enumerate(visits):
                room_uuid = visit['room_uuid']
                room_name = room_mapping.get(room_uuid, f"Room-{idx+1}")

                room_join_str = datetime.fromtimestamp(visit['join_ts']/1000).strftime('%H:%M:%S')

                if visit['leave_ts']:
                    room_leave_str = datetime.fromtimestamp(visit['leave_ts']/1000).strftime('%H:%M:%S')
                    room_duration = round((visit['leave_ts'] - visit['join_ts']) / 60000, 1)
                else:
                    room_leave_str = ''
                    room_duration = 0

                # Calculate camera time for this room (proportional)
                if room_duration > 0:
                    room_cam_on = round(total_cam_on * (room_duration / total_room_time), 1)
                    room_cam_off = round(total_cam_off * (room_duration / total_room_time), 1)
                    room_cam_pct = round((room_cam_on / room_duration) * 100, 1) if room_duration > 0 else 0
                else:
                    room_cam_on = 0
                    room_cam_off = 0
                    room_cam_pct = 0

                # Next room
                next_room = "Left Meeting"
                if idx + 1 < len(visits):
                    next_uuid = visits[idx + 1]['room_uuid']
                    next_room = room_mapping.get(next_uuid, f"Room-{idx+2}")

                w.writerow([
                    name,
                    email,
                    meeting_join_str,
                    meeting_leave_str,
                    meeting_duration,
                    room_name,
                    room_join_str,
                    room_leave_str,
                    room_duration,
                    room_cam_on,
                    room_cam_off,
                    f"{room_cam_pct}%",
                    next_room
                ])

    print(f"  [OK] {report_file}")

    # ROOM SUMMARY
    room_file = os.path.join(OUTPUT_DIR, f'ROOMS_{date_str}.csv')
    with open(room_file, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Room Name', 'Room UUID', 'Total Participants', 'Total Joins', 'Participant List'])

        for uuid, data in sorted(rooms.items(), key=lambda x: len(x[1]['participants']), reverse=True):
            room_name = room_mapping.get(uuid, f"Room-{uuid[:8]}")
            w.writerow([
                room_name,
                uuid,
                len(data['participants']),
                data['joins'],
                ', '.join(sorted(data['participants']))
            ])

    print(f"  [OK] {room_file}")

    return report_file, room_file


# =============================================================================
# MAIN
# =============================================================================

def main():
    import sys

    print("=" * 70)
    print("ZOOM BREAKOUT ROOM TRACKER")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if '--list' in sys.argv:
        token = get_access_token()
        if token:
            meetings = fetch_meeting_instances(token)
            print(f"\nAvailable meetings ({len(meetings)}):")
            for m in sorted(meetings, key=lambda x: x.get('start_time', ''), reverse=True)[:15]:
                print(f"  {m.get('start_time')}")
        return

    # Get date
    if '--date' in sys.argv:
        idx = sys.argv.index('--date')
        date_filter = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
    else:
        date_filter = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    print(f"Date: {date_filter}\n")

    # Step 1: Load webhook data
    print("[1/4] Loading webhook data (room info)...", end=" ")
    payloads = load_webhook_data()
    print(f"{len(payloads)} events")

    if not payloads:
        print("\n[!] No webhook data found!")
        print("    Run: python zoom_webhook_listener.py during meeting")
        return

    # Step 2: Process webhook data
    print(f"[2/4] Processing data for {date_filter}...", end=" ")
    rooms, journeys = process_webhook_data(payloads, date_filter)
    print(f"{len(rooms)} rooms, {len(journeys)} participants")

    if not rooms:
        print(f"\n[!] No breakout room data found for {date_filter}")
        return

    # Setup mode
    if '--setup' in sys.argv:
        room_mapping = setup_room_names(rooms)
    else:
        room_mapping = load_room_mapping()

    # Step 3: Get camera data from API
    print("[3/4] Fetching camera data from API...", end=" ")
    token = get_access_token()
    video_stats = {}

    if token:
        meetings = fetch_meeting_instances(token)
        target = find_meeting_for_date(meetings, date_filter)
        if target:
            video_stats = fetch_qos_data(token, target.get('uuid', ''))
            print(f"{len(video_stats)} participants")
        else:
            print("Meeting not found in API")
    else:
        print("API token failed (check credentials)")

    # Step 4: Generate reports
    print("[4/4] Generating reports...")
    generate_report(date_filter, rooms, journeys, room_mapping, video_stats)

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)
    print(f"\nReports: {OUTPUT_DIR}/")
    print(f"  - DAILY_REPORT_{date_filter}.csv")
    print(f"  - ROOMS_{date_filter}.csv")

    if not room_mapping:
        print(f"\nTIP: Name your rooms: python generate_daily_report.py --date {date_filter} --setup")


if __name__ == '__main__':
    main()
