# Zoom Breakout Room Tracker

Track participant activity across Zoom breakout rooms including room visits, duration, and camera usage.

## Features

- Track which breakout rooms each participant visited
- Record join/leave times for each room
- Monitor camera on/off time per participant
- Generate detailed daily reports in CSV format
- Automatic tracking with scheduled scripts

## Output Report Format

| Column | Description |
|--------|-------------|
| Participant Name | Name of the participant |
| Email ID | Participant's email |
| Meeting Join Time | When they joined the meeting |
| Meeting Left Time | When they left the meeting |
| Meeting Total Duration | Total time in meeting (mins) |
| Room Number/Name | Breakout room name or ID |
| Room Join Time | When they joined this room |
| Room Left Time | When they left this room |
| Room Duration | Time spent in this room (mins) |
| Camera ON Time | Minutes with camera on |
| Camera OFF Time | Minutes with camera off |
| Camera ON % | Percentage of time camera was on |
| Next Room | Which room they went to next |

## Prerequisites

- Python 3.8+
- ngrok account (free) - [Download](https://ngrok.com/download)
- Zoom Server-to-Server OAuth App

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/zoom-breakout-tracker.git
   cd zoom-breakout-tracker
   ```

2. Install dependencies:
   ```bash
   pip install flask requests
   ```

3. Download ngrok and place `ngrok.exe` in this folder

4. Configure your Zoom credentials in `generate_daily_report.py`:
   ```python
   ACCOUNT_ID = 'your_account_id'
   CLIENT_ID = 'your_client_id'
   CLIENT_SECRET = 'your_client_secret'
   MEETING_ID = 'your_meeting_id'
   ```

5. Configure the same credentials in `zoom_webhook_listener.py`:
   ```python
   SECRET_TOKEN = "your_webhook_secret_token"
   ```

## Zoom App Setup

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/)
2. Create a **Server-to-Server OAuth** app
3. Add scopes: `meeting:read:admin`, `dashboard_meetings:read:admin`
4. Enable **Event Subscriptions**
5. Add events:
   - `meeting.participant_joined_breakout_room`
   - `meeting.participant_left_breakout_room`
6. Set webhook URL to your ngrok URL (e.g., `https://xxxx.ngrok.io/webhook`)

## Usage

### Manual Method

**Step 1: Start ngrok (Terminal 1)**
```bash
ngrok http 5000
```
Copy the HTTPS URL and update in Zoom webhook settings.

**Step 2: Start webhook listener (Terminal 2)**
```bash
python zoom_webhook_listener.py
```

**Step 3: After meeting ends, stop the webhook (Ctrl+C)**

**Step 4: Generate report**
```bash
python generate_daily_report.py --date 2024-02-02
```

### Automated Method (Windows)

1. Edit meeting times in `auto_tracker.py`:
   ```python
   MEETING_START_HOUR = 9    # 9:00 AM
   MEETING_END_HOUR = 13     # 1:00 PM
   ```

2. Add to Windows Startup:
   - Press `Win + R`, type `shell:startup`
   - Copy `start_auto_tracker.vbs` to that folder

3. The script will automatically:
   - Start webhook before meeting
   - Capture all room data
   - Stop webhook after meeting
   - Generate report

## Commands

```bash
# Generate report for specific date
python generate_daily_report.py --date 2024-02-02

# Generate report for yesterday
python generate_daily_report.py

# List available meetings
python generate_daily_report.py --list

# Name your rooms interactively
python generate_daily_report.py --date 2024-02-02 --setup
```

## Files

| File | Purpose |
|------|---------|
| `zoom_webhook_listener.py` | Captures room join/leave events |
| `generate_daily_report.py` | Generates CSV reports |
| `auto_tracker.py` | Automated scheduling script |
| `start_auto_tracker.vbs` | Silent startup script |
| `zoom_raw_payloads.json` | Webhook data (auto-generated) |
| `room_name_mapping.json` | Room UUID to name mapping |
| `reports/` | Output CSV files |

## Troubleshooting

### No webhook data found
- Make sure `zoom_webhook_listener.py` was running during the meeting
- Check that ngrok was running and URL was set in Zoom

### Camera data not available
- QOS data takes 2-4 hours to be available after meeting
- Check your Zoom API credentials

### Room names showing as UUIDs
- Run with `--setup` flag to name rooms interactively
- Room UUIDs change each meeting, so setup once per meeting series

## License

MIT License
