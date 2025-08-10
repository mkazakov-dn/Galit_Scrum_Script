# Port Mirroring Monitor

A real-time web-based monitoring application for network port mirroring sessions. This tool connects to network devices via SSH, monitors port mirroring configurations, and validates mirroring effectiveness by comparing source and destination traffic rates.

## Features

- **Real-time Monitoring**: Automatically refreshes every 2-5 seconds (configurable)
- **Smart Direction Detection**: Handles `ingress`, `egress`, and `both` direction mirroring
- **Traffic Validation**: Compares source and destination traffic with intelligent delta analysis
- **Visual Web Interface**: Clean, responsive web UI showing all sessions at once
- **SSH Connection Management**: Robust SSH connection handling with automatic reconnection
- **Comprehensive Validation**:
  - ✅ **Match**: Source and destination traffic within 10% delta
  - ⚠️ **Warning**: High delta or unexpected traffic patterns
  - ❌ **Error**: Source has traffic but destination is idle

## How It Works

### Direction-Aware Validation

The monitor intelligently validates traffic based on the configured mirroring direction:

- **`direction both`**: Validates that destination TX = source RX + source TX
- **`direction ingress`**: Validates that destination TX = source RX only
- **`direction egress`**: Validates that destination TX = source TX only
- **No direction specified**: Defaults to `both` behavior

### Example

For a session configured as:
```
services port-mirroring session example source-interface bundle-1.100 direction both
services port-mirroring session example destination-interface ge100-1/0/5
```

If the source interface has:
- RX: 20.21 Mbps
- TX: 4.19 Mbps

The monitor expects the destination interface to transmit: **24.40 Mbps** (20.21 + 4.19)

## Installation

### Prerequisites

- Python 3.7 or higher
- Network device with SSH access
- Device must support the commands:
  - `sh conf services port-mirroring | flatten`
  - `sh interfaces counters <interface> | inc regex "^\s*(RX|TX) octets:"`

### Setup

1. **Clone the repository**:
   ```bash
   git clone git@github.com:mkazakov-dn/Galit_Scrum_Script.git
   cd Galit_Scrum_Script/port_mirroring_monitor
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure SSH connectivity**:
   ```bash
   ssh dnroot@<your-device-hostname>
   ```

## Usage

### Basic Usage

```bash
python3 monitor_port_mirroring.py --host <device-hostname> --port 8080 --interval 5
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--host` | Device hostname or IP address | **Required** |
| `--port` | Web server port | 8080 |
| `--interval` | Monitoring interval in seconds | 5 |
| `--debug` | Enable debug mode | False |

### Example

```bash
# Monitor device with 2-second intervals
python3 monitor_port_mirroring.py --host dn40-cl-301a-ncc0 --port 8080 --interval 2

# Monitor with debug output
python3 monitor_port_mirroring.py --host dn40-cl-301a-ncc0 --debug
```

### Access the Web Interface

Once running, open your browser and navigate to:
```
http://localhost:8080
```

## Web Interface

The web interface displays:

- **Status Bar**: Connection status and last update time
- **Session Cards**: Each port mirroring session in a compact grid layout
- **Traffic Validation**: Color-coded validation results with detailed breakdown
- **Interface Counters**: Real-time RX/TX statistics for source and destination interfaces

### Session Card Example

```
Session: alpha_9990 - description alpha_tango_milke

✅ bundle-1.9990 → ge100-2/0/24
Source RX+TX (both: 20.21+4.19): 24.40 Mbps | Dest TX: 24.54 Mbps
Match (0.6% delta)

📥 Source: bundle-1.9990          📤 Destination: ge100-2/0/24
RX: 959,382,060 octets            RX: 30,117 octets
TX: 2,801,001,280 octets          TX: 2,990,352,189 octets
Rate: RX: 20.21 Mbps | TX: 4.19  Rate: RX: 0 Mbps | TX: 24.54 Mbps
```

## Configuration

### SSH Authentication

The application uses default credentials (`dnroot/dnroot`). To modify authentication:

1. Edit the `PortMirroringMonitor` class constructor in `monitor_port_mirroring.py`
2. Modify the `username` and `password` parameters

### Validation Thresholds

- **Delta Threshold**: 10% (configurable in `validate_mirroring_session` method)
- **Idle Threshold**: 0.1 Mbps (configurable in validation logic)

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**:
   - Verify device hostname/IP is reachable
   - Check SSH credentials
   - Ensure device accepts SSH connections

2. **Pattern Not Detected**:
   - Device prompt may differ from expected pattern
   - Check if device supports required commands

3. **Port Already in Use**:
   ```bash
   # Use a different port
   python3 monitor_port_mirroring.py --host <device> --port 8081
   ```

4. **Zero Counters**:
   - Verify port mirroring sessions are active
   - Check if interfaces have traffic

### Debug Mode

Run with `--debug` flag to see detailed SSH command output and connection information.

## Files

- `monitor_port_mirroring.py`: Main application
- `Class_SSH_Con.py`: SSH connection management class
- `templates/index.html`: Web interface template
- `requirements.txt`: Python dependencies

## API Endpoints

- `GET /`: Main web interface
- `GET /api/data`: JSON data for all sessions
- `GET /api/status`: Current connection status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is for internal network monitoring purposes.

---

**Note**: This tool is designed for Dell DNOS devices. Modify command patterns in the code for other network operating systems. 